#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Amazon Listing Prompt Builder V2.5

Purpose
-------
Compile a validated listing_plan.json + the selected template JSON files
into production-oriented image prompts.

V2.5 focuses on four hard requirements:
1. Evidence Compiler:
   - Confirmed facts can enter factual prompt content.
   - Inferred / Unknown facts cannot become factual claims.
   - Planner-selected selling points are revalidated before use.
2. Template Compiler:
   - Reads the actual selected template JSON.
   - Extracts its composition/layout/elements/text/camera/style/constraints.
   - Places those rules into the final prompt as template-specific instructions.
3. Role Compiler:
   - H1-H5 have distinct Amazon image roles.
   - H1 never receives feature-infographic copy rules.
   - H4 defaults to self-differentiation / multi-angle proof when competitor
     evidence is unavailable.
   - H1 product occupancy is NOT hard-coded to a fixed percentage.

4. Template Adapter:
   - Supports the actual prompt_template/defaults/variants/category_tips schema used by the 25 source templates.
   - Fails loudly if a selected template produces zero structured rules.

Important
---------
This script does NOT analyze product images and does NOT invent product facts.
The validated listing_plan.json is the source of truth.

Usage
-----
From project root:

    python scripts/prompt_builder.py scripts/listing_plan.json

Optional:

    python scripts/prompt_builder.py scripts/listing_plan.json -o prompts
    python scripts/prompt_builder.py scripts/listing_plan.json \
        --templates references/templates

Outputs
-------
    prompts/H1.txt
    prompts/H2.txt
    prompts/H3.txt
    prompts/H4.txt
    prompts/H5.txt
    prompts/listing_prompts.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


VERSION = "2.5.2"
DEFAULT_PLAN = Path("scripts/listing_plan.json")
DEFAULT_TEMPLATE_DIR = Path("references/templates")
DEFAULT_OUTPUT_DIR = Path("prompts")


# ============================================================
# Basic utilities
# ============================================================

def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def first(data: Dict[str, Any], keys: Iterable[str], default: str = "") -> str:
    for key in keys:
        value = clean(data.get(key))
        if value:
            return value
    return default


def as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def dedupe(values: Iterable[str]) -> List[str]:
    result = []
    seen = set()
    for value in values:
        value = clean(value)
        if not value:
            continue
        key = value.casefold()
        if key not in seen:
            seen.add(key)
            result.append(value)
    return result


# ============================================================
# Plan accessors
# ============================================================

def product_block(plan: Dict[str, Any]) -> Dict[str, Any]:
    value = plan.get("product", {})
    return value if isinstance(value, dict) else {}


def style_lock(plan: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("campaign_style", "campaign_style_lock", "style_lock"):
        value = plan.get(key)
        if isinstance(value, dict):
            return value
    return {}


def images_from_plan(plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    value = plan.get("images", [])
    if not isinstance(value, list):
        return []
    return [x for x in value if isinstance(x, dict)]


def image_id(image: Dict[str, Any]) -> str:
    return first(image, ["image_id", "id", "slot", "name"], "IMAGE")


def template_id(image: Dict[str, Any]) -> str:
    return first(image, ["template_id", "template", "template_name"])


def template_file(image: Dict[str, Any]) -> str:
    return first(image, ["template_file", "template_path"])


def image_role(image: Dict[str, Any]) -> str:
    return first(image, ["role", "image_role"], "Amazon Listing Image")


def image_purpose(image: Dict[str, Any]) -> str:
    return first(
        image,
        ["amazon_purpose", "purpose", "listing_purpose"],
        "Amazon Listing image",
    )


def primary_selling_point(image: Dict[str, Any]) -> str:
    return first(
        image,
        [
            "primary_selling_point",
            "selling_point",
            "primary_benefit",
            "key_message",
        ],
    )


def image_camera(image: Dict[str, Any]) -> str:
    return first(
        image,
        ["camera_view_angle", "camera_angle", "view_angle", "angle"],
    )


def image_composition(image: Dict[str, Any]) -> str:
    return first(
        image,
        ["composition", "visual_direction", "scene"],
    )


def image_text(image: Dict[str, Any]) -> str:
    return first(
        image,
        ["text", "text_rule", "copy_direction"],
    )


def image_reference(image: Dict[str, Any]) -> str:
    return first(
        image,
        ["product_reference", "reference_image", "reference"],
        "Use the supplied product reference image as the primary identity source.",
    )


# ============================================================
# Evidence Compiler
# ============================================================

HIGH_RISK_RE = re.compile(
    r"""
    (
        waterproof|water[- ]resistant|splash[- ]resistant|ip\d+|
        battery|battery life|playtime|hours?|
        watt|watts|output power|driver specification|
        bluetooth|wi[- ]fi|wireless|protocol|pairing|app|
        certified|certification|guarantee|warranty|
        medical|clinically|safe|safety|
        shockproof|drop[- ]proof|dustproof|
        compatible|compatibility|
        dimensions?|weight|kilograms?|kg|grams?|g|mm|cm|inch|
        best|#1|number one|top[- ]selling|
        review|rating|award|ranking|sales|
        premium performance|high[- ]power
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)


def point_text(point: Any) -> str:
    if isinstance(point, dict):
        return first(
            point,
            ["text", "selling_point", "claim", "benefit", "description"],
        )
    return clean(point)


def point_evidence(point: Any) -> str:
    if isinstance(point, dict):
        return first(
            point,
            ["evidence", "evidence_level", "confidence", "status", "source"],
        ).casefold()
    return ""


def evidence_rank(point: Any) -> int:
    evidence = point_evidence(point)
    if evidence in {
        "confirmed",
        "visual_confirmed",
        "source_confirmed",
        "user_confirmed",
        "verified",
    }:
        return 3
    if evidence in {"inferred", "inference"}:
        return 1
    if evidence in {"unknown", "unverified"}:
        return 0
    # Some existing plans store simple strings without an evidence field.
    # Those are NOT automatically promoted to hard facts.
    return 0


# V2.5.2 semantic safety filters
# These are intentionally conservative: marketing language is not treated as
# confirmed merely because the planner tagged it visual_confirmed.

# V2.5.2: separate confirmed visual facts from confirmed marketing/selling points.
# A visible fact can be used to drive composition or a factual visual label,
# without being promoted into an unsupported performance/benefit claim.
VISUAL_FACT_PATTERNS = [
    r"\bwoven\b", r"\bfabric\b", r"\bmesh\b", r"\blogo\b", r"\bbutton\b",
    r"\bcontrol\b", r"\bcarry loop\b", r"\bloop\b", r"\btop panel\b",
    r"\brounded rectangular\b", r"\bsoft edges\b", r"\bmatte\b",
    r"\bteal\b", r"\bcolorway\b", r"\boutline\b", r"\btexture\b",
    r"\bmaterial\b", r"\bseam\b", r"\bvisible\b", r"\bfront face\b"
]

FUNCTIONAL_CLAIM_PATTERNS = [
    r"\bwaterproof\b", r"\bsplash[- ]?proof\b", r"\bbluetooth\b",
    r"\bbattery\b", r"\bplaytime\b", r"\b\d+\s*(?:h|hours?|mah|w|watts?|db)\b",
    r"\boutput power\b", r"\bconnect(?:s|ed|ivity)?\b", r"\bwireless\b",
    r"\bcompatible\b", r"\bperformance\b", r"\bcertif(?:ied|ication)\b",
    r"\brating\b", r"\bip\d{2}\b", r"\bportable\b", r"\bhands[- ]?free\b",
    r"\bwithout (?:reaching|using)\b", r"\bchange tracks\b", r"\badjust volume\b",
    r"\bpremium\b", r"\bperfect\b", r"\bideal\b", r"\bwherever\b"
]

def evidence_usage_class(text_value):
    """Return one of: visual_fact, functional_claim, neutral."""
    s = str(text_value or "").strip().lower()
    if any(re.search(p, s, re.I) for p in FUNCTIONAL_CLAIM_PATTERNS):
        return "functional_claim"
    if any(re.search(p, s, re.I) for p in VISUAL_FACT_PATTERNS):
        return "visual_fact"
    return "neutral"

def build_visual_evidence_block(confirmed_facts, max_items=6):
    """
    V2.5.2: confirmed visual facts are usable as image evidence even when
    no selling point survives the marketing/claim gate.
    """
    usable = []
    seen = set()
    for fact in confirmed_facts or []:
        value = str(fact).strip()
        if not value:
            continue
        if evidence_usage_class(value) != "visual_fact":
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        usable.append(value)
        if len(usable) >= max_items:
            break

    lines = ["VISUAL EVIDENCE — CONFIRMED AND USABLE:"]
    if not usable:
        lines.append("- None.")
    else:
        lines.extend(f"- {x}" for x in usable)
    lines.extend([
        "- These are confirmed visible/product attributes, not independent performance claims.",
        "- They may guide composition, close-ups, labels, arrows, icons or visual proof.",
        "- Do not rewrite them into unsupported benefits, specifications or capabilities."
    ])
    return "\n".join(lines)

MARKETING_INFERENCE_PATTERNS = [
    r"\bany (?:bag|pocket|palm)\b", r"\bwherever\b", r"\bpremium\b",
    r"\bhands?-free\b", r"\bclip\b", r"\bbelt\b", r"\bwithout (?:reaching|using)\b",
    r"\bchange tracks?\b", r"\badjust volume\b", r"\bmusic\b",
    r"\bperfect\b", r"\bideal\b", r"\bfor [a-z]+ users\b", r"\bany desk\b",
    r"\bwherever the day goes\b", r"\bportable\b", r"\bgrab-and-go\b",
    r"\bmodern accent\b", r"\bfits (?:desk|home|shelf|outdoor)\b", r"\bpremium look\b",
]
MARKETING_INFERENCE_RE = re.compile("|".join(MARKETING_INFERENCE_PATTERNS), re.I)

TEMPLATE_UNSAFE_PATTERNS = [
    r"\b(?:fcc|ce|rohs|ul|ip\d{2}|waterproof|water[- ]?resistant)\b",
    r"\b(?:battery|playtime|mah|watts?|wattage|db|decibels?)\b",
    r"\b(?:certif(?:ied|ication)|rating|award|best[- ]seller|#1)\b",
    r"\b(?:competitor|compare with|versus|vs\.?|comparison)\b",
    r"\b(?:review|stars?|5-star|testimonial|sales|sold)\b",
    r"\b(?:formula|ingredient|clinical|medical|therapeutic)\b",
    r"\b(?:price|discount|sale|coupon|limited[- ]time)\b",
]
TEMPLATE_UNSAFE_RE = re.compile("|".join(TEMPLATE_UNSAFE_PATTERNS), re.I)


def sanitize_marketing_claim(text: str) -> Tuple[bool, str]:
    """Return whether a selling point is safe as factual copy."""
    t = clean(text)
    if not t:
        return False, "empty"
    if MARKETING_INFERENCE_RE.search(t):
        return False, "contains inferred benefit/marketing language"
    return True, ""


def template_rule_safe(text: str) -> bool:
    """Template rules are visual recipes, not permission to invent claims."""
    return not TEMPLATE_UNSAFE_RE.search(clean(text))


def role_callout_limit(image_id: str) -> int:
    return {"H1": 0, "H2": 1, "H3": 1, "H4": 0, "H5": 1}.get(image_id.upper(), 1)

def classify_point(point: Any) -> Tuple[str, str]:
    text = point_text(point)
    evidence = point_evidence(point)
    if not text:
        return "BLOCKED", "empty"
    rank = evidence_rank(point)
    if HIGH_RISK_RE.search(text) and rank < 3:
        return "BLOCKED", "high-risk claim without confirmed evidence"
    if evidence in {"unknown", "unverified", "inferred", "inference"}:
        return "BLOCKED", f"evidence={evidence}"
    if rank != 3:
        return "BLOCKED", "no explicit confirmed evidence"
    safe, reason = sanitize_marketing_claim(text)
    if not safe:
        return "BLOCKED", reason
    return "ALLOWED", evidence


def compile_selling_points(plan: Dict[str, Any]) -> Dict[str, Any]:
    raw = plan.get("selling_points", [])
    allowed: List[str] = []
    blocked: List[Dict[str, str]] = []
    for point in as_list(raw):
        text = point_text(point)
        status, reason = classify_point(point)
        if status == "ALLOWED":
            allowed.append(text)
        elif text:
            blocked.append({"text": text, "reason": reason})
    return {"allowed": dedupe(allowed), "blocked": blocked}

def feature_texts(product: Dict[str, Any], key: str) -> List[str]:
    raw = product.get(key, [])
    values = []

    if isinstance(raw, dict):
        raw = list(raw.values())

    for item in as_list(raw):
        if isinstance(item, dict):
            text = first(
                item,
                ["feature", "text", "description", "value", "claim"],
            )
        else:
            text = clean(item)
        if text:
            values.append(text)

    return dedupe(values)


def build_evidence_block(plan: Dict[str, Any]) -> List[str]:
    product = product_block(plan)

    confirmed = feature_texts(product, "confirmed_features")
    inferred = feature_texts(product, "inferred_features")
    unknown = feature_texts(product, "unknown_features")

    points = compile_selling_points(plan)
    allowed_points = points["allowed"]
    blocked_points = points["blocked"]

    lines = [
        "EVIDENCE COMPILER — HARD CLAIM GATE:",
        "Only confirmed evidence may become factual product copy.",
        "",
        "CONFIRMED PRODUCT FACTS — ALLOWED:",
    ]

    if confirmed:
        lines.extend(f"- {x}" for x in confirmed)
    else:
        lines.append("- None explicitly confirmed in the Listing Plan.")

    lines += [
        "",
        "INFERRED PRODUCT FACTS — VISUAL GUIDANCE ONLY:",
    ]
    if inferred:
        lines.extend(f"- {x}" for x in inferred)
    else:
        lines.append("- None.")

    lines += [
        "",
        "UNKNOWN PRODUCT FACTS — DO NOT CLAIM:",
    ]
    if unknown:
        lines.extend(f"- {x}" for x in unknown)
    else:
        lines.append("- None.")

    lines += [
        "",
        "SELLING POINTS — CONFIRMED AND USABLE:",
    ]
    if allowed_points:
        lines.extend(f"- {x}" for x in allowed_points)
    else:
        lines.append("- None.")

    lines += [
        "",
        "SELLING POINTS — BLOCKED FROM FACTUAL COPY:",
    ]
    if blocked_points:
        for item in blocked_points:
            lines.append(f"- {item['text']} [{item['reason']}]")
    else:
        lines.append("- None.")

    lines += [
        "",
        "ENFORCEMENT:",
        "- Never convert inferred information into a product specification.",
        "- Never convert unknown information into a product claim.",
        "- Never invent numbers, certifications, compatibility, performance, reviews, rankings, awards, accessories or safety claims.",
        "- If the selected selling point is blocked, do not repeat it as factual marketing copy.",
    ]

    return lines


# ============================================================
# Template Compiler
# ============================================================

def resolve_template(
    template_dir: Path,
    wanted_id: str,
    wanted_file: str,
) -> Path:
    candidates = []

    if wanted_file:
        name = Path(wanted_file).name
        candidates += [
            template_dir / name,
            template_dir / name.lower(),
        ]

    if wanted_id:
        tid = Path(wanted_id).name
        candidates += [
            template_dir / tid,
            template_dir / f"{tid}.json",
        ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    # Case-insensitive filename/stem matching.
    id_lower = Path(wanted_id).stem.casefold() if wanted_id else ""
    file_lower = Path(wanted_file).name.casefold() if wanted_file else ""

    if template_dir.exists():
        for path in template_dir.glob("*.json"):
            if path.name.casefold() == file_lower:
                return path
            if path.stem.casefold() == id_lower:
                return path

    raise FileNotFoundError(
        f"Template '{wanted_file or wanted_id}' not found in {template_dir}"
    )


TEMPLATE_KEY_GROUPS = {
    "purpose": ["purpose", "amazon_purpose", "usage", "goal"],
    "composition": ["composition", "composition_rules", "scene", "scene_description", "visual_direction", "arrangement"],
    "layout": ["layout", "layout_rules", "grid", "structure", "separators"],
    "elements": ["elements", "required_elements", "components", "visual_elements", "content", "subject", "features", "variation", "props", "setting", "focus_area", "detail"],
    "text": ["text", "text_rules", "copy", "typography", "text_guidelines", "copy_rules", "labels", "data_vis"],
    "camera": ["camera", "camera_angle", "view", "angle", "camera_rules", "viewpoint", "type"],
    "lighting": ["lighting", "light", "lighting_rules"],
    "style": ["style", "visual_style", "aesthetic", "style_rules", "mood", "color_palette", "color_scheme", "color_temperature", "quality"],
    "constraints": ["constraints", "negative", "negative_constraints", "forbidden", "avoid", "restrictions", "anti_ai_tips"],
}


def normalize_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().casefold()).strip("_")


def flatten_scalar_values(value: Any, prefix: str = "") -> List[str]:
    """Flatten template fields without losing semantic key names."""
    out: List[str] = []
    if isinstance(value, str):
        text = clean(value)
        if text:
            out.append(f"{prefix}: {text}" if prefix else text)
    elif isinstance(value, (int, float, bool)):
        out.append(f"{prefix}: {value}" if prefix else str(value))
    elif isinstance(value, list):
        for item in value:
            out.extend(flatten_scalar_values(item, prefix))
    elif isinstance(value, dict):
        for k, v in value.items():
            nk = clean(k)
            out.extend(flatten_scalar_values(v, nk if not prefix else f"{prefix} / {nk}"))
    return out


def find_nested_dicts(obj: Any, wanted_keys: set[str]) -> List[Dict[str, Any]]:
    found: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        normalized = {normalize_key(k) for k in obj.keys()}
        if normalized & wanted_keys:
            found.append(obj)
        for value in obj.values():
            found.extend(find_nested_dicts(value, wanted_keys))
    elif isinstance(obj, list):
        for item in obj:
            found.extend(find_nested_dicts(item, wanted_keys))
    return found


def infer_template_variant(template: Dict[str, Any], image: Dict[str, Any]) -> Optional[str]:
    """Pick a variant only when the Listing Plan clearly asks for it."""
    variants = template.get("variants")
    if not isinstance(variants, dict):
        return None

    haystack = " ".join([
        image_purpose(image),
        image_composition(image),
        image_text(image),
        str(image.get("variant", "")),
        str(image.get("template_variant", "")),
    ]).casefold()

    aliases = {
        "feature-grid": ["feature-grid", "feature grid", "功能标注", "卖点网格", "callout", "feature blocks"],
        "angle-view": ["angle-view", "多角度", "multi-angle", "different angles"],
        "amazon-a-plus": ["amazon-a-plus", "a+", "a plus"],
        "comparison": ["comparison", "对比", "competitor"],
        "texture": ["texture", "材质纹理", "weave", "material"],
        "craftsmanship": ["craftsmanship", "工艺", "stitching", "joint", "precision"],
        "morning": ["morning", "早晨", "morning light"],
        "cozy": ["cozy", "温馨", "comfortable"],
        "outdoor": ["outdoor", "户外", "golden hour"],
        "luxury": ["luxury", "奢华", "premium"],
        "minimal": ["minimal", "极简"],
        "tech": ["tech", "科技感", "technology"],
    }
    for variant_id in variants.keys():
        terms = aliases.get(variant_id, [variant_id.replace("-", " ")])
        if any(term.casefold() in haystack for term in terms):
            return variant_id
    return None


def classify_template_field(key: str, value: Any) -> Optional[str]:
    nk = normalize_key(key)
    for category, keys in TEMPLATE_KEY_GROUPS.items():
        normalized = {normalize_key(k) for k in keys}
        if nk in normalized:
            return category
    # Semantic fallback for fields commonly used by the source templates.
    if any(x in nk for x in ("background", "setting", "scene", "subject", "props", "focus_area", "detail", "features", "variation")):
        return "elements"
    if any(x in nk for x in ("grid", "layout", "separator", "arrangement", "structure")):
        return "layout"
    if any(x in nk for x in ("lighting", "light")):
        return "lighting"
    if any(x in nk for x in ("camera", "view", "angle", "type")):
        return "camera"
    if any(x in nk for x in ("color", "mood", "quality", "aesthetic", "style")):
        return "style"
    if any(x in nk for x in ("label", "text", "copy", "typography", "data_vis")):
        return "text"
    if any(x in nk for x in ("negative", "avoid", "forbidden", "anti_ai", "restriction")):
        return "constraints"
    return None


def extract_template_rules(template: Dict[str, Any], image: Optional[Dict[str, Any]] = None) -> Dict[str, List[str]]:
    """Adapter for the real 25-template schema used by the source library.

    Source templates primarily use prompt_template/defaults/variants/category_tips/
    examples rather than the generic top-level rule keys expected by older versions.
    This adapter normalizes those fields into one internal specification.
    """
    result: Dict[str, List[str]] = {key: [] for key in TEMPLATE_KEY_GROUPS}

    def add(category: str, value: Any, prefix: str = "") -> None:
        if category not in result:
            return
        values = flatten_scalar_values(value, prefix)
        for item in values:
            # Do not let a template example silently introduce claims/specs.
            # Visual structure remains useful; unsafe copy is discarded.
            if category in {"text", "elements", "style", "constraints", "purpose", "composition", "layout", "camera", "lighting"} and not template_rule_safe(item):
                continue
            result[category].append(item)

    # 1) Direct/generic rules, for compatibility with other template libraries.
    for category, keys in TEMPLATE_KEY_GROUPS.items():
        wanted = {normalize_key(k) for k in keys}
        for k, value in template.items():
            if normalize_key(k) in wanted:
                add(category, value, clean(k))

    # 2) Source-library schema: prompt_template is the core visual specification.
    prompt_template = template.get("prompt_template")
    if isinstance(prompt_template, dict):
        for key, value in prompt_template.items():
            category = classify_template_field(key, value)
            if category:
                add(category, value, clean(key))

    # 3) defaults are lower-priority but useful as concrete fallback instructions.
    defaults = template.get("defaults")
    if isinstance(defaults, dict):
        for key, value in defaults.items():
            category = classify_template_field(key, value)
            if category:
                add(category, value, f"default {clean(key)}")

    # 4) Explicit variant requested by the plan, or infer only when unambiguous.
    variants = template.get("variants")
    if isinstance(variants, dict) and image:
        variant_id = image.get("template_variant") or image.get("variant")
        if not variant_id:
            variant_id = infer_template_variant(template, image)
        if variant_id and variant_id in variants:
            variant = variants[variant_id]
            if isinstance(variant, dict):
                desc = variant.get("description")
                if desc:
                    add("style", f"selected variant {variant_id}: {desc}")
                overrides = variant.get("overrides", {})
                if isinstance(overrides, dict):
                    for key, value in overrides.items():
                        category = classify_template_field(key, value)
                        if category:
                            add(category, value, f"variant {variant_id} {clean(key)}")

    # 5) Category-specific guidance: use only when category can be matched.
    category_text = str((image or {}).get("category", "")).casefold()
    category_tips = template.get("category_tips")
    if isinstance(category_tips, dict) and category_text:
        aliases = {
            "electronics": ["electronics", "consumer electronics", "audio", "portable audio", "tech"],
            "audio": ["audio", "speaker", "headphone", "earbud"],
            "beauty": ["beauty", "skincare", "cosmetic"],
            "fashion": ["fashion", "apparel", "clothing"],
            "home": ["home", "household", "furniture"],
            "food": ["food", "grocery", "snack"],
            "sports": ["sports", "fitness", "outdoor"],
            "jewelry": ["jewelry", "jewellery"],
        }
        for key, tip in category_tips.items():
            terms = aliases.get(normalize_key(key), [normalize_key(key).replace("_", " ")])
            if any(term in category_text for term in terms):
                add("elements", f"category tip ({key}): {tip}")

    # 6) Examples are reference-only and are never emitted into production prompts.
    # This prevents placeholder claims, competitor/comparison layouts, specs or badges
    # from leaking from a template example into the generated image instruction.

    anti_ai = template.get("anti_ai_tips")
    if anti_ai:
        add("constraints", anti_ai, "anti-AI guidance")

    for category in result:
        result[category] = dedupe(result[category])

    return result


def template_identity(
    path: Path,
    template: Dict[str, Any],
) -> Tuple[str, str]:
    tid = first(
        template,
        ["template_id", "id", "slug"],
        path.stem,
    )
    name = first(
        template,
        ["name", "template_name", "title"],
        path.stem,
    )
    return tid, name


def build_template_block(
    path: Path,
    template: Dict[str, Any],
    image: Optional[Dict[str, Any]] = None,
) -> List[str]:
    tid, name = template_identity(path, template)
    rules = extract_template_rules(template, image)

    lines = [
        "TEMPLATE COMPILER — SELECTED VISUAL TEMPLATE:",
        f"- Template ID: {tid}",
        f"- Template file: {path.name}",
        f"- Template name: {name}",
        "- The following rules are template-specific and must be followed:",
    ]

    labels = {
        "purpose": "Purpose",
        "composition": "Composition",
        "layout": "Layout",
        "elements": "Required visual elements",
        "text": "Text / typography",
        "camera": "Camera / viewpoint",
        "lighting": "Lighting",
        "style": "Style",
        "constraints": "Template constraints",
    }

    any_rule = False

    for category, label in labels.items():
        values = rules.get(category, [])
        if not values:
            continue

        any_rule = True
        lines.append(f"- {label}:")
        for value in values[:8]:
            lines.append(f"  - {value}")

    if not any_rule:
        raise ValueError(
            f"Template adapter extracted zero visual rules from {path.name}; "
            "refusing to silently generate a generic prompt."
        )

    return lines


# ============================================================
# Role Compiler
# ============================================================

ROLE_RULES: Dict[str, Dict[str, Any]] = {
    "H1": {
        "name": "Amazon Main Image",
        "purpose": "Instant product recognition",
        "rules": [
            "Product-recognition image, not a feature infographic.",
            "Use the main-image background required by the selected template.",
            "No marketing headline, feature callout, badge, rating, review, promotion or decorative prop.",
            "Show the complete product without cropping important parts.",
            "Make the product the dominant visual subject with comfortable margins.",
            "Product scale must be visually appropriate for the category; do not force a fixed percentage of frame occupancy.",
            "Prioritize exact product identity over dramatic composition.",
            "Do not visually imply unsupported performance or specifications.",
        ],
    },
    "H2": {
        "name": "Core Benefit / Feature",
        "purpose": "Communicate one evidence-supported core benefit",
        "rules": [
            "Communicate one primary supported selling point only.",
            "Use visual proof or a clear feature-to-benefit relationship.",
            "Keep the product as the visual anchor.",
            "If the planner-selected selling point is not confirmed, replace it with a confirmed visual feature or remove factual claim language.",
            "Text must be concise and evidence-supported.",
            "Do not stack unrelated benefits.",
        ],
    },
    "H3": {
        "name": "Lifestyle / Usage",
        "purpose": "Show a believable use context",
        "rules": [
            "Show one realistic use context that matches a supported visual/product story.",
            "Lifestyle context must not imply unsupported product capabilities.",
            "Keep product identity and scale visually believable.",
            "Props and environment support the product story and do not compete with it.",
            "Avoid generic stock-photo aesthetics and implausible AI interactions.",
            "Do not use lifestyle context as indirect proof of battery life, waterproofing, connectivity or performance unless confirmed.",
        ],
    },
    "H4": {
        "name": "Differentiation / Multi-Angle Proof",
        "purpose": "Prove a visible differentiator or product structure",
        "rules": [
            "Communicate one clear differentiation or self-comparison axis.",
            "Only compare attributes explicitly supported by the Listing Plan.",
            "Never invent competitors, competitor logos, test results or numerical superiority.",
            "If no verified competitor data exists, use self-differentiation or multi-angle feature proof.",
            "Labels must describe visible/confirmed attributes only.",
            "Do not imply superiority without comparative evidence.",
        ],
    },
    "H5": {
        "name": "Detail / Secondary Benefit",
        "purpose": "Reveal one concrete visible detail",
        "rules": [
            "Reveal one concrete secondary feature, material, control or construction detail.",
            "Use macro/detail composition when appropriate.",
            "Detail must correspond to what is visible or confirmed.",
            "Do not use close-up imagery to imply unsupported engineering specifications.",
            "Keep the Campaign Style Lock consistent with H1-H4.",
        ],
    },
}


def build_role_block(image_id: str, image: Dict[str, Any]) -> List[str]:
    key = image_id.upper()
    role = ROLE_RULES.get(
        key,
        {
            "name": image_role(image),
            "purpose": image_purpose(image),
            "rules": [
                "Follow the Listing Plan purpose.",
                "Preserve product identity and evidence constraints.",
            ],
        },
    )

    lines = [
        f"IMAGE ROLE: {role['name']}",
        f"- Amazon role objective: {role['purpose']}",
        "- Role-specific rules:",
    ]
    lines.extend(f"  - {rule}" for rule in role["rules"])
    limit = role_callout_limit(key)
    if key == "H2":
        lines.append(f"  - Callout budget: {limit} primary benefit; supporting visual evidence may be shown without becoming separate benefit claims.")
    elif key in {"H3", "H5"}:
        lines.append(f"  - Callout budget: at most {limit} evidence-backed callout; keep copy minimal.")
    return lines


# ============================================================
# Style Lock Compiler
# ============================================================

STYLE_FIELDS = [
    ("color_palette", "Color palette"),
    ("color_temperature", "Color temperature"),
    ("typography", "Typography"),
    ("background", "Background"),
    ("lighting", "Lighting"),
    ("icon_style", "Icon style"),
    ("layout_language", "Layout language"),
    ("product_presentation", "Product presentation"),
    ("whitespace", "Whitespace"),
]


def style_value(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(clean(x) for x in value if clean(x))
    if isinstance(value, dict):
        return "; ".join(
            f"{k}: {clean(v)}"
            for k, v in value.items()
            if clean(v)
        )
    return clean(value)


def build_style_block(plan: Dict[str, Any]) -> List[str]:
    style = style_lock(plan)

    lines = [
        "CAMPAIGN STYLE LOCK — CONSISTENT ACROSS THE LISTING SET:",
    ]

    found = False

    for key, label in STYLE_FIELDS:
        if key not in style:
            continue
        value = style_value(style[key])
        if value:
            lines.append(f"- {label}: {value}")
            found = True

    forbidden = (
        style.get("forbidden_style_drift")
        or style.get("forbidden")
        or style.get("negative_constraints")
    )

    if forbidden:
        lines.append("- Forbidden style drift:")
        for item in as_list(forbidden):
            text = clean(item)
            if text:
                lines.append(f"  - {text}")

    if not found and not forbidden:
        lines.append(
            "- Preserve one coherent product presentation, lighting logic, "
            "color system, typography system and visual language across H1-H5."
        )

    return lines


# ============================================================
# Product Identity Compiler
# ============================================================

def build_product_block(plan: Dict[str, Any]) -> List[str]:
    product = product_block(plan)

    name = first(
        product,
        ["name", "product_name", "title"],
        "Unknown product",
    )
    category = first(
        product,
        ["category", "product_category"],
        "Unknown category",
    )
    confirmed = feature_texts(product, "confirmed_features")

    lines = [
        "PRODUCT IDENTITY — DO NOT REDESIGN:",
        f"- Product: {name}",
        f"- Category: {category}",
        "- Confirmed visual/product facts:",
    ]

    if confirmed:
        lines.extend(f"  - {x}" for x in confirmed)
    else:
        lines.append("  - None explicitly confirmed.")

    lines += [
        "",
        "PRODUCT CONSISTENCY:",
        "- Preserve exact identity from the supplied product reference.",
        "- Preserve shape, proportions, geometry, structure, visible controls, materials, colors, logo placement and visible details.",
        "- Do not redesign, recolor, rebrand, simplify or add product features.",
        "- Do not use inferred information as a factual specification.",
        "- If generated text conflicts with the product reference, remove the unsupported claim.",
    ]

    return lines


# ============================================================
# Selling Point Compiler
# ============================================================

def build_selling_point_block(
    plan: Dict[str, Any],
    image: Dict[str, Any],
) -> Tuple[List[str], Optional[str], List[Dict[str, str]]]:
    compiled = compile_selling_points(plan)
    allowed = compiled["allowed"]
    blocked = compiled["blocked"]
    primary = primary_selling_point(image)
    primary_allowed = None
    if primary:
        for candidate in allowed:
            if candidate.casefold() == primary.casefold():
                primary_allowed = candidate
                break

    lines = ["SELLING POINT COMPILER — SEMANTICALLY FILTERED:"]
    if primary:
        if primary_allowed:
            lines.append(f"- Primary supported selling point: {primary_allowed}")
        else:
            lines.append(f"- Planner-selected selling point BLOCKED: {primary}")
            lines.append("- Reason: planner text is not sufficient evidence for a factual claim.")
            lines.append("- Use visible confirmed product attributes instead of repeating the blocked marketing statement.")
    if allowed:
        lines.append("- Confirmed selling points that survived the semantic claim filter:")
        lines.extend(f"  - {point}" for point in allowed)
    else:
        lines.append("- No selling point survived the semantic claim filter.")
    if blocked:
        lines.append("- Blocked selling points:")
        for item in blocked:
            lines.append(f"  - {item['text']} [{item['reason']}]")
    return lines, primary_allowed, blocked


# ============================================================
# Image Direction Compiler
# ============================================================

def build_image_direction(
    image: Dict[str, Any],
    confirmed_primary: Optional[str],
) -> List[str]:
    purpose = image_purpose(image)
    camera = image_camera(image)
    composition = image_composition(image)
    text = image_text(image)
    reference = image_reference(image)

    lines = [
        "IMAGE-SPECIFIC DIRECTION:",
        f"- Amazon purpose: {purpose}",
    ]

    if confirmed_primary:
        lines.append(
            f"- Primary supported selling point: {confirmed_primary}"
        )
    else:
        lines.append(
            "- Primary selling point: none confirmed; prioritize visible/"
            "confirmed product attributes instead of inventing a claim."
        )

    if camera:
        lines.append(f"- Camera/view angle: {camera}")

    if composition:
        if image_id(image).upper() == "H1":
            composition = re.sub(r"\b(?:occupying|occupy|fills?|filling)\s+(?:about\s+)?\d+(?:\.\d+)?\s*[-–—]?\s*\d*%\s*(?:of\s+the\s+frame|of\s+frame)?", "", composition, flags=re.I)
            composition = re.sub(r"\b\d+(?:\.\d+)?\s*[-–—]?\s*\d*%\s+(?:of\s+)?(?:the\s+)?frame\b", "", composition, flags=re.I)
            composition = re.sub(r"\s{2,}", " ", composition).strip(" ,;.-")
            composition = re.sub(r"\s*,\s*,\s*", ", ", composition).strip(" ,;.-")
        if composition:
            lines.append(f"- Composition direction: {composition}")

    if text:
        lines.append(f"- Text direction: {text}")

    lines.append(f"- Product reference: {reference}")

    return lines


# ============================================================
# Conversion Driver
# ============================================================

def build_conversion_block(plan: Dict[str, Any]) -> List[str]:
    conversion = plan.get("conversion_driver")
    if not conversion:
        return []

    lines = ["CONVERSION DRIVER:"]

    if isinstance(conversion, dict):
        primary = clean(conversion.get("primary"))
        secondary = conversion.get("secondary")
        reason = clean(conversion.get("reason"))

        if primary:
            lines.append(f"- Primary: {primary}")

        if secondary:
            if isinstance(secondary, list):
                values = [clean(x) for x in secondary if clean(x)]
                if values:
                    lines.append(f"- Secondary: {', '.join(values)}")
            else:
                lines.append(f"- Secondary: {clean(secondary)}")

        if reason:
            lines.append(f"- Reason: {reason}")
    else:
        lines.append(f"- {clean(conversion)}")

    lines.append(
        "- Conversion intent must never override the Evidence Compiler."
    )
    return lines


# ============================================================
# Final Quality / Negative Constraints
# ============================================================

def build_quality_block(image_id: str) -> List[str]:
    role = image_id.upper()

    lines = [
        "AMAZON VISUAL QUALITY GATE:",
        "- Product must be immediately recognizable.",
        "- Visual hierarchy must communicate the intended purpose quickly.",
        "- Keep composition commercially credible and easy to scan.",
        "- Avoid clutter and unnecessary decorative elements.",
        "- Avoid generic AI-looking hands, reflections, textures, props and environments.",
        "- Product edges, logos, controls, seams and materials must remain coherent.",
        "",
        "UNIVERSAL NEGATIVE CONSTRAINTS:",
        "- No invented product features.",
        "- No unsupported specifications, certifications or ratings.",
        "- No fake reviews, stars, awards, rankings, badges or sales numbers.",
        "- No competitor logos or fabricated competitor comparisons.",
        "- No distorted product geometry.",
        "- No extra product variants unless explicitly required.",
        "- No product recoloring or logo redesign.",
        "- No inconsistent campaign style.",
        "- No malformed, garbled or unreadable text.",
    ]

    if role == "H1":
        lines += [
            "",
            "H1 HARD CONSTRAINTS:",
            "- No feature callouts.",
            "- No promotional copy.",
            "- No decorative lifestyle props.",
            "- Do not force a fixed product occupancy percentage; use natural category-appropriate scale.",
        ]

    elif role == "H2":
        lines += [
            "",
            "H2 HARD CONSTRAINTS:",
            "- One primary supported benefit only.",
            "- Every callout must map to a confirmed visual/product fact.",
            "- Remove any unsupported numeric or performance statement.",
        ]

    elif role == "H3":
        lines += [
            "",
            "H3 HARD CONSTRAINTS:",
            "- One believable usage context.",
            "- Context cannot be used as hidden evidence for unconfirmed capabilities.",
            "- Keep product scale and physical interaction realistic.",
        ]

    elif role == "H4":
        lines += [
            "",
            "H4 HARD CONSTRAINTS:",
            "- No fabricated competitor comparison.",
            "- Prefer self-comparison / multi-angle proof when competitor evidence is absent.",
            "- Labels must describe visible or confirmed attributes only.",
        ]

    elif role == "H5":
        lines += [
            "",
            "H5 HARD CONSTRAINTS:",
            "- Focus on one visible detail.",
            "- Do not infer engineering specifications from macro appearance.",
        ]

    lines += [
        "",
        "FINAL PRE-GENERATION CHECK:",
        "1. Product identity matches the supplied reference.",
        "2. Selected template rules are actually followed.",
        "3. Image role and Amazon purpose are clear.",
        "4. Every factual claim is confirmed.",
        "5. Inferred information has not become a hard claim.",
        "6. Unknown information is not presented as fact.",
        "7. Campaign Style Lock is preserved.",
        "8. No prohibited or fabricated claims are present.",
    ]

    return lines


# ============================================================
# Prompt compilation
# ============================================================

def build_prompt(
    plan: Dict[str, Any],
    image: Dict[str, Any],
    template_path: Path,
    template: Dict[str, Any],
) -> Tuple[str, Dict[str, Any]]:
    iid = image_id(image)

    selling_lines, confirmed_primary, blocked = build_selling_point_block(
        plan,
        image,
    )

    lines: List[str] = [
        "You are an Amazon Listing Visual Strategist and Image Prompt Engineer.",
        f"Create Amazon Listing image {iid}.",
        "",
    ]

    lines.extend(build_role_block(iid, image))
    lines.append("")

    lines.extend(build_image_direction(image, confirmed_primary))
    lines.append("")

    lines.extend(build_product_block(plan))
    lines.append("")

    lines.extend(build_evidence_block(plan))
    lines.append("")

    confirmed_facts = feature_texts(product_block(plan), "confirmed_features")
    lines.extend(build_visual_evidence_block(confirmed_facts).splitlines())
    lines.append("")

    lines.extend(selling_lines)
    lines.append("")

    conversion_lines = build_conversion_block(plan)
    if conversion_lines:
        lines.extend(conversion_lines)
        lines.append("")

    lines.extend(build_style_block(plan))
    lines.append("")

    # This is the key V2.5 change:
    # actual selected template rules are compiled into the prompt.
    lines.extend(build_template_block(template_path, template))
    lines.append("")

    lines.extend(build_quality_block(iid))

    prompt = "\n".join(lines).strip() + "\n"

    tid, tname = template_identity(template_path, template)

    rule_counts = {k: len(v) for k, v in extract_template_rules(template, image).items()}
    metadata = {
        "version": VERSION,
        "template_rule_counts": rule_counts,
        "template_reference_examples_available": len(template.get("examples", [])) if isinstance(template.get("examples"), list) else 0,
        "template_examples_in_prompt": False,
        "template_safety_filter": "enabled",
        "evidence_layer": "V2.5.2: confirmed visual facts are usable as visual evidence; functional/marketing claims remain gated",
        "semantic_claim_filter": "enabled",
        "image_id": iid,
        "role": image_role(image),
        "amazon_purpose": image_purpose(image),
        "template_id": tid,
        "template_file": template_path.name,
        "template_name": tname,
        "confirmed_primary_selling_point": confirmed_primary,
        "blocked_selling_points": blocked,
        "prompt_file": f"{iid}.txt",
        "prompt": prompt,
    }

    return prompt, metadata


# ============================================================
# Main
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Amazon Listing Prompt Builder V2.5"
    )
    parser.add_argument(
        "plan",
        nargs="?",
        default=str(DEFAULT_PLAN),
        help="Path to validated listing_plan.json",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=str(DEFAULT_OUTPUT_DIR),
        help="Prompt output directory",
    )
    parser.add_argument(
        "--templates",
        default=str(DEFAULT_TEMPLATE_DIR),
        help="Template directory",
    )

    args = parser.parse_args()

    plan_path = Path(args.plan)
    output_dir = Path(args.output)
    template_dir = Path(args.templates)

    try:
        plan = load_json(plan_path)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    images = images_from_plan(plan)
    if not images:
        print("ERROR: listing_plan.json contains no images.")
        return 1

    if not template_dir.exists():
        print(f"ERROR: template directory not found: {template_dir}")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, Any]] = []
    errors: List[str] = []

    for image in images:
        iid = image_id(image)

        try:
            path = resolve_template(
                template_dir,
                template_id(image),
                template_file(image),
            )
            template = load_json(path)

            prompt, metadata = build_prompt(
                plan,
                image,
                path,
                template,
            )

            txt_path = output_dir / f"{iid}.txt"
            txt_path.write_text(prompt, encoding="utf-8")

            records.append(metadata)

        except Exception as exc:
            errors.append(f"{iid}: {exc}")

    if errors:
        print("ERROR: prompt generation failed.")
        for error in errors:
            print(f"- {error}")
        return 1

    result = {
        "version": VERSION,
        "source_plan": str(plan_path).replace("\\", "/"),
        "template_dir": str(template_dir).replace("\\", "/"),
        "prompt_count": len(records),
        "compiler_policy": {
            "evidence_gate": "confirmed-only factual claims",
            "inferred_claims": "blocked",
            "unknown_claims": "blocked",
            "template_rules": "compiled from selected template JSON",
            "h1_fixed_occupancy": False,
            "h4_competitor_claims_without_evidence": False,
        },
        "prompts": records,
    }

    output_json = output_dir / "listing_prompts.json"
    write_json(output_json, result)

    print(f"OK: generated {len(records)} prompts.")
    print(f"Version: {VERSION}")
    print(f"JSON: {output_json}")

    for record in records:
        primary = record.get("confirmed_primary_selling_point") or "NONE"
        blocked_count = len(record.get("blocked_selling_points", []))
        print(
            f"- {record['image_id']}: "
            f"{record['template_file']} -> "
            f"{record['prompt_file']} | "
            f"confirmed primary={primary!r} | "
            f"blocked={blocked_count}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
