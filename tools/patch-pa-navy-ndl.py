#!/usr/bin/env python3
"""Patch the temporary Navy NDL/miniSDL tree for MEMU's device model."""

from pathlib import Path


NDL_SOURCE = r'''#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>

static int evtdev = -1;
static int fbdev = -1;
static int sbctl = -1;
static int sb = -1;
static int disp_w = 0;
static int disp_h = 0;
static int canvas_w = 0;
static int canvas_h = 0;
static int off_x = 0;
static int off_y = 0;
static int fit_w = 0;
static int fit_h = 0;
/* Shadow canvas + row buffer, used only when the canvas is larger than the
 * display and must be scaled down to fit. */
static uint32_t *shadow = NULL;
static uint32_t *rowbuf = NULL;

uint32_t NDL_GetTicks() {
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return (uint32_t)(tv.tv_sec * 1000u + tv.tv_usec / 1000u);
}

int NDL_PollEvent(char *buf, int len) {
  if (evtdev < 0 || buf == NULL || len <= 1) return 0;
  int n = read(evtdev, buf, (size_t)len - 1);
  if (n <= 0) return 0;
  buf[n] = '\0';
  return n;
}

static void read_dispinfo(void) {
  int dispinfo = open("/proc/dispinfo", O_RDONLY);
  if (dispinfo < 0) return;
  char info[64] = {};
  int n = read(dispinfo, info, sizeof(info) - 1);
  if (n > 0) sscanf(info, "WIDTH:%d\nHEIGHT:%d", &disp_w, &disp_h);
  close(dispinfo);
}

void NDL_OpenCanvas(int *w, int *h) {
  read_dispinfo();
  if (*w == 0 || *h == 0) {
    *w = disp_w;
    *h = disp_h;
  }
  canvas_w = *w;
  canvas_h = *h;
  free(shadow);
  shadow = NULL;
  free(rowbuf);
  rowbuf = NULL;
  if (canvas_w <= disp_w && canvas_h <= disp_h) {
    fit_w = canvas_w;
    fit_h = canvas_h;
  } else {
    fit_h = disp_h;
    fit_w = (int)((long)canvas_w * disp_h / canvas_h);
    if (fit_w > disp_w) {
      fit_w = disp_w;
      fit_h = (int)((long)canvas_h * disp_w / canvas_w);
    }
    shadow = calloc((size_t)canvas_w * (size_t)canvas_h, sizeof(uint32_t));
    rowbuf = malloc((size_t)fit_w * sizeof(uint32_t));
  }
  off_x = (disp_w - fit_w) / 2;
  off_y = (disp_h - fit_h) / 2;
  if (fbdev < 0) fbdev = open("/dev/fb", O_WRONLY);
}

void NDL_DrawRect(uint32_t *pixels, int x, int y, int w, int h) {
  if (fbdev < 0 || pixels == NULL || w <= 0 || h <= 0) return;
  if (x < 0 || y < 0 || x + w > canvas_w || y + h > canvas_h) return;
  if (shadow == NULL) {
    for (int row = 0; row < h; row++) {
      off_t offset = (off_t)((off_y + y + row) * disp_w + off_x + x) * (off_t)sizeof(uint32_t);
      if (lseek(fbdev, offset, SEEK_SET) < 0) return;
      if (write(fbdev, pixels + row * w, (size_t)w * sizeof(uint32_t)) < 0) return;
    }
  } else {
    if (rowbuf == NULL) return;
    for (int row = 0; row < h; row++) {
      memcpy(shadow + (y + row) * canvas_w + x, pixels + row * w,
             (size_t)w * sizeof(uint32_t));
    }
    for (int dy = 0; dy < fit_h; dy++) {
      const uint32_t *src = shadow + ((long)dy * canvas_h / fit_h) * canvas_w;
      for (int dx = 0; dx < fit_w; dx++) {
        rowbuf[dx] = src[(long)dx * canvas_w / fit_w];
      }
      off_t offset = (off_t)((off_y + dy) * disp_w + off_x) * (off_t)sizeof(uint32_t);
      if (lseek(fbdev, offset, SEEK_SET) < 0) return;
      if (write(fbdev, rowbuf, (size_t)fit_w * sizeof(uint32_t)) < 0) return;
    }
  }
  *(volatile uint32_t *)0xa0000104 = 1;
}

void NDL_OpenAudio(int freq, int channels, int samples) {
  if (sbctl < 0) sbctl = open("/dev/sbctl", O_RDWR);
  if (sb < 0) sb = open("/dev/sb", O_WRONLY);
  if (sbctl < 0 || sb < 0) return;
  uint32_t config[3] = {(uint32_t)freq, (uint32_t)channels, (uint32_t)samples};
  (void)write(sbctl, config, sizeof(config));
}

void NDL_CloseAudio() {
  if (sb >= 0) close(sb);
  if (sbctl >= 0) close(sbctl);
  sb = -1;
  sbctl = -1;
}

int NDL_PlayAudio(void *buf, int len) {
  if (sb < 0 || buf == NULL || len <= 0) return 0;
  return write(sb, buf, (size_t)len);
}

int NDL_QueryAudio() {
  if (sbctl < 0) return 0;
  uint32_t available = 0;
  if (read(sbctl, &available, sizeof(available)) != sizeof(available)) return 0;
  return (int)available;
}

int NDL_Init(uint32_t flags) {
  (void)flags;
  if (evtdev < 0) evtdev = open("/dev/events", O_RDONLY);
  return 0;
}

void NDL_Quit() {
  if (evtdev >= 0) close(evtdev);
  if (fbdev >= 0) close(fbdev);
  NDL_CloseAudio();
  evtdev = -1;
  fbdev = -1;
  free(shadow);
  shadow = NULL;
  free(rowbuf);
  rowbuf = NULL;
}
'''


AUDIO_SOURCE = r'''#include <NDL.h>
#include <SDL.h>
#include <stdlib.h>
#include <string.h>

static SDL_AudioSpec audio_spec;
static int audio_opened = 0;
static int audio_paused = 1;

int SDL_OpenAudio(SDL_AudioSpec *desired, SDL_AudioSpec *obtained) {
  if (desired == NULL || desired->callback == NULL) return -1;
  audio_spec = *desired;
  audio_spec.size = (uint32_t)audio_spec.samples * audio_spec.channels *
                    (audio_spec.format == AUDIO_U8 ? 1u : 2u);
  NDL_OpenAudio(audio_spec.freq, audio_spec.channels, audio_spec.samples);
  audio_opened = 1;
  audio_paused = 1;
  if (obtained != NULL) *obtained = audio_spec;
  return 0;
}

void SDL_CloseAudio() {
  if (audio_opened) NDL_CloseAudio();
  audio_opened = 0;
  audio_paused = 1;
}

void SDL_PauseAudio(int pause_on) {
  audio_paused = pause_on != 0;
}

void miniSDL_audio_pump(void) {
  if (!audio_opened || audio_paused || audio_spec.callback == NULL) return;
  uint32_t len = audio_spec.size;
  if (len == 0 || NDL_QueryAudio() < (int)len) return;
  uint8_t *buffer = malloc(len);
  if (buffer == NULL) return;
  audio_spec.callback(audio_spec.userdata, buffer, (int)len);
  (void)NDL_PlayAudio(buffer, (int)len);
  free(buffer);
}

void SDL_MixAudio(uint8_t *dst, uint8_t *src, uint32_t len, int volume) {
  if (dst == NULL || src == NULL || volume <= 0) return;
  if (volume >= SDL_MIX_MAXVOLUME) {
    memcpy(dst, src, len);
    return;
  }
  for (uint32_t i = 0; i + 1 < len; i += 2) {
    int sample = (int)(int16_t)(src[i] | ((uint16_t)src[i + 1] << 8));
    sample = sample * volume / SDL_MIX_MAXVOLUME;
    dst[i] = (uint8_t)sample;
    dst[i + 1] = (uint8_t)(sample >> 8);
  }
}

SDL_AudioSpec *SDL_LoadWAV(const char *file, SDL_AudioSpec *spec,
                           uint8_t **audio_buf, uint32_t *audio_len) {
  (void)file; (void)spec; (void)audio_buf; (void)audio_len;
  return NULL;
}

void SDL_FreeWAV(uint8_t *audio_buf) {
  free(audio_buf);
}

void SDL_LockAudio() {
}

void SDL_UnlockAudio() {
}
'''


EVENT_SOURCE = r'''#include <NDL.h>
#include <SDL.h>
#include <stdio.h>
#include <string.h>

#define KEY_CASE(k) if (strcmp(name, #k) == 0) return SDLK_##k

static uint8_t key_state[256];
extern void miniSDL_audio_pump(void);

static uint8_t key_code(const char *name) {
  KEY_CASE(ESCAPE); KEY_CASE(F1); KEY_CASE(F2); KEY_CASE(F3); KEY_CASE(F4);
  KEY_CASE(F5); KEY_CASE(F6); KEY_CASE(F7); KEY_CASE(F8); KEY_CASE(F9);
  KEY_CASE(F10); KEY_CASE(F11); KEY_CASE(F12); KEY_CASE(GRAVE);
  KEY_CASE(1); KEY_CASE(2); KEY_CASE(3); KEY_CASE(4); KEY_CASE(5);
  KEY_CASE(6); KEY_CASE(7); KEY_CASE(8); KEY_CASE(9); KEY_CASE(0);
  KEY_CASE(MINUS); KEY_CASE(EQUALS); KEY_CASE(BACKSPACE); KEY_CASE(TAB);
  KEY_CASE(Q); KEY_CASE(W); KEY_CASE(E); KEY_CASE(R); KEY_CASE(T); KEY_CASE(Y);
  KEY_CASE(U); KEY_CASE(I); KEY_CASE(O); KEY_CASE(P); KEY_CASE(LEFTBRACKET);
  KEY_CASE(RIGHTBRACKET); KEY_CASE(BACKSLASH); KEY_CASE(CAPSLOCK); KEY_CASE(A);
  KEY_CASE(S); KEY_CASE(D); KEY_CASE(F); KEY_CASE(G); KEY_CASE(H); KEY_CASE(J);
  KEY_CASE(K); KEY_CASE(L); KEY_CASE(SEMICOLON); KEY_CASE(APOSTROPHE);
  KEY_CASE(RETURN); KEY_CASE(LSHIFT); KEY_CASE(Z); KEY_CASE(X); KEY_CASE(C);
  KEY_CASE(V); KEY_CASE(B); KEY_CASE(N); KEY_CASE(M); KEY_CASE(COMMA);
  KEY_CASE(PERIOD); KEY_CASE(SLASH); KEY_CASE(RSHIFT); KEY_CASE(LCTRL);
  KEY_CASE(APPLICATION); KEY_CASE(LALT); KEY_CASE(SPACE); KEY_CASE(RALT);
  KEY_CASE(RCTRL); KEY_CASE(UP); KEY_CASE(DOWN); KEY_CASE(LEFT); KEY_CASE(RIGHT);
  KEY_CASE(INSERT); KEY_CASE(DELETE); KEY_CASE(HOME); KEY_CASE(END);
  KEY_CASE(PAGEUP); KEY_CASE(PAGEDOWN);
  return SDLK_NONE;
}

int SDL_PushEvent(SDL_Event *ev) {
  (void)ev;
  return 0;
}

int SDL_PollEvent(SDL_Event *ev) {
  miniSDL_audio_pump();
  if (ev == NULL) return 0;
  char line[64];
  if (!NDL_PollEvent(line, sizeof(line))) return 0;
  char state[8], name[32];
  if (sscanf(line, "%7s %31s", state, name) != 2) return 0;
  ev->key.type = strcmp(state, "kd") == 0 ? SDL_KEYDOWN : SDL_KEYUP;
  ev->key.keysym.sym = key_code(name);
  if (ev->key.keysym.sym != SDLK_NONE) {
    key_state[ev->key.keysym.sym] = ev->key.type == SDL_KEYDOWN;
  }
  return 1;
}

int SDL_WaitEvent(SDL_Event *event) {
  while (!SDL_PollEvent(event)) {
  }
  return 1;
}

int SDL_PeepEvents(SDL_Event *ev, int numevents, int action, uint32_t mask) {
  (void)action; (void)mask;
  if (numevents <= 0) return 0;
  return SDL_PollEvent(ev);
}

uint8_t* SDL_GetKeyState(int *numkeys) {
  if (numkeys) *numkeys = 256;
  return key_state;
}
'''


TIMER_SOURCE = r'''#include <stddef.h>
#include <NDL.h>
#include <sdl-timer.h>

SDL_TimerID SDL_AddTimer(uint32_t interval, SDL_NewTimerCallback callback, void *param) {
  (void)interval; (void)callback; (void)param;
  return NULL;
}

int SDL_RemoveTimer(SDL_TimerID id) {
  (void)id;
  return 1;
}

uint32_t SDL_GetTicks() {
  return NDL_GetTicks();
}

void SDL_Delay(uint32_t ms) {
  uint32_t start = SDL_GetTicks();
  while ((uint32_t)(SDL_GetTicks() - start) < ms) {
  }
}
'''


VIDEO_REPLACEMENTS = {
    '''void SDL_BlitSurface(SDL_Surface *src, SDL_Rect *srcrect, SDL_Surface *dst, SDL_Rect *dstrect) {
  assert(dst && src);
  assert(dst->format->BitsPerPixel == src->format->BitsPerPixel);
}''': r'''void SDL_BlitSurface(SDL_Surface *src, SDL_Rect *srcrect, SDL_Surface *dst, SDL_Rect *dstrect) {
  assert(dst && src);
  assert(dst->format->BitsPerPixel == src->format->BitsPerPixel);
  int sx = srcrect ? srcrect->x : 0;
  int sy = srcrect ? srcrect->y : 0;
  int w = srcrect ? srcrect->w : src->w;
  int h = srcrect ? srcrect->h : src->h;
  int dx = dstrect ? dstrect->x : 0;
  int dy = dstrect ? dstrect->y : 0;
  int bpp = src->format->BytesPerPixel;
  for (int y = 0; y < h; y++) {
    if (sy + y < 0 || sy + y >= src->h || dy + y < 0 || dy + y >= dst->h) continue;
    for (int x = 0; x < w; x++) {
      if (sx + x < 0 || sx + x >= src->w || dx + x < 0 || dx + x >= dst->w) continue;
      memcpy(dst->pixels + (dy + y) * dst->pitch + (dx + x) * bpp,
             src->pixels + (sy + y) * src->pitch + (sx + x) * bpp, bpp);
    }
  }
}''',
    '''void SDL_FillRect(SDL_Surface *dst, SDL_Rect *dstrect, uint32_t color) {
}''': r'''void SDL_FillRect(SDL_Surface *dst, SDL_Rect *dstrect, uint32_t color) {
  assert(dst);
  int x0 = dstrect ? dstrect->x : 0;
  int y0 = dstrect ? dstrect->y : 0;
  int w = dstrect ? dstrect->w : dst->w;
  int h = dstrect ? dstrect->h : dst->h;
  for (int y = 0; y < h; y++) {
    if (x0 < 0 || y0 + y < 0 || x0 + w > dst->w || y0 + y >= dst->h) continue;
    if (dst->format->BytesPerPixel == 1) {
      memset(dst->pixels + (y0 + y) * dst->pitch + x0, (uint8_t)color, (size_t)w);
    } else if (dst->format->BytesPerPixel == 4) {
      for (int x = 0; x < w; x++) {
        ((uint32_t *)dst->pixels)[(y0 + y) * dst->w + x0 + x] = color;
      }
    }
  }
}''',
    '''void SDL_UpdateRect(SDL_Surface *s, int x, int y, int w, int h) {
}''': r'''void SDL_UpdateRect(SDL_Surface *s, int x, int y, int w, int h) {
  extern void miniSDL_audio_pump(void);
  miniSDL_audio_pump();
  if (s == NULL || !(s->flags & SDL_HWSURFACE)) return;
  if (w == 0) w = s->w;
  if (h == 0) h = s->h;
  if (x < 0 || y < 0 || x + w > s->w || y + h > s->h) return;
  if (s->format->BytesPerPixel == 4) {
    NDL_DrawRect((uint32_t *)s->pixels + y * s->w + x, x, y, w, h);
    return;
  }
  if (s->format->BytesPerPixel != 1 || s->format->palette == NULL) return;

  uint32_t *converted = malloc((size_t)w * (size_t)h * sizeof(*converted));
  if (converted == NULL) return;
  for (int row = 0; row < h; row++) {
    const uint8_t *src = s->pixels + (y + row) * s->pitch + x;
    for (int col = 0; col < w; col++) {
      SDL_Color color = s->format->palette->colors[src[col]];
      converted[row * w + col] = UINT32_C(0xff000000) |
          ((uint32_t)color.r << 16) | ((uint32_t)color.g << 8) | color.b;
    }
  }
  NDL_DrawRect(converted, x, y, w, h);
  free(converted);
}''',
}


FILE_SOURCE = r'''#include <sdl-file.h>
#include <stdio.h>
#include <stdlib.h>

static int64_t rw_size(SDL_RWops *f) {
  long cur = ftell(f->fp);
  fseek(f->fp, 0, SEEK_END);
  long sz = ftell(f->fp);
  fseek(f->fp, cur, SEEK_SET);
  return sz;
}

static int64_t rw_seek(SDL_RWops *f, int64_t offset, int whence) {
  return fseek(f->fp, (long)offset, whence);
}

static size_t rw_read(SDL_RWops *f, void *buf, size_t size, size_t nmemb) {
  return fread(buf, size, nmemb, f->fp);
}

static size_t rw_write(SDL_RWops *f, const void *buf, size_t size, size_t nmemb) {
  return fwrite(buf, size, nmemb, f->fp);
}

static int rw_close(SDL_RWops *f) {
  int ret = 0;
  if (f->fp != NULL) { ret = fclose(f->fp); f->fp = NULL; }
  free(f);
  return ret;
}

SDL_RWops* SDL_RWFromFile(const char *filename, const char *mode) {
  FILE *fp = fopen(filename, mode);
  if (fp == NULL) return NULL;
  SDL_RWops *rw = calloc(1, sizeof(SDL_RWops));
  if (rw == NULL) { fclose(fp); return NULL; }
  rw->type = RW_TYPE_FILE;
  rw->fp = fp;
  rw->size = rw_size;
  rw->seek = rw_seek;
  rw->read = rw_read;
  rw->write = rw_write;
  rw->close = rw_close;
  return rw;
}

SDL_RWops* SDL_RWFromMem(void *mem, int size) {
  if (mem == NULL || size <= 0) return NULL;
  SDL_RWops *rw = calloc(1, sizeof(SDL_RWops));
  if (rw == NULL) return NULL;
  rw->type = RW_TYPE_MEM;
  rw->mem.base = mem;
  rw->mem.size = size;
  return rw;
}
'''


IMAGE_SOURCE = r'''#include <SDL.h>
#include <SDL_image.h>
#include <stdio.h>
#include <stdlib.h>

#define STBI_NO_STDIO
#define STB_IMAGE_IMPLEMENTATION
#include "stb_image.h"

SDL_Surface* IMG_Load(const char *filename) {
  FILE *fp = fopen(filename, "rb");
  if (fp == NULL) return NULL;
  fseek(fp, 0, SEEK_END);
  long sz = ftell(fp);
  fseek(fp, 0, SEEK_SET);
  unsigned char *buf = malloc(sz);
  if (buf == NULL) { fclose(fp); return NULL; }
  if (fread(buf, 1, sz, fp) != (size_t)sz) { free(buf); fclose(fp); return NULL; }
  fclose(fp);

  int w, h, comp;
  unsigned char *data = stbi_load_from_memory(buf, (int)sz, &w, &h, &comp, 4);
  free(buf);
  if (data == NULL) return NULL;

  SDL_Surface *s = SDL_CreateRGBSurfaceFrom(data, w, h, 32, w * 4,
      0x000000ff, 0x0000ff00, 0x00ff0000, 0xff000000);
  if (s == NULL) { free(data); return NULL; }
  s->flags &= ~SDL_PREALLOC;
  return s;
}

SDL_Surface* IMG_Load_RW(SDL_RWops *src, int freesrc) {
  (void)src; (void)freesrc;
  return NULL;
}

int IMG_isPNG(SDL_RWops *src) {
  (void)src;
  return 0;
}

SDL_Surface* IMG_LoadJPG_RW(SDL_RWops *src) {
  return IMG_Load_RW(src, 0);
}

char *IMG_GetError() {
  return "Navy IMG_GetError";
}
'''


def patch_tree(navy: Path) -> None:
    (navy / "libs/libndl/NDL.c").write_text(NDL_SOURCE, encoding="ascii")
    (navy / "libs/libminiSDL/src/event.c").write_text(EVENT_SOURCE, encoding="ascii")
    (navy / "libs/libminiSDL/src/audio.c").write_text(AUDIO_SOURCE, encoding="ascii")
    (navy / "libs/libminiSDL/src/timer.c").write_text(TIMER_SOURCE, encoding="ascii")

    video_path = navy / "libs/libminiSDL/src/video.c"
    video = video_path.read_text(encoding="ascii")
    for old, new in VIDEO_REPLACEMENTS.items():
        if old not in video:
            raise SystemExit(f"missing miniSDL video stub: {old.splitlines()[0]}")
        video = video.replace(old, new)
    video_path.write_text(video, encoding="ascii")

    (navy / "libs/libminiSDL/src/file.c").write_text(FILE_SOURCE, encoding="ascii")
    (navy / "libs/libSDL_image/src/image.c").write_text(IMAGE_SOURCE, encoding="ascii")


def main() -> int:
    import sys

    if len(sys.argv) != 2:
        print("usage: patch-pa-navy-ndl.py /path/to/navy-apps", file=sys.stderr)
        return 2
    patch_tree(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
