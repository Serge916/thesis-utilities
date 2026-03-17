from pathlib import Path
import argparse
import numpy as np
import matplotlib.pyplot as plt

frame_height = 128
MAX_CHANNELS = 256

# bits 15..8 = row
# bits 7..0  = channel
ROW_SHIFT = 8
ROW_MASK = 0x7F
CHANNEL_MASK = 0xFF


def parse_metadata(meta_str: str) -> tuple[int, int]:
    meta = int(meta_str, 16)
    row = (meta >> ROW_SHIFT) & ROW_MASK
    channel = meta & CHANNEL_MASK
    return row, channel


def read_frames(input_file: str) -> tuple[dict[int, dict[int, str]], int]:
    input_path = Path(input_file)
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

            if not (0 <= row < frame_height):
                raise ValueError(
                    f"Line {line_num}: row {row} out of range 0..{frame_height - 1}"
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
        raise ValueError("No data found.")

    return frames, expected_width


def rebuild_frames(
    input_file: str, output_dir: str, fill_missing_with_zeros: bool = True
):
    frames, expected_width = read_frames(input_file)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    zero_row = "0" * expected_width

    for channel in sorted(frames):
        out_file = output_path / f"channel_{channel:03d}.txt"
        rows = frames[channel]

        with out_file.open("w", encoding="utf-8") as out:
            for row in range(frame_height):
                if row in rows:
                    out.write(rows[row] + "\n")
                else:
                    if fill_missing_with_zeros:
                        out.write(zero_row + "\n")
                    else:
                        raise ValueError(f"Missing row {row} for channel {channel}")

        print(f"Wrote {out_file}")


def build_channel_array(
    rows: dict[int, str], width: int, fill_missing_with_zeros: bool = True
) -> np.ndarray:
    arr = np.zeros((frame_height, width), dtype=np.uint8)

    for row in range(frame_height):
        if row in rows:
            arr[row] = np.fromiter(
                (int(c) for c in rows[row]), dtype=np.uint8, count=width
            )
        else:
            if not fill_missing_with_zeros:
                raise ValueError(f"Missing row {row}")
            # already zero-filled

    return arr


def visualize_frames(input_file: str, fill_missing_with_zeros: bool = True):
    frames, width = read_frames(input_file)
    channels = sorted(frames)

    if not channels:
        raise ValueError("No channels found.")

    arrays = {
        ch: build_channel_array(frames[ch], width, fill_missing_with_zeros)
        for ch in channels
    }

    state = {"index": 0}

    fig, ax = plt.subplots()
    img = ax.imshow(
        arrays[channels[state["index"]]],
        cmap="gray",
        interpolation="nearest",
        vmax=1,
        vmin=0,
    )
    ax.set_title(f"Channel {channels[state['index']]}")
    ax.set_xlabel("Column")
    ax.set_ylabel("Row")

    def update():
        ch = channels[state["index"]]
        img.set_data(arrays[ch])
        ax.set_title(f"Channel {ch}")
        fig.canvas.draw_idle()

    def on_key(event):
        if event.key == "right":
            state["index"] = (state["index"] + 1) % len(channels)
            update()
        elif event.key == "left":
            state["index"] = (state["index"] - 1) % len(channels)
            update()

    fig.canvas.mpl_connect("key_press_event", on_key)
    plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rebuild channel frames from bitstring+metadata input."
    )
    parser.add_argument("input_file", help="Input text file")
    parser.add_argument(
        "output_dir",
        nargs="?",
        help="Output directory for per-channel files (required unless --visualize-only is used)",
    )
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Open an interactive viewer. Use left/right arrow keys to switch channels.",
    )
    parser.add_argument(
        "--height",
        "-r",
        type=int,
        required=True,
        help="Frame height.",
    )
    parser.add_argument(
        "--visualize-only",
        action="store_true",
        help="Only visualize; do not write output files.",
    )
    parser.add_argument(
        "--no-fill-missing",
        action="store_true",
        help="Error out if a row is missing instead of filling it with zeros.",
    )

    args = parser.parse_args()
    fill_missing_with_zeros = not args.no_fill_missing
    frame_height = args.height

    if not args.visualize_only and args.output_dir is None:
        parser.error("output_dir is required unless --visualize-only is used")

    if not args.visualize_only:
        rebuild_frames(args.input_file, args.output_dir, fill_missing_with_zeros)

    if args.visualize or args.visualize_only:
        visualize_frames(args.input_file, fill_missing_with_zeros)
