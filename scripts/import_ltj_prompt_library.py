"""Build and import static LTJ Prompt fragments through AI Drawing's MCP tool."""

from __future__ import annotations

import ast
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx


CATEGORY_SPECS = (
    ("body-appearance", "人物與身形", "人物的身體特徵與外觀描述。", ("BODY_BREASTS", "BODY_THIGHS", "BODY_ASS", "BODY_FRAME", "MALE_PROMPTS", "MALE_FACES", "PENIS_TYPES", "PENIS_MODS")),
    ("clothing", "服裝", "外搭、內搭與服裝狀態描述。", ("OUTERWEARS", "INNERWEARS", "FLIRT_CLOTHING_OPTS", "TEASING_CLOTHING_OPTS")),
    ("underwear", "內衣褲", "內衣、內褲款式、材質與顏色描述。", ("BRA_TYPES", "BRA_MATS", "PANTIES_TYPES", "PANTIES_MATS", "PG_BRA_TYPES", "PG_PANTIES_TYPES", "BRA_COLORS")),
    ("accessories", "配件", "服飾配件與特殊穿搭描述。", ("SPECIAL_ACC",)),
    ("environment", "場景與氛圍", "地點與畫面氛圍描述。", ("LOC_PLACES", "LOC_ATMOS")),
    ("camera-composition", "鏡頭與構圖", "鏡頭角度、景別與視角描述。", ("ANGLES", "PG_ANGLES", "PG_SHOT_SIZES", "AFTER_ANGLES", "CUM_SHOWER_ANGLES", "PERSPECTIVES")),
    ("poses", "姿勢與體位", "人物姿勢與體位描述。", ("POSITIONS", "CUM_SHOWER_POSES", "CUM_SHOWER_BODY")),
    ("actions-interactions", "動作與互動", "互動、動作、高潮與脫衣描述。", ("P_EXTRA_ACTS", "CLIMAXES", "FLIRT_ACTS", "ORAL_ACTS", "UNDRESS_ACTS", "TEASING_WET_OPTS", "TEASING_MILK_OPTS", "CUM_SHOWER_TONGUES", "CUM_SHOWER_DYNAMICS", "WETNESS_OPTS", "AFTER_CONDOMS", "AFTER_CUMS")),
    ("expressions", "表情", "人物表情與情緒描述。", ("EXPRESSIONS_LIST", "TEASING_EXPS")),
    ("physical-effects", "身體效果", "汗水、蒸氣與事後畫面效果。", ("AFTER_EFFECTS",)),
)


def _literal_constants(source: Path) -> dict[str, Any]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    constants: dict[str, Any] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            continue
        try:
            constants[node.targets[0].id] = ast.literal_eval(node.value)
        except (ValueError, TypeError):
            continue
    return constants


def _slug(text: str, used: set[str]) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "prompt"
    candidate, suffix = base, 2
    while candidate in used:
        candidate = f"{base}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _is_prompt(value: str) -> bool:
    return value.strip() not in {"", "(none)", "None", "Threesome", "Gangbang"}


def _entries(constants: dict[str, Any], names: tuple[str, ...]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    used: set[str] = set()
    for name in names:
        value = constants.get(name, [])
        pairs = value.items() if isinstance(value, dict) and name == "MALE_PROMPTS" else value
        for item in pairs:
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            label, prompt = item
            if not isinstance(label, str) or not isinstance(prompt, str) or not _is_prompt(prompt):
                continue
            entries.append({
                "id": _slug(f"{name}-{prompt}", used),
                "name_zh": label.split("(", 1)[0].strip() or label,
                "description_zh": f"加入 LTJ 的「{label}」提示詞片段。",
                "prompt": prompt,
                "aliases": [label, prompt],
                "keywords": [name.lower(), "ltj", "prompt"],
                "order": len(entries) + 10,
                "revision": 1,
                "archived": False,
            })
    return entries


def _quality_categories(constants: dict[str, Any]) -> list[dict[str, Any]]:
    positive: list[dict[str, Any]] = []
    negative: list[dict[str, Any]] = []
    for family, values in constants["BASE_MODEL_QUALITY_TAGS"].items():
        positive.append({"id": _slug(f"{family}-quality", {entry["id"] for entry in positive}), "name_zh": f"{family} 品質詞", "description_zh": f"LTJ 收錄的 {family} 品質詞組合。", "prompt": values["quality"], "aliases": [family, "quality"], "keywords": ["quality", family.lower(), "ltj"], "order": len(positive) + 10, "revision": 1, "archived": False})
        for rating, tag in values["ratings"].items():
            positive.append({"id": _slug(f"{family}-{rating}", {entry["id"] for entry in positive}), "name_zh": f"{family} 分級 {rating}", "description_zh": f"LTJ 收錄的 {family} 內容分級詞。", "prompt": tag, "aliases": [family, rating, tag], "keywords": ["rating", family.lower(), "ltj"], "order": len(positive) + 10, "revision": 1, "archived": False})
        negative.append({"id": _slug(f"{family}-negative", {entry["id"] for entry in negative}), "name_zh": f"{family} 基礎負向詞", "description_zh": f"LTJ 收錄的 {family} 基礎負向提示詞組合。", "prompt": values["negative"], "aliases": [family, "negative"], "keywords": ["negative", family.lower(), "ltj"], "order": len(negative) + 10, "revision": 1, "archived": False})
    return [
        {"id": "quality-ratings", "polarity": "positive", "name_zh": "品質與分級", "description_zh": "LTJ 的品質詞與內容分級提示詞。", "aliases": ["quality", "rating"], "keywords": ["ltj", "quality", "rating"], "order": 10, "revision": 1, "archived": False, "entries": positive},
        {"id": "base-negative", "polarity": "negative", "name_zh": "基礎負向詞", "description_zh": "LTJ 的基礎負向提示詞組合。", "aliases": ["negative"], "keywords": ["ltj", "negative"], "order": 10, "revision": 1, "archived": False, "entries": negative},
    ]


def build_categories(ltj_source: Path) -> list[dict[str, Any]]:
    constants = _literal_constants(ltj_source)
    categories = _quality_categories(constants)
    for order, (category_id, name_zh, description_zh, names) in enumerate(CATEGORY_SPECS, start=20):
        categories.append({"id": category_id, "polarity": "positive", "name_zh": name_zh, "description_zh": description_zh, "aliases": [name_zh, category_id], "keywords": ["ltj", "positive", category_id], "order": order * 10, "revision": 1, "archived": False, "entries": _entries(constants, names)})
    return categories


def validate_categories(categories: list[dict[str, Any]]) -> None:
    category_ids = [str(category["id"]) for category in categories]
    if len(category_ids) != len(set(category_ids)):
        raise ValueError("duplicate category id")
    for category in categories:
        entry_ids = [str(entry["id"]) for entry in category["entries"]]
        if len(entry_ids) != len(set(entry_ids)):
            raise ValueError(f"duplicate entry id in {category['id']}")
        for entry in category["entries"]:
            if not all(str(entry[key]).strip() for key in ("name_zh", "description_zh", "prompt")):
                raise ValueError(f"incomplete entry: {entry['id']}")


def require_healthy_backend(backend_url: str) -> None:
    try:
        response = httpx.get(f"{backend_url.rstrip('/')}/health", timeout=5.0)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"backend health check failed: {exc}") from exc


def clear_existing_categories(root: Path) -> list[Path]:
    resolved_root = root.resolve()
    removed: list[Path] = []
    for polarity in ("positive", "negative"):
        directory = (resolved_root / polarity).resolve()
        if directory.parent != resolved_root:
            raise ValueError("invalid Prompt Library directory")
        for path in directory.glob("*.json"):
            path.unlink()
            removed.append(path)
    return removed


def import_categories_via_mcp(categories: list[dict[str, Any]], backend_url: str, project_root: Path) -> dict[str, int]:
    mcp_root = project_root / "mcp-server"
    async def _import() -> dict[str, int]:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        environment = dict(os.environ)
        environment["MCP_BACKEND_API_URL"] = backend_url.rstrip("/")
        server = StdioServerParameters(
            command=sys.executable,
            args=["-m", "mcp_server.server"],
            cwd=str(mcp_root),
            env=environment,
        )
        async with stdio_client(server) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                if "prompt_library_save" not in {tool.name for tool in tools.tools}:
                    raise RuntimeError("MCP server does not expose prompt_library_save")
                imported_entries = 0
                for category in categories:
                    category_payload = {
                        key: category[key]
                        for key in ("name_zh", "description_zh", "aliases", "keywords", "order")
                    }
                    result = await session.call_tool(
                        "prompt_library_save",
                        arguments={
                            "resource_type": "category",
                            "resource_id": str(category["id"]),
                            "payload": category_payload,
                            "expected_revision": 0,
                            "polarity": str(category["polarity"]),
                        },
                    )
                    payload = json.loads(result.content[0].text)
                    if not payload.get("ok"):
                        raise RuntimeError(f"MCP import failed for {category['id']}: {payload}")
                    version = payload["category"]
                    for entry in category["entries"]:
                        entry_payload = {
                            key: entry[key]
                            for key in ("name_zh", "description_zh", "prompt", "aliases", "keywords", "order")
                        }
                        entry_result = await session.call_tool(
                            "prompt_library_save",
                            arguments={
                                "resource_type": "entry",
                                "resource_id": str(entry["id"]),
                                "payload": entry_payload,
                                "expected_revision": version["category"]["revision"],
                                "expected_etag": version["etag"],
                                "polarity": str(category["polarity"]),
                                "category_id": str(category["id"]),
                            },
                        )
                        entry_response = json.loads(entry_result.content[0].text)
                        if not entry_response.get("ok"):
                            raise RuntimeError(f"MCP import failed for {entry['id']}: {entry_response}")
                        version = entry_response["category"]
                        imported_entries += 1
                return {"categories": len(categories), "entries": imported_entries}

    return asyncio.run(_import())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend-url", default="http://127.0.0.1:8001")
    parser.add_argument("--library-root", type=Path, default=Path("prompt_library"))
    parser.add_argument("--ltj-source", type=Path, default=Path(__file__).resolve().parents[2] / "LTJ" / "scenario_gui.py")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    categories = build_categories(args.ltj_source)
    validate_categories(categories)
    print(f"Prepared {len(categories)} categories and {sum(len(category['entries']) for category in categories)} entries.")
    if not args.apply:
        return
    require_healthy_backend(args.backend_url)
    removed = clear_existing_categories(args.library_root)
    imported = import_categories_via_mcp(categories, args.backend_url, Path(__file__).resolve().parents[1])
    print(f"Removed {len(removed)} test documents; imported {imported['categories']} categories and {imported['entries']} entries.")


if __name__ == "__main__":
    main()
