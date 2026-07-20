#ifndef MEMU_DEVICE_H
#define MEMU_DEVICE_H

#include "memu/common.h"

#define MEMU_SERIAL_ADDR UINT32_C(0xa00003f8)
#define MEMU_RTC_ADDR UINT32_C(0xa0000048)
#define MEMU_KBD_ADDR UINT32_C(0xa0000060)
#define MEMU_VGACTL_ADDR UINT32_C(0xa0000100)
#define MEMU_AUDIO_ADDR UINT32_C(0xa0000200)
#define MEMU_DISK_ADDR UINT32_C(0xa0000300)
#define MEMU_FB_ADDR UINT32_C(0xa1000000)
#define MEMU_AUDIO_SBUF_ADDR UINT32_C(0xa1200000)

#define MEMU_SCREEN_W 400u
#define MEMU_SCREEN_H 300u
#define MEMU_FB_SIZE (MEMU_SCREEN_W * MEMU_SCREEN_H * 4u)
#define MEMU_AUDIO_SBUF_SIZE UINT32_C(0x10000)
#define MEMU_KEYDOWN_MASK UINT32_C(0x8000)

void device_init(void);
void device_set_trace(bool trace);
void device_set_sdl(bool enabled);
bool device_poll(void);
void device_fb_dump_ppm(const char *path);
uint32_t device_read_key_event(void);
const char *device_key_name(uint32_t event);
uint32_t device_key_code(const char *name);
void device_inject_key_events_from_file(const char *path);
bool device_in_range(uint32_t addr, uint32_t len);
uint32_t device_read(uint32_t addr, int len);
void device_write(uint32_t addr, int len, uint32_t data);
uint32_t device_audio_query(void);
void device_audio_configure(uint32_t freq, uint32_t channels, uint32_t samples);
uint32_t device_audio_play(const uint8_t *data, uint32_t len);
void device_audio_close(void);

#endif
