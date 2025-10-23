import numpy as np
import matplotlib.pyplot as plt
import os
import argparse

# CLI
parser = argparse.ArgumentParser(description="Expand the dataset.")
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
    "--extend-dataset",
    "-e",
    type=int,
    default=2,
    help="Extends the dataset by placing multiplying the frames. Default: 1",
)

args = parser.parse_args()

input_file = args.input
output_dir = args.output_dir
extend = args.extend_dataset


#  Configuration
channels = 2
height = 128
width = 128
frames_per_sequence = 8
frame_size = channels * height * width  # 2 * 128 * 128 = 32768

os.makedirs(output_dir, exist_ok=True)
#  Read binary values
with open(input_file, "r") as f:
    raw_data = f.read().split()

# Convert to integers (ignore invalid values)
original_values = [int(x) for x in raw_data if x in ("0", "1")]
original_values = np.array(original_values, dtype=np.uint8)  # or dtype=bool

#  Check number of full frames
num_frames = len(original_values) // frame_size
remainder = len(original_values) % frame_size

if remainder != 0:
    raise ("Not even amount of values!")

print(f"Total frames found: {num_frames}")


# Create generator function
def chunks_gen(seq, chunk_size=frame_size * frames_per_sequence):
    for i in range(0, len(seq), chunk_size):
        yield seq[i : i + chunk_size]


frames = np.empty(frame_size * num_frames * extend, dtype=int)
write = 0
target = frames.size

for chunk in chunks_gen(original_values, chunk_size=frame_size * frames_per_sequence):
    # works whether chunk is list or np.ndarray
    dup = np.tile(np.asarray(chunk, dtype=int), extend)

    # how much space remains, and how much of dup to copy
    take = min(dup.size, target - write)
    if take <= 0:
        break

    frames[write : write + take] = dup[:take]
    write += take

frames = frames.reshape((num_frames * extend, channels, height, width))

# Save txt file
file_name, file_extension = os.path.splitext(os.path.basename(input_file))
file_name = f"{file_name}_extended_by_{extend}{file_extension}"
output_file_path = os.path.join(output_dir, file_name)

#  Split into frames
frames2d = frames.reshape(num_frames * extend, frame_size)
np.savetxt(output_file_path, frames2d, fmt="%d", delimiter=" ")
print(f"Event stream has been saved to {output_file_path}")
