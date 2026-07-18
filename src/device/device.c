#include "memu/device.h"

#include <string.h>

#ifdef MEMU_ENABLE_SDL
#include <SDL.h>
#endif

#ifdef __APPLE__
#include <mach/mach_time.h>
#else
#include <time.h>
#endif

typedef uint32_t (*DeviceRead)(uint32_t addr, int len);
typedef void (*DeviceWrite)(uint32_t addr, int len, uint32_t data);

typedef struct {
  const char *name;
  uint32_t base;
  uint32_t size;
  DeviceRead read;
  DeviceWrite write;
} MMIOMap;

static bool trace_device = false;
static bool sdl_requested = false;
static uint8_t fb[MEMU_FB_SIZE];
static uint8_t audio_sbuf[MEMU_AUDIO_SBUF_SIZE];
static uint32_t audio_regs[6];

/* Input injection queue — usable in both SDL and non-SDL modes. */
#define INJECT_QUEUE_SIZE 256
static uint32_t inject_queue[INJECT_QUEUE_SIZE];
static size_t inject_head = 0;
static size_t inject_tail = 0;

/* Full AM key list in NEMU's numbering order; codes start at 1. */
#define AM_KEY_LIST(_) \
  _(ESCAPE) _(F1) _(F2) _(F3) _(F4) _(F5) _(F6) _(F7) _(F8) _(F9) _(F10) _(F11) _(F12) \
  _(GRAVE) _(1) _(2) _(3) _(4) _(5) _(6) _(7) _(8) _(9) _(0) _(MINUS) _(EQUALS) _(BACKSPACE) \
  _(TAB) _(Q) _(W) _(E) _(R) _(T) _(Y) _(U) _(I) _(O) _(P) _(LEFTBRACKET) _(RIGHTBRACKET) _(BACKSLASH) \
  _(CAPSLOCK) _(A) _(S) _(D) _(F) _(G) _(H) _(J) _(K) _(L) _(SEMICOLON) _(APOSTROPHE) _(RETURN) \
  _(LSHIFT) _(Z) _(X) _(C) _(V) _(B) _(N) _(M) _(COMMA) _(PERIOD) _(SLASH) _(RSHIFT) \
  _(LCTRL) _(APPLICATION) _(LALT) _(SPACE) _(RALT) _(RCTRL) \
  _(UP) _(DOWN) _(LEFT) _(RIGHT) _(INSERT) _(DELETE) _(HOME) _(END) _(PAGEUP) _(PAGEDOWN)

enum {
  AM_KEY_NONE = 0,
#define AM_KEY_ENUM(k) AM_KEY_##k,
  AM_KEY_LIST(AM_KEY_ENUM)
#undef AM_KEY_ENUM
  AM_KEY_COUNT,
};

static const char *const am_key_names[AM_KEY_COUNT] = {
  "NONE",
#define AM_KEY_NAME(k) #k,
  AM_KEY_LIST(AM_KEY_NAME)
#undef AM_KEY_NAME
};

static void inject_push(uint32_t event) {
  size_t next = (inject_tail + 1u) % INJECT_QUEUE_SIZE;
  if (next != inject_head) {
    inject_queue[inject_tail] = event;
    inject_tail = next;
  }
}

static uint32_t inject_pop(void) {
  if (inject_head == inject_tail) {
    return AM_KEY_NONE;
  }
  uint32_t event = inject_queue[inject_head];
  inject_head = (inject_head + 1u) % INJECT_QUEUE_SIZE;
  return event;
}

#ifdef MEMU_ENABLE_SDL
#define KBD_QUEUE_SIZE 64
#define SDL_SCALE 2

static SDL_Window *sdl_window = NULL;
static SDL_Renderer *sdl_renderer = NULL;
static SDL_Texture *sdl_texture = NULL;
static SDL_AudioDeviceID sdl_audio_device = 0;
static bool sdl_ready = false;
static bool sdl_quit = false;
static uint32_t kbd_queue[KBD_QUEUE_SIZE];
static size_t kbd_head = 0;
static size_t kbd_tail = 0;

static void kbd_push(uint32_t event) {
  size_t next = (kbd_tail + 1u) % KBD_QUEUE_SIZE;
  if (next != kbd_head) {
    kbd_queue[kbd_tail] = event;
    kbd_tail = next;
  }
}

static uint32_t kbd_pop(void) {
  if (kbd_head == kbd_tail) {
    return AM_KEY_NONE;
  }
  uint32_t event = kbd_queue[kbd_head];
  kbd_head = (kbd_head + 1u) % KBD_QUEUE_SIZE;
  return event;
}

static uint32_t sdl_key_to_am(SDL_Keycode key) {
  static const struct {
    SDL_Keycode sdl;
    uint32_t am;
  } table[] = {
    {SDLK_ESCAPE, AM_KEY_ESCAPE},
    {SDLK_F1, AM_KEY_F1}, {SDLK_F2, AM_KEY_F2}, {SDLK_F3, AM_KEY_F3},
    {SDLK_F4, AM_KEY_F4}, {SDLK_F5, AM_KEY_F5}, {SDLK_F6, AM_KEY_F6},
    {SDLK_F7, AM_KEY_F7}, {SDLK_F8, AM_KEY_F8}, {SDLK_F9, AM_KEY_F9},
    {SDLK_F10, AM_KEY_F10}, {SDLK_F11, AM_KEY_F11}, {SDLK_F12, AM_KEY_F12},
    {SDLK_BACKQUOTE, AM_KEY_GRAVE},
    {SDLK_1, AM_KEY_1}, {SDLK_2, AM_KEY_2}, {SDLK_3, AM_KEY_3},
    {SDLK_4, AM_KEY_4}, {SDLK_5, AM_KEY_5}, {SDLK_6, AM_KEY_6},
    {SDLK_7, AM_KEY_7}, {SDLK_8, AM_KEY_8}, {SDLK_9, AM_KEY_9},
    {SDLK_0, AM_KEY_0},
    {SDLK_MINUS, AM_KEY_MINUS}, {SDLK_EQUALS, AM_KEY_EQUALS},
    {SDLK_BACKSPACE, AM_KEY_BACKSPACE}, {SDLK_TAB, AM_KEY_TAB},
    {SDLK_q, AM_KEY_Q}, {SDLK_w, AM_KEY_W}, {SDLK_e, AM_KEY_E},
    {SDLK_r, AM_KEY_R}, {SDLK_t, AM_KEY_T}, {SDLK_y, AM_KEY_Y},
    {SDLK_u, AM_KEY_U}, {SDLK_i, AM_KEY_I}, {SDLK_o, AM_KEY_O},
    {SDLK_p, AM_KEY_P},
    {SDLK_LEFTBRACKET, AM_KEY_LEFTBRACKET},
    {SDLK_RIGHTBRACKET, AM_KEY_RIGHTBRACKET},
    {SDLK_BACKSLASH, AM_KEY_BACKSLASH}, {SDLK_CAPSLOCK, AM_KEY_CAPSLOCK},
    {SDLK_a, AM_KEY_A}, {SDLK_s, AM_KEY_S}, {SDLK_d, AM_KEY_D},
    {SDLK_f, AM_KEY_F}, {SDLK_g, AM_KEY_G}, {SDLK_h, AM_KEY_H},
    {SDLK_j, AM_KEY_J}, {SDLK_k, AM_KEY_K}, {SDLK_l, AM_KEY_L},
    {SDLK_SEMICOLON, AM_KEY_SEMICOLON}, {SDLK_QUOTE, AM_KEY_APOSTROPHE},
    {SDLK_RETURN, AM_KEY_RETURN}, {SDLK_LSHIFT, AM_KEY_LSHIFT},
    {SDLK_z, AM_KEY_Z}, {SDLK_x, AM_KEY_X}, {SDLK_c, AM_KEY_C},
    {SDLK_v, AM_KEY_V}, {SDLK_b, AM_KEY_B}, {SDLK_n, AM_KEY_N},
    {SDLK_m, AM_KEY_M},
    {SDLK_COMMA, AM_KEY_COMMA}, {SDLK_PERIOD, AM_KEY_PERIOD},
    {SDLK_SLASH, AM_KEY_SLASH}, {SDLK_RSHIFT, AM_KEY_RSHIFT},
    {SDLK_LCTRL, AM_KEY_LCTRL}, {SDLK_APPLICATION, AM_KEY_APPLICATION},
    {SDLK_LALT, AM_KEY_LALT}, {SDLK_SPACE, AM_KEY_SPACE},
    {SDLK_RALT, AM_KEY_RALT}, {SDLK_RCTRL, AM_KEY_RCTRL},
    {SDLK_UP, AM_KEY_UP}, {SDLK_DOWN, AM_KEY_DOWN},
    {SDLK_LEFT, AM_KEY_LEFT}, {SDLK_RIGHT, AM_KEY_RIGHT},
    {SDLK_INSERT, AM_KEY_INSERT}, {SDLK_DELETE, AM_KEY_DELETE},
    {SDLK_HOME, AM_KEY_HOME}, {SDLK_END, AM_KEY_END},
    {SDLK_PAGEUP, AM_KEY_PAGEUP}, {SDLK_PAGEDOWN, AM_KEY_PAGEDOWN},
  };
  for (size_t i = 0; i < MEMU_ARRAY_LEN(table); i++) {
    if (table[i].sdl == key) {
      return table[i].am;
    }
  }
  return AM_KEY_NONE;
}

static void sdl_shutdown(void) {
  if (sdl_audio_device != 0) {
    SDL_CloseAudioDevice(sdl_audio_device);
    sdl_audio_device = 0;
  }
  if (sdl_texture != NULL) {
    SDL_DestroyTexture(sdl_texture);
    sdl_texture = NULL;
  }
  if (sdl_renderer != NULL) {
    SDL_DestroyRenderer(sdl_renderer);
    sdl_renderer = NULL;
  }
  if (sdl_window != NULL) {
    SDL_DestroyWindow(sdl_window);
    sdl_window = NULL;
  }
  if (sdl_ready) {
    SDL_Quit();
    sdl_ready = false;
  }
}

static bool sdl_init_once(void) {
  if (!sdl_requested || sdl_ready) {
    return true;
  }
  if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS) != 0) {
    fprintf(stderr, "MEMU SDL init failed: %s\n", SDL_GetError());
    return false;
  }
  sdl_window = SDL_CreateWindow("MEMU",
                                SDL_WINDOWPOS_CENTERED,
                                SDL_WINDOWPOS_CENTERED,
                                (int)MEMU_SCREEN_W * SDL_SCALE,
                                (int)MEMU_SCREEN_H * SDL_SCALE,
                                SDL_WINDOW_SHOWN);
  if (sdl_window == NULL) {
    fprintf(stderr, "MEMU SDL window failed: %s\n", SDL_GetError());
    sdl_shutdown();
    return false;
  }
  sdl_renderer = SDL_CreateRenderer(sdl_window, -1, SDL_RENDERER_ACCELERATED);
  if (sdl_renderer == NULL) {
    sdl_renderer = SDL_CreateRenderer(sdl_window, -1, SDL_RENDERER_SOFTWARE);
  }
  if (sdl_renderer == NULL) {
    fprintf(stderr, "MEMU SDL renderer failed: %s\n", SDL_GetError());
    sdl_shutdown();
    return false;
  }
  sdl_texture = SDL_CreateTexture(sdl_renderer,
                                  SDL_PIXELFORMAT_ARGB8888,
                                  SDL_TEXTUREACCESS_STREAMING,
                                  (int)MEMU_SCREEN_W,
                                  (int)MEMU_SCREEN_H);
  if (sdl_texture == NULL) {
    fprintf(stderr, "MEMU SDL texture failed: %s\n", SDL_GetError());
    sdl_shutdown();
    return false;
  }
  sdl_ready = true;
  atexit(sdl_shutdown);
  return true;
}

static void sdl_present(void) {
  if (!sdl_init_once()) {
    sdl_quit = true;
    return;
  }
  SDL_UpdateTexture(sdl_texture, NULL, fb, (int)MEMU_SCREEN_W * 4);
  SDL_RenderClear(sdl_renderer);
  SDL_RenderCopy(sdl_renderer, sdl_texture, NULL, NULL);
  SDL_RenderPresent(sdl_renderer);
}

static uint32_t sdl_audio_queued(void) {
  if (sdl_audio_device == 0) {
    return 0;
  }
  return SDL_GetQueuedAudioSize(sdl_audio_device);
}

static void sdl_audio_init_from_regs(void) {
  if (!sdl_requested || !sdl_init_once()) {
    return;
  }
  if (SDL_InitSubSystem(SDL_INIT_AUDIO) != 0) {
    fprintf(stderr, "MEMU SDL audio init failed: %s\n", SDL_GetError());
    return;
  }
  if (sdl_audio_device != 0) {
    SDL_CloseAudioDevice(sdl_audio_device);
    sdl_audio_device = 0;
  }

  SDL_AudioSpec want;
  SDL_zero(want);
  want.freq = audio_regs[0] != 0 ? (int)audio_regs[0] : 44100;
  want.format = AUDIO_S16SYS;
  want.channels = audio_regs[1] != 0 ? (Uint8)audio_regs[1] : 1;
  want.samples = audio_regs[2] != 0 ? (Uint16)audio_regs[2] : 1024;
  want.callback = NULL;

  sdl_audio_device = SDL_OpenAudioDevice(NULL, 0, &want, NULL, 0);
  if (sdl_audio_device == 0) {
    fprintf(stderr, "MEMU SDL audio open failed: %s\n", SDL_GetError());
    return;
  }
  SDL_PauseAudioDevice(sdl_audio_device, 0);
}

static void sdl_audio_queue_from_sbuf(uint32_t old_count, uint32_t new_count) {
  if (sdl_audio_device == 0 || new_count <= old_count) {
    return;
  }
  uint32_t len = new_count - old_count;
  if (old_count >= MEMU_AUDIO_SBUF_SIZE) {
    return;
  }
  if (old_count + len > MEMU_AUDIO_SBUF_SIZE) {
    len = MEMU_AUDIO_SBUF_SIZE - old_count;
  }
  SDL_QueueAudio(sdl_audio_device, audio_sbuf + old_count, len);
}
#endif

#ifdef __APPLE__
static uint64_t boot_tick = 0;
static mach_timebase_info_data_t timebase;

static uint64_t host_time_us(void) {
  uint64_t elapsed = mach_absolute_time() - boot_tick;
  uint64_t ns = elapsed * (uint64_t)timebase.numer / (uint64_t)timebase.denom;
  return ns / 1000u;
}
#else
static struct timespec boot_time;

static uint64_t host_time_us(void) {
  struct timespec now;
  int ret = clock_gettime(CLOCK_MONOTONIC, &now);
  MEMU_ASSERT(ret == 0, "clock_gettime(CLOCK_MONOTONIC) failed");
  uint64_t sec = (uint64_t)(now.tv_sec - boot_time.tv_sec);
  int64_t nsec = (int64_t)now.tv_nsec - (int64_t)boot_time.tv_nsec;
  if (nsec < 0) {
    sec--;
    nsec += 1000000000;
  }
  return sec * 1000000u + (uint64_t)nsec / 1000u;
}
#endif

static void trace_read(const char *name, uint32_t addr, int len, uint32_t data) {
  if (trace_device) {
    printf("[device] read  %-8s addr=0x%08x len=%d value=0x%08x\n",
           name, addr, len, data);
  }
}

static void trace_write(const char *name, uint32_t addr, int len, uint32_t data) {
  if (trace_device) {
    printf("[device] write %-8s addr=0x%08x len=%d value=0x%08x\n",
           name, addr, len, data);
  }
}

static uint32_t mask_for_len(int len) {
  switch (len) {
    case 1:
      return UINT32_C(0xff);
    case 2:
      return UINT32_C(0xffff);
    case 4:
      return UINT32_C(0xffffffff);
    default:
      MEMU_PANIC("invalid device access length: %d", len);
  }
  return 0;
}

static uint32_t serial_read(uint32_t addr, int len) {
  uint32_t data = 0;
  trace_read("serial", addr, len, data);
  return data;
}

static void serial_write(uint32_t addr, int len, uint32_t data) {
  trace_write("serial", addr, len, data);
  (void)addr;
  MEMU_ASSERT(len == 1 || len == 2 || len == 4,
              "invalid serial write length: %d", len);
  fputc((int)(data & 0xffu), stdout);
  fflush(stdout);
}

static uint32_t rtc_read(uint32_t addr, int len) {
  MEMU_ASSERT(len == 4, "rtc supports only 32-bit reads, got len=%d", len);
  uint64_t us = host_time_us();
  uint32_t data = (addr == MEMU_RTC_ADDR) ? (uint32_t)us : (uint32_t)(us >> 32);
  trace_read((addr == MEMU_RTC_ADDR) ? "rtc.low" : "rtc.high", addr, len, data);
  return data;
}

static void rtc_write(uint32_t addr, int len, uint32_t data) {
  (void)addr;
  (void)len;
  (void)data;
  MEMU_PANIC("rtc is read-only");
}

static uint32_t kbd_read(uint32_t addr, int len) {
  MEMU_ASSERT(len == 4, "keyboard supports only 32-bit reads, got len=%d", len);
  uint32_t data = inject_pop();
#ifdef MEMU_ENABLE_SDL
  if (data == 0 && sdl_requested) {
    device_poll();
    data = kbd_pop();
  }
#endif
  trace_read("keyboard", addr, len, data);
  return data;
}

static void kbd_write(uint32_t addr, int len, uint32_t data) {
  (void)addr;
  (void)len;
  (void)data;
  MEMU_PANIC("keyboard is read-only");
}

static uint32_t fb_checksum(void) {
  uint32_t hash = UINT32_C(2166136261);
  for (size_t i = 0; i < sizeof(fb); i++) {
    hash ^= fb[i];
    hash *= UINT32_C(16777619);
  }
  return hash;
}

static uint32_t vgactl_read(uint32_t addr, int len) {
  MEMU_ASSERT(len == 4, "vgactl supports only 32-bit accesses, got len=%d", len);
  uint32_t off = addr - MEMU_VGACTL_ADDR;
  uint32_t data = 0;
  if (off == 0) {
    data = (MEMU_SCREEN_W << 16) | MEMU_SCREEN_H;
  }
  trace_read("vgactl", addr, len, data);
  return data;
}

static void vgactl_write(uint32_t addr, int len, uint32_t data) {
  MEMU_ASSERT(len == 4, "vgactl supports only 32-bit accesses, got len=%d", len);
  trace_write("vgactl", addr, len, data);
  if (addr == MEMU_VGACTL_ADDR + 4u && data != 0) {
#ifdef MEMU_ENABLE_SDL
    if (sdl_requested) {
      sdl_present();
    } else
#endif
    {
      printf("MEMU: framebuffer checksum 0x%08x\n", fb_checksum());
    }
  }
}

static uint32_t fb_read(uint32_t addr, int len) {
  uint32_t off = addr - MEMU_FB_ADDR;
  uint32_t data = 0;
  for (int i = 0; i < len; i++) {
    data |= (uint32_t)fb[off + (uint32_t)i] << (i * 8);
  }
  trace_read("fb", addr, len, data);
  return data;
}

static void fb_write(uint32_t addr, int len, uint32_t data) {
  uint32_t off = addr - MEMU_FB_ADDR;
  trace_write("fb", addr, len, data);
  for (int i = 0; i < len; i++) {
    fb[off + (uint32_t)i] = (uint8_t)(data >> (i * 8));
  }
}

static uint32_t audio_read(uint32_t addr, int len) {
  MEMU_ASSERT(len == 4, "audio control supports only 32-bit accesses, got len=%d", len);
  uint32_t off = addr - MEMU_AUDIO_ADDR;
  uint32_t data = 0;
  if (off == 0x0cu) {
    data = MEMU_AUDIO_SBUF_SIZE;
  } else if (off == 0x14u) {
#ifdef MEMU_ENABLE_SDL
    data = sdl_audio_queued();
#else
    data = 0;
#endif
    audio_regs[5] = data;
  } else if (off < sizeof(audio_regs)) {
    data = audio_regs[off / 4u];
  }
  trace_read("audio", addr, len, data);
  return data;
}

static void audio_write(uint32_t addr, int len, uint32_t data) {
  MEMU_ASSERT(len == 4, "audio control supports only 32-bit accesses, got len=%d", len);
  uint32_t off = addr - MEMU_AUDIO_ADDR;
  trace_write("audio", addr, len, data);
  if (off < sizeof(audio_regs)) {
    uint32_t old_count = audio_regs[5];
    (void)old_count;
    audio_regs[off / 4u] = data;
    if (off == 0x10u && data != 0) {
#ifdef MEMU_ENABLE_SDL
      sdl_audio_init_from_regs();
#endif
    } else if (off == 0x14u) {
#ifdef MEMU_ENABLE_SDL
      sdl_audio_queue_from_sbuf(old_count, data);
      audio_regs[5] = sdl_audio_queued();
#else
      audio_regs[5] = 0;
#endif
    }
  }
  audio_regs[3] = MEMU_AUDIO_SBUF_SIZE;
}

static uint32_t audio_sbuf_read(uint32_t addr, int len) {
  uint32_t off = addr - MEMU_AUDIO_SBUF_ADDR;
  uint32_t data = 0;
  for (int i = 0; i < len; i++) {
    data |= (uint32_t)audio_sbuf[off + (uint32_t)i] << (i * 8);
  }
  trace_read("audio-sbuf", addr, len, data);
  return data;
}

static void audio_sbuf_write(uint32_t addr, int len, uint32_t data) {
  uint32_t off = addr - MEMU_AUDIO_SBUF_ADDR;
  trace_write("audio-sbuf", addr, len, data);
  for (int i = 0; i < len; i++) {
    audio_sbuf[off + (uint32_t)i] = (uint8_t)(data >> (i * 8));
  }
}

static uint32_t disk_read(uint32_t addr, int len) {
  MEMU_ASSERT(len == 4, "disk control supports only 32-bit accesses, got len=%d", len);
  uint32_t off = addr - MEMU_DISK_ADDR;
  uint32_t data = 0;
  if (off == 8u) {
    data = 1;
  }
  trace_read("disk", addr, len, data);
  return data;
}

static void disk_write(uint32_t addr, int len, uint32_t data) {
  MEMU_ASSERT(len == 4, "disk control supports only 32-bit accesses, got len=%d", len);
  trace_write("disk", addr, len, data);
}

static const MMIOMap maps[] = {
  {"rtc", MEMU_RTC_ADDR, 8, rtc_read, rtc_write},
  {"kbd", MEMU_KBD_ADDR, 4, kbd_read, kbd_write},
  {"vgactl", MEMU_VGACTL_ADDR, 8, vgactl_read, vgactl_write},
  {"audio", MEMU_AUDIO_ADDR, sizeof(audio_regs), audio_read, audio_write},
  {"disk", MEMU_DISK_ADDR, 16, disk_read, disk_write},
  {"serial", MEMU_SERIAL_ADDR, 8, serial_read, serial_write},
  {"fb", MEMU_FB_ADDR, MEMU_FB_SIZE, fb_read, fb_write},
  {"audio-sbuf", MEMU_AUDIO_SBUF_ADDR, MEMU_AUDIO_SBUF_SIZE, audio_sbuf_read, audio_sbuf_write},
};

static const MMIOMap *find_map(uint32_t addr, uint32_t len) {
  for (size_t i = 0; i < MEMU_ARRAY_LEN(maps); i++) {
    const MMIOMap *map = &maps[i];
    uint64_t off = (uint64_t)addr - map->base;
    if (addr >= map->base && off + len <= map->size) {
      return map;
    }
  }
  return NULL;
}

void device_init(void) {
  memset(fb, 0, sizeof(fb));
  memset(audio_sbuf, 0, sizeof(audio_sbuf));
  memset(audio_regs, 0, sizeof(audio_regs));
  audio_regs[3] = MEMU_AUDIO_SBUF_SIZE;
#ifdef __APPLE__
  mach_timebase_info(&timebase);
  boot_tick = mach_absolute_time();
#else
  int ret = clock_gettime(CLOCK_MONOTONIC, &boot_time);
  MEMU_ASSERT(ret == 0, "clock_gettime(CLOCK_MONOTONIC) failed");
#endif
}

void device_set_trace(bool trace) {
  trace_device = trace;
}

void device_set_sdl(bool enabled) {
  sdl_requested = enabled;
#ifndef MEMU_ENABLE_SDL
  MEMU_ASSERT(!enabled, "this MEMU binary was built without SDL support");
#else
  if (enabled) {
    MEMU_ASSERT(sdl_init_once(), "failed to initialize SDL video");
  }
#endif
}

bool device_poll(void) {
#ifdef MEMU_ENABLE_SDL
  if (!sdl_requested) {
    return true;
  }
  if (!sdl_init_once()) {
    return false;
  }
  SDL_Event event;
  while (SDL_PollEvent(&event)) {
    if (event.type == SDL_QUIT) {
      sdl_quit = true;
    } else if (event.type == SDL_KEYDOWN || event.type == SDL_KEYUP) {
        uint32_t key = sdl_key_to_am(event.key.keysym.sym);
        if (key != AM_KEY_NONE) {
          uint32_t value = key;
          if (event.type == SDL_KEYDOWN) {
            value |= MEMU_KEYDOWN_MASK;
          }
          kbd_push(value);
        }
    }
  }
  return !sdl_quit;
#else
  (void)sdl_requested;
  return true;
#endif
}

uint32_t device_read_key_event(void) {
  uint32_t injected = inject_pop();
  if (injected != AM_KEY_NONE) {
    return injected;
  }
#ifdef MEMU_ENABLE_SDL
  if (sdl_requested) {
    device_poll();
    return kbd_pop();
  }
#endif
  return AM_KEY_NONE;
}

const char *device_key_name(uint32_t event) {
  uint32_t code = event & ~MEMU_KEYDOWN_MASK;
  if (code == AM_KEY_NONE || code >= AM_KEY_COUNT) {
    return NULL;
  }
  return am_key_names[code];
}

uint32_t device_key_code(const char *name) {
  for (uint32_t code = 1; code < AM_KEY_COUNT; code++) {
    if (strcmp(name, am_key_names[code]) == 0) {
      return code;
    }
  }
  return AM_KEY_NONE;
}

void device_inject_key_events_from_file(const char *path) {
  FILE *f = fopen(path, "r");
  MEMU_ASSERT(f != NULL, "cannot open key events file: %s", path);
  char line[64];
  while (fgets(line, sizeof(line), f) != NULL) {
    char state[8], name[32];
    if (sscanf(line, "%7s %31s", state, name) != 2) {
      continue;
    }
    uint32_t code = device_key_code(name);
    if (code == AM_KEY_NONE) {
      fprintf(stderr, "MEMU: ignoring unknown key in events file: %s\n", name);
      continue;
    }
    uint32_t event = code;
    if (strcmp(state, "kd") == 0) {
      event |= MEMU_KEYDOWN_MASK;
    }
    inject_push(event);
  }
  fclose(f);
  printf("MEMU: injected %zu key events from %s\n",
         (inject_tail - inject_head + INJECT_QUEUE_SIZE) % INJECT_QUEUE_SIZE, path);
}

bool device_in_range(uint32_t addr, uint32_t len) {
  return find_map(addr, len) != NULL;
}

uint32_t device_read(uint32_t addr, int len) {
  MEMU_ASSERT(len == 1 || len == 2 || len == 4,
              "invalid device read length: %d", len);
  const MMIOMap *map = find_map(addr, (uint32_t)len);
  MEMU_ASSERT(map != NULL, "unmapped device read: addr=0x%08x len=%d", addr, len);
  return map->read(addr, len) & mask_for_len(len);
}

void device_write(uint32_t addr, int len, uint32_t data) {
  MEMU_ASSERT(len == 1 || len == 2 || len == 4,
              "invalid device write length: %d", len);
  const MMIOMap *map = find_map(addr, (uint32_t)len);
  MEMU_ASSERT(map != NULL, "unmapped device write: addr=0x%08x len=%d", addr, len);
  map->write(addr, len, data & mask_for_len(len));
}
