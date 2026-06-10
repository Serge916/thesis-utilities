#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


def extract_int8_values(text: str):
    """
    Extract int8 values from messy text.

    Handles cases like:
        -128
        - 128
        6, 46, 61, - 128
        6 46 61 -128 4 - 128

    Ignores comments starting with # or //.
    """
    values = []

    for line_no, line in enumerate(text.splitlines(), start=1):
        # Remove comments
        line = line.split("#", 1)[0]
        line = line.split("//", 1)[0]

        # Normalize separated minus signs:
        # "- 128" -> "-128"
        line = re.sub(r"-\s+(\d+)", r"-\1", line)

        # Extract signed integers
        tokens = re.findall(r"[+-]?\d+", line)

        for tok in tokens:
            value = int(tok)

            if value < -128 or value > 127:
                raise ValueError(
                    f"Invalid int8 value at input line {line_no}: {value}. "
                    "Expected range is [-128, 127]."
                )

            values.append(value)

    return values


def write_grouped_values(values, output_path: Path, group_size: int, pad: bool):
    remainder = len(values) % group_size

    if remainder != 0:
        if pad:
            missing = group_size - remainder
            print(
                f"Warning: input has {len(values)} values, which is not a multiple "
                f"of {group_size}. Padding with {missing} zero(s)."
            )
            values = values + [0] * missing
        else:
            raise ValueError(
                f"Input has {len(values)} int8 values, which is not a multiple "
                f"of {group_size}. Remainder: {remainder}.\n"
                f"Use --pad-zero if you intentionally want to pad the last group."
            )

    with output_path.open("w", encoding="utf-8") as f:
        for i in range(0, len(values), group_size):
            group = values[i:i + group_size]
            f.write(" ".join(str(v) for v in group) + "\n")

    return len(values) // group_size


def main():
    parser = argparse.ArgumentParser(
        description="Clean raw int8 weight files for network_ctrl load-int8."
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Input raw int8 weights file."
    )

    parser.add_argument(
        "output",
        type=Path,
        help="Output cleaned int8 weights file."
    )

    parser.add_argument(
        "--group-size",
        type=int,
        default=8,
        choices=[8, 9],
        help=(
            "Number of int8 values per memory entry. "
            "Use 8 for head_lin/head_conv/encoder1, 9 for conv layers. "
            "Default: 8."
        )
    )

    parser.add_argument(
        "--pad-zero",
        action="store_true",
        help="Pad the final incomplete group with zeros instead of failing."
    )

    args = parser.parse_args()

    text = args.input.read_text(encoding="utf-8", errors="replace")

    values = extract_int8_values(text)

    if not values:
        raise ValueError("No int8 values found in input file.")

    entries = write_grouped_values(
        values=values,
        output_path=args.output,
        group_size=args.group_size,
        pad=args.pad_zero,
    )

    print("Cleaning complete.")
    print(f"Input file:  {args.input}")
    print(f"Output file: {args.output}")
    print(f"Total int8 values: {len(values)}")
    print(f"Group size: {args.group_size}")
    print(f"Memory entries written: {entries}")


if __name__ == "__main__":
    main()
