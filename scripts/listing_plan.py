#!/usr/bin/env python3
"""
listing_plan.py

Amazon Listing Agent 的结构化计划层。

职责：
1. 接收 Agent 生成的 Listing Plan JSON
2. 校验 Product Evidence / Selling Points / Campaign Style / H1-H5
3. 自动读取 references/templates 下的模板，检查 Template ID 是否存在
4. 阻止明显的 unsupported claims 进入图片计划
5. 输出规范化后的 listing_plan.json

注意：
- 本脚本不负责“看图”和“理解产品”。
- 图片理解、卖点提取、模板选择仍由 Agent / 多模态模型完成。
- Python 在这里负责结构化、校验和防止后续步骤拿到脏数据。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


DEFAULT_MAX_IMAGES = 5
DEFAULT_OUTPUT = "listing_plan.json"

# 高风险 Claims：没有证据时不允许进入最终图片计划。
HIGH_RISK_CLAIMS = [
    "tpu",
    "silicone",
    "leather",
    "stainless steel",
    "shockproof",
    "drop protection",
    "waterproof",
    "ip rating",
    "scratch resistant",
    "reinforced corners",
    "camera protection",
    "military grade",
    "magsafe",
    "fast charging",
    "battery capacity",
    "compatible",
    "compatibility",
    "防摔",
    "防水",
    "防刮",
    "减震",
    "加厚",
    "强化边角",
    "摄像头保护",
    "精准开孔",
    "兼容",
    "材质",
    "尺寸",
    "重量",
    "厚度",
]

REQUIRED_IMAGE_FIELDS = [
    "id",
    "purpose",
    "template",
]

VALID_EVIDENCE_LEVELS = {
    "confirmed",
    "visual_confirmed",
    "source_confirmed",
    "inferred",
    "unknown",
}

VALID_IMAGE_IDS = {"H1", "H2", "H3", "H4", "H5"}


def fail(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        fail(f"找不到输入文件：{path}")

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"JSON 格式错误：{exc}")

    if not isinstance(data, dict):
        fail("Listing Plan 根节点必须是 JSON object。")

    return data


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def find_template_dir(project_root: Path) -> Path:
    candidates = [
        project_root / ".claude" / "skills" / "ecom-details-image"
        / "references" / "templates",
        project_root / "references" / "templates",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    fail(
        "找不到 templates 目录。"
        "请从项目根目录运行，或使用 --template-dir 指定目录。"
    )


def load_template_ids(template_dir: Path) -> set[str]:
    return {
        p.name
        for p in template_dir.glob("*.json")
        if p.is_file()
    }


def normalize_evidence_level(value: Any) -> str:
    if value is None:
        return "unknown"

    value = str(value).strip().lower().replace(" ", "_")

    aliases = {
        "visual_confirmed": "visual_confirmed",
        "visual": "visual_confirmed",
        "source_confirmed": "source_confirmed",
        "source": "source_confirmed",
        "confirmed": "confirmed",
        "inferred": "inferred",
        "unknown": "unknown",
    }

    return aliases.get(value, "unknown")


def contains_high_risk_claim(text: str) -> list[str]:
    text_lower = text.lower()
    return [claim for claim in HIGH_RISK_CLAIMS if claim in text_lower]


def text_from_value(value: Any) -> str:
    if isinstance(value, str):
        return value

    if isinstance(value, list):
        return " ".join(text_from_value(v) for v in value)

    if isinstance(value, dict):
        return " ".join(
            f"{k} {text_from_value(v)}" for k, v in value.items()
        )

    return str(value)


def validate_product(product: Any, warnings: list[str]) -> dict[str, Any]:
    if not isinstance(product, dict):
        fail("product 必须是 object。")

    product.setdefault("confirmed_features", [])
    product.setdefault("inferred_features", [])
    product.setdefault("unknown_features", [])

    for key in (
        "confirmed_features",
        "inferred_features",
        "unknown_features",
    ):
        if not isinstance(product[key], list):
            fail(f"product.{key} 必须是 array。")

    # confirmed 里的内容如果含高风险 Claim，提醒人工复核。
    confirmed_text = text_from_value(product["confirmed_features"])
    risky = contains_high_risk_claim(confirmed_text)
    if risky:
        warnings.append(
            "confirmed_features 含高风险 Claim，请确认这些信息确实来自用户资料"
            f"或可靠产品资料：{', '.join(risky)}"
        )

    return product


def validate_selling_points(
    selling_points: Any,
    warnings: list[str],
) -> list[dict[str, Any]]:
    if not isinstance(selling_points, list):
        fail("selling_points 必须是 array。")

    normalized = []

    for index, item in enumerate(selling_points, start=1):
        if not isinstance(item, dict):
            fail(f"selling_points[{index}] 必须是 object。")

        feature = str(item.get("feature", "")).strip()
        benefit = str(item.get("benefit", "")).strip()
        proof = str(item.get("visual_proof", "")).strip()
        evidence = normalize_evidence_level(item.get("evidence_level"))

        if not feature:
            fail(f"selling_points[{index}] 缺少 feature。")

        # 没有证据的功能性卖点不允许直接作为事实。
        risky = contains_high_risk_claim(feature + " " + benefit)

        if risky and evidence in {"inferred", "unknown"}:
            warnings.append(
                f"卖点 #{index} 含高风险 Claim 且证据等级为 {evidence}，"
                f"后续不得作为功能性事实使用：{', '.join(risky)}"
            )

        normalized.append(
            {
                "feature": feature,
                "benefit": benefit,
                "visual_proof": proof,
                "evidence_level": evidence,
            }
        )

    return normalized


def validate_campaign_style(
    campaign_style: Any,
) -> dict[str, Any]:
    if not isinstance(campaign_style, dict):
        fail("campaign_style 必须是 object。")

    defaults = {
        "visual_direction": "",
        "color_palette": [],
        "temperature": "",
        "typography": "",
        "background": "",
        "lighting": "",
        "layout": "",
        "product_presentation": "",
        "whitespace": "",
        "forbidden_drift": [],
    }

    for key, default in defaults.items():
        campaign_style.setdefault(key, default)

    return campaign_style


def validate_images(
    images: Any,
    template_ids: set[str],
    warnings: list[str],
    max_images: int,
) -> list[dict[str, Any]]:
    if not isinstance(images, list):
        fail("images 必须是 array。")

    if len(images) > max_images:
        fail(
            f"当前最多允许 {max_images} 张图片，"
            f"但 Listing Plan 包含 {len(images)} 张。"
        )

    normalized = []
    seen_ids: set[str] = set()

    for index, image in enumerate(images, start=1):
        if not isinstance(image, dict):
            fail(f"images[{index}] 必须是 object。")

        for field in REQUIRED_IMAGE_FIELDS:
            if not image.get(field):
                fail(f"images[{index}] 缺少必填字段：{field}")

        image_id = str(image["id"]).upper().strip()
        template = Path(str(image["template"])).name

        if image_id not in VALID_IMAGE_IDS:
            fail(
                f"images[{index}] 的 id 为 {image_id}，"
                f"必须属于 {sorted(VALID_IMAGE_IDS)}。"
            )

        if image_id in seen_ids:
            fail(f"图片 ID 重复：{image_id}")
        seen_ids.add(image_id)

        if template not in template_ids:
            fail(
                f"{image_id} 使用不存在的模板：{template}"
            )

        # 每张图补齐后续 Prompt / QA 需要的字段。
        image["id"] = image_id
        image["template"] = template
        image.setdefault("template_name", "")
        image.setdefault("selling_point", "")
        image.setdefault("angle", "")
        image.setdefault("composition", "")
        image.setdefault("scene", "")
        image.setdefault("allowed_text", [])
        image.setdefault("forbidden_claims", [])
        image.setdefault("negative_constraints", [])
        image.setdefault("aspect_ratio", "1:1")

        # 检查 allowed_text 中是否混入明显高风险 Claim。
        allowed_text = text_from_value(image["allowed_text"])
        risky = contains_high_risk_claim(allowed_text)
        if risky:
            warnings.append(
                f"{image_id} 的 allowed_text 含高风险 Claim，"
                f"建议删除或提供 Source Confirmed 证据：{', '.join(risky)}"
            )

        normalized.append(image)

    # Amazon 默认 H1-H5 顺序。
    order = {"H1": 1, "H2": 2, "H3": 3, "H4": 4, "H5": 5}
    normalized.sort(key=lambda x: order[x["id"]])

    return normalized


def validate_main_image(images: list[dict[str, Any]], warnings: list[str]) -> None:
    h1 = next((item for item in images if item["id"] == "H1"), None)

    if h1 is None:
        warnings.append("Listing Plan 没有 H1。Amazon 主图通常应作为第一张图。")
        return

    allowed_text = h1.get("allowed_text", [])
    if allowed_text:
        warnings.append("H1 主图存在 allowed_text，Amazon 主图应默认无文字。")

    forbidden = text_from_value(h1.get("forbidden_claims", []))
    if contains_high_risk_claim(forbidden):
        # forbidden_claims 出现风险词本身是合理的，但这里只做信息提示。
        pass


def build_plan(
    raw: dict[str, Any],
    template_ids: set[str],
    max_images: int,
) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []

    raw.setdefault("product", {})
    raw.setdefault("selling_points", [])
    raw.setdefault("conversion_driver", {})
    raw.setdefault("campaign_style", {})
    raw.setdefault("images", [])
    raw.setdefault("assumptions", [])

    product = validate_product(raw["product"], warnings)
    selling_points = validate_selling_points(raw["selling_points"], warnings)
    campaign_style = validate_campaign_style(raw["campaign_style"])
    images = validate_images(
        raw["images"],
        template_ids,
        warnings,
        max_images,
    )
    validate_main_image(images, warnings)

    conversion_driver = raw["conversion_driver"]
    if not isinstance(conversion_driver, dict):
        fail("conversion_driver 必须是 object。")

    conversion_driver.setdefault("primary", "")
    conversion_driver.setdefault("secondary", [])

    assumptions = raw["assumptions"]
    if not isinstance(assumptions, list):
        fail("assumptions 必须是 array。")

    plan = {
        "schema_version": "1.0",
        "agent": "Amazon Listing Visual Strategist",
        "product": product,
        "selling_points": selling_points,
        "conversion_driver": conversion_driver,
        "campaign_style": campaign_style,
        "images": images,
        "assumptions": assumptions,
        "qa": {
            "status": "READY_WITH_WARNINGS" if warnings else "READY",
            "warnings": warnings,
        },
    }

    return plan, warnings


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate and normalize Amazon Listing Plan JSON."
    )
    parser.add_argument(
        "input",
        help="Agent 输出的 Listing Plan JSON，例如 listing_plan_draft.json",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"输出文件，默认：{DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--project-root",
        default=".",
        help="项目根目录，默认当前目录",
    )
    parser.add_argument(
        "--template-dir",
        default=None,
        help="模板目录；不指定时自动寻找 references/templates",
    )
    parser.add_argument(
        "--max-images",
        type=int,
        default=DEFAULT_MAX_IMAGES,
        help=f"最多图片数量，默认 {DEFAULT_MAX_IMAGES}",
    )

    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()

    if args.template_dir:
        template_dir = Path(args.template_dir).resolve()
    else:
        template_dir = find_template_dir(project_root)

    template_ids = load_template_ids(template_dir)

    if not template_ids:
        fail(f"模板目录为空：{template_dir}")

    raw = load_json(Path(args.input).resolve())
    plan, warnings = build_plan(
        raw,
        template_ids,
        args.max_images,
    )

    output = Path(args.output).resolve()
    save_json(output, plan)

    print("Listing Plan 校验完成")
    print(f"模板数量：{len(template_ids)}")
    print(f"图片数量：{len(plan['images'])}")
    print(f"QA 状态：{plan['qa']['status']}")
    print(f"输出：{output}")

    if warnings:
        print("\nWarnings:")
        for warning in warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
