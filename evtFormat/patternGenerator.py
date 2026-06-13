#!/usr/bin/env python3
"""
Generate a 512x512 EVT2.1 checkerboard pattern with repeated/interleaved addresses.

Goal:
- Revisit the same neurons enough times to fire the output neurons.
- Avoid sending the same memory address too soon, because the filter checks
  hazards across pipeStage(0)..pipeStage(4).

Output:
- Text file with one 64-bit EVT2.1 word per line.
- 16 lowercase hex chars per line.

EVT2.1 fields:
- 64-bit word, top 4 bits = type
- EVT_TIME_HIGH: type=0x8, bits 59..32 = timestamp_high, low 32 bits = 0
- EVT_POS: type=0x1, EVT_NEG: type=0x0
  bits 59..54 = timestamp_low
  bits 53..43 = x
  bits 42..32 = y
  bits 31..0  = valid mask
"""

from __future__ import annotations

import argparse
from pathlib import Path

TYPE_NEG = 0x0
TYPE_POS = 0x1
TYPE_TIME_HIGH = 0x8


def pack_time_high(timestamp_us: int) -> int:
    ts_high = (timestamp_us >> 6) & 0x0FFFFFFF
    return (TYPE_TIME_HIGH << 60) | (ts_high << 32)


def pack_cd_event(
    is_pos: bool,
    timestamp_us: int,
    x_aligned: int,
    y: int,
    valid_mask: int,
) -> int:
    typ = TYPE_POS if is_pos else TYPE_NEG
    ts_low = timestamp_us & 0x3F

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


def choose_polarity(mode: str, sq_row: int, sq_col: int) -> bool:
    if mode == "pos":
        return True
    if mode == "neg":
        return False
    if mode == "checkerboard":
        return (sq_row + sq_col) % 2 == 0

    raise ValueError(f"Unknown polarity mode: {mode}")


def build_checkerboard_addresses(
    width: int,
    height: int,
    square: int,
    yoff: int,
    xoff: int,
    stride: int,
    polarity: str,
    valid_mask: int,
):
    """
    Build one full checkerboard pass as a list of event descriptors.

    Each descriptor is:
        (is_pos, x_aligned, y, valid_mask)
    """
    if width % 32 != 0:
        raise ValueError("width must be a multiple of 32.")
    if width % square != 0 or height % square != 0:
        raise ValueError("width and height must be multiples of square size.")
    if stride <= 0:
        raise ValueError("--row-stride must be positive.")

    blocks_per_row = width // 32
    events = []

    for phase in range(stride):
        for y in range(yoff + phase, yoff + height, stride):
            sq_row = y // square

            for b in range(blocks_per_row):
                x0 = b * 32 + xoff
                sq_col = x0 // square

                is_pos = choose_polarity(polarity, sq_row, sq_col)
                events.append((is_pos, x0, y, valid_mask))

    return events


def interleaved_repeated_order(
    events, repeats_per_address: int, interleave_addresses: int
):
    """
    Reorder events so that each group of N addresses is repeated like:

        A B C D E F A B C D E F A B C D E F ...

    instead of:

        A A A A A B B B B B ...

    This helps avoid the filter pipeline hazard.

    Note:
    The RTL checks pipeStage(0)..pipeStage(4), so interleave_addresses=6
    is safer than 5.
    """
    if repeats_per_address <= 0:
        raise ValueError("--repeats-per-address must be positive.")
    if interleave_addresses <= 0:
        raise ValueError("--interleave-addresses must be positive.")

    for group_start in range(0, len(events), interleave_addresses):
        group = events[group_start : group_start + interleave_addresses]

        for _ in range(repeats_per_address):
            for ev in group:
                yield ev


def generate_evt21_checkerboard(
    width: int,
    height: int,
    square: int,
    dt_us: int,
    yoff: int,
    xoff: int,
    repeats_per_address: int,
    interleave_addresses: int,
    row_stride: int,
    polarity: str,
    valid_mask: int,
):
    if dt_us <= 0:
        raise ValueError("--dt must be a positive integer.")

    base_events = build_checkerboard_addresses(
        width=width,
        height=height,
        square=square,
        yoff=yoff,
        xoff=xoff,
        stride=row_stride,
        polarity=polarity,
        valid_mask=valid_mask,
    )

    t = 0
    prev_cd_ts_low = None

    for is_pos, x_aligned, y, mask in interleaved_repeated_order(
        base_events,
        repeats_per_address=repeats_per_address,
        interleave_addresses=interleave_addresses,
    ):
        cd_ts_low = t & 0x3F

        if prev_cd_ts_low is None or cd_ts_low < prev_cd_ts_low:
            yield pack_time_high(t)
            t += dt_us
            cd_ts_low = t & 0x3F

        yield pack_cd_event(
            is_pos=is_pos,
            timestamp_us=t,
            x_aligned=x_aligned,
            y=y,
            valid_mask=mask,
        )

        prev_cd_ts_low = cd_ts_low
        t += dt_us


def main():
    ap = argparse.ArgumentParser()

    ap.add_argument(
        "--out",
        type=Path,
        default=Path("checkerboard_evt21.hex"),
        help="Output text file.",
    )

    ap.add_argument("--width", type=int, default=512)
    ap.add_argument("--height", type=int, default=512)
    ap.add_argument("--yoff", type=int, default=0)
    ap.add_argument("--xoff", type=int, default=0)

    ap.add_argument(
        "--square",
        type=int,
        default=128,
        help="Checkerboard square size in pixels.",
    )

    ap.add_argument(
        "--dt",
        type=int,
        default=1,
        help="Time increment in microseconds between output lines.",
    )

    ap.add_argument(
        "--repeats-per-address",
        type=int,
        default=10,
        help="How many times each address is revisited.",
    )

    ap.add_argument(
        "--interleave-addresses",
        type=int,
        default=6,
        help=(
            "Number of different addresses interleaved before repeating. "
            "Use 6 for the current filter because it checks pipeStage(0)..pipeStage(4)."
        ),
    )

    ap.add_argument(
        "--row-stride",
        type=int,
        default=4,
        help="Interlaced row stride. Original script used 4.",
    )

    ap.add_argument(
        "--polarity",
        choices=["checkerboard", "pos", "neg"],
        default="checkerboard",
        help="Polarity mode.",
    )

    ap.add_argument(
        "--mask",
        type=lambda x: int(x, 0),
        default=0xFFFFFFFF,
        help="EVT2.1 valid mask, e.g. 0xffffffff or 0x00000001.",
    )

    args = ap.parse_args()

    with args.out.open("w", encoding="utf-8") as f:
        for w in generate_evt21_checkerboard(
            width=args.width,
            height=args.height,
            square=args.square,
            dt_us=args.dt,
            yoff=args.yoff,
            xoff=args.xoff,
            repeats_per_address=args.repeats_per_address,
            interleave_addresses=args.interleave_addresses,
            row_stride=args.row_stride,
            polarity=args.polarity,
            valid_mask=args.mask,
        ):
            f.write(f"{w:016x}\n")

    print(f"Wrote EVT2.1 hex stream to: {args.out}")


if __name__ == "__main__":
    main()
