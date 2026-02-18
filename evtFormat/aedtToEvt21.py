import dv_processing as dv
import argparse
import os

# EVT2.1 word types (top nibble bits [63..60])
TYPE_NEG = 0x0
TYPE_POS = 0x1
TYPE_TIME_HIGH = 0x8


def evt_time_high_word(time_high: int) -> int:
    # [63..60]=type, [59..32]=time_high (28 bits), [31..0]=0
    return (TYPE_TIME_HIGH << 60) | ((time_high & ((1 << 28) - 1)) << 32)


def evt_polarity_word(p: int, time_low: int, x: int, y: int) -> int:
    """
    EVT_POS/EVT_NEG format:
      [63..60] type
      [59..54] time_low (6 bits)
      [53..43] x_base (11 bits, multiple of 32)
      [42..32] y      (11 bits)
      [31..0]  valid  (bitmask of 32 pixels: x = x_base + bit_index)
    """
    typ = TYPE_POS if p else TYPE_NEG
    x_base = (x // 32) * 32
    bit = x % 32
    valid = 1 << bit

    return (
        ((typ & 0xF) << 60)
        | ((time_low & 0x3F) << 54)
        | ((x_base & 0x7FF) << 43)
        | ((y & 0x7FF) << 32)
        | (valid & 0xFFFFFFFF)
    )


def aedat4_to_evt21_hex(aedat4_path: str, evt21_hex_path: str, rescale: bool):
    """
    Convert AEDAT4 events to EVT2.1 as ASCII hex:
      - One 64-bit EVT word per line
      - 16 lowercase hex digits per line (no 0x), newline-separated
    """
    reader = dv.io.MonoCameraRecording(aedat4_path)
    last_time_high = None

    with open(evt21_hex_path, "w", encoding="ascii") as f:
        while reader.isRunning():
            batch = reader.getNextEventBatch()
            if not batch:
                continue

            for e in batch:
                # dv-processing bindings in your setup expose getters as methods
                t = int(e.timestamp())
                if rescale:
                    x = int(e.x()) * 4 + 384
                    y = int(e.y()) * 4 + 104
                else:
                    x = int(e.x())
                    y = int(e.y())

                p = 1 if bool(e.polarity()) else 0

                time_high = t >> 6
                time_low = t & 0x3F

                # Must emit TIME_HIGH before polarity words that use it
                if last_time_high is None or time_high != last_time_high:
                    w = evt_time_high_word(time_high)
                    f.write(f"{w:016x}\n")
                    last_time_high = time_high

                w = evt_polarity_word(p, time_low, x, y)
                f.write(f"{w:016x}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Decode AEDT 4 file into Prophesee EVT2.1."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Path to input AEDT 4 file.",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to output EVT21. "
        "If omitted, '.evt' is added as extenstion to the input filename.",
    )

    parser.add_argument(
        "-r",
        "--rescale",
        # default=True,
        action=argparse.BooleanOptionalAction,
        default=False,
        type=bool,
        help="Rescale to meet the output format of IMX636.",
    )
    args = parser.parse_args()

    input_path = args.input

    if args.output:
        output_path = args.output
    else:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}{'.evt'}"

    print("Running!")

    aedat4_to_evt21_hex(input_path, output_path, args.rescale)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
