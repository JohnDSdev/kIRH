# SPDX-License-Identifier: GPL-3.0-or-later
"""Core raster algorithm for Inner Rim Highlight.

This module deliberately has no Krita/PyQt dependencies so the math can be
unit-tested outside Krita.
"""

from array import array

INF = 65535
CARDINAL = 3
DIAGONAL = 4


def _forward_distance(alpha, width, height, threshold, progress=None):
    """Approximate Euclidean distance to transparency using a 3-4 chamfer mask.

    Distances are stored in units where 3 ~= 1 pixel. Transparent pixels have
    distance 0. Pixels outside the processed rectangle are also treated as
    transparent, which is exactly what we want for a layer's alpha bounds.
    """
    n = width * height
    dist = array("H", [INF]) * n

    for y in range(height):
        row = y * width
        prev = row - width
        for x in range(width):
            i = row + x
            if alpha[i] < threshold:
                dist[i] = 0
                continue

            best = INF

            # Left and top. At the rectangle edge, the virtual neighbor is
            # transparent and therefore has distance zero.
            if x == 0:
                best = CARDINAL
            else:
                v = dist[i - 1] + CARDINAL
                if v < best:
                    best = v

            if y == 0:
                if CARDINAL < best:
                    best = CARDINAL
            else:
                v = dist[prev + x] + CARDINAL
                if v < best:
                    best = v

                if x > 0:
                    v = dist[prev + x - 1] + DIAGONAL
                    if v < best:
                        best = v
                if x + 1 < width:
                    v = dist[prev + x + 1] + DIAGONAL
                    if v < best:
                        best = v

            dist[i] = best if best < INF else INF

        if progress is not None and (y & 31) == 0:
            progress(0.45 * ((y + 1) / max(1, height)))

    return dist


def _backward_distance(dist, alpha, width, height, threshold, progress=None):
    for y in range(height - 1, -1, -1):
        row = y * width
        nxt = row + width
        for x in range(width - 1, -1, -1):
            i = row + x
            if alpha[i] < threshold:
                continue

            best = dist[i]

            if x == width - 1:
                if CARDINAL < best:
                    best = CARDINAL
            else:
                v = dist[i + 1] + CARDINAL
                if v < best:
                    best = v

            if y == height - 1:
                if CARDINAL < best:
                    best = CARDINAL
            else:
                v = dist[nxt + x] + CARDINAL
                if v < best:
                    best = v

                if x > 0:
                    v = dist[nxt + x - 1] + DIAGONAL
                    if v < best:
                        best = v
                if x + 1 < width:
                    v = dist[nxt + x + 1] + DIAGONAL
                    if v < best:
                        best = v

            dist[i] = best

        if progress is not None and ((height - 1 - y) & 31) == 0:
            progress(0.45 + 0.35 * ((height - y) / max(1, height)))


def make_inner_highlight_bgra(
    alpha,
    width,
    height,
    rim_width=28,
    opacity=0.80,
    softness=0.70,
    threshold=8,
    selection=None,
    progress=None,
):
    """Return BGRA/U8 pixels for a white, soft inner rim highlight.

    Args:
        alpha: bytes-like object with one source-alpha byte per pixel.
        width, height: dimensions of alpha.
        rim_width: approximate highlight width in pixels.
        opacity: maximum output opacity, 0..1.
        softness: 0..1. Higher values make the fade broader/softer.
        threshold: alpha below this is considered outside the shape.
        selection: optional one-byte-per-pixel selection mask. Output is
            multiplied by it.
        progress: optional callback accepting a fraction 0..1.
    """
    if width <= 0 or height <= 0:
        return bytearray()
    if len(alpha) != width * height:
        raise ValueError("alpha length does not match width*height")
    if selection is not None and len(selection) != width * height:
        raise ValueError("selection length does not match width*height")

    rim_width = max(1.0, float(rim_width))
    opacity = min(1.0, max(0.0, float(opacity)))
    softness = min(1.0, max(0.0, float(softness)))
    threshold = int(min(255, max(1, threshold)))

    dist = _forward_distance(alpha, width, height, threshold, progress)
    _backward_distance(dist, alpha, width, height, threshold, progress)

    # High softness = a broad gentle fade. Low softness = a tight rim.
    gamma = 2.6 - (2.1 * softness)  # 2.6 .. 0.5
    limit = rim_width * CARDINAL
    out = bytearray(width * height * 4)

    for i, d in enumerate(dist):
        src_a = alpha[i]
        if src_a < threshold or d >= limit:
            continue

        px_distance = d / CARDINAL
        t = 1.0 - (px_distance / rim_width)
        if t <= 0.0:
            continue

        strength = t ** gamma
        a = strength * opacity * (src_a / 255.0)
        if selection is not None:
            a *= selection[i] / 255.0

        out_a = int(a * 255.0 + 0.5)
        if out_a <= 0:
            continue

        j = i * 4
        # Krita's U8 RGBA pixelData order is BGRA.
        out[j] = 255
        out[j + 1] = 255
        out[j + 2] = 255
        out[j + 3] = min(255, out_a)

        if progress is not None and (i & 0x3FFFF) == 0:
            progress(0.80 + 0.20 * ((i + 1) / max(1, width * height)))

    if progress is not None:
        progress(1.0)
    return out
