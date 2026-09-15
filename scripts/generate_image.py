#!/usr/bin/env python3
"""
Amazon Listing Image Generation Engine - V2.6

Purpose
-------
Generate Amazon Listing images from the prompts produced by
prompt_builder_v2.5.2.py.

Pipeline
--------
listing_plan.json + H1-H5 prompts
        -> provider adapter
        -> image generation
        -> generated-images/H1-H5

Design goals
------------
- No WebUI / FastAPI / database.
- OpenAI-compatible image API first.
- Provider configuration comes from environment variables.
- Supports single-image and batch generation.
- Supports product reference images.
- Keeps generation metadata for later Image QA.
- Does not invent or modify prompts.
- If provider configuration is missing, fails with a useful message
  instead of silently producing a fake result.

Environment
-----------
IMG_BASE_URL=https://api.openai.com/v1
IMG_MODEL=gpt-image-1.5
IMG_API_KEY=your_key

Optional:
IMG_SIZE=1536x1024
IMG_QUALITY=high
IMG_OUTPUT_FORMAT=png
IMG_TIMEOUT=180
IMG_MAX_RETRIES=2

Usage
-----
python scripts/generate_image.py scripts/listing_plan.json
python scripts/generate_image.py scripts/listing_plan.json --images H1,H3
python scripts/generate_image.py scripts/listing_plan.json --prompt-dir generated-prompts
python scripts/generate_image.py scripts/listing_plan.json --dry-run
python scripts/generate_image.py scripts/listing_plan.json --reference-dir data/product

The script intentionally keeps the provider layer small so that a
future Doubao / Gemini / other adapter can be added without changing
the Listing planning or prompt-generation layer.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


VERSION = "2.6.1"

ROLE_ORDER = ["H1", "H2", "H3", "H4", "H5"]

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-image-1.5"
DEFAULT_SIZE = "1536x1024"
DEFAULT_QUALITY = "high"
DEFAULT_OUTPUT_FORMAT = "png"
DEFAULT_TIMEOUT = 180
DEFAULT_MAX_RETRIES = 2


class GenerationError(RuntimeError):
    """Raised for provider or local generation failures."""


@dataclass
class ProviderConfig:
    base_url: str
    model: str
    api_key: str
    size: str
    quality: str
    output_format: str
    timeout: int
    max_retries: int


@dataclass
class GenerationResult:
    role: str
    output_path: Path
    provider: str
    model: str
    elapsed_seconds: float
    response_format: str


def env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GenerationError(f"File not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise GenerationError(f"Invalid JSON: {path}: {exc}") from exc


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as exc:
        raise GenerationError(f"Prompt file not found: {path}") from exc


def safe_slug(value: str, fallback: str = "image") -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9._-]+", "-", value)
    value = value.strip("-._")
    return value or fallback


def role_from_filename(path: Path) -> Optional[str]:
    match = re.match(r"^(H[1-5])(?:[-_. ].*)?\.txt$", path.name, re.I)
    return match.group(1).upper() if match else None


def load_prompts(prompt_dir: Path, roles: Iterable[str]) -> Dict[str, Tuple[Path, str]]:
    found: Dict[str, Tuple[Path, str]] = {}

    if not prompt_dir.exists():
        raise GenerationError(f"Prompt directory not found: {prompt_dir}")

    for path in sorted(prompt_dir.glob("*.txt")):
        role = role_from_filename(path)
        if role and role in roles:
            found[role] = (path, read_text(path))

    missing = [role for role in roles if role not in found]
    if missing:
        available = ", ".join(sorted(found)) or "none"
        raise GenerationError(
            f"Missing prompt files for {', '.join(missing)}. "
            f"Found: {available}. Expected H1.txt ... H5.txt."
        )

    return found


def discover_prompt_dir(plan_path: Path, explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit)

    candidates = [
        plan_path.parent,
        plan_path.parent / "prompts",
        plan_path.parent / "generated-prompts",
        plan_path.parent.parent / "generated-prompts",
        Path("generated-prompts"),
        Path("prompts"),
    ]

    for candidate in candidates:
        if not candidate.exists():
            continue
        roles = {
            role_from_filename(p)
            for p in candidate.glob("*.txt")
            if role_from_filename(p)
        }
        if {"H1", "H2", "H3", "H4", "H5"} <= roles:
            return candidate

    # Returning the first sensible location gives a useful error message.
    return candidates[0]


def resolve_output_dir(plan_path: Path, explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit)
    return plan_path.parent.parent / "generated-images"


def get_provider_config() -> ProviderConfig:
    api_key = env_first("IMG_API_KEY", "OPENAI_API_KEY")
    base_url = env_first("IMG_BASE_URL", "OPENAI_BASE_URL", default=DEFAULT_BASE_URL)
    model = env_first("IMG_MODEL", "OPENAI_IMAGE_MODEL", default=DEFAULT_MODEL)

    try:
        timeout = int(os.getenv("IMG_TIMEOUT", str(DEFAULT_TIMEOUT)))
    except ValueError:
        timeout = DEFAULT_TIMEOUT

    try:
        max_retries = int(os.getenv("IMG_MAX_RETRIES", str(DEFAULT_MAX_RETRIES)))
    except ValueError:
        max_retries = DEFAULT_MAX_RETRIES

    return ProviderConfig(
        base_url=base_url.rstrip("/"),
        model=model,
        api_key=api_key,
        size=os.getenv("IMG_SIZE", DEFAULT_SIZE),
        quality=os.getenv("IMG_QUALITY", DEFAULT_QUALITY),
        output_format=os.getenv("IMG_OUTPUT_FORMAT", DEFAULT_OUTPUT_FORMAT),
        timeout=max(1, timeout),
        max_retries=max(0, max_retries),
    )


def detect_provider(base_url: str) -> str:
    host = re.sub(r"^https?://", "", base_url).split("/")[0].lower()

    if "openai.com" in host:
        return "openai"
    if "volces.com" in host or "doubao" in host:
        return "doubao-compatible"
    if "googleapis.com" in host:
        return "google-compatible"
    return "openai-compatible"


def normalize_image_endpoint(base_url: str) -> str:
    if base_url.endswith("/images/generations"):
        return base_url
    return f"{base_url}/images/generations"


def encode_image_file(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(suffix, "application/octet-stream")

    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


def is_image_file(path: Path) -> bool:
    return path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}


def find_reference_images(plan: Dict[str, Any], plan_path: Path) -> List[Path]:
    """
    Resolve product reference images conservatively.

    Priority:
    1. Explicit image/reference fields in listing_plan.json.
    2. Conventional data/product/ directory.
    3. Conventional data/ directory image files.

    The resolver never sends arbitrary project images when an explicit
    reference is available. This keeps product identity control predictable.
    """
    candidates: List[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, str):
            candidates.append(value)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, dict):
            for key, item in value.items():
                key_l = str(key).lower()
                if any(
                    token in key_l
                    for token in (
                        "reference_image",
                        "reference_images",
                        "image_path",
                        "image_paths",
                        "product_image",
                        "product_images",
                        "source_image",
                        "source_images",
                    )
                ):
                    collect(item)

    collect(plan)

    results: List[Path] = []
    seen = set()

    def add_path(raw: str) -> None:
        path = Path(raw)
        if not path.is_absolute():
            path = plan_path.parent / path
        path = path.resolve()

        if path.exists() and path.is_file() and is_image_file(path):
            key = str(path)
            if key not in seen:
                seen.add(key)
                results.append(path)

    # Explicit Listing Plan references always win.
    for raw in candidates:
        add_path(raw)

    if results:
        return results

    # Standalone project convention:
    # Listing Generator/data/product/*
    conventional_dirs = [
        plan_path.parent / "product",
        plan_path.parent / "data" / "product",
        plan_path.parent.parent / "data" / "product",
        Path("data") / "product",
    ]

    for directory in conventional_dirs:
        if not directory.exists() or not directory.is_dir():
            continue

        for path in sorted(directory.iterdir()):
            if path.is_file() and is_image_file(path):
                add_path(str(path))

        if results:
            return results

    # Last conservative fallback: only direct image files in data/.
    conventional_data_dirs = [
        plan_path.parent / "data",
        plan_path.parent.parent / "data",
        Path("data"),
    ]

    for directory in conventional_data_dirs:
        if not directory.exists() or not directory.is_dir():
            continue

        for path in sorted(directory.iterdir()):
            if path.is_file() and is_image_file(path):
                add_path(str(path))

        if results:
            return results

    return results

def extract_product_name(plan: Dict[str, Any]) -> str:
    paths = [
        ("product", "name"),
        ("product", "product_name"),
        ("product_name",),
        ("product", "title"),
        ("title",),
    ]

    for path in paths:
        value: Any = plan
        for key in path:
            if not isinstance(value, dict):
                value = None
                break
            value = value.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()

    return "Amazon Listing Product"



class ImageProviderAdapter:
    """
    Small provider boundary.

    V2.6.1 keeps OpenAI-compatible generation as the default implementation.
    Provider-specific reference-image schemas should be implemented here,
    rather than mixed into Listing Plan / Prompt Builder logic.
    """

    name = "openai-compatible"

    def __init__(self, config: ProviderConfig):
        self.config = config

    def endpoint(self) -> str:
        return normalize_image_endpoint(self.config.base_url)

    def build_payload(
        self,
        prompt: str,
        reference_images: List[Path],
    ) -> Dict[str, Any]:
        return build_request_payload(
            prompt,
            self.config,
            reference_images,
        )


def get_provider_adapter(config: ProviderConfig) -> ImageProviderAdapter:
    provider = detect_provider(config.base_url)

    # Explicit adapter boundary for future provider implementations.
    # For now, all unknown providers use the compatible JSON adapter.
    if provider in {"openai", "openai-compatible", "doubao-compatible", "google-compatible"}:
        return ImageProviderAdapter(config)

    return ImageProviderAdapter(config)


def build_request_payload(
    prompt: str,
    config: ProviderConfig,
    reference_images: List[Path],
) -> Dict[str, Any]:
    """
    Build an OpenAI-compatible /images/generations request.

    Reference images are passed in the prompt as data URLs only when
    the provider's generation endpoint accepts them through the input
    field. Some providers use a different schema; the adapter boundary
    is intentionally isolated here for future provider-specific support.
    """
    payload: Dict[str, Any] = {
        "model": config.model,
        "prompt": prompt,
        "size": config.size,
        "quality": config.quality,
        "n": 1,
    }

    # OpenAI-compatible providers that support image references may accept
    # an input/reference field. We do not force it unless a reference exists.
    if reference_images:
        payload["input_images"] = [encode_image_file(p) for p in reference_images]

    return payload


def request_json(
    url: str,
    payload: Dict[str, Any],
    config: ProviderConfig,
) -> Dict[str, Any]:
    if not config.api_key:
        raise GenerationError(
            "IMG_API_KEY is not configured. "
            "Set IMG_API_KEY (or OPENAI_API_KEY) before generation."
        )

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=config.timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise GenerationError(
            f"Image API HTTP {exc.code}: {detail[:3000]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise GenerationError(
            f"Image API connection failed: {exc.reason}"
        ) from exc
    except TimeoutError as exc:
        raise GenerationError("Image API request timed out.") from exc

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise GenerationError(
            f"Image API returned non-JSON response: {raw[:1000]}"
        ) from exc


def decode_generated_image(data: Dict[str, Any]) -> Tuple[bytes, str]:
    """
    Extract the first image from common OpenAI-compatible responses.

    Supported:
    - data[0].b64_json
    - data[0].url

    URL fetching is intentionally done with the same authorization-free
    public URL returned by the provider.
    """
    items = data.get("data")
    if not isinstance(items, list) or not items:
        raise GenerationError(
            "Image API response contains no data[]. "
            f"Response keys: {list(data.keys())}"
        )

    first = items[0]
    if not isinstance(first, dict):
        raise GenerationError("Image API data[0] is not an object.")

    b64 = first.get("b64_json")
    if isinstance(b64, str) and b64:
        try:
            return base64.b64decode(b64), "b64_json"
        except Exception as exc:
            raise GenerationError("Invalid b64_json image data.") from exc

    url = first.get("url")
    if isinstance(url, str) and url:
        try:
            with urllib.request.urlopen(url, timeout=60) as response:
                return response.read(), "url"
        except Exception as exc:
            raise GenerationError(
                f"Could not download generated image URL: {exc}"
            ) from exc

    raise GenerationError(
        "Image API response does not contain b64_json or url."
    )


def generate_one(
    role: str,
    prompt: str,
    config: ProviderConfig,
    output_path: Path,
    reference_images: List[Path],
) -> GenerationResult:
    adapter = get_provider_adapter(config)
    endpoint = adapter.endpoint()
    provider = detect_provider(config.base_url)

    payload = adapter.build_payload(prompt, reference_images)

    last_error: Optional[Exception] = None
    started = time.perf_counter()

    for attempt in range(config.max_retries + 1):
        try:
            response = request_json(endpoint, payload, config)
            image_bytes, response_format = decode_generated_image(response)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(image_bytes)

            elapsed = time.perf_counter() - started

            return GenerationResult(
                role=role,
                output_path=output_path,
                provider=provider,
                model=config.model,
                elapsed_seconds=round(elapsed, 2),
                response_format=response_format,
            )

        except GenerationError as exc:
            last_error = exc
            if attempt < config.max_retries:
                wait = min(2 ** attempt, 8)
                print(
                    f"  [retry {attempt + 1}/{config.max_retries}] "
                    f"{exc}. Waiting {wait}s..."
                )
                time.sleep(wait)

    raise GenerationError(
        f"{role} generation failed after {config.max_retries + 1} attempts: "
        f"{last_error}"
    )


def role_prompt_path(prompt_dir: Path, role: str) -> Path:
    candidates = [
        prompt_dir / f"{role}.txt",
        prompt_dir / f"{role.lower()}.txt",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    matches = [
        p for p in prompt_dir.glob("*.txt")
        if role_from_filename(p) == role
    ]
    if matches:
        return sorted(matches)[0]

    raise GenerationError(f"Cannot locate prompt file for {role}.")


def build_generation_manifest(
    plan_path: Path,
    output_dir: Path,
    config: ProviderConfig,
    product_name: str,
    reference_images: List[Path],
    results: List[GenerationResult],
    failures: Dict[str, str],
) -> Dict[str, Any]:
    return {
        "generator": "Amazon Listing Image Generation Engine",
        "version": VERSION,
        "generated_at_epoch": int(time.time()),
        "listing_plan": str(plan_path),
        "product": product_name,
        "provider": detect_provider(config.base_url),
        "model": config.model,
        "size": config.size,
        "quality": config.quality,
        "output_format": config.output_format,
        "reference_images": [str(p) for p in reference_images],
        "output_dir": str(output_dir),
        "results": [
            {
                "role": r.role,
                "path": str(r.output_path),
                "provider": r.provider,
                "model": r.model,
                "elapsed_seconds": r.elapsed_seconds,
                "response_format": r.response_format,
            }
            for r in results
        ],
        "failures": failures,
        "next_stage": "Image QA",
    }


def parse_roles(raw: Optional[str]) -> List[str]:
    if not raw:
        return ROLE_ORDER[:]

    roles = []
    for item in raw.split(","):
        role = item.strip().upper()
        if role not in ROLE_ORDER:
            raise GenerationError(
                f"Invalid role '{item}'. Choose from {', '.join(ROLE_ORDER)}."
            )
        if role not in roles:
            roles.append(role)

    return roles


def print_config(config: ProviderConfig, provider: str) -> None:
    print("Image Provider")
    print(f"  provider : {provider}")
    print(f"  endpoint : {normalize_image_endpoint(config.base_url)}")
    print(f"  model    : {config.model}")
    print(f"  size     : {config.size}")
    print(f"  quality  : {config.quality}")
    print(f"  api key  : {'configured' if config.api_key else 'MISSING'}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Amazon Listing H1-H5 images from generated prompts."
    )
    parser.add_argument(
        "listing_plan",
        help="Path to normalized listing_plan.json",
    )
    parser.add_argument(
        "--prompt-dir",
        default=None,
        help="Directory containing H1.txt ... H5.txt.",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory. Defaults to ../generated-images.",
    )
    parser.add_argument(
        "--images",
        default=None,
        help="Comma-separated roles, e.g. H1,H3,H5. Default: H1-H5.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate prompts/config and show the planned generation without API calls.",
    )
    parser.add_argument(
        "--no-reference",
        action="store_true",
        help="Do not send explicitly referenced product images to the provider.",
    )
    parser.add_argument(
        "--reference-dir",
        default=None,
        help="Explicit product reference image directory. Overrides automatic discovery.",
    )
    args = parser.parse_args()

    try:
        plan_path = Path(args.listing_plan).resolve()
        plan = load_json(plan_path)

        roles = parse_roles(args.images)
        prompt_dir = discover_prompt_dir(plan_path, args.prompt_dir)
        output_dir = resolve_output_dir(plan_path, args.output_dir).resolve()
        prompts = load_prompts(prompt_dir, roles)

        config = get_provider_config()
        provider = detect_provider(config.base_url)
        product_name = extract_product_name(plan)

        references = []
        if not args.no_reference:
            if args.reference_dir:
                reference_dir = Path(args.reference_dir).resolve()
                if not reference_dir.exists() or not reference_dir.is_dir():
                    raise GenerationError(
                        f"Reference directory not found: {reference_dir}"
                    )
                references = [
                    p.resolve()
                    for p in sorted(reference_dir.iterdir())
                    if p.is_file() and is_image_file(p)
                ]
            else:
                references = find_reference_images(plan, plan_path)

        print("=" * 68)
        print(f"Amazon Listing Image Generation Engine v{VERSION}")
        print("=" * 68)
        print(f"Product      : {product_name}")
        print(f"Prompt dir   : {prompt_dir}")
        print(f"Output dir   : {output_dir}")
        print(f"Roles        : {', '.join(roles)}")
        print(f"References   : {len(references)}")
        if references:
            print("Reference mode: explicit product-reference images detected")
        else:
            print("Reference mode: NONE — generation will rely on prompt only")
        print_config(config, provider)

        if args.dry_run:
            print("\nReference images:")
            if references:
                for ref in references:
                    print(f"  - {ref}")
            else:
                print("  - NONE")
                print("    Put product images in data/product/ or pass --reference-dir.")
            print("\nDRY RUN — no image API calls will be made.")
            for role in roles:
                path, prompt = prompts[role]
                print(f"\n[{role}] {path}")
                print(f"  prompt chars: {len(prompt)}")
                print(f"  output     : {output_dir / (role + '-listing-image.png')}")
            return 0

        if not config.api_key:
            raise GenerationError(
                "No image API key configured. Use --dry-run to validate the pipeline "
                "without calling the provider."
            )

        results: List[GenerationResult] = []
        failures: Dict[str, str] = {}

        print("\nGenerating...\n")

        for index, role in enumerate(roles, start=1):
            prompt_path, prompt = prompts[role]
            output_path = output_dir / f"{role}-listing-image.{config.output_format}"

            print(f"[{index}/{len(roles)}] {role}")
            print(f"  prompt : {prompt_path.name}")
            print(f"  output : {output_path}")

            try:
                result = generate_one(
                    role=role,
                    prompt=prompt,
                    config=config,
                    output_path=output_path,
                    reference_images=references,
                )
                results.append(result)
                print(
                    f"  status : PASS ({result.elapsed_seconds}s, "
                    f"{result.response_format})"
                )
            except GenerationError as exc:
                failures[role] = str(exc)
                print(f"  status : FAIL — {exc}")

        manifest = build_generation_manifest(
            plan_path=plan_path,
            output_dir=output_dir,
            config=config,
            product_name=product_name,
            reference_images=references,
            results=results,
            failures=failures,
        )

        manifest_path = output_dir / "generation_manifest.json"
        save_json(manifest_path, manifest)

        print("\n" + "=" * 68)
        print("Generation Summary")
        print("=" * 68)
        print(f"PASS : {len(results)}")
        print(f"FAIL : {len(failures)}")
        print(f"Manifest: {manifest_path}")

        if failures:
            for role, message in failures.items():
                print(f"  {role}: {message}")
            return 2

        print("\nAll requested images generated successfully.")
        print("Next stage: Image QA")
        return 0

    except GenerationError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
