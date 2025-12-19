#!/usr/bin/env python3
"""
Encode an event (Prophesee EVT 2.1 format) into a 64-bit integer.

Bit layout (MSB..LSB):

63..60 : type       (4 bits)  -> EVT_NEG = 0b0000
59..54 : timestamp  (6 bits)  -> least significant bits of event time base
53..43 : x          (11 bits) -> pixel X coordinate aligned on 32
42..32 : y          (11 bits) -> pixel Y coordinate
31..0  : valid      (32 bits) -> bitmap of valid events (x+i, y) for i=0..31
"""

import argparse


EVT_NEG_TYPE = 0b0000  # fixed for EVT_NEG


def encode_evt(
    evtType: int, timestamp_lsb: int, x: int, y: int, valid_mask: int
) -> int:
    """
    Encode the given fields into a 64-bit integer.
    """
    # Basic range checks (will raise ValueError if out of range)
    if not (0 <= timestamp_lsb < (1 << 6)):
        raise ValueError("timestamp_lsb must be in [0, 64).")
    if not (0 <= x < (1 << 11)):
        raise ValueError("x must be in [0, 2048).")
    if not (0 <= y < (1 << 11)):
        raise ValueError("y must be in [0, 2048).")
    if not (0 <= valid_mask < (1 << 32)):
        raise ValueError("valid_mask must be a 32-bit value.")
    # if not (0 <= evtType < (1 << 4)):
    #     raise ValueError("evtType must be a 4-bit value.")

    value = 0
    value |= (evtType & 0xF) << 60  # bits 63..60
    value |= (timestamp_lsb & 0x3F) << 54  # bits 59..54
    value |= (x & 0x7FF) << 43  # bits 53..43
    value |= (y & 0x7FF) << 32  # bits 42..32
    value |= valid_mask & 0xFFFFFFFF  # bits 31..0

    return value


def main():
    parser = argparse.ArgumentParser(
        description="Encode an EVT_NEG event into a 64-bit integer."
    )
    parser.add_argument(
        "t",
        type=int,
        help="Event type (4 bits).",
    )
    parser.add_argument(
        "timestamp_lsb",
        type=int,
        help="Least significant 6 bits of the event time base (0-63).",
    )
    parser.add_argument(
        "x",
        type=int,
        help="X coordinate aligned on 32 (0-2047).",
    )
    parser.add_argument(
        "y",
        type=int,
        help="Y coordinate (0-2047).",
    )
    parser.add_argument(
        "valid_mask",
        type=lambda s: int(s, 0),
        help="32-bit valid bitmap (int, can be in decimal or 0x... hex).",
    )

    args = parser.parse_args()

    encoded = encode_evt(args.t, args.timestamp_lsb, args.x, args.y, args.valid_mask)

    print(f"Encoded value (decimal): {encoded}")
    print(f"Encoded value (hex)    : {encoded:016X}")


if __name__ == "__main__":
    main()
