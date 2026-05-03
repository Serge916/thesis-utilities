import sys


def normalize_hex(s: str) -> str:
    s = s.strip().lower()
    if s.startswith("0x"):
        s = s[2:]
    return s.lstrip("0") or "0"


def compare_tdata(file_a, file_b):
    with open(file_a, "r") as fa, open(file_b, "r") as fb:
        lines_a = fa.readlines()
        lines_b = fb.readlines()

    # Skip header if present
    start_idx = 1 if lines_a[0].lower().startswith("tdata") else 0

    max_len = max(len(lines_a), len(lines_b))

    mismatch_found = False

    for i in range(start_idx, max_len):
        if i >= len(lines_a):
            print(f"Mismatch at line {i}: file A ended early")
            mismatch_found = True
            continue

        if i >= len(lines_b):
            print(f"Mismatch at line {i}: file B ended early")
            mismatch_found = True
            continue

        tdata_a = lines_a[i].split(",")[0]
        tdata_b = lines_b[i].split(",")[0]

        if normalize_hex(tdata_a) != normalize_hex(tdata_b):
            print(f"Mismatch at line {i}:")
            print(f"  A: {tdata_a.strip()}")
            print(f"  B: {tdata_b.strip()}")
            mismatch_found = True

    if not mismatch_found:
        print("No mismatches found.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python compare_logs.py file_a.csv file_b.csv")
        sys.exit(1)

    compare_tdata(sys.argv[1], sys.argv[2])
