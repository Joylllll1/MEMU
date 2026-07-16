# Stage 7: Ramdisk、简易文件系统与应用程序

## 参考 NEMU 的位置

对应 NEMU PA3 的文件系统和应用程序。NEMU 的 SFS 思路是把文件作为 ramdisk 上的固定字节序列，并用文件记录表维护名字、大小和偏移。

## 为什么做

当用户程序数量和数据变多后，直接让程序访问 ramdisk 偏移会非常脆弱。文件系统提供了更高层的抽象：用户程序通过文件名和 fd 访问数据，OS 负责映射到底层 ramdisk。

## 要实现什么

- ramdisk image。
- 固定文件表：name、size、disk_offset、open_offset。
- syscall：`open`、`read`、`write`、`lseek`、`close`。
- 特殊文件：stdin、stdout、stderr、可选 `/dev/events`、`/dev/fb`。
- loader 从文件系统加载用户程序。

## 怎么做

1. 写工具把若干文件打包成 ramdisk image 和 file table。
2. OS 初始化时加载 file table。
3. `open(path)` 查表并返回 fd。
4. `read(fd, buf, len)` 从 ramdisk 当前 offset 拷贝。
5. `write(fd, buf, len)` 对 stdout/stderr 输出，对普通文件先可选只读。
6. `lseek(fd, off, whence)` 更新 open offset。
7. loader 通过文件名读取 ELF 或 raw binary。

## 怎么验证

```sh
./build/memu --kernel tests/images/fs-os.elf --ramdisk tests/images/ramdisk.img --batch
```

期望结果：

- 用户程序能打开文本文件并打印内容。
- 多个程序能从文件系统中被 loader 加载。
- `lseek` 测试能重复读取指定位置。
- 越界读写返回合理结果，不破坏内存。

## 常见坑

- 文件 offset 是每个打开文件独立的，不是全局文件共享一个 offset。
- `read` 到 EOF 应返回实际读取字节数。
- 文件名比较要处理不存在文件。
- ramdisk offset 和 guest virtual address 完全不是一回事。
- 用户 buffer 在 guest memory 中，syscall handler 要通过 guest memory 读写。

## 给 LLM 的提示

先实现只读普通文件和 stdout，再实现 lseek，最后接 loader。不要实现目录、创建、删除、动态扩容，这些超出教学版 SFS 的范围。

## 和 NEMU 对齐的验收

对应 NEMU PA3 的文件系统和精彩应用程序。Stage 7 完成后，MEMU 应该从“能跑用户程序”推进到“能跑 Navy-apps 的代表程序”：

- Navy-apps 的简单文本程序能通过 Nanos-lite 运行。
- `/dev/events`、`/dev/fb`、timer 相关接口足以支撑 NDL。
- miniSDL 中 `SDL_BlitSurface()`、`SDL_UpdateRect()` 等最小图形 API 可用。
- `NSlider` 能显示第一张幻灯片，并能响应翻页输入。
- Flappy Bird 或同等级图形程序可无音频运行。
- PAL/仙剑类应用至少能进入可见画面；若未完全可玩，必须记录卡在文件系统、像素格式、输入、timer、miniSDL 还是运行时初始化。

这一阶段的验收要明确区分“能启动”“能显示”“能交互”“能长时间稳定运行”，不要只写“能跑”。

## 完成标准

- 用户程序可以通过 syscall 读取 ramdisk 文件。
- loader 可以按文件名加载程序。
- 文件系统错误路径有稳定返回值和日志。
