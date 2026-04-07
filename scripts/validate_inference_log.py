import argparse
import re
import sys
from pathlib import Path

START_RE = re.compile(r"^\[START\] task=[^\s]+ .+$")
STEP_RE = re.compile(r"^\[STEP\] task=[^\s]+ step=\d+ action=[^\s]+ reward=\d+\.\d{4} done=(True|False) source=[^\s]+.*$")
END_RE = re.compile(r"^\[END\] task=[^\s]+ .+$")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate inference structured log format")
    parser.add_argument("--log", required=True, help="Path to inference log file")
    args = parser.parse_args()

    log_path = Path(args.log)
    if not log_path.exists():
        print(f"[FAIL] log file not found: {log_path}")
        return 1

    lines = [line.rstrip("\n") for line in log_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        print("[FAIL] log file is empty")
        return 1

    start_count = 0
    step_count = 0
    end_count = 0
    task_starts = set()
    task_ends = set()

    for idx, line in enumerate(lines, start=1):
        if line.startswith("[START]"):
            if not START_RE.match(line):
                print(f"[FAIL] invalid START line at {idx}: {line}")
                return 1
            start_count += 1
            parts = line.split()
            for part in parts:
                if part.startswith("task="):
                    task_starts.add(part.split("=", 1)[1])
                    break
            continue

        if line.startswith("[STEP]"):
            if not STEP_RE.match(line):
                print(f"[FAIL] invalid STEP line at {idx}: {line}")
                return 1
            step_count += 1
            continue

        if line.startswith("[END]"):
            if not END_RE.match(line):
                print(f"[FAIL] invalid END line at {idx}: {line}")
                return 1
            end_count += 1
            parts = line.split()
            for part in parts:
                if part.startswith("task="):
                    task_ends.add(part.split("=", 1)[1])
                    break
            continue

        print(f"[FAIL] unexpected line at {idx}: {line}")
        return 1

    required_tasks = {"task_1", "task_2", "task_3"}
    if not required_tasks.issubset(task_starts):
        missing = sorted(required_tasks - task_starts)
        print(f"[FAIL] missing START for tasks: {', '.join(missing)}")
        return 1
    if not required_tasks.issubset(task_ends):
        missing = sorted(required_tasks - task_ends)
        print(f"[FAIL] missing END for tasks: {', '.join(missing)}")
        return 1

    if step_count == 0:
        print("[FAIL] no STEP lines found")
        return 1

    print(f"[PASS] START={start_count} STEP={step_count} END={end_count}")
    print("[PASS] required task markers present: task_1, task_2, task_3")
    print("[NOTE] For exact official format parity, compare with the official sample inference script field ordering.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
