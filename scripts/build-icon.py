#!/usr/bin/env python3
"""生成 Character 应用图标（纯标准库、零网络、零依赖）。

把 app 左上角的阴阳鱼 logo 重绘成 1024x1024 PNG，并可打包成 macOS .icns。
用法：
    python3 build-icon.py                  # 只生成 web/app-icon.png
    python3 build-icon.py --icns OUT.icns  # 顺便打包 .icns
"""
import os
import sys
import struct
import math
import zlib

SIZE = 1024
MARGIN = 100                    # Apple 规范：四周留透明边距，防止 macOS 自动加深色底板
CONTENT = SIZE - 2 * MARGIN     # 内容区 824
S = CONTENT / 96.0              # logo path 占 viewBox 2..98（共 96 单位），直接铺满内容区

def P(x, y):
    return (MARGIN + (x - 2) * S, MARGIN + (y - 2) * S)

# 还原 app.html 里那个阴阳鱼 path（viewBox 100x100），并映射到内容区
poly = []
poly.append(P(2, 2))
poly.append(P(69.88, 2))
N = 28
for i in range(1, N + 1):
    th = math.radians(45 * i / N)
    poly.append(P(2 + 67.88 * math.cos(th), 2 + 67.88 * math.sin(th)))
poly.append(P(50, 50))
for i in range(1, N + 1):
    th = math.radians(225 - 45 * i / N)
    poly.append(P(98 + 67.88 * math.cos(th), 98 + 67.88 * math.sin(th)))
poly.append(P(30.12, 98))
poly.append(P(2, 98))


def point_in_poly(x, y, poly):
    inside = False
    n = len(poly)
    j = n - 1
    for i in range(n):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


RADIUS = CONTENT * 0.225        # Apple squircle 圆角比例（约 185）

def in_round(x, y):
    if x < MARGIN or x >= SIZE - MARGIN or y < MARGIN or y >= SIZE - MARGIN:
        return False
    cx = min(max(x, MARGIN + RADIUS), SIZE - MARGIN - RADIUS)
    cy = min(max(y, MARGIN + RADIUS), SIZE - MARGIN - RADIUS)
    return (x - cx) ** 2 + (y - cy) ** 2 <= RADIUS * RADIUS


BG = (23, 22,20)
LT = (244, 243, 240)
LB = (185, 181, 173)

def light(y):
    t = (y - MARGIN) / CONTENT
    t = max(0.0, min(1.0, t))
    return tuple(int(LT[i] + (LB[i] - LT[i]) * t) for i in range(3))


def _png(raw, w, h):
    def chunk(typ, data):
        c = typ + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xffffffff)
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def render_png(path):
    raw = bytearray()
    for y in range(SIZE):
        raw.append(0)
        for x in range(SIZE):
            if not in_round(x, y):
                raw.extend((0, 0, 0, 0))
            elif point_in_poly(x + 0.5, y + 0.5, poly):   # 像素中心采样，避免浮点边界差 1 行
                raw.extend(light(y) + (255,))
            else:
                raw.extend(BG + (255,))
    with open(path, "wb") as f:
        f.write(_png(raw, SIZE, SIZE))
    print("PNG ->", path)


def make_icns(png_path, icns_path):
    with open(png_path, "rb") as f:
        png = f.read()
    assert png[:8] == b"\x89PNG\r\n\x1a\n", "source is not a PNG"
    # 现代 macOS 接受直接内嵌 PNG 的条目类型
    TYPES = [b"ic08", b"ic09", b"ic10", b"ic14"]
    entries = b""
    for t in TYPES:
        entries += t + struct.pack(">I", len(png) + 8) + png
    icns = b"icns" + struct.pack(">I", len(entries) + 8) + entries
    with open(icns_path, "wb") as f:
        f.write(icns)
    print("ICNS ->", icns_path)


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    web = os.path.join(os.path.dirname(here), "web")     # scripts/../web
    png_out = os.path.join(web, "app-icon.png")
    render_png(png_out)
    if "--icns" in sys.argv:
        i = sys.argv.index("--icns")
        if i + 1 < len(sys.argv):
            make_icns(png_out, sys.argv[i + 1])
        else:
            print("用法: build-icon.py --icns <输出.icns>")
