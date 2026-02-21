#!/usr/bin/env python3
"""
Generate a 512x512 EVT2.1 checkerboard pattern with 128x128 squares.

Output: text file with one 64-bit EVT2.1 word per line (16 hex chars, lowercase).
Time: increments by --dt microseconds from one output line to the next.

EVT2.1 fields (per Prophesee docs):
- 64-bit word, top 4 bits = type
- EVT_TIME_HIGH: type=0x8, bits 59..32 = timestamp_high (28 bits), low 32 bits = 0
- EVT_POS: type=0x1, EVT_NEG: type=0x0
  bits 59..54 = timestamp_low (6 bits)
  bits 53..43 = x (11 bits, aligned to 32)
  bits 42..32 = y (11 bits)
  bits 31..0  = valid (32-bit mask of x offsets)
"""

from __future__ import annotations

import argparse
from pathlib import Path


TYPE_NEG = 0x0
TYPE_POS = 0x1
TYPE_TIME_HIGH = 0x8


def pack_time_high(timestamp_us: int) -> int:
    # timestamp_high = bits 6..33 of full timestamp (28 bits)
    ts_high = (timestamp_us >> 6) & 0x0FFFFFFF
    return (TYPE_TIME_HIGH << 60) | (ts_high << 32)


def pack_cd_event(
    is_pos: bool, timestamp_us: int, x_aligned: int, y: int, valid_mask: int
) -> int:
    typ = TYPE_POS if is_pos else TYPE_NEG
    ts_low = timestamp_us & 0x3F  # lower 6 bits
    if x_aligned % 32 != 0:
        raise ValueError(f"x_aligned must be multiple of 32, got {x_aligned}")
    if not (0 <= x_aligned < (1 << 11)):
        raise ValueError(f"x_aligned out of 11-bit range: {x_aligned}")
    if not (0 <= y < (1 << 11)):
        raise ValueError(f"y out of 11-bit range: {y}")
    valid_mask &= 0xFFFFFFFF

    return (
        (typ << 60)
        | (ts_low << 54)
        | ((x_aligned & 0x7FF) << 43)
        | ((y & 0x7FF) << 32)
        | valid_mask
    )


def generate_evt21_checkerboard(
    width: int,
    height: int,
    square: int,
    dt_us: int,
    yoff: int,
    xoff: int,
):
    if width % 32 != 0:
        raise ValueError("width must be a multiple of 32 (EVT2.1 x-block size).")
    if width % square != 0 or height % square != 0:
        raise ValueError("width and height must be multiples of square size.")
    if dt_us <= 0:
        raise ValueError("--dt must be a positive integer (microseconds).")

    blocks_per_row = width // 32

    t = 0
    prev_cd_ts_low = None  # previous CD event's low 6 bits

    stride = 4  # interlace factor: 0,4,8,... then 1,5,9,... etc

    # Interlaced row order: phase 0 rows, then phase 1 rows, ...
    for phase in range(stride):
        for y in range(yoff + phase, yoff + height, stride):
            sq_row = y // square

            for b in range(blocks_per_row):
                x0 = b * 32 + xoff
                sq_col = x0 // square

                is_pos = (sq_row + sq_col) % 2 == 0
                valid = 0xFFFFFFFF

                cd_ts_low = t & 0x3F

                # TIME_HIGH at start or when low bits wrap
                if prev_cd_ts_low is None or cd_ts_low < prev_cd_ts_low:
                    yield pack_time_high(t)
                    t += dt_us
                    cd_ts_low = t & 0x3F

                yield pack_cd_event(
                    is_pos=is_pos, timestamp_us=t, x_aligned=x0, y=y, valid_mask=valid
                )
                prev_cd_ts_low = cd_ts_low
                t += dt_us


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--out",
        type=Path,
        default=Path("checkerboard_evt21.hex"),
        help="Output text file (one 64-bit hex word per line).",
    )
    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--yoff", type=int, default=0)
    ap.add_argument("--xoff", type=int, default=0)
    ap.add_argument(
        "--square", type=int, default=128, help="Square size in pixels (default: 128)."
    )
    ap.add_argument(
        "--dt",
        type=int,
        default=1,
        help="Time increment (microseconds) between output lines.",
    )
    args = ap.parse_args()

    with args.out.open("w", encoding="utf-8") as f:
        for w in generate_evt21_checkerboard(
            args.width, args.height, args.square, args.dt, args.yoff, args.xoff
        ):
            f.write(f"{w:016x}\n")

    print(f"Wrote EVT2.1 hex stream to: {args.out}")


if __name__ == "__main__":
    main()
