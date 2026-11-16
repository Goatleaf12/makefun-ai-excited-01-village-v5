#!/usr/bin/env python3
"""ai-excited-01 v5 — "The Village That Sailed the Sky".

Draws, from scratch, a floating village in a dawn sky: rocky islands with
warm little houses, waterfalls spilling into the clouds, and a great sailing
ship flying past the sun. Pure Python standard library only: the rasterizer
and the PNG encoder (zlib) are written here, no third-party code, no network,
no randomness — the same bytes come out every run.
"""
import os
import struct
import zlib

W = H = 1024

# ---------------------------------------------------------------- buffer
img = bytearray(W * H * 3)


def set_px(x, y, r, g, b):
    if 0 <= x < W and 0 <= y < H:
        i = (y * W + x) * 3
        img[i] = r
        img[i + 1] = g
        img[i + 2] = b


def blend_px(x, y, r, g, b, a):
    """Blend color (r,g,b) over the pixel at (x,y); a in 0..1."""
    if 0 <= x < W and 0 <= y < H and a > 0.0:
        if a >= 1.0:
            set_px(x, y, r, g, b)
            return
        i = (y * W + x) * 3
        img[i] = int(img[i] + (r - img[i]) * a + 0.5)
        img[i + 1] = int(img[i + 1] + (g - img[i + 1]) * a + 0.5)
        img[i + 2] = int(img[i + 2] + (b - img[i + 2]) * a + 0.5)


def lerp(a, b, t):
    return a + (b - a) * t


def lerp_c(c1, c2, t):
    return (int(lerp(c1[0], c2[0], t) + 0.5),
            int(lerp(c1[1], c2[1], t) + 0.5),
            int(lerp(c1[2], c2[2], t) + 0.5))


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


# ------------------------------------------------------- deterministic rng
_seed = 1234567


def rnd():
    global _seed
    _seed = (_seed * 1103515245 + 12345) & 0x7FFFFFFF
    return _seed / 0x7FFFFFFF


# ---------------------------------------------------------------- shapes
def fill_rect(x0, y0, x1, y1, c, a=1.0):
    x0 = max(0, int(x0))
    y0 = max(0, int(y0))
    x1 = min(W, int(x1))
    y1 = min(H, int(y1))
    r, g, b = c
    for y in range(y0, y1):
        base = (y * W + x0) * 3
        if a >= 1.0:
            row = bytes((r, g, b)) * (x1 - x0)
            img[base:base + (x1 - x0) * 3] = row
        else:
            for x in range(x0, x1):
                blend_px(x, y, r, g, b, a)


def line(x0, y0, x1, y1, c, a=1.0):
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        blend_px(x0, y0, c[0], c[1], c[2], a)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def fill_poly(points, c, a=1.0, grad=None):
    """Scanline polygon fill. grad=(c_top, c_bottom, y_top, y_bot) optional."""
    if len(points) < 3:
        return
    ys = [p[1] for p in points]
    y0 = max(0, int(min(ys)))
    y1 = min(H - 1, int(max(ys)) + 1)
    n = len(points)
    for y in range(y0, y1):
        xs = []
        for i in range(n):
            x1, yy1 = points[i]
            x2, yy2 = points[(i + 1) % n]
            if (yy1 <= y < yy2) or (yy2 <= y < yy1):
                t = (y - yy1) / (yy2 - yy1)
                xs.append(x1 + t * (x2 - x1))
        if len(xs) < 2:
            continue
        xs.sort()
        if grad is not None:
            ct, cb, gt, gb = grad
            t = clamp((y - gt) / max(1, gb - gt), 0.0, 1.0)
            col = lerp_c(ct, cb, t)
        else:
            col = c
        for k in range(0, len(xs) - 1, 2):
            xa = max(0, int(xs[k]))
            xb = min(W, int(xs[k + 1]) + 1)
            for x in range(xa, xb):
                blend_px(x, y, col[0], col[1], col[2], a)


def soft_ellipse(cx, cy, rx, ry, c, a, power=0.8):
    """Ellipse with a soft falloff edge."""
    x0 = max(0, int(cx - rx))
    x1 = min(W - 1, int(cx + rx) + 1)
    y0 = max(0, int(cy - ry))
    y1 = min(H - 1, int(cy + ry) + 1)
    for y in range(y0, y1):
        dy = (y - cy) / ry
        for x in range(x0, x1):
            dx = (x - cx) / rx
            d = dx * dx + dy * dy
            if d < 1.0:
                fall = (1.0 - d) ** power
                blend_px(x, y, c[0], c[1], c[2], a * fall)


def bezier(p0, p1, p2, steps=24):
    pts = []
    for i in range(steps + 1):
        t = i / steps
        u = 1.0 - t
        x = u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0]
        y = u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1]
        pts.append((x, y))
    return pts


# ------------------------------------------------------------------- sky
def draw_sky():
    stops = [
        (0.00, (14, 12, 44)),
        (0.18, (48, 28, 84)),
        (0.38, (128, 52, 106)),
        (0.55, (214, 96, 84)),
        (0.68, (248, 158, 96)),
        (0.78, (255, 198, 128)),
        (1.00, (252, 214, 160)),
    ]
    for y in range(H):
        t = y / (H - 1)
        for i in range(len(stops) - 1):
            t0, c0 = stops[i]
            t1, c1 = stops[i + 1]
            if t0 <= t <= t1:
                col = lerp_c(c0, c1, (t - t0) / (t1 - t0))
                break
        else:
            col = stops[-1][1]
        base = y * W * 3
        img[base:base + W * 3] = bytes(col) * W


def draw_sun():
    cx, cy = 772, 268
    # wide glow
    soft_ellipse(cx, cy, 330, 330, (255, 176, 92), 0.55, power=1.6)
    soft_ellipse(cx, cy, 200, 200, (255, 205, 130), 0.7, power=1.2)
    # disc
    for y in range(cy - 66, cy + 67):
        for x in range(cx - 66, cx + 67):
            d = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
            if d <= 66:
                t = d / 66.0
                col = lerp_c((255, 244, 214), (255, 196, 110), t)
                set_px(x, y, col[0], col[1], col[2])


def draw_light_rays():
    # diagonal god-rays streaming down-left from the sun
    for (x0, wdt, a) in [(700, 46, 0.10), (620, 70, 0.07), (800, 34, 0.08),
                         (540, 90, 0.05)]:
        pts = [(x0, 300), (x0 + wdt, 300), (x0 + wdt - 260, 1024),
               (x0 - 260, 1024)]
        fill_poly(pts, (255, 214, 150), a=a)


def draw_far_clouds():
    # thin high clouds, lavender and rose
    for (cx, cy, rx, ry, c, a) in [
        (210, 210, 180, 26, (196, 150, 190), 0.35),
        (430, 150, 220, 22, (170, 130, 185), 0.30),
        (880, 130, 200, 24, (200, 155, 185), 0.30),
        (120, 420, 160, 22, (214, 150, 160), 0.28),
        (950, 400, 170, 24, (210, 148, 158), 0.26),
        (520, 620, 240, 26, (226, 160, 150), 0.25),
    ]:
        soft_ellipse(cx, cy, rx, ry, c, a, power=1.0)


# ---------------------------------------------------------------- islands
def rock_island(top, bot_x, bot_y, jag, c_top, c_bot, grass=True):
    """top: list of (x,y) along the top edge (left->right).
    Rock body tapers down to a point near (bot_x, bot_y) with jagged sides."""
    left = top[0]
    right = top[-1]
    pts = list(top)
    # right side down to the point
    n = 6
    for i in range(1, n + 1):
        t = i / n
        x = right[0] + (bot_x - right[0]) * t + (rnd() - 0.5) * jag * (1 - t)
        y = right[1] + (bot_y - right[1]) * t
        pts.append((x, y))
    # left side back up
    for i in range(n - 1, 0, -1):
        t = i / n
        x = left[0] + (bot_x - left[0]) * t + (rnd() - 0.5) * jag * (1 - t)
        y = left[1] + (bot_y - left[1]) * t
        pts.append((x, y))
    fill_poly(pts, c_top, a=1.0,
              grad=(c_top, c_bot, min(p[1] for p in top), bot_y))
    if grass:
        # grassy rim along the top edge
        for i in range(len(top) - 1):
            x0, y0 = top[i]
            x1, y1 = top[i + 1]
            fill_poly([(x0, y0), (x1, y1), (x1, y1 + 12), (x0, y0 + 12)],
                      (122, 148, 72), a=1.0)
        # warm rim light on the top edge
        line(int(top[0][0]), int(top[0][1]), int(top[-1][0]),
             int(top[-1][1]), (255, 214, 140), a=0.55)
    return pts


def house(x, y, w, h, body, roof, lit=True):
    """A tiny house; (x,y) is the bottom-left of the body."""
    fill_rect(x, y - h, x + w, y, body)
    fill_poly([(x - 3, y - h), (x + w + 3, y - h), (x + w / 2, y - h - 12)],
              roof)
    if lit:
        wx = x + w // 2 - 4
        fill_rect(wx, y - h + 6, wx + 8, y - h + 14, (255, 214, 120))
        fill_rect(x + 3, y - 8, x + 9, y, (60, 40, 52))
    # chimney
    fill_rect(x + w - 8, y - h - 10, x + w - 4, y - h, (70, 52, 62))


def smoke(x, y):
    for i in range(4):
        soft_ellipse(x + i * 6 - 4, y - i * 12, 10 + i * 3, 8 + i * 2,
                     (235, 225, 225), 0.28 - i * 0.05, power=1.0)


def waterfall(x, y0, y1, wdt):
    # falling water: two faint slanted strands, brightness breathing along
    # the fall so it never reads as a solid pole
    import math
    for strand, off in ((0.55, -3), (0.4, 3)):
        for y in range(int(y0), int(y1)):
            xs = int(x) + off + int((y - y0) * 0.05)
            breathe = 0.75 + 0.25 * math.sin(y * 0.11)
            for dx in range(-wdt // 2, wdt // 2 + 1):
                t = 1.0 - abs(dx) / (wdt / 2 + 1)
                blend_px(xs + dx, y, 208, 226, 242, strand * t * breathe)
    soft_ellipse(x + int((y1 - y0) * 0.05), y1 + 14, wdt * 3.2, 22,
                 (235, 240, 248), 0.30, power=1.0)


def draw_islands():
    # far tiny island, hazy
    pts = rock_island([(168, 322), (206, 312), (248, 314), (288, 324)],
                      228, 402, 8, (96, 88, 128), (58, 52, 92), grass=False)
    fill_poly(pts, (150, 140, 180), a=0.30)
    house(216, 316, 22, 16, (120, 96, 110), (86, 60, 76), lit=True)

    # main island, left
    top = [(138, 598), (200, 588), (268, 584), (340, 588), (412, 596)]
    rock_island(top, 282, 806, 26, (62, 56, 84), (26, 22, 46))
    house(158, 592, 34, 24, (196, 150, 118), (146, 84, 74))
    house(206, 590, 28, 20, (168, 128, 140), (120, 70, 84))
    house(246, 588, 36, 26, (206, 168, 120), (150, 92, 70))
    house(296, 590, 30, 22, (178, 140, 132), (128, 76, 80))
    house(340, 594, 34, 24, (188, 158, 124), (140, 88, 72))
    smoke(330, 560)
    smoke(186, 562)
    waterfall(196, 660, 872, 11)
    waterfall(330, 706, 890, 8)
    soft_ellipse(282, 884, 130, 34, (240, 235, 240), 0.28, power=1.0)

    # right island, higher
    top2 = [(648, 498), (712, 490), (782, 490), (852, 500)]
    rock_island(top2, 748, 648, 20, (70, 62, 92), (30, 26, 50))
    house(672, 494, 30, 22, (200, 156, 122), (148, 86, 76))
    house(716, 492, 34, 25, (176, 138, 138), (124, 74, 82))
    house(766, 494, 28, 20, (204, 164, 122), (146, 90, 72))
    smoke(742, 462)
    waterfall(742, 560, 760, 7)
    soft_ellipse(748, 772, 90, 26, (240, 235, 240), 0.26, power=1.0)


# ------------------------------------------------------------------- ship
def draw_ship(scale=1.0, ox=0, oy=0, alpha=1.0):
    """The hero ship, sailing up to the right. Scaled/translated copy
    allowed for the distant ship (alpha<1)."""
    S = scale
    X = lambda v: ox + v * S
    Y = lambda v: oy + v * S

    # hull
    hull = [(X(520), Y(448)), (X(560), Y(474)), (X(740), Y(482)),
            (X(806), Y(452)), (X(788), Y(436)), (X(540), Y(432))]
    fill_poly(hull, (52, 38, 48), a=alpha,
              grad=((74, 54, 60), (34, 24, 34), Y(432), Y(482)))
    line(int(X(524)), int(Y(448)), int(X(800)), int(Y(450)),
         (255, 200, 120), a=0.6 * alpha)
    # stern castle + bow
    fill_poly([(X(540), Y(432)), (X(592), Y(432)), (X(592), Y(410)),
               (X(540), Y(410))], (62, 46, 56), a=alpha)
    fill_poly([(X(788), Y(436)), (X(812), Y(452)), (X(788), Y(452))],
              (62, 46, 56), a=alpha)

    # masts
    line(int(X(618)), int(Y(438)), int(X(618)), int(Y(272)),
         (58, 42, 50), a=alpha)
    line(int(X(726)), int(Y(440)), int(X(726)), int(Y(306)),
         (58, 42, 50), a=alpha)

    # mainsail: big belly, sunlit
    sail = bezier((X(624), Y(286)), (X(700), Y(300)), (X(720), Y(436)))
    sail += [(X(624), Y(436))]
    fill_poly(sail, (250, 236, 204), a=alpha,
              grad=((255, 242, 214), (232, 184, 132), Y(286), Y(436)))
    # sail seams
    for t in (0.33, 0.66):
        y = Y(286 + (436 - 286) * t)
        line(int(X(626)), int(y), int(X(718)), int(y + 8),
             (210, 170, 130), a=0.35 * alpha)
    # jib sail to the bow
    jib = [(X(732), Y(318)), (X(806), Y(438)), (X(732), Y(436))]
    fill_poly(jib, (252, 240, 214), a=alpha,
              grad=((255, 244, 220), (236, 196, 146), Y(318), Y(438)))
    # topsail
    fill_poly([(X(622), Y(276)), (X(664), Y(282)), (X(660), Y(320)),
               (X(624), Y(318))], (248, 232, 198), a=alpha)

    # flag
    fill_poly([(X(618), Y(272)), (X(652), Y(280)), (X(618), Y(290))],
              (214, 74, 66), a=alpha)
    # rigging
    line(int(X(618)), int(Y(276)), int(X(806)), int(Y(446)),
         (40, 30, 40), a=0.55 * alpha)
    line(int(X(726)), int(Y(310)), int(X(540)), int(Y(436)),
         (40, 30, 40), a=0.55 * alpha)
    line(int(X(618)), int(Y(276)), int(X(540)), int(Y(436)),
         (40, 30, 40), a=0.45 * alpha)
    # glowing windows on the hull
    for wx in (600, 640, 680, 720):
        fill_rect(int(X(wx)), int(Y(452)), int(X(wx + 10)),
                  int(Y(462)), (255, 210, 110), a=0.9 * alpha)


def draw_distant_ship():
    # small hazy ship far to the left, for scale
    draw_ship(scale=0.30, ox=-140, oy=60, alpha=0.75)
    soft_ellipse(60, 430, 130, 26, (240, 220, 220), 0.25, power=1.0)


def draw_birds():
    for (bx, by, s) in [(300, 240, 7), (360, 210, 6), (480, 180, 8),
                        (880, 180, 6), (930, 230, 7), (180, 300, 5),
                        (560, 150, 6), (700, 130, 5)]:
        line(bx - s, by, bx, by - s // 2, (52, 40, 64), a=0.85)
        line(bx, by - s // 2, bx + s, by, (52, 40, 64), a=0.85)


# -------------------------------------------------------------- cloud sea
def draw_cloud_sea():
    # the sea of clouds the village floats above
    for y in range(700, H):
        t = (y - 700) / (H - 700)
        col = lerp_c((250, 198, 158), (238, 176, 168), t)
        base = y * W * 3
        img[base:base + W * 3] = bytes(col) * W
    puffs = [
        (120, 760, 190, 60, (255, 226, 190), 0.75),
        (330, 800, 230, 70, (255, 214, 176), 0.7),
        (580, 750, 210, 62, (255, 222, 186), 0.72),
        (820, 800, 240, 72, (255, 210, 172), 0.7),
        (950, 740, 180, 56, (250, 206, 168), 0.65),
        (60, 850, 200, 66, (246, 200, 168), 0.6),
        (450, 880, 260, 74, (250, 208, 172), 0.65),
        (720, 900, 230, 70, (244, 198, 166), 0.6),
        (220, 940, 240, 70, (238, 190, 164), 0.55),
        (880, 950, 220, 66, (240, 192, 164), 0.55),
        (520, 960, 280, 60, (236, 188, 162), 0.5),
        (400, 730, 200, 48, (255, 220, 182), 0.55),
        (60, 730, 150, 42, (252, 214, 176), 0.5),
        (930, 830, 150, 44, (252, 212, 174), 0.5),
        (300, 700, 170, 40, (250, 210, 172), 0.45),
    ]
    for (cx, cy, rx, ry, c, a) in puffs:
        soft_ellipse(cx, cy, rx, ry, c, a, power=0.9)
    # cool shadow folds between puffs
    for (cx, cy, rx, ry) in [(260, 830, 180, 34), (640, 840, 200, 36),
                             (880, 880, 160, 30), (140, 920, 170, 32)]:
        soft_ellipse(cx, cy, rx, ry, (178, 128, 150), 0.35, power=1.0)


def draw_vignette():
    cx, cy = W / 2, H / 2
    for y in range(0, H, 2):
        for x in range(0, W, 2):
            d = (((x - cx) / 720.0) ** 2 + ((y - cy) / 720.0) ** 2) ** 0.5
            if d > 0.72:
                a = min(0.16, (d - 0.72) * 0.5)
                blend_px(x, y, 20, 12, 40, a)
                blend_px(x + 1, y, 20, 12, 40, a)
                blend_px(x, y + 1, 20, 12, 40, a)
                blend_px(x + 1, y + 1, 20, 12, 40, a)


# -------------------------------------------------------------------- text
FONT = {
    'A': ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    'B': ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    'C': ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    'D': ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    'E': ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    'F': ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    'G': ["01110", "10001", "10000", "10111", "10001", "10001", "01111"],
    'H': ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    'I': ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    'J': ["00111", "00010", "00010", "00010", "00010", "10010", "01100"],
    'K': ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    'L': ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    'M': ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    'N': ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    'O': ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    'P': ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    'Q': ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    'R': ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    'S': ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    'T': ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    'U': ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    'V': ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    'W': ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    'X': ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    'Y': ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    'Z': ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    '.': ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ' ': ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
}


def draw_text(text, cx, y, scale, c, a=1.0):
    gw = 5 * scale + scale  # glyph advance
    total = len(text) * gw - scale
    x = cx - total // 2
    for ch in text:
        glyph = FONT.get(ch, FONT[' '])
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == '1':
                    fill_rect(x + col * scale, y + row * scale,
                              x + (col + 1) * scale, y + (row + 1) * scale,
                              c, a)
        x += gw


def draw_caption():
    # soft dark band so the caption reads over the cloud sea
    fill_rect(0, 902, W, 1024, (28, 18, 48), a=0.38)
    draw_text("THE VILLAGE THAT SAILED THE SKY", W // 2, 922, 5,
              (255, 240, 208))
    draw_text("IT NEVER CAME DOWN.", W // 2, 972, 3, (255, 214, 150))


# --------------------------------------------------------------------- png
def png_bytes():
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)  # filter: None
        raw += img[y * stride:(y + 1) * stride]
    comp = zlib.compress(bytes(raw), 6)

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", comp) + chunk(b"IEND", b""))


def main():
    draw_sky()
    draw_sun()
    draw_light_rays()
    draw_far_clouds()
    draw_islands()
    draw_distant_ship()
    draw_ship(ox=-120, oy=-80)  # hero ship flies free, clear of the islands
    draw_birds()
    draw_cloud_sea()
    draw_vignette()
    draw_caption()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "entry.png"), "wb") as f:
        f.write(png_bytes())


if __name__ == "__main__":
    main()
