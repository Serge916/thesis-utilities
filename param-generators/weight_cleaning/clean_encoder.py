#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


def parse_int8_values(path: Path) -> list[int]:
    values: list[int] = []
    text = path.read_text(encoding="utf-8", errors="replace")

    for line_no, line in enumerate(text.splitlines(), start=1):
        # Remove comments
        line = line.split("#", 1)[0]
        line = line.split("//", 1)[0]

        # Fix broken negatives: "- 128" -> "-128"
        line = re.sub(r"-\s+(\d+)", r"-\1", line)

        for tok in re.findall(r"[+-]?\d+", line):
            v = int(tok)

            if v < -128 or v > 127:
                raise ValueError(
                    f"Invalid int8 value at {path}:{line_no}: {v}. "
                    "Expected range [-128, 127]."
                )

            values.append(v)

    if not values:
        raise ValueError(f"No int8 values found in {path}")

    return values


def pack_entry_to_hex(entry: list[int]) -> str:
    word = 0
    for i, v in enumerate(entry):
        word |= (v & 0xFF) << (8 * i)
    return f"{word:016x}"


def rearrange_encoder_for_load_int8(
    raw_values: list[int],
    *,
    encoder_channels: int = 256,
    outputs_per_raw_word: int = 8,
    encoder_weights_per_word: int = 8,
) -> list[list[int]]:
    """
    Convert raw encoder weights into the exact memory layout produced by
    the VHDL to_encoder_mem() function.

    Original raw logical layout:
        weight[out_chan][in_chan]

    Destination encoder memory layout:
        memory word contains 8 consecutive output channels
        for the same input channel:

            word 0: in=0, out=0..7
            word 1: in=0, out=8..15
            word 2: in=0, out=16..23
            ...
            word 32: in=1, out=0..7
            ...

    VHDL equivalent:
        raw_linear_idx = out_chan * ENCODER1_CHANNELS + in_chan
        raw_word_idx   = raw_linear_idx / 2048
        raw_weight_idx = raw_linear_idx mod 2048

    With 256 channels and 8 outputs per raw word:
        raw_word_idx   = out_chan // 8
        raw_weight_idx = (out_chan % 8) * 256 + in_chan
    """

    expected_values = encoder_channels * encoder_channels

    if len(raw_values) != expected_values:
        raise ValueError(
            f"Input has {len(raw_values)} int8 values, but expected "
            f"{expected_values} = {encoder_channels} × {encoder_channels}."
        )

    raw_weights_per_word = encoder_channels * outputs_per_raw_word

    if len(raw_values) % raw_weights_per_word != 0:
        raise ValueError(
            f"Input length {len(raw_values)} is not divisible by "
            f"raw_weights_per_word={raw_weights_per_word}."
        )

    raw_word_count = len(raw_values) // raw_weights_per_word
    expected_raw_word_count = encoder_channels // outputs_per_raw_word

    if raw_word_count != expected_raw_word_count:
        raise ValueError(
            f"Expected {expected_raw_word_count} raw words, got {raw_word_count}."
        )

    reordered_values: list[int] = []

    for in_chan in range(encoder_channels):
        for out_base in range(0, encoder_channels, encoder_weights_per_word):
            entry: list[int] = []

            for k in range(encoder_weights_per_word):
                out_chan = out_base + k

                raw_word_idx = out_chan // outputs_per_raw_word
                raw_weight_idx = (
                    (out_chan % outputs_per_raw_word) * encoder_channels
                    + in_chan
                )

                raw_index = raw_word_idx * raw_weights_per_word + raw_weight_idx
                entry.append(raw_values[raw_index])

            reordered_values.extend(entry)

    entries: list[list[int]] = []

    for i in range(0, len(reordered_values), encoder_weights_per_word):
        entry = reordered_values[i:i + encoder_weights_per_word]

        if len(entry) != encoder_weights_per_word:
            raise ValueError("Internal error: incomplete output entry")

        entries.append(entry)

    return entries


def write_entries(entries: list[list[int]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(" ".join(str(v) for v in entry) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Clean and rearrange encoder int8 weights into the layout expected "
            "by load-int8 encoder1."
        )
    )

    parser.add_argument(
        "-f", "--input_file",
        required=True,
        type=Path,
        help="Input raw encoder int8 file."
    )

    parser.add_argument(
        "-o", "--output",
        required=True,
        type=Path,
        help="Output file ready for load-int8 encoder1."
    )

    parser.add_argument(
        "--encoder_channels",
        type=int,
        default=256,
        help="ENCODER1_CHANNELS. Default: 256."
    )

    parser.add_argument(
        "--outputs_per_raw_word",
        type=int,
        default=8,
        help="Number of output channels grouped per raw word. Default: 8."
    )

    parser.add_argument(
        "--encoder_weights_per_word",
        type=int,
        default=8,
        help="ENCODER1_WEIGHTS_PER_WORD. Default: 8."
    )

    parser.add_argument(
        "--preview",
        type=int,
        default=32,
        help="Number of output entries to preview. Default: 32."
    )

    args = parser.parse_args()

    raw_values = parse_int8_values(args.input_file)

    entries = rearrange_encoder_for_load_int8(
        raw_values,
        encoder_channels=args.encoder_channels,
        outputs_per_raw_word=args.outputs_per_raw_word,
        encoder_weights_per_word=args.encoder_weights_per_word,
    )

    write_entries(entries, args.output)

    print("Done.")
    print(f"Input file:              {args.input_file}")
    print(f"Output file:             {args.output}")
    print(f"Raw int8 values:         {len(raw_values)}")
    print(f"Encoder channels:        {args.encoder_channels}")
    print(f"Outputs per raw word:    {args.outputs_per_raw_word}")
    print(f"Output memory entries:   {len(entries)}")
    print()

    print("First entries:")
    for i in range(min(args.preview, len(entries))):
        entry = entries[i]
        print(
            f"[{i:4d}] "
            f"{' '.join(f'{v:4d}' for v in entry)}    "
            f"hex={pack_entry_to_hex(entry)}"
        )

    print()
    print("Load with one of:")
    print(f"  ./network_ctrl load-int8 encoder1 {args.output} qk")
    print(f"  ./network_ctrl load-int8 encoder1 {args.output} v")
    print(f"  ./network_ctrl load-int8 encoder1 {args.output} final")


if __name__ == "__main__":
    main()
