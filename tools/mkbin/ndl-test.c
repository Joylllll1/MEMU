#include <NDL.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

int main(void) {
  if (NDL_Init(0) != 0) {
    printf("FAIL: NDL_Init returned non-zero\n");
    return 1;
  }

  int w = 400, h = 300;
  NDL_OpenCanvas(&w, &h);
  if (w <= 0 || h <= 0) {
    printf("FAIL: NDL_OpenCanvas got bad dimensions: %dx%d\n", w, h);
    return 1;
  }
  printf("NDL_OpenCanvas: %dx%d\n", w, h);

  static uint32_t pixels[32 * 32];
  for (int i = 0; i < 32 * 32; i++) {
    pixels[i] = 0xFFFF0000;
  }
  NDL_DrawRect(pixels, 0, 0, 32, 32);

  for (int i = 0; i < 32 * 32; i++) {
    pixels[i] = 0xFF00FF00;
  }
  NDL_DrawRect(pixels, 50, 50, 32, 32);

  uint32_t t0 = NDL_GetTicks();
  if (t0 == 0) {
    printf("FAIL: NDL_GetTicks returned 0\n");
    return 1;
  }

  for (volatile int i = 0; i < 100000; i++) {
  }

  uint32_t t1 = NDL_GetTicks();
  if (t1 < t0) {
    printf("FAIL: NDL_GetTicks went backwards: %u -> %u\n", t0, t1);
    return 1;
  }
  printf("NDL_GetTicks: %u -> %u (delta=%u)\n", t0, t1, t1 - t0);

  char buf[64];
  int n = NDL_PollEvent(buf, sizeof(buf));
  while (n > 0) {
    buf[n] = '\0';
    printf("NDL event: %s", buf);
    n = NDL_PollEvent(buf, sizeof(buf));
  }

  NDL_Quit();
  printf("PASS: ndl-test\n");
  return 0;
}
