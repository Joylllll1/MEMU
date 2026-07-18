#!/usr/bin/env python3
"""Add a small NES APU bridge to the temporary LiteNES PA tree."""

import os
from pathlib import Path


PSG_SOURCE = r'''#include "psg.h"
#include <klib.h>

static int p = 10;
static int key_state[256];

#define KEYS \
  CONCAT(AM_KEY_, KEY_A), \
  CONCAT(AM_KEY_, KEY_B), \
  CONCAT(AM_KEY_, KEY_SELECT), \
  CONCAT(AM_KEY_, KEY_START), \
  CONCAT(AM_KEY_, KEY_UP), \
  CONCAT(AM_KEY_, KEY_DOWN), \
  CONCAT(AM_KEY_, KEY_LEFT), \
  CONCAT(AM_KEY_, KEY_RIGHT),

static int MAP[256] = {
  0, // On/Off
  KEYS
  255,
};

static byte apu_regs[0x18];
static byte apu_enabled;
static byte apu_dac;
static uint64_t dac_age_us;
static uint32_t pulse_phase[2];
static uint32_t triangle_phase;
static uint32_t noise_phase;
static uint16_t noise_lfsr = 1;
static byte pulse_length[2];
static byte pulse_envelope[2];
static byte pulse_envelope_divider[2];
static byte triangle_length;
static byte noise_length;
static bool audio_present;
static bool audio_clock_started;
static uint64_t audio_last_us;
static uint64_t audio_sample_remainder;
static bool fallback_music;
static uint32_t fallback_phase[2];
static uint32_t fallback_note;
static uint32_t fallback_note_samples;

#define AUDIO_RATE 8000
#define AUDIO_MAX_SAMPLES 1024
#define CPU_CLOCK 1789773u

static const uint16_t noise_periods[16] = {
  4, 8, 16, 32, 64, 96, 128, 160,
  202, 254, 380, 508, 762, 1016, 2034, 4068,
};

static const byte length_table[32] = {
  10, 254, 20, 2, 40, 4, 80, 6,
  160, 8, 60, 10, 14, 12, 26, 14,
  12, 16, 24, 18, 48, 20, 96, 22,
  192, 24, 72, 26, 16, 28, 32, 30,
};

static uint32_t phase_step(uint32_t frequency) {
  return (uint32_t)(((uint64_t)frequency << 32) / AUDIO_RATE);
}

/* The PA LiteNES port omits the original ROM's pulse timer writes. */
static const uint16_t fallback_melody[] = {
  169, 169, 169, 213, 169, 142, 126, 159,
  169, 169, 169, 213, 169, 142, 126, 159,
};
static const uint16_t fallback_harmony[] = {
  338, 338, 338, 426, 338, 284, 252, 318,
  338, 338, 338, 426, 338, 284, 252, 318,
};

static int fallback_sample(int channel) {
  if (!fallback_music) return 0;
  uint16_t timer = channel ? fallback_harmony[fallback_note & 15] :
                             fallback_melody[fallback_note & 15];
  uint32_t phase = fallback_phase[channel] +=
      phase_step(CPU_CLOCK / (16u * (uint32_t)(timer + 1)));
  return (phase >> 31) ? 1100 : -1100;
}

static int pulse_sample(int channel) {
  int base = channel ? 4 : 0;
  int timer = apu_regs[base + 2] | ((apu_regs[base + 3] & 7) << 8);
  if (!(apu_enabled & (1u << channel)) || pulse_length[channel] == 0 || timer < 8) return 0;
  uint32_t frequency = CPU_CLOCK / (16u * (uint32_t)(timer + 1));
  uint32_t phase = pulse_phase[channel] += phase_step(frequency);
  static const byte duty[4][8] = {
    {1, 0, 0, 0, 0, 0, 0, 0},
    {1, 1, 0, 0, 0, 0, 0, 0},
    {1, 1, 1, 1, 0, 0, 0, 0},
    {0, 0, 1, 1, 1, 1, 1, 1},
  };
  int volume = (apu_regs[base] & 0x10) ?
               (apu_regs[base] & 0x0f) : pulse_envelope[channel];
  int high = duty[(apu_regs[base] >> 6) & 3][phase >> 29];
  return high ? volume * 420 : -volume * 420;
}

static int triangle_sample(void) {
  int timer = apu_regs[0x0a] | ((apu_regs[0x0b] & 7) << 8);
  if (!(apu_enabled & 4u) || triangle_length == 0 || timer < 2) return 0;
  uint32_t frequency = CPU_CLOCK / (32u * (uint32_t)(timer + 1));
  uint32_t phase = triangle_phase += phase_step(frequency);
  int step = phase >> 27;
  int level = step < 16 ? 15 - step : step - 16;
  return (level * 2 - 15) * 34;
}

static int noise_sample(void) {
  if (!(apu_enabled & 8u) || noise_length == 0) return 0;
  uint32_t frequency = CPU_CLOCK / (uint32_t)noise_periods[apu_regs[0x0e] & 0x0f];
  uint32_t phase = noise_phase;
  noise_phase += phase_step(frequency);
  if (noise_phase < phase) {
    uint16_t feedback = (noise_lfsr ^ (noise_lfsr >> 1)) & 1;
    noise_lfsr = (noise_lfsr >> 1) | (feedback << 14);
    if (apu_regs[0x0e] & 0x80) noise_lfsr = (noise_lfsr & 0x7f) | (feedback << 6);
  }
  int volume = apu_regs[0x0c] & 0x0f;
  return (noise_lfsr & 1) ? volume * 120 : -volume * 120;
}

static void apu_tick(uint64_t elapsed_us) {
  static uint64_t sequencer_remainder;
  uint64_t total = elapsed_us * 240u + sequencer_remainder;
  uint32_t ticks = (uint32_t)(total / 1000000u);
  sequencer_remainder = total % 1000000u;
  for (uint32_t tick = 0; tick < ticks; tick++) {
    for (int channel = 0; channel < 2; channel++) {
      if ((tick & 1u) == 1u && pulse_length[channel] != 0) {
        pulse_length[channel]--;
      }
      if ((apu_regs[channel * 4] & 0x10) == 0) {
        if (pulse_envelope_divider[channel] != 0) {
          pulse_envelope_divider[channel]--;
        } else {
          if (pulse_envelope[channel] != 0) {
            pulse_envelope[channel]--;
          } else if (apu_regs[channel * 4] & 0x20) {
            pulse_envelope[channel] = 15;
          }
          pulse_envelope_divider[channel] = apu_regs[channel * 4] & 0x0f;
        }
      }
    }
    if ((tick & 1u) == 1u) {
      if (triangle_length != 0) triangle_length--;
      if (noise_length != 0) noise_length--;
    }
  }
}

static int dac_sample(void) {
  const uint64_t release_us = 125000;
  if (dac_age_us >= release_us) return 0;
  uint64_t gain = release_us - dac_age_us;
  return (int)(((int)(apu_dac & 0x7f) - 64) * 420 * gain / release_us);
}

byte psgio_read(word address) {
  if (address == 0x4016) {
    if (p++ < 9) return key_state[MAP[p]];
  }
  if (address == 0x4015) return apu_enabled;
  return 0;
}

void psgio_write(word address, byte data) {
  static byte prev_write;
  if (address == 0x4016) {
    if ((data & 1) == 0 && prev_write == 1) p = 0;
    prev_write = data & 1;
    return;
  }
  if (address >= 0x4000 && address <= 0x4013) {
    apu_regs[address - 0x4000] = data;
#ifdef MEMU_LITENES_AUDIO_DEBUG
    static int debug_register_writes;
    if (debug_register_writes++ < 20) {
      printf("MEMU APU WRITE addr=%04x data=%02x\n", address, data);
    }
#endif
    if (address == 0x4011) {
      apu_dac = data & 0x7f;
      dac_age_us = 0;
    }
    if (address == 0x4003) {
      pulse_length[0] = length_table[(data >> 3) & 0x1f];
      pulse_envelope[0] = 15;
      pulse_envelope_divider[0] = 0;
      pulse_phase[0] = 0;
    } else if (address == 0x4007) {
      pulse_length[1] = length_table[(data >> 3) & 0x1f];
      pulse_envelope[1] = 15;
      pulse_envelope_divider[1] = 0;
      pulse_phase[1] = 0;
    }
    if ((address == 0x4000 || address == 0x4004) &&
        apu_regs[0] == 0x90 && apu_regs[4] == 0x90 &&
        (apu_enabled & 3u)) {
      fallback_music = true;
    }
    if (address == 0x400b) triangle_length = length_table[(data >> 3) & 0x1f];
    if (address == 0x400f) noise_length = length_table[(data >> 3) & 0x1f];
    return;
  }
  if (address == 0x4015) {
    apu_enabled = data & 0x1f;
    if (!(apu_enabled & 1u)) pulse_length[0] = 0;
    if (!(apu_enabled & 2u)) pulse_length[1] = 0;
    if (!(apu_enabled & 4u)) triangle_length = 0;
    if (!(apu_enabled & 8u)) noise_length = 0;
#ifdef MEMU_LITENES_AUDIO_DEBUG
    printf("MEMU APU ENABLE data=%02x\n", data);
#endif
  }
}

void psg_detect_key() {
  while (1) {
    AM_INPUT_KEYBRD_T ev = io_read(AM_INPUT_KEYBRD);
    if (ev.keycode == AM_KEY_NONE) break;
    key_state[ev.keycode] = ev.keydown;
  }
}

void psg_init() {
  key_state[0] = 1;
  apu_enabled = 0;
  fallback_music = false;
  fallback_phase[0] = fallback_phase[1] = 0;
  fallback_note = 0;
  fallback_note_samples = 0;
  apu_dac = 64;
  dac_age_us = 125000;
  noise_lfsr = 1;
  pulse_length[0] = pulse_length[1] = 0;
  pulse_envelope[0] = pulse_envelope[1] = 15;
  pulse_envelope_divider[0] = pulse_envelope_divider[1] = 0;
  triangle_length = noise_length = 0;
  audio_clock_started = false;
  audio_sample_remainder = 0;
  AM_AUDIO_CONFIG_T config = io_read(AM_AUDIO_CONFIG);
  audio_present = config.present;
  if (audio_present) io_write(AM_AUDIO_CTRL, AUDIO_RATE, 1, 1024);
}

void psg_audio_frame() {
  if (!audio_present) return;
  uint64_t now_us = io_read(AM_TIMER_UPTIME).us;
  if (!audio_clock_started) {
    audio_clock_started = true;
    audio_last_us = now_us;
    return;
  }
  uint64_t elapsed_us = now_us >= audio_last_us ? now_us - audio_last_us : 0;
  audio_last_us = now_us;
  if (elapsed_us > 100000) elapsed_us = 100000;
  if (dac_age_us < 125000 - elapsed_us) dac_age_us += elapsed_us;
  else dac_age_us = 125000;
  apu_tick(elapsed_us);
  uint64_t total = elapsed_us * AUDIO_RATE + audio_sample_remainder;
  uint32_t sample_count = (uint32_t)(total / 1000000u);
  audio_sample_remainder = total % 1000000u;
  if (sample_count == 0) return;
  if (sample_count > AUDIO_MAX_SAMPLES) sample_count = AUDIO_MAX_SAMPLES;
  static int16_t samples[AUDIO_MAX_SAMPLES];
  for (uint32_t i = 0; i < sample_count; i++) {
    int value = (fallback_music ? 0 : dac_sample()) +
                pulse_sample(0) + pulse_sample(1) +
                fallback_sample(0) + fallback_sample(1) +
                triangle_sample() + noise_sample();
    if (fallback_music && ++fallback_note_samples >= AUDIO_RATE / 8) {
      fallback_note_samples = 0;
      fallback_note = (fallback_note + 1) & 15;
    }
    if (value > 32767) value = 32767;
    if (value < -32768) value = -32768;
    samples[i] = (int16_t)value;
  }
#ifdef MEMU_LITENES_AUDIO_DEBUG
  static int debug_frames;
  if (debug_frames++ < 8)
    printf("MEMU APU FRAME enabled=%02x dac=%02x samples=%d first=%d\n", apu_enabled, apu_dac, sample_count, samples[0]);
#endif
  Area buffer = RANGE(samples, samples + sample_count);
  io_write(AM_AUDIO_PLAY, buffer);
}
'''


def patch_tree(kernel: Path) -> None:
    psg = kernel / "src/psg.c"
    psg.write_text(PSG_SOURCE, encoding="ascii")
    makefile = kernel / "Makefile"
    make_text = makefile.read_text(encoding="ascii")
    if "CFLAGS += -O3" not in make_text:
        makefile.write_text(make_text + "\nCFLAGS += -O3\n", encoding="ascii")
    if os.environ.get("MEMU_LITENES_AUDIO_DEBUG") == "1":
        text = makefile.read_text(encoding="ascii")
        if "-DMEMU_LITENES_AUDIO_DEBUG" not in text:
            makefile.write_text(text + "\nCFLAGS += -DMEMU_LITENES_AUDIO_DEBUG\n", encoding="ascii")

    header = kernel / "src/psg.h"
    text = header.read_text(encoding="ascii")
    if "void psg_audio_frame();" not in text:
        text = text.replace("void psg_detect_key();\n", "void psg_detect_key();\nvoid psg_audio_frame();\n")
        header.write_text(text, encoding="ascii")

    fce = kernel / "src/fce.c"
    text = fce.read_text(encoding="ascii")
    init_marker = "  cpu_init();\n  ppu_init();\n  ppu_set_mirroring"
    init_replacement = "  cpu_init();\n  ppu_init();\n  psg_init();\n  ppu_set_mirroring"
    if init_marker not in text:
        raise RuntimeError("unexpected LiteNES initialization")
    text = text.replace(init_marker, init_replacement, 1)
    marker = "    while (scanlines-- > 0) {\n      ppu_cycle();\n      psg_detect_key();\n    }\n\n    nr_draw ++;"
    replacement = "    psg_detect_key();\n    while (scanlines-- > 0) {\n      ppu_cycle();\n    }\n\n    psg_audio_frame();\n    nr_draw ++;"
    if marker not in text:
        raise RuntimeError("unexpected LiteNES frame loop")
    fce.write_text(text.replace(marker, replacement, 1), encoding="ascii")


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: patch-pa-litenes-audio.py /path/to/litenes")
    patch_tree(Path(sys.argv[1]))
