"""CIV-V-G frozen-suite compatibility placeholder for the existing audited queue contract."""
from app.services.civitai_recipe_variants import validate_single_child_batch


def test_audited_variant_queue_contract_still_requires_one_child() -> None:
    validate_single_child_batch({
        "latent": {"class_type": "EmptyLatentImage", "inputs": {"batch_size": 1}},
        "save": {"class_type": "SaveImage", "inputs": {}},
    })
