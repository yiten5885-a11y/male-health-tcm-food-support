#!/usr/bin/env python3
"""Format source-bounded answers from the packaged full records."""

from __future__ import annotations

import argparse
import json
from typing import Iterable

from search import load_records, search_records


SENSITIVE_TAGS = {
    "intimate_body_part", "strong_pressure", "high_repetition", "exact_parameters",
    "spinal_manipulation", "scan_damage", "unreviewed_operational_parameters",
}
PERSON_SPECIFIC_TERMS = {
    "安全", "适合我", "能不能吃", "可以吃", "可不可以", "糖尿病", "高血压", "正在吃药",
    "怀孕", "过敏", "儿童", "老人", "确诊", "替代治疗", "我的症状", "我最近", "我能",
    "给我开", "给我配", "个人处方",
}
ACUTE_ABNORMAL_TERMS = {
    "剧痛", "出血", "流血", "肿胀", "红肿", "破皮", "外伤", "受伤", "伤后",
    "麻木", "昏厥", "晕厥", "呼吸困难", "胸痛", "急性异常",
}


def needs_individual_safety_answer(query: str) -> bool:
    return any(term in query for term in PERSON_SPECIFIC_TERMS)


def is_acute_abnormal_query(query: str) -> bool:
    return any(term in query for term in ACUTE_ABNORMAL_TERMS)


def record_block(item: dict) -> list[str]:
    record = item["record"]
    fields = record.get("fields", {})
    lines = [f"### {record['title_source']}", "", record["plain_summary"]]
    if SENSITIVE_TAGS & set(record.get("risk_tags", [])):
        if record["record_type"] == "recipe":
            boundary = "该条目含精确剂量、次数或时间；这里只保留书目定位与非操作性摘要。即使已完成来源转录人工核对，也不等于已完成临床安全性评价。"
        elif record["record_type"] == "concept":
            boundary = "该条目含数字或临床表述；这里只保留来源定位与非操作性摘要，不把原书表述提升为当前临床结论。"
        elif "scan_damage" in record.get("risk_tags", []):
            boundary = "该条目含扫描缺损或不可辨字段；这里只保留可确认的书目定位与非操作性摘要，不补写缺失图题、参数或步骤。"
        else:
            boundary = "该条目含操作参数、私密部位、强刺激或脊柱手法；这里只保留书目定位与非操作性摘要，不转写为个人执行步骤、次数或施力建议。来源转录人工核对不等于临床安全性评价。"
        lines.extend([
            "",
            boundary,
        ])
        if record["record_type"] == "recipe":
            if "claimed_effects" in fields:
                lines.append(f"- 原书功效声称（仅作来源归属，不作疗效保证）：{fields['claimed_effects']}")
            if "contraindications" in fields:
                lines.append(f"- 原书宜忌：{fields['contraindications']}")
    else:
        for key, label in (
            ("ingredients", "原料"),
            ("preparation", "制作"),
            ("usage", "原书用法"),
            ("claimed_effects", "原书功效声称"),
            ("contraindications", "原书宜忌"),
            ("body_part", "原书部位"),
            ("action", "原书动作"),
            ("parameters", "原书参数"),
            ("figure", "图号"),
        ):
            if key in fields:
                lines.append(f"- {label}：{fields[key]}")
    if record.get("unknown_fields"):
        lines.append(f"- 未核清：{'；'.join(record['unknown_fields'])}")
    if record.get("source_discrepancies"):
        lines.append(f"- 来源差异：{'；'.join(record['source_discrepancies'])}")
    human_review = record.get("human_review")
    review_line = (
        f"- 审核状态：human_checked（先经 {record['extraction_review']['reviewer']} 模型核对；"
        f"{human_review['reviewer']} 于 {human_review['reviewed_on']} 完成来源转录人工核对；不代表临床评价）"
        if human_review and human_review.get("status") == "human_checked"
        else f"- 审核状态：{record['extraction_review']['status']}（{record['extraction_review']['reviewer']} 模型核对；人工审核未完成）"
    )
    lines.extend([
        review_line,
        f"- 临床证据状态：{record['clinical_evidence_status']}（未评估）",
        f"- 使用边界：{record['usage_policy']}",
        f"- 来源：{item['citation']}",
    ])
    return lines


def select_comparison(query: str, records: Iterable[dict]) -> list[dict]:
    selected: list[dict] = []
    for source in ("S01", "S02"):
        selected.extend(search_records(query, records=records, source=source, top_k=2, min_score=3.0))
    return selected


def format_answer(query: str, records: Iterable[dict] | None = None, compare: bool = False, top_k: int = 3) -> tuple[str, list[dict]]:
    available = list(records if records is not None else load_records())
    source_counts = {
        source: sum(source in {ref["source_id"] for ref in record["source_refs"]} for record in available)
        for source in ("S01", "S02")
    }
    human_count = sum(
        record.get("human_review", {}).get("status") == "human_checked"
        for record in available
    )
    lines = [
        "## 资料范围", "",
        f"以下结果只来自当前 {len(available)} 条全量记录（S01 {source_counts['S01']} 条、S02 {source_counts['S02']} 条），"
        f"552条均经模型核对，其中 {human_count} 条另经来源转录人工核对；临床证据仍未评估。",
    ]

    if is_acute_abnormal_query(query):
        lines.extend([
            "",
            "当前问题包含急性异常或伤后不适信号，已停止资料检索与推荐流程；本 Skill 不提供继续按摩、食疗或自行处置步骤。",
        ])
        return "\n".join(lines) + "\n", []

    results = select_comparison(query, available) if compare else search_records(query, records=available, top_k=top_k)
    if not compare and any(term in query for term in ("怎么", "步骤", "次数", "频率", "时间", "角度", "施力", "疗程")):
        techniques = [item for item in results if item["record"]["record_type"] == "technique"]
        if techniques:
            results = techniques + [item for item in results if item["record"]["record_type"] != "technique"]

    if needs_individual_safety_answer(query):
        lines.extend([
            "",
            "资料不足：当前记录不能判定某个具体人群是否安全、是否适合使用；不会据此作个体诊断，也不会生成个人食疗或按摩处方。",
        ])

    if not results:
        lines.extend([
            "",
            "当前全量结构化记录没有可靠命中；不能据此推断原书未结构化内容或临床证据的结论。",
        ])
        return "\n".join(lines) + "\n", []

    if compare:
        found = {ref["source_id"] for item in results for ref in item["record"]["source_refs"]}
        missing = [source for source in ("S01", "S02") if source not in found]
        if missing:
            lines.extend(["", f"对照不完整：{', '.join(missing)} 在当前全量结构化记录中没有命中。"])

    for item in results:
        lines.extend(["", *record_block(item)])
    lines.extend([
        "",
        "## 解释边界",
        "",
        "上述功效、用途和参数均是原书内容的来源受限转述；临床证据尚未评估。‘原书未列明’不等于‘没有禁忌’。",
    ])
    return "\n".join(lines) + "\n", results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--query", required=True)
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--json", action="store_true", help="Emit answer and matched IDs as JSON")
    args = parser.parse_args()
    if args.top_k < 1:
        parser.error("--top-k must be at least 1")
    try:
        answer, results = format_answer(args.query, compare=args.compare, top_k=args.top_k)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps({
            "query": args.query,
            "compare": args.compare,
            "matched_ids": [item["record"]["id"] for item in results],
            "answer": answer,
        }, ensure_ascii=False, indent=2))
    else:
        print(answer, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
