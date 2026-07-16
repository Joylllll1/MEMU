#!/usr/bin/env python3
"""Patch the temporary Navy NDL/miniSDL tree for MEMU's device model."""

from pathlib import Path


NDL_SOURCE = r'''#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>

static int evtdev = -1;
static int fbdev = -1;
static int screen_w = 0;
static int screen_h = 0;

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

void NDL_OpenCanvas(int *w, int *h) {
  int dispinfo = open("/proc/dispinfo", O_RDONLY);
  if (dispinfo >= 0 && (*w == 0 || *h == 0)) {
    char info[64] = {};
    int n = read(dispinfo, info, sizeof(info) - 1);
    if (n > 0) {
      int parsed_w = 0, parsed_h = 0;
      if (sscanf(info, "WIDTH:%d\nHEIGHT:%d", &parsed_w, &parsed_h) == 2) {
        if (*w == 0) *w = parsed_w;
        if (*h == 0) *h = parsed_h;
      }
    }
    close(dispinfo);
  }
  screen_w = *w;
  screen_h = *h;
  if (fbdev < 0) fbdev = open("/dev/fb", O_WRONLY);
}

void NDL_DrawRect(uint32_t *pixels, int x, int y, int w, int h) {
  if (fbdev < 0 || pixels == NULL || w <= 0 || h <= 0) return;
  if (x < 0 || y < 0 || x + w > screen_w || y + h > screen_h) return;
  for (int row = 0; row < h; row++) {
    off_t offset = (off_t)((y + row) * screen_w + x) * (off_t)sizeof(uint32_t);
    if (lseek(fbdev, offset, SEEK_SET) < 0) return;
    if (write(fbdev, pixels + row * w, (size_t)w * sizeof(uint32_t)) < 0) return;
  }
}

void NDL_OpenAudio(int freq, int channels, int samples) {
  (void)freq; (void)channels; (void)samples;
}

void NDL_CloseAudio() {
}

int NDL_PlayAudio(void *buf, int len) {
  (void)buf;
  return len;
}

int NDL_QueryAudio() {
  return 0;
}

int NDL_Init(uint32_t flags) {
  (void)flags;
  if (evtdev < 0) evtdev = open("/dev/events", O_RDONLY);
  return 0;
}

void NDL_Quit() {
  if (evtdev >= 0) close(evtdev);
  if (fbdev >= 0) close(fbdev);
  evtdev = -1;
  fbdev = -1;
}
'''


EVENT_SOURCE = r'''#include <NDL.h>
#include <SDL.h>
#include <stdio.h>
#include <string.h>

#define KEY_CASE(k) if (strcmp(name, #k) == 0) return SDLK_##k

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
  if (ev == NULL) return 0;
  char line[64];
  if (!NDL_PollEvent(line, sizeof(line))) return 0;
  char state[8], name[32];
  if (sscanf(line, "%7s %31s", state, name) != 2) return 0;
  ev->key.type = strcmp(state, "kd") == 0 ? SDL_KEYDOWN : SDL_KEYUP;
  ev->key.keysym.sym = key_code(name);
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
  static uint8_t keys[256];
  if (numkeys) *numkeys = 256;
  return keys;
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
  assert(dst && dst->format->BytesPerPixel == 4);
  int x0 = dstrect ? dstrect->x : 0;
  int y0 = dstrect ? dstrect->y : 0;
  int w = dstrect ? dstrect->w : dst->w;
  int h = dstrect ? dstrect->h : dst->h;
  for (int y = 0; y < h; y++) {
    for (int x = 0; x < w; x++) {
      if (x0 + x >= 0 && x0 + x < dst->w && y0 + y >= 0 && y0 + y < dst->h) {
        ((uint32_t *)dst->pixels)[(y0 + y) * dst->w + x0 + x] = color;
      }
    }
  }
}''',
    '''void SDL_UpdateRect(SDL_Surface *s, int x, int y, int w, int h) {
}''': r'''void SDL_UpdateRect(SDL_Surface *s, int x, int y, int w, int h) {
  if (s == NULL || !(s->flags & SDL_HWSURFACE)) return;
  if (w == 0) w = s->w;
  if (h == 0) h = s->h;
  NDL_DrawRect((uint32_t *)s->pixels + y * s->w + x, x, y, w, h);
}''',
}


def patch_tree(navy: Path) -> None:
    (navy / "libs/libndl/NDL.c").write_text(NDL_SOURCE, encoding="ascii")
    (navy / "libs/libminiSDL/src/event.c").write_text(EVENT_SOURCE, encoding="ascii")
    (navy / "libs/libminiSDL/src/timer.c").write_text(TIMER_SOURCE, encoding="ascii")

    video_path = navy / "libs/libminiSDL/src/video.c"
    video = video_path.read_text(encoding="ascii")
    for old, new in VIDEO_REPLACEMENTS.items():
        if old not in video:
            raise SystemExit(f"missing miniSDL video stub: {old.splitlines()[0]}")
        video = video.replace(old, new)
    video_path.write_text(video, encoding="ascii")


def main() -> int:
    import sys

    if len(sys.argv) != 2:
        print("usage: patch-pa-navy-ndl.py /path/to/navy-apps", file=sys.stderr)
        return 2
    patch_tree(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
