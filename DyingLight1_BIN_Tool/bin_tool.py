# -*- coding: utf-8 -*-
"""消逝的光芒1（Dying Light 1）.bin 文本解包 / 回包工具（重写版）

用于替代原 DyingLightBIN.exe，适用于整个游戏（不限 MOD），操作方式一致：
  - 将 .bin 文件拖到本程序图标上运行（或手动输入路径）
  - 第一次运行（不存在 .txt）：解包 .bin -> .bin.txt
  - 再次运行（存在 .txt）  ：回包 .txt  -> .bin2

相比原工具，本版修复：
  1. 原工具不反转义 \"，导致含 <font color=\"...\"> 的汉化菜单在游戏内闪退；
     本版完整反转义 \\r \\n \\t \\" \\\\ 等。
  2. 原工具行数识别依赖 CRLF，遇到非标准换行会错乱；
     本版按条目（含 = 的行）计数，并在回包前严格校验行数与 .bin 条目数一致。

版本：1.0.0
"""

import os
import sys
import struct

TOOL_VERSION = "1.0.0"

# .bin 条目数合理性范围（用于快速识别无效文件）
BIN_MIN_COUNT = 1
BIN_MAX_COUNT = 10000000


def setup_console():
    """把 Windows 控制台切换到 UTF-8，保证中文正常显示。"""
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def wait():
    """等待用户按键，避免错误时窗口自动关闭。"""
    try:
        input("\n按 Enter 键退出...")
    except (EOFError, KeyboardInterrupt):
        pass


def parse_bin(data):
    """解析 .bin 二进制为 [(key, value), ...]。"""
    if len(data) < 8:
        raise ValueError("文件太小，不是有效的 .bin 文件")
    version = struct.unpack_from("<I", data, 0)[0]
    count = struct.unpack_from("<I", data, 4)[0]
    if count < BIN_MIN_COUNT or count > BIN_MAX_COUNT:
        raise ValueError("条目数异常（%d），可能不是有效的 .bin 文件" % count)
    off = 8
    entries = []
    for _ in range(count):
        klen = struct.unpack_from("<H", data, off)[0]
        off += 2
        key = data[off:off + klen].decode("latin-1")
        off += klen
        vlen = struct.unpack_from("<H", data, off)[0]
        off += 2
        value = data[off:off + 2 * vlen].decode("utf-16-le")
        off += 2 * vlen
        entries.append((key, value))
    return entries


def pack_bin(entries):
    """把 [(key, value), ...] 打包为 .bin 二进制。"""
    out = bytearray()
    out += struct.pack("<I", 1)              # 版本号
    out += struct.pack("<I", len(entries))   # 条目总数
    for key, value in entries:
        kb = key.encode("latin-1")
        out += struct.pack("<H", len(kb))
        out += kb
        value = unescape(value)
        vb = value.encode("utf-16-le")
        out += struct.pack("<H", len(vb) // 2)
        out += vb
    return bytes(out)


def escape(value):
    """真实换行 -> \\r \\n 转义（解包方向）。"""
    return value.replace("\r", "\\r").replace("\n", "\\n")


def unescape(value):
    """\\r \\n \\t \\" \\' \\\\ 转义 -> 真实字符（回包方向）。"""
    esc = {"r": "\r", "n": "\n", "t": "\t", '"': '"', "'": "'", "\\": "\\"}
    out = []
    i = 0
    n = len(value)
    while i < n:
        c = value[i]
        if c == "\\" and i + 1 < n and value[i + 1] in esc:
            out.append(esc[value[i + 1]])
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


def read_txt(txt_path):
    """读取 UTF-16 LE 的 key=value 文本，返回 [(key, value), ...]。"""
    with open(txt_path, "rb") as f:
        raw = f.read()
    if len(raw) < 2 or raw[:2] != b"\xff\xfe":
        raise ValueError("文本不是 UTF-16 LE 编码（缺少 BOM），无法回包")
    text = raw.decode("utf-16").lstrip("\ufeff")
    entries = []
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            entries.append((k, v))
    return entries


def do_extract(bin_path):
    """解包：.bin -> .bin.txt"""
    with open(bin_path, "rb") as f:
        data = f.read()
    entries = parse_bin(data)
    lines = [key + "=" + escape(value) for key, value in entries]
    content = "\ufeff" + "\r\n".join(lines) + "\r\n"
    txt_path = bin_path + ".txt"
    with open(txt_path, "wb") as f:
        f.write(content.encode("utf-16-le"))
    print("解包完成：%s" % txt_path)
    print("共 %d 条文本" % len(entries))
    print("请编辑该文件后，再次将 .bin 拖到本程序上运行以回包。")


def do_repack(bin_path):
    """回包：.txt -> .bin2（含行数校验）"""
    with open(bin_path, "rb") as f:
        data = f.read()
    bin_count = struct.unpack_from("<I", data, 4)[0]
    txt_path = bin_path + ".txt"
    entries = read_txt(txt_path)

    # 行数校验：必须与 .bin 条目数完全一致
    if len(entries) != bin_count:
        print("[错误] 行数不匹配，已中止回包！")
        print("  .bin 条目数：%d" % bin_count)
        print("  .txt 行数  ：%d" % len(entries))
        print("  请检查汉化文本是否有缺行或多行，确保与原文完全一致。")
        return

    packed = pack_bin(entries)
    bin2_path = bin_path + "2"
    with open(bin2_path, "wb") as f:
        f.write(packed)
    print("回包完成：%s" % bin2_path)
    print("共 %d 条文本（行数校验通过）" % len(entries))


def main():
    setup_console()
    print("=" * 52)
    print("  消逝的光芒1（Dying Light 1）.bin 文本解包 / 回包工具")
    print("  版本 %s" % TOOL_VERSION)
    print("=" * 52)

    args = sys.argv[1:]
    if not args:
        print()
        print("使用方法：")
        print("  将 .bin 文件拖到本程序图标上运行。")
        print("  - 第一次运行：解包，生成 .bin.txt")
        print("  - 再次运行  ：回包，生成 .bin2")
        print()
        path = input("也可以直接输入 .bin 文件路径后按回车：").strip().strip('"')
        if not path:
            wait()
            return
        args = [path]

    bin_path = args[0]
    if not os.path.isfile(bin_path):
        print("[错误] 文件不存在：%s" % bin_path)
        wait()
        return

    try:
        if os.path.isfile(bin_path + ".txt"):
            do_repack(bin_path)
        else:
            do_extract(bin_path)
    except Exception as e:
        print("[错误] 处理失败：%s" % e)

    wait()


if __name__ == "__main__":
    main()
