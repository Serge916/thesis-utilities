#!/usr/bin/env python3
import argparse
from pathlib import Path


def to_twos_complement(value: int, bits: int) -> int:
    min_val = -(1 << (bits - 1))
    max_val = (1 << (bits - 1)) - 1
    if not (min_val <= value <= max_val):
        raise ValueError(
            f"value {value} does not fit in signed {bits}-bit range "
            f"[{min_val}, {max_val}]"
        )
    return value & ((1 << bits) - 1)


def parse_numbers(text: str) -> list[int]:
    return [int(tok) for tok in text.split()]


def pack_words(values: list[int], elem_bytes: int, nums_per_word: int) -> list[int]:
    elem_bits = elem_bytes * 8
    mask = (1 << elem_bits) - 1

    packed = []
    for i in range(0, len(values), nums_per_word):
        chunk = values[i : i + nums_per_word]

        if len(chunk) < nums_per_word:
            chunk = chunk + [0] * (nums_per_word - len(chunk))

        word = 0
        for j, v in enumerate(chunk):
            encoded = to_twos_complement(v, elem_bits)
            word |= (encoded & mask) << (j * elem_bits)

        packed.append(word)

    return packed


def format_vhdl_entries(
    values: list[int],
    elem_bytes: int,
    nums_per_word: int,
    per_line: int = 8,
) -> str:
    word_bits = elem_bytes * 8 * nums_per_word
    hex_digits = (word_bits + 3) // 4

    packed_words = pack_words(values, elem_bytes, nums_per_word)

    entries = [
        f'    {i} => x"{word:0{hex_digits}X}"' for i, word in enumerate(packed_words)
    ]

    lines = []
    for i in range(0, len(entries), per_line):
        lines.append(",\n".join(entries[i : i + per_line]))

    return ",\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert signed integer weights into packed VHDL constant entries."
    )
    parser.add_argument("--input_file", "-i", help="Path to input text file")
    parser.add_argument(
        "--elem_size_bytes",
        "-s",
        type=int,
        help="Size of each input number in bytes, e.g. 1 for int8, 2 for int16",
    )
    parser.add_argument(
        "--nums_per_word",
        "-n",
        type=int,
        help="How many numbers to pack into each output VHDL word",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output file path. Defaults to <input>.vhdl.txt",
    )
    args = parser.parse_args()

    if args.elem_size_bytes <= 0:
        raise ValueError("elem_size_bytes must be positive")
    if args.nums_per_word <= 0:
        raise ValueError("nums_per_word must be positive")

    input_path = Path(args.input_file)
    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_suffix(input_path.suffix + ".vhdl.txt")
    )

    text = input_path.read_text(encoding="utf-8")
    values = parse_numbers(text)
    body = format_vhdl_entries(values, args.elem_size_bytes, args.nums_per_word)

    output_path.write_text(body + "\n", encoding="utf-8")

    word_bits = args.elem_size_bytes * 8 * args.nums_per_word
    print(
        f"Wrote {((len(values) + args.nums_per_word - 1) // args.nums_per_word)} "
        f"packed words ({word_bits} bits/word) to {output_path}"
    )


if __name__ == "__main__":
    main()
