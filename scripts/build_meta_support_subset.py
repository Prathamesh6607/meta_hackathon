from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Iterable, Dict, Any

META_HINTS = ("facebook", "instagram", "whatsapp", "messenger", "meta", "ads", "account", "login", "privacy", "ban")


def iter_rows(path: Path) -> Iterable[Dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        with path.open("r", encoding="utf-8", newline="") as handle:
            yield from csv.DictReader(handle)
    elif suffix == ".jsonl":
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)
    elif suffix == ".json":
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            yield from data
        elif isinstance(data, dict):
            for value in data.values():
                if isinstance(value, list):
                    yield from value
    else:
        raise ValueError(f"Unsupported file type: {path.suffix}")


def row_text(row: Dict[str, Any]) -> str:
    parts = [
        str(row.get("subject") or row.get("title") or row.get("topic") or ""),
        str(row.get("body") or row.get("text") or row.get("message") or ""),
        str(row.get("sender") or row.get("author_id") or row.get("customer_email") or ""),
    ]
    return " ".join(part for part in parts if part).lower()


def is_meta_related(row: Dict[str, Any]) -> bool:
    text = row_text(row)
    return any(hint in text for hint in META_HINTS)


def normalize_row(row: Dict[str, Any], source: str, index: int) -> Dict[str, Any]:
    subject = str(row.get("subject") or row.get("title") or row.get("topic") or "")
    body = str(row.get("body") or row.get("text") or row.get("message") or "")
    sender = str(row.get("sender") or row.get("author_id") or row.get("customer_email") or "")
    label = str(
        row.get("true_category")
        or row.get("category")
        or row.get("label")
        or row.get("sentiment")
        or row.get("inbound")
        or "unknown"
    )
    return {
        "id": str(row.get("id") or row.get("tweet_id") or row.get("ticket_id") or f"{source}:{index}"),
        "subject": subject,
        "body": body,
        "sender": sender,
        "label": label,
        "source": source,
    }


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python scripts/build_meta_support_subset.py <input> <output> [max_rows]", file=sys.stderr)
        return 1

    input_path = Path(sys.argv[1]).expanduser().resolve()
    output_path = Path(sys.argv[2]).expanduser().resolve()
    max_rows = int(sys.argv[3]) if len(sys.argv) > 3 else 50000

    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected = []
    for index, row in enumerate(iter_rows(input_path)):
        if len(selected) >= max_rows:
            break
        if is_meta_related(row):
            selected.append(normalize_row(row, input_path.name, index))

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "subject", "body", "sender", "label", "source"])
        writer.writeheader()
        writer.writerows(selected)

    print(f"Wrote {len(selected)} Meta-related support rows to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
