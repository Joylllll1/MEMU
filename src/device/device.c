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

enum {
  AM_KEY_NONE = 0,
  AM_KEY_ESCAPE = 1,
  AM_KEY_Q = 29,
  AM_KEY_W = 30,
  AM_KEY_U = 35,
  AM_KEY_I = 36,
  AM_KEY_A = 43,
  AM_KEY_S = 44,
  AM_KEY_D = 45,
  AM_KEY_J = 49,
  AM_KEY_K = 50,
  AM_KEY_UP = 73,
  AM_KEY_DOWN = 74,
  AM_KEY_LEFT = 75,
  AM_KEY_RIGHT = 76,
};

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
  switch (key) {
    case SDLK_ESCAPE:
      return AM_KEY_ESCAPE;
    case SDLK_q:
      return AM_KEY_Q;
    case SDLK_w:
      return AM_KEY_W;
    case SDLK_a:
      return AM_KEY_A;
    case SDLK_s:
      return AM_KEY_S;
    case SDLK_d:
      return AM_KEY_D;
    case SDLK_u:
      return AM_KEY_U;
    case SDLK_i:
      return AM_KEY_I;
    case SDLK_j:
      return AM_KEY_J;
    case SDLK_k:
      return AM_KEY_K;
    case SDLK_UP:
      return AM_KEY_UP;
    case SDLK_DOWN:
      return AM_KEY_DOWN;
    case SDLK_LEFT:
      return AM_KEY_LEFT;
    case SDLK_RIGHT:
      return AM_KEY_RIGHT;
    default:
      return AM_KEY_NONE;
  }
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
  sdl_window = SDL_CreateWindow("MEMU Mario",
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
  uint32_t data = 0;
#ifdef MEMU_ENABLE_SDL
  if (sdl_requested) {
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
#ifdef MEMU_ENABLE_SDL
  if (sdl_requested) {
    device_poll();
    return kbd_pop();
  }
#endif
  return AM_KEY_NONE;
}

const char *device_key_name(uint32_t event) {
  switch (event & ~MEMU_KEYDOWN_MASK) {
    case AM_KEY_ESCAPE:
      return "ESCAPE";
    case AM_KEY_Q:
      return "Q";
    case AM_KEY_W:
      return "W";
    case AM_KEY_U:
      return "U";
    case AM_KEY_I:
      return "I";
    case AM_KEY_A:
      return "A";
    case AM_KEY_S:
      return "S";
    case AM_KEY_D:
      return "D";
    case AM_KEY_J:
      return "J";
    case AM_KEY_K:
      return "K";
    case AM_KEY_UP:
      return "UP";
    case AM_KEY_DOWN:
      return "DOWN";
    case AM_KEY_LEFT:
      return "LEFT";
    case AM_KEY_RIGHT:
      return "RIGHT";
    default:
      return NULL;
  }
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
