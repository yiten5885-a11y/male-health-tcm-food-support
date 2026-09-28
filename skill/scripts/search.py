#!/usr/bin/env python3
"""Search the packaged, source-reviewed full records deterministically."""

from __future__ import annotations

import argparse
import json
import unicodedata
from pathlib import Path
from typing import Iterable


SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECORDS = SKILL_ROOT / "assets" / "records.jsonl"
STOP_GRAMS = {
    "什么", "哪些", "怎么", "如何", "是否", "有没有", "多少", "需要", "原书",
    "方法", "资料", "记录", "请问", "一下", "对应", "可以", "适合", "安全",
    "原料", "用法", "功效", "宜忌", "禁忌", "时长", "时间", "图号", "疗程", "频率",
}


def normalize(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value)).lower()
    return "".join(char for char in text if char.isalnum() or "\u3400" <= char <= "\u9fff")


def grams(text: str) -> set[str]:
    normalized = normalize(text)
    result: set[str] = set()
    for size in (2, 3, 4):
        for index in range(max(0, len(normalized) - size + 1)):
            gram = normalized[index:index + size]
            if gram not in STOP_GRAMS:
                result.add(gram)
    return result


def load_records(path: Path = DEFAULT_RECORDS) -> list[dict]:
    if not path.is_file():
        raise FileNotFoundError(
            f"资料库未安装：{path}。请先接入拥有使用许可的 records.jsonl；不要用未获授权的 PDF、页图或转录替代。"
        )
    records = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
    return records


def source_ids(record: dict) -> set[str]:
    return {ref["source_id"] for ref in record["source_refs"]}


def searchable_text(record: dict) -> str:
    fields = " ".join(str(value) for value in record.get("fields", {}).values())
    return " ".join([
        record["title_source"],
        " ".join(record["chapter_path"]),
        record["plain_summary"],
        fields,
        record["source_text"],
    ])


def score_record(query: str, record: dict) -> tuple[float, list[str]]:
    query_norm = normalize(query)
    title_norm = normalize(record["title_source"])
    document = searchable_text(record)
    document_norm = normalize(document)
    query_grams = grams(query)
    title_grams = grams(record["title_source"])
    document_grams = grams(document)
    score = 0.0
    reasons: list[str] = []

    if query_norm == title_norm:
        score += 140
        reasons.append("exact_title")
    elif title_norm and title_norm in query_norm:
        score += 100
        reasons.append("title_in_query")
    elif query_norm and query_norm in title_norm:
        score += 90
        reasons.append("query_in_title")

    title_overlap = query_grams & title_grams
    body_overlap = query_grams & document_grams
    if title_overlap:
        score += min(70, len(title_overlap) * 14)
        reasons.append(f"title_grams:{len(title_overlap)}")
    if body_overlap:
        score += min(55, len(body_overlap) * 3)
        reasons.append(f"body_grams:{len(body_overlap)}")
    if query_norm and query_norm in document_norm:
        score += 35
        reasons.append("exact_phrase")

    intent_terms = {
        "recipe": ("汤", "食疗", "原料", "制作", "用法", "宜忌"),
        "technique": ("按摩", "手法", "怎么", "频率", "时间", "分钟", "次数", "施力", "按揉", "推捋"),
        "acupoint": ("经络", "经脉", "穴位", "奇穴"),
        "reflex_zone": ("反射区",),
        "figure": ("图号", "哪张图", "图示", "插图"),
        "prevention": ("预防", "调理"),
    }
    if any(term in query for term in intent_terms.get(record["record_type"], ())):
        score += 45
        reasons.append(f"type_intent:{record['record_type']}")

    return score, reasons


def citation(record: dict) -> str:
    parts = []
    for ref in record["source_refs"]:
        pdf_pages = "、".join(str(page) for page in ref["pdf_pages"])
        book_pages = "、".join("未确认" if page is None else str(page) for page in ref["book_pages"])
        parts.append(f"[{ref['source_id']}｜PDF {pdf_pages}页｜书内{book_pages}页｜{record['id']}]")
    return " ".join(parts)


def search_records(
    query: str,
    records: Iterable[dict] | None = None,
    source: str | None = None,
    record_type: str | None = None,
    chapter: str | None = None,
    pdf_page: int | None = None,
    top_k: int = 5,
    min_score: float = 12.0,
) -> list[dict]:
    if not query.strip():
        raise ValueError("query must not be empty")
    candidates = list(records if records is not None else load_records())
    ranked = []
    for record in candidates:
        if source and source not in source_ids(record):
            continue
        if record_type and record["record_type"] != record_type:
            continue
        if chapter and normalize(chapter) not in normalize(" ".join(record["chapter_path"])):
            continue
        if pdf_page is not None and not any(pdf_page in ref["pdf_pages"] for ref in record["source_refs"]):
            continue
        score, reasons = score_record(query, record)
        if score < min_score:
            continue
        ranked.append({
            "score": round(score, 2),
            "match_reasons": reasons,
            "citation": citation(record),
            "record": record,
        })
    ranked.sort(key=lambda item: (-item["score"], item["record"]["id"]))
    if not ranked:
        return []
    strong_title_match = any(
        reason in {"exact_title", "title_in_query", "query_in_title"}
        for reason in ranked[0]["match_reasons"]
    )
    relative_floor = max(min_score, ranked[0]["score"] * (0.55 if strong_title_match else 0.30))
    return [item for item in ranked if item["score"] >= relative_floor][:top_k]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--source", choices=("S01", "S02"))
    parser.add_argument(
        "--type",
        dest="record_type",
        choices=("recipe", "technique", "concept", "acupoint", "reflex_zone", "figure", "prevention"),
    )
    parser.add_argument("--chapter", help="Filter by a chapter-path substring")
    parser.add_argument("--pdf-page", type=int, help="Filter by one-based physical PDF page")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--records", type=Path, default=DEFAULT_RECORDS)
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    try:
        results = search_records(
            query=args.query,
            records=load_records(args.records),
            source=args.source,
            record_type=args.record_type,
            chapter=args.chapter,
            pdf_page=args.pdf_page,
            top_k=args.top_k,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(json.dumps({"query": args.query, "count": len(results), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
