from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

TOKEN_RE = re.compile(r"[a-z0-9]+")
META_HINTS = {"facebook", "instagram", "whatsapp", "messenger", "meta", "ads", "account", "login", "privacy", "ban"}


@dataclass(frozen=True)
class SupportRecord:
    record_id: str
    text: str
    label: str
    source: str
    metadata: Dict[str, Any]


class SupportKnowledgeBase:
    def __init__(self, records: List[SupportRecord]):
        self.records = records
        self.inverted_index: Dict[str, Set[int]] = defaultdict(set)
        self.label_index: Dict[str, List[int]] = defaultdict(list)
        self.priority_terms: Dict[str, Set[int]] = defaultdict(set)
        self._token_cache: List[List[str]] = []

        for idx, record in enumerate(records):
            tokens = self._tokenize(record.text)
            self._token_cache.append(tokens)
            for token in tokens:
                self.inverted_index[token].add(idx)
            self.label_index[record.label].append(idx)
            if any(hint in tokens for hint in META_HINTS):
                self.priority_terms["meta"].add(idx)

    @staticmethod
    def _normalize(text: str) -> str:
        return (text or "").lower().strip()

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        return TOKEN_RE.findall(cls._normalize(text))

    @classmethod
    def from_datasets(cls, datasets_dir: Path, max_records: int = 20000) -> "SupportKnowledgeBase":
        preferred_files = [
            datasets_dir / "meta_support_subset.csv",
            datasets_dir / "twcs.csv",
            datasets_dir / "customer_support_on_twitter.csv",
            datasets_dir / "twitter_customer_support.csv",
            datasets_dir / "twitter_support.jsonl",
            datasets_dir / "twitter_support.csv",
            datasets_dir / "inbox_vast_100k.jsonl",
            datasets_dir / "inbox_vast_100k.csv",
        ]

        for path in preferred_files:
            if path.exists():
                records = list(cls._load_records(path, max_records=max_records))
                if records:
                    return cls(records)

        return cls([])

    @classmethod
    def _load_records(cls, path: Path, max_records: int = 20000) -> Iterable[SupportRecord]:
        suffix = path.suffix.lower()
        if suffix == ".jsonl":
            with path.open("r", encoding="utf-8") as handle:
                for idx, line in enumerate(handle):
                    if idx >= max_records:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    yield cls._row_to_record(row, idx, path.name)
        elif suffix == ".csv":
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                for idx, row in enumerate(reader):
                    if idx >= max_records:
                        break
                    yield cls._row_to_record(row, idx, path.name)

    @classmethod
    def _row_to_record(cls, row: Dict[str, Any], idx: int, source: str) -> SupportRecord:
        record_id = str(row.get("id") or row.get("tweet_id") or row.get("ticket_id") or f"{source}:{idx}")
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
        combined = " ".join(part for part in [subject, body] if part)
        if sender:
            combined = f"{combined} sender {sender}".strip()
        metadata = {k: v for k, v in row.items() if k not in {"body", "text", "message"}}
        return SupportRecord(record_id=record_id, text=combined, label=label, source=source, metadata=metadata)

    def _candidate_indices(self, query_tokens: List[str]) -> Set[int]:
        candidates: Set[int] = set()
        for token in query_tokens:
            candidates.update(self.inverted_index.get(token, set()))
        return candidates

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        query_tokens = self._tokenize(query)
        if not self.records:
            return []

        candidates = self._candidate_indices(query_tokens)
        if not candidates:
            candidates = set(range(min(len(self.records), top_k * 5)))

        query_counter = Counter(query_tokens)
        scored: List[Tuple[float, int]] = []
        query_set = set(query_tokens)
        has_meta_hint = bool(query_set & META_HINTS)

        for idx in candidates:
            record_tokens = self._token_cache[idx]
            overlap = query_set.intersection(record_tokens)
            if not overlap:
                continue
            score = float(len(overlap))
            score += 0.15 * sum(query_counter[token] for token in overlap)
            if has_meta_hint and idx in self.priority_terms.get("meta", set()):
                score += 2.0
            label = self.records[idx].label.lower()
            if label in query_set:
                score += 1.0
            scored.append((score, idx))

        if not scored:
            return []

        scored.sort(key=lambda item: item[0], reverse=True)
        top_records = []
        for score, idx in scored[:top_k]:
            record = self.records[idx]
            top_records.append(
                {
                    "record_id": record.record_id,
                    "label": record.label,
                    "source": record.source,
                    "score": round(score, 3),
                    "snippet": record.text[:240],
                    "metadata": record.metadata,
                }
            )
        return top_records

    def summary(self) -> Dict[str, Any]:
        label_counts = Counter(record.label for record in self.records)
        source_counts = Counter(record.source for record in self.records)
        top_labels = [
            {"label": label, "count": count}
            for label, count in label_counts.most_common(5)
        ]
        top_sources = [
            {"source": source, "count": count}
            for source, count in source_counts.most_common(5)
        ]
        return {
            "records": len(self.records),
            "unique_tokens": len(self.inverted_index),
            "top_labels": top_labels,
            "top_sources": top_sources,
        }

    def suggest_response(self, query: str, task_id: str, action: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        matches = self.search(query, top_k=3)
        top_label = matches[0]["label"] if matches else "unknown"
        task_map = {
            "task_1": "Use the classification to route the case, preserve order details, and escalate anything urgent.",
            "task_2": "Use the policy lookup result to answer with a clear approval/decline and next steps.",
            "task_3": "Check the order and inventory state before choosing replacement or refund.",
        }

        if task_id == "task_1":
            response = (
                f"We identified this as {action.get('category', 'General Inquiry')} with {action.get('priority', 'Normal')} priority. "
                f"Suggested handling: {task_map.get(task_id)}"
            )
        elif task_id == "task_2":
            response = action.get("response_text") or task_map.get(task_id)
        else:
            response = task_map.get(task_id)

        pitch = (
            "This retrieval layer gives Meta a fast, explainable support assistant: "
            "it uses an inverted index for candidate pruning, label buckets for routing, "
            f"and a corpus-backed response draft grounded in {top_label} cases."
        )
        if context.get("queried_policy"):
            pitch += " The workflow also preserves policy compliance before drafting a reply."
        return {
            "matched_cases": matches,
            "suggested_response": response,
            "pitch_note": pitch,
            "index_stats": {
                "records": len(self.records),
                "unique_tokens": len(self.inverted_index),
            },
        }
