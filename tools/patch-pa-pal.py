#!/usr/bin/env python3
"""Apply MEMU-specific portability fixes to the PAL source tree."""

import re
import sys
import os
from pathlib import Path


def patch_dbopl(pal: Path) -> None:
    source = pal / "src/sound/adplug/dosbox/dbopl.cpp.h"
    text = source.read_text(encoding="ascii")
    if "#include <stddef.h>" not in text:
        text = text.replace("#include <string.h>\n", "#include <string.h>\n#include <stddef.h>\n", 1)

    new_channel = """\t\tChanOffsetTable[i] = (Bit16u)(offsetof(Chip, chan) +
\t\t                                      sizeof(Channel) * index);"""
    new_operator = """\t\tOpOffsetTable[i] = (Bit16u)(ChanOffsetTable[chNum] +
\t\t                                    offsetof(Channel, op) +
\t\t                                    sizeof(Operator) * opNum);"""

    channel_pattern = r"\t\tBitu blah = reinterpret_cast<Bitu>\( &\(chip->chan\[ index \]\) \);\n\t\tChanOffsetTable\[i\] = blah;"
    operator_pattern = r"\t\t/\*DBOPL::\*/Channel\* chan = 0;\n\t\tBitu blah = reinterpret_cast<Bitu>\( &\(chan->op\[opNum\]\) \);\n\t\tOpOffsetTable\[i\] = ChanOffsetTable\[ chNum \] \+ blah;"
    has_original_tables = re.search(channel_pattern, text) and re.search(operator_pattern, text)
    has_patched_tables = new_channel in text and new_operator in text
    if has_original_tables:
        text = re.sub(channel_pattern, new_channel, text, count=1)
        text = re.sub(operator_pattern, new_operator, text, count=1)
    elif not has_patched_tables:
        raise RuntimeError("unexpected DOSBox OPL table-generation source")
    source.write_text(text, encoding="ascii")

    header = pal / "src/sound/adplug/dosbox/dbopl.h"
    header_text = header.read_text(encoding="ascii")
    header_text = header_text.replace("\nbool InitTables(void);\n", "\n")
    header_guard_end = header_text.rfind("#endif")
    if header_guard_end < 0:
        raise RuntimeError("unexpected PAL DOSBox OPL header")
    header_text = (header_text[:header_guard_end] +
                   "bool InitTables(void);\n\n" +
                   header_text[header_guard_end:])
    header.write_text(header_text, encoding="ascii")

    wrapper = pal / "src/sound/adplug/emuopls.cpp"
    wrapper_text = wrapper.read_text(encoding="ascii")
    marker = "\tif (type != Copl::TYPE_OPL2 && type != Copl::TYPE_DUAL_OPL2 && type != Copl::TYPE_OPL3) {"
    replacement = "\tDBOPL::InitTables();\n\n" + marker
    if "DBOPL::InitTables();" not in wrapper_text:
        if marker not in wrapper_text:
            raise RuntimeError("unexpected PAL OPL factory source")
        wrapper.write_text(wrapper_text.replace(marker, replacement, 1), encoding="ascii")

    tables_source = pal / "src/sound/adplug/dosbox_opls.cpp"
    tables_text = tables_source.read_text(encoding="ascii")
    tables_text = tables_text.replace("\tstatic bool doneTables = InitTables();\n", "")
    tables_source.write_text(tables_text, encoding="ascii")


def patch_audio_debug(pal: Path) -> None:
    source = pal / "src/sound/rixplay.cpp"
    text = source.read_text(encoding="ascii")
    marker = "        pRixPlayer->opl->update((short *)(pRixPlayer->buf), sample_count);"
    debug = marker + r'''
#ifdef MEMU_PAL_AUDIO_DEBUG
        {
            static int debug_count = 0;
            if (debug_count < 8) {
                int nonzero = 0;
                for (int i = 0; i < sample_count * gConfig.iAudioChannels; i++) {
                    if (((short *)pRixPlayer->buf)[i] != 0) nonzero++;
                }
                printf("PAL AUDIO DEBUG samples=%d nonzero=%d first=%d\\n",
                       sample_count, nonzero, ((short *)pRixPlayer->buf)[0]);
                debug_count++;
            }
        }
#endif'''
    if marker not in text:
        raise RuntimeError("unexpected PAL RIX audio update source")
    if "MEMU_PAL_AUDIO_DEBUG" in text:
        return
    callback_marker = "\tLPRIXPLAYER pRixPlayer = (LPRIXPLAYER)object;"
    callback_debug = callback_marker + r'''
#ifdef MEMU_PAL_AUDIO_DEBUG
    {
        static int callback_count = 0;
        if (callback_count < 8) {
            printf("PAL RIX CALLBACK player=%p ready=%d music=%d next=%d fade=%d len=%d\n",
                   pRixPlayer, pRixPlayer ? pRixPlayer->fReady : 0,
                   pRixPlayer ? pRixPlayer->iMusic : 0,
                   pRixPlayer ? pRixPlayer->iNextMusic : 0,
                   pRixPlayer ? pRixPlayer->FadeType : 0, len);
            callback_count++;
        }
    }
#endif'''
    if callback_marker not in text:
        raise RuntimeError("unexpected PAL RIX callback source")
    text = text.replace(callback_marker, callback_debug, 1)
    source.write_text(text.replace(marker, debug, 1), encoding="ascii")

    makefile = pal / "Makefile"
    make_text = makefile.read_text(encoding="ascii")
    if "-DMEMU_PAL_AUDIO_DEBUG" not in make_text:
        make_text += "\nCFLAGS += -DMEMU_PAL_AUDIO_DEBUG\nCXXFLAGS += -DMEMU_PAL_AUDIO_DEBUG\n"
        makefile.write_text(make_text, encoding="ascii")
    app_makefile = pal.parent / "Makefile"
    app_make_text = app_makefile.read_text(encoding="ascii")
    if "-DMEMU_PAL_AUDIO_DEBUG" not in app_make_text:
        app_make_text += "\nCFLAGS += -DMEMU_PAL_AUDIO_DEBUG\nCXXFLAGS += -DMEMU_PAL_AUDIO_DEBUG\n"
        app_makefile.write_text(app_make_text, encoding="ascii")

    audio_source = pal / "src/sound/audio.c"
    audio_text = audio_source.read_text(encoding="ascii")
    opened_marker = "   gAudioDevice.fOpened = TRUE;"
    opened_debug = opened_marker + "\n   printf(\"PAL AUDIO INIT music=%d player=%p game=%s\\n\", gConfig.eMusicType, gAudioDevice.pMusPlayer, gConfig.pszGamePath ? gConfig.pszGamePath : \"(null)\");"
    if opened_marker in audio_text and "PAL AUDIO INIT music=" not in audio_text:
        audio_text = audio_text.replace(opened_marker, opened_debug, 1)
    play_marker = "      gAudioDevice.pMusPlayer->Play(gAudioDevice.pMusPlayer, iNumRIX, fLoop, flFadeTime);"
    play_debug = play_marker + "\n      printf(\"PAL AUDIO PLAY music=%d player=%p\\n\", iNumRIX, gAudioDevice.pMusPlayer);"
    if play_marker in audio_text and "PAL AUDIO PLAY music=" not in audio_text:
        audio_text = audio_text.replace(play_marker, play_debug, 1)
    fill_marker = "   memset(stream, 0, len);"
    fill_debug = fill_marker + r'''
#ifdef MEMU_PAL_AUDIO_DEBUG
   {
      static int fill_count = 0;
      if (fill_count < 8) {
         printf("PAL AUDIO FILL enabled=%d volume=%d player=%p len=%d\\n",
                gAudioDevice.fMusicEnabled, gAudioDevice.iMusicVolume,
                gAudioDevice.pMusPlayer, len);
         fill_count++;
      }
   }
#endif'''
    if fill_marker in audio_text and "PAL AUDIO FILL" not in audio_text:
        audio_text = audio_text.replace(fill_marker, fill_debug, 1)
    audio_source.write_text(audio_text, encoding="ascii")

    navy = pal.parent.parent.parent
    ndl = navy / "libs/libndl/NDL.c"
    ndl_text = ndl.read_text(encoding="ascii")
    ndl_marker = "  if (sbctl < 0 || sb < 0) return;"
    ndl_replacement = """  if (sbctl < 0 || sb < 0) {
    printf(\"PAL NDL AUDIO open sbctl=%d sb=%d\\n\", sbctl, sb);
    return;
  }
  printf(\"PAL NDL AUDIO open sbctl=%d sb=%d freq=%d\\n\", sbctl, sb, freq);"""
    if ndl_marker in ndl_text and "PAL NDL AUDIO open" not in ndl_text:
        ndl.write_text(ndl_text.replace(ndl_marker, ndl_replacement, 1), encoding="ascii")

    mini_audio = navy / "libs/libminiSDL/src/audio.c"
    mini_text = mini_audio.read_text(encoding="ascii")
    mini_marker = "  NDL_OpenAudio(audio_spec.freq, audio_spec.channels, audio_spec.samples);"
    mini_replacement = mini_marker + "\n  printf(\"PAL SDL AUDIO open freq=%d channels=%d samples=%d\\n\", audio_spec.freq, audio_spec.channels, audio_spec.samples);"
    if mini_marker in mini_text and "PAL SDL AUDIO open" not in mini_text:
        mini_audio.write_text(mini_text.replace(mini_marker, mini_replacement, 1), encoding="ascii")


def patch_early_audio(pal: Path) -> None:
    source = pal / "src/main.c"
    text = source.read_text(encoding="ascii")
    marker = "   PAL_LoadConfig(TRUE);"
    replacement = marker + "\n   AUDIO_OpenDevice();"
    if os.environ.get("MEMU_PAL_EARLY_MUSIC") == "1":
        replacement += "\n   AUDIO_PlayMusic(5, TRUE, 0);"
    if marker not in text:
        raise RuntimeError("unexpected PAL startup source")
    if replacement not in text:
        source.write_text(text.replace(marker, replacement, 1), encoding="ascii")


def patch_start_music_after_audio(pal: Path) -> None:
    source = pal / "src/main.c"
    text = source.read_text(encoding="ascii")
    marker = "   AUDIO_OpenDevice();"
    replacement = marker + "\n   AUDIO_PlayMusic(5, TRUE, 0);"
    if marker not in text:
        raise RuntimeError("unexpected PAL audio startup source")
    if replacement not in text:
        source.write_text(text.replace(marker, replacement, 1), encoding="ascii")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: patch-pa-pal.py /path/to/pal/repo", file=sys.stderr)
        return 2
    patch_dbopl(Path(sys.argv[1]))
    if os.environ.get("MEMU_PAL_AUDIO_DEBUG") == "1":
        patch_audio_debug(Path(sys.argv[1]))
    if os.environ.get("MEMU_PAL_EARLY_AUDIO") == "1":
        patch_early_audio(Path(sys.argv[1]))
    elif os.environ.get("MEMU_PAL_START_MUSIC_AFTER_AUDIO") == "1":
        patch_start_music_after_audio(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
