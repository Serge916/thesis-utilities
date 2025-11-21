import argparse
import os


def convert_file(input_path: str, output_path: str) -> None:
    with open(input_path, "r") as fin, open(output_path, "w") as fout:
        for line in fin:
            # Remove trailing newline
            line = line.rstrip("\n")

            # Optionally skip empty lines
            if not line:
                fout.write("\n")
                continue

            # Turn "0101" into "0 1 0 1"
            spaced = " ".join(list(line))
            fout.write(spaced + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Convert text with no separators into space-separated values per line."
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Path to input text file (no separators).",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Path to output CSV-like file (space-separated). "
        "If omitted, '_spaced' is appended to the input filename.",
    )
    args = parser.parse_args()

    input_path = args.input

    if args.output:
        output_path = args.output
    else:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_spaced{ext or '.txt'}"

    convert_file(input_path, output_path)
    print(f"Converted file written to: {output_path}")


if __name__ == "__main__":
    main()
