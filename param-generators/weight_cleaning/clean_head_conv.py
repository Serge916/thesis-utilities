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

        tokens = re.findall(r"[+-]?\d+", line)

        for tok in tokens:
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
    """
    Pack 8 signed int8 values little-endian into one 64-bit word,
    just for preview/debug.
    """
    if len(entry) != 8:
        raise ValueError("Entry must have exactly 8 values")

    word = 0
    for i, v in enumerate(entry):
        word |= (v & 0xFF) << (8 * i)

    return f"{word:016x}"


def rearrange_head_conv(
    raw_values: list[int],
    *,
    source_channels: int = 64,
    frame_width: int = 8,
    frame_height: int = 8,
    channels_per_merged_word: int = 8,
) -> tuple[list[list[int]], int]:
    """
    Rearrange raw head_conv weights into the final memory layout expected
    by the hardware and by `load-int8 head_conv`.

    Output:
      - list of memory entries
      - inferred HEAD_CONV_CHANNELS
    """
    values_per_output_channel = frame_width * frame_height

    if len(raw_values) % values_per_output_channel != 0:
        raise ValueError(
            f"Input has {len(raw_values)} values, which is not divisible by "
            f"{frame_width} * {frame_height} = {values_per_output_channel}."
        )

    head_conv_channels = len(raw_values) // values_per_output_channel

    if head_conv_channels % channels_per_merged_word != 0:
        raise ValueError(
            f"Inferred HEAD_CONV_CHANNELS = {head_conv_channels}, which is not "
            f"divisible by channels_per_merged_word = {channels_per_merged_word}."
        )

    block_size = source_channels * frame_width  # 64 * 8 = 512

    num_blocks = head_conv_channels // channels_per_merged_word

    expected_total = num_blocks * block_size
    if len(raw_values) != expected_total:
        raise ValueError(
            f"Internal consistency error:\n"
            f"  inferred HEAD_CONV_CHANNELS = {head_conv_channels}\n"
            f"  num_blocks = {num_blocks}\n"
            f"  expected total values = {expected_total}\n"
            f"  actual total values   = {len(raw_values)}"
        )

    out_entries: list[list[int]] = []

    for row in range(frame_height):
        for ch in range(head_conv_channels):
            block_idx = ch // channels_per_merged_word
            lane_idx = ch % channels_per_merged_word

            start = (
                block_idx * block_size
                + lane_idx * (frame_height * frame_width)
                + row * frame_width
            )

            entry = raw_values[start : start + frame_width]

            if len(entry) != frame_width:
                raise ValueError(
                    f"Failed to read full entry for row={row}, ch={ch}. "
                    f"start={start}, got {len(entry)} values."
                )

            out_entries.append(entry)

    return out_entries, head_conv_channels


def write_output(entries: list[list[int]], output_path: Path) -> None:
    with output_path.open("w", encoding="utf-8") as f:
        for entry in entries:
            f.write(" ".join(str(v) for v in entry) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Clean and rearrange raw head_conv int8 weights into the final "
            "layout expected by `load-int8 head_conv`."
        )
    )

    parser.add_argument(
        "-f", "--input_file",
        required=True,
        type=Path,
        help="Input raw weights file"
    )

    parser.add_argument(
        "-o", "--output",
        required=True,
        type=Path,
        help="Output file ready for `load-int8 head_conv`"
    )

    parser.add_argument(
        "--source_channels",
        type=int,
        default=64,
        help="Number of merged source channels in the original generator. Default: 64"
    )

    parser.add_argument(
        "--frame_width",
        type=int,
        default=8,
        help="HEAD_CONV_FRAME_WIDTH. Default: 8"
    )

    parser.add_argument(
        "--frame_height",
        type=int,
        default=8,
        help="HEAD_CONV_FRAME_HEIGHT. Default: 8"
    )

    parser.add_argument(
        "--channels_per_merged_word",
        type=int,
        default=8,
        help="CHANNELS_PER_MERGED_WORD_C. Default: 8"
    )

    parser.add_argument(
        "--preview",
        type=int,
        default=16,
        help="How many output entries to preview. Default: 16"
    )

    args = parser.parse_args()

    raw_values = parse_int8_values(args.input_file)

    entries, head_conv_channels = rearrange_head_conv(
        raw_values,
        source_channels=args.source_channels,
        frame_width=args.frame_width,
        frame_height=args.frame_height,
        channels_per_merged_word=args.channels_per_merged_word,
    )

    write_output(entries, args.output)

    print("Done.")
    print(f"Input file:              {args.input_file}")
    print(f"Output file:             {args.output}")
    print(f"Raw int8 values:         {len(raw_values)}")
    print(f"Inferred channels:       {head_conv_channels}")
    print(f"Output memory entries:   {len(entries)}")
    print()
    print("First entries (decimal and packed hex):")

    preview_n = min(args.preview, len(entries))
    for i in range(preview_n):
        entry = entries[i]
        print(
            f"[{i:4d}] "
            f"{' '.join(f'{v:4d}' for v in entry)}    "
            f"hex={pack_entry_to_hex(entry)}"
        )

    print()
    print("Load with:")
    print(f"  ./network_ctrl load-int8 head_conv {args.output}")


if __name__ == "__main__":
    main()
