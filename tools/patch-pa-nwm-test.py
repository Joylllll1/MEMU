#!/usr/bin/env python3
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) not in (2, 3):
        raise SystemExit("usage: patch-pa-nwm-test.py NWM_APP_DIR [autospawn]")
    path = Path(sys.argv[1]) / "src/main.cpp"
    text = path.read_text(encoding="ascii")
    autospawn = len(sys.argv) == 3 and sys.argv[2] == "autospawn"
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

    copy_marker = "    } while (1);\n    int y;\n"
    copy_guard = (
        "    } while (1);\n"
        "    if (fb == nullptr || canvas == nullptr || fw <= 0 || fh <= 0) return;\n"
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
