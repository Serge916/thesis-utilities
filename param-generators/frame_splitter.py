from pathlib import Path
import sys

HEIGHT = 128
WIDTH = 128
CHANNELS = 2
BITS_PER_FRAME = HEIGHT * WIDTH * CHANNELS


def split_frames(input_file, output_dir):
    input_path = Path(input_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8") as f:
        for frame_idx, line in enumerate(f):
            line = line.strip()
            if not line:
                continue

            bits = line.split()

            if len(bits) != BITS_PER_FRAME:
                raise ValueError(
                    f"Frame {frame_idx}: expected {BITS_PER_FRAME} bits, got {len(bits)}"
                )

            if any(bit not in {"0", "1"} for bit in bits):
                raise ValueError(f"Frame {frame_idx}: found values other than 0 or 1")

            # Split into two channels
            ch0 = bits[: HEIGHT * WIDTH]
            ch1 = bits[HEIGHT * WIDTH :]

            out_file = output_path / f"frame_{frame_idx:06d}.txt"
            with out_file.open("w", encoding="utf-8") as out:
                for row in range(HEIGHT):
                    start = row * WIDTH
                    end = start + WIDTH

                    row_ch0 = "".join(reversed(ch0[start:end]))
                    row_ch1 = "".join(reversed(ch1[start:end]))

                    out.write(row_ch0 + row_ch1 + "\n")

            print(f"Wrote {out_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python frame_splitter.py input.txt output_dir")
        sys.exit(1)

    split_frames(sys.argv[1], sys.argv[2])
