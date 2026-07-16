# Chapter 8: Ramdisk、简易文件系统与应用

## 8.1 为什么需要文件系统

Chapter 7 的批处理系统可以顺序运行多个程序，但程序列表仍然来自 host path 或硬编码数组。这不够像一个操作系统。

如果程序和数据都能作为文件存放在 ramdisk 中，OS 就可以通过文件名加载程序，用户程序也可以通过 `open/read/write/lseek/close` 访问数据。

本章实现一个教学版 simple file system，简称 SFS。

## 8.2 本章结束时应该看到什么

运行：

```sh
./build/memu --kernel tests/images/fs-os.elf --ramdisk tests/images/ramdisk.img --batch
```

或者简化：

```sh
./build/memu --ramdisk tests/images/ramdisk.img --run /bin/cat /share/message.txt
```

预期：

```text
Hello from ramdisk
HIT GOOD TRAP
```

具体 CLI 可调整，但本章核心是：guest 通过文件名读到 ramdisk 中的数据。

## 8.3 SFS 的简化规则

教学版文件系统采用：

- 文件数量固定。
- 文件大小固定。
- 文件连续存放在 ramdisk。
- 没有目录树，路径只是字符串。
- 不支持创建和删除。
- 普通文件可以先只读。

这不是完整文件系统，但足够支撑 loader 和用户程序。

## 8.4 新增模块

```text
include/
  memu/
    ramdisk.h
    fs.h
src/
  os/
    ramdisk.c
    fs.c
tools/
  mkfs/
    mkfs.c
fsimg/
  bin/
  share/
tests/
  images/
    ramdisk.img
    ramdisk_table.c 或 .h
```

## 8.5 第一件事：ramdisk

ramdisk 是一个 host 文件，MEMU 把它读入内存数组：

```c
static uint8_t *ramdisk;
static size_t ramdisk_size;
```

接口：

```c
bool ramdisk_load(const char *path);
size_t ramdisk_read(void *buf, size_t offset, size_t len);
size_t ramdisk_write(const void *buf, size_t offset, size_t len);
size_t ramdisk_size(void);
```

`ramdisk_read()` 和 `ramdisk_write()` 操作的是 host buffer，不是 guest memory。syscall 层负责在 guest memory 和 ramdisk 之间拷贝。

## 8.6 第二件事：文件表

定义：

```c
typedef struct {
  const char *name;
  uint32_t size;
  uint32_t disk_offset;
} FileInfo;
```

例如：

```c
{ "/share/message.txt", 19, 0 },
{ "/bin/hello", 1024, 19 },
```

文件表可以由 `tools/mkfs` 生成，也可以第一版手写。

## 8.7 第三件事：mkfs 工具

`mkfs` 输入一个目录：

```text
fsimg/
  share/message.txt
  bin/hello
```

输出：

```text
tests/images/ramdisk.img
tests/images/ramdisk_table.h
```

流程：

```text
遍历文件
按固定顺序写入 ramdisk.img
记录每个文件的 name、size、offset
生成 C header
```

第一版可以不递归目录，只处理清单文件：

```text
fsimg/MANIFEST
/share/message.txt fsimg/share/message.txt
/bin/hello fsimg/bin/hello
```

这样实现更可控。

## 8.8 第四件事：open file table

文件表描述文件本身。打开文件还需要 fd 状态：

```c
typedef struct {
  bool used;
  int file_index;
  uint32_t open_offset;
} OpenFile;
```

为什么 offset 不能放在 `FileInfo`？

因为同一个文件可以被打开多次，每个 fd 有自己的当前位置。

预留：

```text
fd 0 stdin
fd 1 stdout
fd 2 stderr
```

普通文件从 fd 3 开始。

## 8.9 第五件事：实现 `open`

syscall：

```text
SYS_open
a0 = guest path address
a1 = flags
a2 = mode
return fd or -1
```

第一版忽略 flags/mode，只支持只读。

关键：path 在 guest memory 中。你需要从 guest memory 读取 C 字符串：

```c
bool guest_read_cstr(uint32_t addr, char *buf, size_t buflen);
```

### Checkpoint 1

guest 调用：

```c
int fd = open("/share/message.txt", 0, 0);
```

返回值应 >= 3。

不存在文件返回 -1。

## 8.10 第六件事：实现 `read`

syscall：

```text
SYS_read
a0 = fd
a1 = guest buffer
a2 = len
return bytes_read
```

流程：

```text
找到 OpenFile
找到 FileInfo
可读长度 = min(len, file.size - open_offset)
从 ramdisk offset = file.disk_offset + open_offset 读取
写入 guest buffer
open_offset += bytes_read
返回 bytes_read
```

EOF 返回 0。

### Checkpoint 2

guest：

```c
fd = open("/share/message.txt", 0, 0);
n = read(fd, buf, sizeof(buf));
write(1, buf, n);
```

预期输出文件内容。

## 8.11 第七件事：实现 `write`

已有 `write` 支持 stdout/stderr。现在可以扩展：

- fd 1/2：输出到 host。
- 普通文件：第一版返回 -1，表示不支持写。

后续如果需要，可以允许不超过原文件大小的写。

## 8.12 第八件事：实现 `lseek`

syscall：

```text
SYS_lseek
a0 = fd
a1 = offset
a2 = whence
return new offset or -1
```

支持：

```text
SEEK_SET = 0
SEEK_CUR = 1
SEEK_END = 2
```

不要让 offset 变成负数或超过文件大小。第一版可以 clamp，也可以返回 -1。建议返回 -1，更容易暴露 bug。

### Checkpoint 3

guest：

```c
read first 5 bytes
lseek(fd, 0, SEEK_SET)
read first 5 bytes again
```

两次内容应一致。

## 8.13 第九件事：实现 `close`

`close(fd)`：

```text
检查 fd 是否有效
标记 OpenFile unused
返回 0
```

fd 0/1/2 可以允许 close 后无效果，或者返回错误。先选择简单明确的行为并写进文档。

## 8.14 第十件事：loader 从文件系统加载程序

现在 batch OS 可以不直接用 host path，而是从 ramdisk 文件加载：

```text
open("/bin/prog-a")
read file content
load as raw/ELF
close
```

这一步让“程序也是文件”的抽象成立。

### Checkpoint 4

ramdisk 包含：

```text
/bin/prog-a
/bin/prog-b
/share/message.txt
```

batch OS 从 `/bin/prog-a` 和 `/bin/prog-b` 加载，按顺序运行。

## 8.15 特殊文件

后续可以加入：

```text
/dev/events
/dev/fb
/proc/dispinfo
```

第一版可以只保留普通文件和 stdout/stderr。不要把设备文件和普通文件一起做复杂。

## 8.16 调试路线

### open 找不到文件

打印 guest path 字符串，确认从 guest memory 读取正确。

### read 输出乱码

检查：

- ramdisk offset。
- open_offset。
- guest buffer 写入。

### 第二次 read 读不到内容

可能是 open_offset 已到 EOF。用 `lseek` 重置。

### 多 fd 互相影响

检查 offset 是否放在 OpenFile，而不是 FileInfo。

## 8.17 必答题

1. ramdisk 和文件系统有什么区别？
2. 为什么 fd 需要 open_offset？
3. 为什么 path 要从 guest memory 读取？
4. EOF 时 `read` 应该返回什么？
5. 为什么第一版 SFS 不支持创建和删除？
6. loader 从文件系统加载程序后，host path 还重要吗？

## 8.18 给 LLM 的提示

建议分任务：

```text
1. 实现 ramdisk_load/read/write。
2. 实现 FileInfo 和 OpenFile。
3. 实现 open/read/write/lseek/close。
4. 写 mkfs 工具和 ramdisk smoke test。
5. 让 loader 支持从文件系统加载 /bin 程序。
```

不要让 LLM 一开始实现目录树、动态文件大小、权限、缓存。

## 8.19 本章完成标准

必须通过：

```sh
./build/memu --ramdisk tests/images/ramdisk.img --run /bin/cat /share/message.txt
```

或者等价测试，并确认：

- open 能找到文件。
- read 能返回文件内容。
- lseek 能改变 offset。
- close 能释放 fd。
- loader 能从 ramdisk 加载用户程序。

通过后进入 Chapter 9。

## 8.20 NEMU PA3 应用层对齐

本章后半段要从“文件系统能读文本”推进到“可以支撑 Navy-apps”。这一步是 PA3 最容易低估的地方，因为它同时牵涉文件、设备、库函数和图形。

建议按下面顺序推进：

```text
plain file read
loader from /bin
/dev/events
/proc/dispinfo
/dev/fb
NDL timer/event/canvas
miniSDL surface/blit/update
NSlider
Flappy Bird
PAL
```

不要从 PAL 开始。PAL 失败时信息量太大，不适合作为第一个调试目标。

### 特殊文件语义

Navy-apps 常见特殊文件：

```text
/dev/events
/dev/fb
/proc/dispinfo
```

建议行为：

- `/dev/events`：`read` 返回一行事件字符串，没有事件时返回 0 或按约定返回空。
- `/dev/fb`：`write` 把 guest buffer 写入 framebuffer，offset 表示像素位置或字节位置，必须和 NDL 约定一致。
- `/proc/dispinfo`：返回屏幕宽高，例如 `WIDTH:640\nHEIGHT:480\n`。

这些特殊文件不要放进 ramdisk 普通文件路径里硬读。它们应该由文件系统层分发到设备逻辑。

### NDL 最小接口

先支持应用最常用的接口：

```text
NDL_Init
NDL_Quit
NDL_GetTicks
NDL_PollEvent
NDL_OpenCanvas
NDL_DrawRect
```

每实现一个接口，都写一个极小应用测试。

例如 timer app：

```text
print NDL_GetTicks twice
assert second >= first
```

例如 draw app：

```text
open 320x240 canvas
draw one red rectangle
exit
```

### miniSDL 最小接口

跑 `NSlider` 前，至少需要：

```text
SDL_Init
SDL_Quit
SDL_SetVideoMode
SDL_CreateRGBSurface
SDL_BlitSurface
SDL_UpdateRect
SDL_PollEvent
SDL_GetTicks
```

miniSDL 的重点不是完整，而是行为足够让目标应用不误判。

常见失败：

- `SDL_BlitSurface` 没处理 pitch。
- surface 像素格式和 framebuffer 像素格式不一致。
- `SDL_UpdateRect` 忽略 x/y/w/h，导致整屏或局部刷新错。
- `SDL_PollEvent` 永远返回 0，应用无法响应输入。

### NSlider 验收

最低验收：

```text
first slide visible
left/right key changes slide
no unknown syscall
no invalid memory access
```

如果第一张幻灯片显示出来但不能翻页，优先查 `/dev/events` 和 `SDL_PollEvent`。  
如果能翻页但图片颜色乱，优先查像素格式和 endian。  
如果打开图片失败，优先查 ramdisk file table 和 path。

### PAL/仙剑预验收

PAL 是综合应用，不建议作为 Chapter 8 的唯一完成标准。但本章至少应该做到：

```text
PAL binary can be loaded
resource files can be opened
initial screen or early log appears
failure reason is classified
```

失败分类只用这些：

```text
loader
syscall
filesystem
NDL
miniSDL
input
timer
framebuffer
cpu
unknown
```

这样后面继续实现时，LLM 能收到非常明确的任务。

## 8.21 本章 NEMU 对齐完成标准

Chapter 8 完成时，至少满足：

- 普通文件 open/read/lseek/close 可用。
- loader 能从 `/bin` 加载用户程序。
- `/dev/events`、`/dev/fb`、`/proc/dispinfo` 有最小实现。
- NDL timer/event/canvas 可用。
- 一个文本 Navy app 通过。
- 一个图形 smoke app 通过。
- `NSlider` 可以显示并响应翻页。
- PAL 状态写入 `docs/compat-status.md`。

如果 PAL 没完全跑通，不算失败；但如果不知道它卡在哪层，就还不能进入下一阶段。
