#!/usr/bin/env python3
import os
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: patch-pa-nwm-test.py NWM_APP_DIR [autospawn]")
    nwm_dir = Path(sys.argv[1])
    path = nwm_dir / "src/main.cpp"
    text = path.read_text(encoding="ascii")
    autospawn = len(sys.argv) == 3 and sys.argv[2] == "autospawn"
    if "MEMU_NWM_IMMEDIATE_COMPOSE" not in text:
        text = text.replace(
            "#include <NDL.h>\n",
            "#include <NDL.h>\n"
            "#define MEMU_NWM_IMMEDIATE_COMPOSE 1\n",
            1,
        )
        text = text.replace(
            "  uint32_t last = 0, now = 0;\n"
            "  char buf[64];\n"
            "  while (1) {\n"
            "    if (NDL_PollEvent(buf, sizeof(buf))) {\n"
            "      wm->handle_event(buf);\n"
            "    }\n\n"
            "    if ((now = NDL_GetTicks()) - last > 1000 / RENDER_FPS) {\n"
            "      wm->handle_event(\"t\");\n"
            "      last = now;\n"
            "    }\n",
            "  char buf[64];\n"
            "  while (1) {\n"
            "    if (NDL_PollEvent(buf, sizeof(buf))) {\n"
            "      wm->handle_event(buf);\n"
            "    }\n"
            "    wm->handle_event(\"t\");\n",
            1,
        )
    nterm_main = nwm_dir.parent / "nterm" / "src" / "main.cpp"
    if nterm_main.exists():
        nterm_text = nterm_main.read_text(encoding="ascii")
        nterm_text = nterm_text.replace(
            'static const char *font_fname = "/share/fonts/Courier-7.bdf";\n',
            'static const char *font_fname = "/share/fonts/Courier-10.bdf";\n',
            1,
        )
        nterm_main.write_text(nterm_text, encoding="ascii")
    # Nanos-lite's compatibility scheduler is cooperative between explicit
    # yields. The NWM timer loop already yields, but nterm's own event/render
    # loops do not, which leaves its freshly drawn memfd framebuffer invisible
    # after the first handoff. Yield after each refresh so NWM can composite it.
    for nterm_loop in ("builtin-sh.cpp", "extern-sh.cpp"):
        nterm_source = nwm_dir.parent / "nterm" / "src" / nterm_loop
        if not nterm_source.exists():
            continue
        nterm_loop_text = nterm_source.read_text(encoding="ascii")
        if "MEMU_NTERM_YIELD" not in nterm_loop_text:
            syscall_decl = (
                "extern \"C\" intptr_t _syscall_(intptr_t, intptr_t, intptr_t, intptr_t);\n"
                "#define MEMU_NTERM_YIELD 1\n"
            )
            if "#include <SDL.h>\n" in nterm_loop_text:
                nterm_loop_text = nterm_loop_text.replace(
                    "#include <SDL.h>\n", "#include <SDL.h>\n" + syscall_decl, 1
                )
            else:
                nterm_loop_text = nterm_loop_text.replace(
                    "#include <unistd.h>\n", "#include <unistd.h>\n" + syscall_decl, 1
                )
            nterm_loop_text = nterm_loop_text.replace(
                "    refresh_terminal();\n",
                "    refresh_terminal();\n"
                "    _syscall_(MEMU_NTERM_YIELD, 0, 0, 0);\n",
                1,
            )
            nterm_source.write_text(nterm_loop_text, encoding="ascii")
    nterm_term = nwm_dir.parent / "nterm" / "src" / "term.cpp"
    if nterm_term.exists():
        nterm_term_text = nterm_term.read_text(encoding="ascii")
        cursor_dirty_clear = (
            "void Terminal::clear() {\n"
            "  for (int i = 0; i < w * h; i ++) dirty[i] = false;\n"
            "  dirty[cursor.x + cursor.y * w] = true;\n"
            "}\n"
        )
        clean_clear = (
            "void Terminal::clear() {\n"
            "  for (int i = 0; i < w * h; i ++) dirty[i] = false;\n"
            "}\n"
        )
        if cursor_dirty_clear in nterm_term_text:
            nterm_term_text = nterm_term_text.replace(cursor_dirty_clear, clean_clear, 1)
            nterm_term.write_text(nterm_term_text, encoding="ascii")
    window = path.parent / "window.cpp"
    window_text = window.read_text(encoding="ascii")
    window_text = window_text.replace(
        "  x = y = w = h = 0;\n  canvas = nullptr;\n  fb = nullptr;\n",
        "  x = y = w = h = fw = fh = dx = dy = 0;\n"
        "  canvas = nullptr;\n  fb = nullptr;\n",
        1,
    )
    current_guard = (
        "void Window::update() {\n"
        "  if (read_fd != -1 && fb != nullptr && canvas != nullptr &&\n"
        "      fw > 0 && fh > 0) {\n"
    )
    basic_guard = "void Window::update() {\n  if (read_fd != -1) {\n"
    if current_guard in window_text:
        window_text = window_text.replace(current_guard, basic_guard, 1)
    elif basic_guard not in window_text:
        raise SystemExit("unexpected NWM update guard")
    window_text = window_text.replace(
        basic_guard, basic_guard + "    bool child_dirty = false;\n", 1
    )

    resize_marker = "      if (ret == 2) resize(w, h);\n"
    resize_dirty = (
        "      if (ret == 2) resize(w, h);\n"
        "      if (strstr(buf, \"d\\n\") != nullptr || strcmp(buf, \"d\") == 0) child_dirty = true;\n"
    )
    if resize_marker in window_text:
        window_text = window_text.replace(resize_marker, resize_dirty, 1)
    elif resize_dirty not in window_text:
        raise SystemExit("unexpected NWM resize handling")

    copy_marker = "    } while (1);\n    int y;\n"
    copy_guard = (
        "    } while (1);\n"
        "    if (fb == nullptr || canvas == nullptr || fw <= 0 || fh <= 0) return;\n"
        "    if (!child_dirty) return;\n"
        "    int y;\n"
    )
    if copy_marker in window_text:
        window_text = window_text.replace(copy_marker, copy_guard, 1)
    window.write_text(window_text, encoding="ascii")

    events = path.parent / "events.cpp"
    events_text = events.read_text(encoding="ascii")
    if "MEMU_SYS_YIELD" not in events_text:
        events_text = events_text.replace(
            "#include <nwm.h>\n",
            "#include <nwm.h>\n"
            "extern \"C\" intptr_t _syscall_(intptr_t, intptr_t, intptr_t, intptr_t);\n"
            "#define MEMU_SYS_YIELD 1\n",
            1,
        )
        events_text = events_text.replace(
            "        spawn(appfinder->getcmd(), (const char **)appfinder->getargv()); // fall through\n",
            "        spawn(appfinder->getcmd(), (const char **)appfinder->getargv()); // fall through\n"
            "        _syscall_(MEMU_SYS_YIELD, 0, 0, 0);\n",
            1,
        )
    events.write_text(events_text, encoding="ascii")

    # NWM's main loop never yields in upstream form, so without a kernel that
    # preempts via timer IRQs a child app (e.g. nterm) starves after the
    # initial post-spawn yield. Inject an explicit SYS_yield at the end of
    # evt_timer so each render pass hands the CPU back to the child(ren).
    events_text = events.read_text(encoding="ascii")
    timer_marker = "  render();\n}\n"
    timer_yield = "  render();\n  _syscall_(MEMU_SYS_YIELD, 0, 0, 0);\n}\n"
    if timer_marker in events_text and timer_yield not in events_text:
        events_text = events_text.replace(timer_marker, timer_yield, 1)
        events.write_text(events_text, encoding="ascii")

    wm = path.parent / "wm.cpp"
    wm_text = wm.read_text(encoding="ascii")
    row_copy = (
        "        for (int i = 0; i < T; i ++) {\n"
        "          int x1 = x * T, y1 = y * T + i;\n"
        "          if (y1 >= h) continue;\n"
        "          int sz = T * n;\n"
        "          if (x1 + T * n > w) {\n"
        "            sz -= x1 + T * n - w;\n"
        "          }\n"
        "          NDL_DrawRect(&fb[y1 * w + x1], x1, y1, sz, 1);\n"
        "        }\n"
    )
    block_copy = (
        "        int x1 = x * T, y1 = y * T;\n"
        "        int sz = T * n;\n"
        "        if (x1 + sz > w) sz = w - x1;\n"
        "        int rows = T;\n"
        "        if (y1 + rows > h) rows = h - y1;\n"
        "        if (rows > 0) NDL_DrawRect(&fb[y1 * w + x1], x1, y1, sz, rows);\n"
    )
    if row_copy in wm_text:
        wm_text = wm_text.replace(row_copy, block_copy, 1)
    spawn_signature = "Window *WindowManager::spawn(const char *path, const char *argv[]) {\n"
    spawn_preamble = (
        spawn_signature
        + "  const char *single_argv[] = { path, NULL };\n"
        + "  const char *onscripter_argv_runtime[] = { \"/bin/onscripter\", \"-r\", \"/share/games/onscripter/clannad\", NULL };\n"
        + "  if (argv == NULL) {\n"
        + "    argv = (strcmp(path, \"/bin/onscripter\") == 0) ? onscripter_argv_runtime : single_argv;\n"
        + "  }\n"
    )
    if spawn_signature in wm_text and "single_argv[] = { path, NULL };" not in wm_text:
        wm_text = wm_text.replace(spawn_signature, spawn_preamble, 1)
    wm.write_text(wm_text, encoding="ascii")

    winimpl = path.parent.parent / "include/winimpl.h"
    winimpl_text = winimpl.read_text(encoding="ascii")
    getcmd_impl = (
        "  const char *getcmd() {\n"
        "    assert(cur < n);\n"
        "    return default_apps[cur].bin;\n"
        "  }\n"
    )
    patched_getcmd_impl = (
        "  const char *getcmd() {\n"
        "    assert(cur < n);\n"
        "    switch (cur) {\n"
        "      case 0: return \"/bin/nterm\";\n"
        "      case 1: return \"/bin/nslider\";\n"
        "      case 2: return \"/bin/typing-game\";\n"
        "      case 3: return \"/bin/fceux\";\n"
        "      case 4: return \"/bin/nplayer\";\n"
        "      case 5: return \"/bin/pal\";\n"
        "      case 6: return \"/bin/onscripter\";\n"
        "      default: return NULL;\n"
        "    }\n"
        "  }\n"
    )
    getargv_impl = (
        "  const char *const *getargv() {\n"
        "    assert(cur < n);\n"
        "    return default_apps[cur].argv;\n"
        "  }\n"
    )
    patched_getargv_impl = (
        "  const char *const *getargv() {\n"
        "    return NULL;\n"
        "  }\n"
    )
    if getcmd_impl in winimpl_text:
        winimpl_text = winimpl_text.replace(getcmd_impl, patched_getcmd_impl, 1)
    if getargv_impl in winimpl_text:
        winimpl_text = winimpl_text.replace(getargv_impl, patched_getargv_impl, 1)

    default_apps_start = "static const struct {\n  const char *name;\n  const char *bin;\n  const char *const *argv;\n} default_apps [] = {\n"
    default_apps_end = "};\n\nclass BgImage: public Window {\n"
    start = winimpl_text.find(default_apps_start)
    end = winimpl_text.find(default_apps_end)
    if start == -1 or end == -1:
        raise SystemExit("unexpected NWM default_apps block")
    default_apps_entries = [
        ("Terminal", "/bin/nterm", '  { "Terminal", nterm_argv[0], nterm_argv },'),
        ("NSlider", "/bin/nslider", '  { "NSlider", nslider_argv[0], nslider_argv },'),
        ("Typing Game", "/bin/typing-game", '  { "Typing Game", typing_argv[0], typing_argv },'),
        ("FCEUX", "/bin/fceux", '  { "FCEUX", fceux_argv[0], fceux_argv },'),
        ("NPlayer", "/bin/nplayer", '  { "NPlayer", nplayer_argv[0], nplayer_argv },'),
        ("Pal", "/bin/pal", '  { "Pal", pal_argv[0], pal_argv },'),
        ("ONScripter", "/bin/onscripter", '  { "ONScripter", onscripter_argv[0], onscripter_argv },'),
    ]
    available = set(filter(None, os.environ.get("MEMU_NWM_AVAILABLE_APPS", "").split(",")))
    if available:
        kept_lines = []
        for _, app_path, line in default_apps_entries:
            if app_path in available:
                kept_lines.append(line)
        if not kept_lines:
            kept_lines.append('  { "Terminal", nterm_argv[0], nterm_argv },')
        filtered_block = default_apps_start + "\n".join(kept_lines) + "\n"
        winimpl_text = winimpl_text[:start] + filtered_block + winimpl_text[end:]
    winimpl.write_text(winimpl_text, encoding="ascii")

    if autospawn and "extern intptr_t _syscall_" not in text:
        text = text.replace(
            "#include <NDL.h>\n",
            "#include <NDL.h>\n"
            "extern \"C\" intptr_t _syscall_(intptr_t, intptr_t, intptr_t, intptr_t);\n"
            "#define MEMU_SYS_YIELD 1\n",
            1,
        )
    marker = "  const char *memu_test_argv[] = {\"/bin/nterm\", NULL};\n"
    spawn = "  wm->spawn(\"/bin/nterm\", memu_test_argv);\n"
    syscall_yield = "  _syscall_(MEMU_SYS_YIELD, 0, 0, 0);\n"
    if not autospawn:
        text = text.replace(marker + spawn + syscall_yield, "", 1)
        text = text.replace(marker + spawn + "  yield();\n", "", 1)
        text = text.replace(marker + spawn, "", 1)
        text = text.replace(
            "extern \"C\" intptr_t _syscall_(intptr_t, intptr_t, intptr_t, intptr_t);\n"
            "#define MEMU_SYS_YIELD 1\n",
            "",
            1,
        )
    elif marker in text:
        if spawn + syscall_yield not in text:
            text = text.replace(spawn, spawn + syscall_yield, 1)
        path.write_text(text, encoding="ascii")
        return
    needle = "  WindowManager *wm = new WindowManager(w, h);\n"
    replacement = (needle + marker +
                   "  wm->spawn(\"/bin/nterm\", memu_test_argv);\n"
                   "  _syscall_(MEMU_SYS_YIELD, 0, 0, 0);\n")
    if autospawn and needle not in text:
        raise SystemExit("NWM main.cpp does not contain the expected startup")
    if autospawn:
        text = text.replace(needle, replacement, 1)
    path.write_text(text, encoding="ascii")


if __name__ == "__main__":
    main()
