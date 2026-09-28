#!/usr/bin/env python3
"""Build a readable, source-bounded male-health self-care answer."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

from search import citation, load_records


SKILL_ROOT = Path(__file__).resolve().parents[1]
GUIDE_IMAGE = SKILL_ROOT / "assets" / "guides" / "low-risk-massage.png"
GUIDE_IMAGES = {
    "erectile": SKILL_ROOT / "assets" / "guides" / "erectile-support.png",
    "premature": SKILL_ROOT / "assets" / "guides" / "premature-relaxation.png",
    "nocturnal": SKILL_ROOT / "assets" / "guides" / "nocturnal-relaxation.png",
    "fatigue": SKILL_ROOT / "assets" / "guides" / "libido-fatigue-recovery.png",
    "fertility": SKILL_ROOT / "assets" / "guides" / "fertility-wellness.png",
    "low_back": SKILL_ROOT / "assets" / "guides" / "low-back-relaxation.png",
    "generic": GUIDE_IMAGE,
}

ACUTE_TERMS = {
    "剧痛", "突发疼痛", "睾丸痛", "睾丸疼", "肿胀", "红肿", "出血", "流血", "破皮",
    "外伤", "受伤", "麻木", "昏厥", "晕厥", "呼吸困难", "胸痛", "高热",
}

TOPICS = (
    (("睾丸炎",), "十四、睾丸炎", "睾丸炎相关不适"),
    (("不射精", "射不出"), "十三、不射精", "不射精"),
    (("阴茎短小", "尺寸小", "太短"), "十二、阴茎短小", "对阴茎尺寸的困扰"),
    (("睾丸发育",), "十一、睾丸发育不良", "睾丸发育相关困扰"),
    (("房劳", "性生活后疲劳", "纵欲", "过度性生活"), "十、房劳过度", "性生活后疲劳"),
    (("更年期",), "九、男子更年期性欲减退", "男性更年期阶段的性欲减退"),
    (("早衰",), "八、早衰", "早衰相关困扰"),
    (("不育", "备孕", "生育"), "七、不育症", "男性生育相关困扰"),
    (("精液", "精子"), "六、精液异常", "精液或精子相关困扰"),
    (("性欲低", "性欲减退", "性功能减退"), "五、性功能减退", "性欲或性功能减退"),
    (("腰痛", "肾虚腰痛", "腰酸"), "四、肾虚腰痛", "腰酸腰痛"),
    (("早泄", "射得快", "时间短"), "三、早泄", "射精控制时间短"),
    (("遗精", "梦遗"), "二、遗精", "遗精"),
    (("阳痿", "勃起", "不举", "举而不坚", "硬度", "硬不起来"), "一、阳痿", "勃起困难或勃起不稳"),
)

PRACTICAL_POSITIVE = {
    "鸡蛋": 6, "萝卜": 5, "虾": 4, "番茄": 5, "牛肉": 3, "鸡肉": 3,
    "猪肉": 3, "莲子": 3, "花生": 3, "黑豆": 3, "银耳": 4, "木耳": 4,
    "冬瓜": 4, "绿豆": 4, "山药": 2, "红枣": 2, "栗子": 3, "鸭肉": 2,
}

PRACTICAL_PENALTIES = {
    "鞭": 20, "睾丸": 20, "外肾": 20, "狗肾": 20, "胎盘": 20, "河车": 20,
    "水蛭": 20, "海马": 10, "蛇": 10, "猫肉": 12, "狗肉": 12, "麻雀": 8,
    "鹿茸": 7, "附片": 15, "仙茅": 8, "肉苁蓉": 6, "菟丝子": 6, "巴戟": 6,
    "虫草": 5, "药包": 4,
}

# Prefer comparatively familiar food preparations before rare-animal or heavily
# medicinal recipes. This is a usability ranking, not a clinical efficacy rank.
PREFERRED_TITLES = {
    "一、阳痿": ("海米萝卜汤", "海松子鸡蛋汤"),
    "二、遗精": ("莲子黑豆羊肉汤", "核桃花生猪尾汤"),
    "三、早泄": ("瘦肉莲子汤", "花生蚕豆汤"),
    "四、肾虚腰痛": ("脊肉薏苡仁汤", "栗子猪尾汤"),
    "五、性功能减退": ("龙井对虾汤", "鲢鱼姜椒汤"),
    "六、精液异常": ("淮山药鳝鱼汤", "鲢鱼山药杞子汤"),
    "七、不育症": ("三鲜银耳汤", "木耳汤"),
    "八、早衰": ("龙眼牛肉汤", "莲藕猪蹄章鱼汤"),
    "九、男子更年期性欲减退": ("百合熟地鸡蛋汤", "红萝卜猪蹄汤"),
    "十、房劳过度": ("蛎肉海带丝汤", "海参鸭肉汤"),
    "十一、睾丸发育不良": ("杜仲鹌鹑汤", "巴戟杞子羊肉汤"),
    "十二、阴茎短小": ("泥鳅河虾汤", "黄精鸭肉海参汤"),
    "十三、不射精": ("葱炖猪蹄汤", "桃仁墨鱼汤"),
    "十四、睾丸炎": ("绿豆煲鸽汤", "冬瓜生鱼汤"),
}


def identify_topic(issue: str) -> tuple[str | None, str]:
    for aliases, chapter, label in TOPICS:
        if any(alias in issue for alias in aliases):
            return chapter, label
    return None, "男性健康困扰"


def is_acute(issue: str) -> bool:
    return any(term in issue for term in ACUTE_TERMS)


def recipe_score(record: dict) -> tuple[int, str]:
    fields = record.get("fields", {})
    text = f"{record.get('title_source', '')} {fields.get('ingredients', '')}"
    score = sum(value for term, value in PRACTICAL_POSITIVE.items() if term in text)
    score -= sum(value for term, value in PRACTICAL_PENALTIES.items() if term in text)
    if record.get("human_review", {}).get("status") == "human_checked":
        score += 1
    return score, record["id"]


def select_recipes(records: Iterable[dict], chapter: str | None, limit: int = 2) -> list[dict]:
    candidates = [
        record for record in records
        if record.get("record_type") == "recipe"
        and (chapter is None or chapter in record.get("chapter_path", []))
    ]
    candidates.sort(key=recipe_score, reverse=True)
    by_title = {record["title_source"]: record for record in candidates}
    selected = [by_title[title] for title in PREFERRED_TITLES.get(chapter or "", ()) if title in by_title]
    selected_ids = {record["id"] for record in selected}
    selected.extend(record for record in candidates if record["id"] not in selected_ids)
    return selected[:limit]


def recipe_block(record: dict, number: int, show_sources: bool) -> list[str]:
    fields = record.get("fields", {})
    contraindications = fields.get("contraindications", "原书未列明")
    if contraindications == "原书未列明":
        contraindications = "原书未列明；这表示未知，不表示没有禁忌。"
    lines = [
        f"### 方案 {number}：{record['title_source']}",
        "",
        f"- 原料：{fields.get('ingredients', '原书信息不完整。')}",
        f"- 做法：{fields.get('preparation', '原书信息不完整。')}",
        f"- 原书用法：{fields.get('usage', '原书未列明。')}",
        f"- 原书所述用途：{fields.get('claimed_effects', '原书未列明。')}",
        f"- 宜忌：{contraindications}",
        "- **本次试用节奏（助手建议，不是原书疗程）**：只选这一道，随一顿正餐 **每天 1 次**，先试 **3 天**；不要因为原书写有“每日多次”就自行加量。",
        "- **第 3 天回访**：告诉我是否胀气、反酸、恶心、腹痛、腹泻、便秘、食欲变化或皮疹，以及这项困扰有没有变化；耐受良好才继续同样频次至 **第 7 天**，第 7 天再次反馈后再决定停用、保持或换一道。",
        "- **立即停止**：任何过敏表现、明显胃肠不适或原有症状加重，都停止这道食疗；不要与另一道方案叠加测试。",
    ]
    if show_sources:
        lines.append(f"- 来源：{citation(record)}")
        review = record.get("human_review", {}).get("status", record["extraction_review"]["status"])
        lines.append(f"- 来源转录审核：{review}；临床证据：{record['clinical_evidence_status']}")
    return lines


def massage_profile(chapter: str | None) -> str:
    return {
        "一、阳痿": "erectile",
        "二、遗精": "nocturnal",
        "三、早泄": "premature",
        "四、肾虚腰痛": "low_back",
        "五、性功能减退": "fatigue",
        "六、精液异常": "fertility",
        "七、不育症": "fertility",
        "八、早衰": "fatigue",
        "九、男子更年期性欲减退": "fatigue",
        "十、房劳过度": "fatigue",
        "十一、睾丸发育不良": "fertility",
        "十二、阴茎短小": "fertility",
        "十三、不射精": "premature",
    }.get(chapter or "", "generic")


def guide_image(chapter: str | None) -> Path:
    return GUIDE_IMAGES[massage_profile(chapter)]


def massage_block(issue: str, chapter: str | None) -> list[str]:
    if "睾丸炎" in issue or ("睾丸" in issue and any(term in issue for term in ("痛", "肿", "热"))):
        return [
            "## 按摩处理",
            "",
            "这类描述不适合做局部按摩，也不要热敷、强压或自行推拿。先做线下检查；本方案不提供睾丸或会阴操作。",
        ]
    profile = massage_profile(chapter)
    common_end = [
        "",
        "共同边界与不在家做：只用舒适力度；出现疼痛、麻木、头晕、心悸或其他不适立即停止。不要做阴茎或会阴推捋、强烈酸痛按压、腰椎斜扳或颈椎牵引。",
    ]
    if profile == "erectile":
        return [
            "## 居家低风险按摩（勃起困扰，约 8～10 分钟）",
            "",
            "下面三步来自原书阳痿一般按摩中的非私密、低风险部分；已排除会阴、阴茎和脊柱操作。",
            "1. **揉摩小腹**：手掌放在肚脐下方，缓慢画圈 3～5 分钟，以温暖舒适为限。",
            "2. **推擦腹部中线**：从胸骨中部向下轻推至下腹，重复 10～20 遍；到耻骨上方即停止。",
            "3. **按揉涌泉**：在脚底前 1/3 附近的凹陷处轻柔画圈，每侧 30～60 秒。",
            *common_end,
        ]
    if profile == "premature":
        return [
            "## 放松辅助（早泄／不射精，约 6～8 分钟）",
            "",
            "按摩书没有把这套动作作为早泄或不射精的针对性治疗；以下只用于降低紧张和身体放松。",
            "1. **慢呼吸**：坐稳，一手放在上腹，缓慢呼吸 2 分钟，不屏气。",
            "2. **轻揉小腹**：隔着衣物缓慢画圈 2～3 分钟，只求放松和温热。",
            "3. **腕部放松**：在腕横纹附近轻揉，每侧 30～60 秒；找不准位置就跳过。",
            *common_end,
        ]
    if profile == "nocturnal":
        return [
            "## 睡前放松（遗精困扰，约 6～8 分钟）",
            "",
            "按摩书没有遗精的针对性按摩方案；以下仅作睡前放松。",
            "1. **慢呼吸**：睡前坐稳或仰卧，缓慢呼吸 2 分钟。",
            "2. **双手温腹**：搓热双手，隔着衣物轻覆下腹 2～3 分钟，不向下按压私密部位。",
            "3. **轻揉足底**：轻柔按摩脚底，每侧约 1 分钟，以温暖为限。",
            *common_end,
        ]
    if profile == "fatigue":
        return [
            "## 恢复辅助（性欲低或性生活后疲劳，约 6～8 分钟）",
            "",
            "这不是针对病因的治疗，只用于一般放松；明显或持续疲劳需要另查原因。",
            "1. **胸腹轻推**：坐稳，用掌面从胸骨中部轻推到上腹，重复 8～10 遍，不压迫胸口。",
            "2. **腕部轻揉**：腕横纹附近轻揉，每侧 30～60 秒。",
            "3. **足底放松**：轻揉足底，每侧约 1 分钟；之后休息并正常补水。",
            *common_end,
        ]
    if profile == "fertility":
        extra = "按摩不能增大阴茎。" if chapter == "十二、阴茎短小" else "按摩不能提高精子质量或替代生育检查。"
        return [
            "## 放松辅助（备孕、精液或发育困扰，约 5～7 分钟）",
            "",
            f"按摩书没有针对这些问题的已验证方案；这里只提供一般放松。{extra}",
            "1. **慢呼吸**：坐稳，缓慢呼吸 2 分钟。",
            "2. **腕部轻揉**：腕横纹附近轻揉，每侧 30～60 秒。",
            "3. **足底放松**：轻揉足底，每侧约 1 分钟。",
            *common_end,
        ]
    if profile == "low_back":
        return [
            "## 腰酸的温和放松（约 5～7 分钟）",
            "",
            "不采用原书中的腰椎斜扳等专业手法。腿部放射痛、麻木无力、外伤后疼痛或大小便异常时不要自行按摩。",
            "1. **温热腰侧**：双手搓热，轻覆并缓慢揉动腰椎两侧肌肉 2～3 分钟，避开脊柱正中。",
            "2. **坐姿呼吸**：保持腰背中立，缓慢呼吸 2 分钟，不扭转腰部。",
            "3. **足底放松**：轻揉足底，每侧约 1 分钟。",
            *common_end,
        ]
    return [
        "## 一般放松按摩（约 5～7 分钟）",
        "",
        "当前描述没有对应到按摩书的明确问题类型，因此只提供一般放松，不写成针对性治疗。",
        "1. **慢呼吸**：坐稳，缓慢呼吸 2 分钟。",
        "2. **轻揉小腹**：隔着衣物轻柔画圈 2～3 分钟。",
        "3. **轻揉足底**：每侧约 1 分钟。",
        *common_end,
    ]


def build_answer(
    issue: str,
    records: Iterable[dict] | None = None,
    show_sources: bool = False,
    recipe_limit: int = 2,
) -> tuple[str, list[dict]]:
    if not issue.strip():
        raise ValueError("issue must not be empty")
    if recipe_limit < 1:
        raise ValueError("recipe_limit must be at least 1")
    available = list(records if records is not None else load_records())
    chapter, label = identify_topic(issue)

    lines = ["# 男性问题中医调节方案", "", "## 先理解你的问题", ""]
    if is_acute(issue):
        lines.extend([
            f"你描述的是“{issue}”，其中包含疼痛、肿胀、出血、外伤或其他急性异常信号。此时不适合继续按摩，也不应靠食疗拖延检查。请停止刺激患处并尽快线下就医。",
            "",
            "本轮不生成食疗或按摩步骤。",
        ])
        return "\n".join(lines) + "\n", []

    lines.extend([
        f"你描述的是“{issue}”。本助手把它暂时归入“{label}”来检索两本原书，但这不是诊断，也不替你判断病因。",
        "",
        "## 可选食疗（一次选一道，不要同时叠加）",
        "",
    ])
    recipes = select_recipes(available, chapter, recipe_limit)
    if not recipes:
        lines.append("两本原书的结构化记录中没有找到足够可靠的对应食疗方，因此不补写。")
    else:
        for index, record in enumerate(recipes, start=1):
            lines.extend(recipe_block(record, index, show_sources))
            lines.append("")

    lines.extend(massage_block(issue, chapter))
    selected_guide = guide_image(chapter)
    if selected_guide.is_file() and "睾丸炎" not in issue:
        lines.extend([
            "",
            "## 按摩定位示意",
            "",
            f"![与当前问题对应的按摩示意]({selected_guide})",
            "",
            "配图是用户版定位示意，不是原书整页截图；动作以本回答的文字步骤和舒适力度为准。",
        ])
    lines.extend([
        "",
        "## 使用前先看",
        "",
        "- 原书中的食疗用途与按摩说法尚未在本资料库中完成临床有效性评价，不能替代检查或治疗。",
        "- 对任一原料过敏，或有慢性病、长期用药、特殊饮食限制时，不要直接照做；先核对食材与用药限制。含酒、药材或不熟悉食材的方案，不按默认节奏自行试用。",
        "- 症状若持续、反复或突然出现，尤其伴随晨勃明显变化、疼痛、排尿异常或全身不适，应做病因评估。",
        "",
        "回访时请直接写：方案名、已吃几天、每天几次、消化情况、症状变化、是否有不适、晨勃是否变化，以及慢性病和长期用药。我会据此只在“停用／维持每天 1 次／换一道”之间调整，不把食疗当成诊断或治疗替代。",
    ])
    return "\n".join(lines) + "\n", recipes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issue", required=True, help="The user's own description of the problem")
    parser.add_argument("--show-sources", action="store_true", help="Append record citations and review status")
    parser.add_argument("--recipe-limit", type=int, default=2)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        answer, recipes = build_answer(
            args.issue,
            show_sources=args.show_sources,
            recipe_limit=args.recipe_limit,
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.json:
        print(json.dumps({
            "issue": args.issue,
            "selected_recipe_ids": [record["id"] for record in recipes],
            "answer": answer,
        }, ensure_ascii=False, indent=2))
    else:
        print(answer, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
