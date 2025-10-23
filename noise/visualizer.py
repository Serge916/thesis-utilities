import numpy as np
import matplotlib.pyplot as plt
import os
import argparse

# CLI
parser = argparse.ArgumentParser(
    description="Render 2-channel 128x128 frames with optional noise."
)
parser.add_argument(
    "--input",
    "-i",
    default="inputs/original.txt",
    help="Path to input text file containing 0/1 values (default: inputs/original.txt)",
)
parser.add_argument(
    "--output-dir",
    "-o",
    default="outputs",
    help="Directory to save output images and noised data (default: outputs)",
)
parser.add_argument(
    "--noise-ratio",
    "-p",
    type=float,
    default=0.0,
    help="Probability each pixel becomes 1 via noise (0..1). Default: 0.0",
)
parser.add_argument(
    "--seed", "-s", type=int, default=None, help="Random seed (optional)"
)
parser.add_argument(
    "--no-show",
    action="store_true",
    help="Do not display figures interactively; only save outputs.",
)
args = parser.parse_args()

input_file = args.input
output_dir = args.output_dir
noise_ratio = args.noise_ratio
seed = args.seed


# Clamp noise_ratio into [0,1]
if noise_ratio < 0 or noise_ratio > 1:
    print(f"Warning: --noise-ratio {noise_ratio} is out of [0,1]. Clamping.")
    noise_ratio = max(0.0, min(1.0, noise_ratio))

#  Configuration
channels = 2
height = 128
width = 128
frame_size = channels * height * width  # 2 * 128 * 128 = 32768

os.makedirs(output_dir, exist_ok=True)
#  Read binary values
with open(input_file, "r") as f:
    raw_data = f.read().split()

# Convert to integers (ignore invalid values)
original_values = [int(x) for x in raw_data if x in ("0", "1")]
rng = np.random

if seed is not None:
    rng = np.random.default_rng(seed)

original_values = np.array(original_values, dtype=np.uint8)  # or dtype=bool
noise_mask = rng.random(original_values.size) < noise_ratio  # boolean mask
binary_values = np.bitwise_or(original_values, noise_mask.astype(np.uint8))

#  Check number of full frames
num_frames = len(binary_values) // frame_size
remainder = len(binary_values) % frame_size

if remainder != 0:
    print(
        f"Warning: Extra {remainder} values ignored (not part of a full {channels}x{height}x{width} frame)."
    )

print(f"Total frames found: {num_frames}")

file_name = (
    f"noise_ratio_{noise_ratio}.txt"
    if seed is None
    else f"noise_ratio_{noise_ratio}_with_seed_{seed}.txt"
)
output_file_path = os.path.join(output_dir, file_name)

#  Split into frames
frames = np.array(binary_values[: num_frames * frame_size], dtype=int)
frames2d = frames.reshape(num_frames, frame_size)
np.savetxt(output_file_path, frames2d, fmt="%d", delimiter=" ")

#  Visualization
frames = frames.reshape((num_frames, channels, height, width))
if not args.no_show:
    for i in range(num_frames):
        fig, axes = plt.subplots(1, channels, figsize=(8, 4))
        for ch in range(channels):
            axes[ch].imshow(frames[i, ch], cmap="gray", interpolation="nearest")
            axes[ch].set_title(f"Frame {i}, Channel {ch}")
            axes[ch].axis("off")
        plt.tight_layout()
        plt.show()
