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


def format_hex_word(word: int, word_bits: int) -> str:
    hex_digits = (word_bits + 3) // 4
    return f'x"{word:0{hex_digits}X}"'


def format_vhdl_entries(
    values: list[int],
    elem_bytes: int,
    nums_per_word: int,
    per_line: int = 8,
) -> str:
    word_bits = elem_bytes * 8 * nums_per_word
    packed_words = pack_words(values, elem_bytes, nums_per_word)

    entries = [
        f"    {i} => {format_hex_word(word, word_bits)}"
        for i, word in enumerate(packed_words)
    ]

    lines = []
    for i in range(0, len(entries), per_line):
        lines.append(",\n".join(entries[i : i + per_line]))

    return ",\n".join(lines)


def split_by_input_channel(
    values: list[int],
    num_input_channels: int,
    values_per_input_channel: int,
) -> list[list[int]]:
    block_size = num_input_channels * values_per_input_channel

    if len(values) % block_size != 0:
        raise ValueError(
            f"Input has {len(values)} values, which is not divisible by one full "
            f"output-channel block size ({block_size} = "
            f"{num_input_channels} * {values_per_input_channel})."
        )

    per_channel = [[] for _ in range(num_input_channels)]

    # File layout assumed:
    # out0_in0, out0_in1, ..., out0_inN,
    # out1_in0, out1_in1, ..., out1_inN, ...
    for base in range(0, len(values), block_size):
        for ch in range(num_input_channels):
            start = base + ch * values_per_input_channel
            end = start + values_per_input_channel
            per_channel[ch].extend(values[start:end])

    return per_channel


def format_merged_vhdl_entries(
    channel_values: list[list[int]],
    elem_bytes: int,
    nums_per_word: int,
    per_line: int = 8,
) -> tuple[str, int]:
    if not channel_values:
        raise ValueError("channel_values must not be empty")

    word_bits = elem_bytes * 8 * nums_per_word
    packed_per_channel = [
        pack_words(vals, elem_bytes, nums_per_word) for vals in channel_values
    ]

    num_words = len(packed_per_channel[0])
    for ch, packed in enumerate(packed_per_channel):
        if len(packed) != num_words:
            raise ValueError(
                f"Channel {ch} has {len(packed)} packed words, expected {num_words}"
            )

    entries = []
    for word_idx in range(num_words):
        # Reverse channel order because VHDL concatenation places the leftmost
        # operand in the most significant bits.
        #
        # This makes channel/index 0 occupy the least significant channel-word
        # inside the merged output word.
        concat_words = " & ".join(
            format_hex_word(packed_per_channel[ch][word_idx], word_bits)
            for ch in reversed(range(len(packed_per_channel)))
        )
        entries.append(f"    {word_idx} => {concat_words}")

    lines = []
    for i in range(0, len(entries), per_line):
        lines.append(",\n".join(entries[i : i + per_line]))

    return ",\n".join(lines), num_words


def format_vhdl_constant(
    constant_name: str,
    body: str,
    num_words: int,
    word_bits: int,
) -> str:
    return (
        f"constant {constant_name} : mem_type(0 to {num_words - 1})"
        f"({word_bits - 1} downto 0) := (\n"
        f"{body}\n"
        f");"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert signed integer weights into packed VHDL constant entries, "
            "optionally generating one constant per input channel or one merged "
            "constant with all channels grouped per word."
        )
    )
    parser.add_argument(
        "--input_file", "-f", required=True, help="Path to input text file"
    )
    parser.add_argument(
        "--elem_size_bytes",
        "-s",
        type=int,
        required=True,
        help="Size of each input number in bytes, e.g. 1 for int8, 2 for int16",
    )
    parser.add_argument(
        "--nums_per_word",
        "-n",
        type=int,
        required=True,
        help="How many numbers to pack into each output VHDL word",
    )
    parser.add_argument(
        "--num_input_channels",
        "-i",
        type=int,
        required=True,
        help="Number of input channels in the weight file",
    )
    parser.add_argument(
        "--values_per_input_channel",
        "-k",
        type=int,
        required=True,
        help=(
            "How many consecutive values belong to one input channel inside one "
            "output-channel block. For a 3x3 kernel, use 9."
        ),
    )
    parser.add_argument(
        "--constant_prefix",
        default="WEIGHTS_CH",
        help='Prefix for generated VHDL constants, e.g. "CONV1_CH"',
    )
    parser.add_argument(
        "--merge_channels",
        action="store_true",
        help=(
            "Generate one merged constant where each entry groups all channels "
            "for the same packed word index, e.g. "
            '0 => x"..." & x"..." & ...'
        ),
    )
    parser.add_argument(
        "--merged_constant_name",
        default="WEIGHTS_MERGED",
        help='Constant name to use with --merge_channels, e.g. "CONV1_WEIGHTS"',
    )
    parser.add_argument(
        "--per_line",
        type=int,
        default=8,
        help="How many packed words to place on each output line",
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
    if args.num_input_channels <= 0:
        raise ValueError("num_input_channels must be positive")
    if args.values_per_input_channel <= 0:
        raise ValueError("values_per_input_channel must be positive")
    if args.per_line <= 0:
        raise ValueError("per_line must be positive")

    input_path = Path(args.input_file)
    output_path = (
        Path(args.output)
        if args.output
        else input_path.with_suffix(input_path.suffix + ".vhdl.txt")
    )

    text = input_path.read_text(encoding="utf-8")
    values = parse_numbers(text)

    channel_values = split_by_input_channel(
        values,
        args.num_input_channels,
        args.values_per_input_channel,
    )

    base_word_bits = args.elem_size_bytes * 8 * args.nums_per_word
    constants = []

    if args.merge_channels:
        body, num_words = format_merged_vhdl_entries(
            channel_values,
            args.elem_size_bytes,
            args.nums_per_word,
            per_line=args.per_line,
        )
        merged_word_bits = base_word_bits * args.num_input_channels
        constants.append(
            format_vhdl_constant(
                args.merged_constant_name,
                body,
                num_words,
                merged_word_bits,
            )
        )
    else:
        for ch, vals in enumerate(channel_values):
            body = format_vhdl_entries(
                vals,
                args.elem_size_bytes,
                args.nums_per_word,
                per_line=args.per_line,
            )
            num_words = (len(vals) + args.nums_per_word - 1) // args.nums_per_word
            const_name = f"{args.constant_prefix}{ch}"
            constants.append(
                format_vhdl_constant(const_name, body, num_words, base_word_bits)
            )

    output_path.write_text("\n\n".join(constants) + "\n", encoding="utf-8")

    if args.merge_channels:
        num_words = len(
            pack_words(channel_values[0], args.elem_size_bytes, args.nums_per_word)
        )
        print(
            f"Wrote merged VHDL constant to {output_path} "
            f"({args.num_input_channels} channels, "
            f"{base_word_bits} bits/channel-word, "
            f"{base_word_bits * args.num_input_channels} bits/merged word)"
        )
        for ch, vals in enumerate(channel_values):
            print(
                f"  Channel {ch}: {len(vals)} values -> "
                f"{(len(vals) + args.nums_per_word - 1) // args.nums_per_word} packed words"
            )
    else:
        print(
            f"Wrote {len(constants)} VHDL constants to {output_path} "
            f"({base_word_bits} bits/word)"
        )
        for ch, vals in enumerate(channel_values):
            num_words = (len(vals) + args.nums_per_word - 1) // args.nums_per_word
            print(f"  Channel {ch}: {len(vals)} values -> {num_words} packed words")


if __name__ == "__main__":
    main()
