from pathlib import Path
import sys

MAX_ROWS = 128
MAX_CHANNELS = 256

# Default interpretation:
# - bits 15..9  = row   (7 bits)
# - bit 8       = unused/reserved
# - bits 7..0   = channel (8 bits)
ROW_SHIFT = 8
ROW_MASK = 0x7F
CHANNEL_MASK = 0xFF


def parse_metadata(meta_str: str) -> tuple[int, int]:
    meta = int(meta_str, 16)
    row = (meta >> ROW_SHIFT) & ROW_MASK
    channel = meta & CHANNEL_MASK
    return row, channel


def rebuild_frames(
    input_file: str, output_dir: str, fill_missing_with_zeros: bool = True
):
    input_path = Path(input_file)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # channel -> {row -> bitstring}
    frames: dict[int, dict[int, str]] = {}

    expected_width = None

    with input_path.open("r", encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                data_str, meta_str = line.split(",", 1)
            except ValueError:
                raise ValueError(f"Line {line_num}: expected '<data>,<metadata>'")

            data_str = data_str.strip()
            meta_str = meta_str.strip()

            if not data_str:
                raise ValueError(f"Line {line_num}: empty data field")

            if any(c not in "01" for c in data_str):
                raise ValueError(
                    f"Line {line_num}: data contains characters other than 0/1"
                )

            row, channel = parse_metadata(meta_str)

            if not (0 <= row < MAX_ROWS):
                raise ValueError(
                    f"Line {line_num}: row {row} out of range 0..{MAX_ROWS - 1}"
                )

            if not (0 <= channel < MAX_CHANNELS):
                raise ValueError(
                    f"Line {line_num}: channel {channel} out of range 0..{MAX_CHANNELS - 1}"
                )

            if expected_width is None:
                expected_width = len(data_str)
            elif len(data_str) != expected_width:
                raise ValueError(
                    f"Line {line_num}: inconsistent row width {len(data_str)} "
                    f"(expected {expected_width})"
                )

            ch_rows = frames.setdefault(channel, {})
            if row in ch_rows:
                raise ValueError(
                    f"Line {line_num}: duplicate entry for channel {channel}, row {row}; meta {meta_str}"
                )

            ch_rows[row] = data_str

    if expected_width is None:
        print("No data found.")
        return

    zero_row = "0" * expected_width

    for channel in sorted(frames):
        out_file = output_path / f"channel_{channel:03d}.txt"
        rows = frames[channel]

        with out_file.open("w", encoding="utf-8") as out:
            for row in range(MAX_ROWS):
                if row in rows:
                    out.write(rows[row] + "\n")
                else:
                    if fill_missing_with_zeros:
                        out.write(zero_row + "\n")
                    else:
                        raise ValueError(f"Missing row {row} for channel {channel}")

        print(f"Wrote {out_file}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python rebuild_channels.py input.txt output_dir")
        sys.exit(1)

    rebuild_frames(sys.argv[1], sys.argv[2])
