"""Repository style-preset catalog naming conventions."""
import json
from pathlib import Path


PRESET_DIR = Path(__file__).resolve().parents[2] / "style_presets" / "agent" / "presets"
FAMILY_PREFIXES = ("[Anima] ", "[Illustrious] ", "[SDXL] ", "[SD1.5] ")


def test_every_style_preset_display_name_has_model_family_prefix() -> None:
    paths = sorted(PRESET_DIR.glob("*.json"))
    assert paths

    missing: list[str] = []
    for path in paths:
        preset = json.loads(path.read_text(encoding="utf-8"))
        for field in ("name", "chinese_name"):
            value = preset.get(field)
            if value is not None and not value.startswith(FAMILY_PREFIXES):
                missing.append(f"{preset['id']}.{field}={value!r}")

    assert not missing, "Missing model-family prefix:\n" + "\n".join(missing)
