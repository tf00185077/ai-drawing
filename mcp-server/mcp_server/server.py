"""
AI Drawing MCP Server

Uses FastMCP, communicates with Cursor and other MCP clients via stdio.
Tools are defined in the mcp_server.tools module.
"""
import sys
import inspect
from functools import wraps
from importlib import import_module
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import ValidationError

# Catalog lookup must reuse the served module when this
# file runs as ``python -m mcp_server.server``, rather than loading a second copy.
if __name__ == "__main__":
    sys.modules["mcp_server.server"] = sys.modules[__name__]

from mcp_server.tools.responses import backend_error_payload, envelope


_SAFE_VALIDATION_CONTEXT_KEYS = frozenset(
    {
        "expected",
        "ge",
        "gt",
        "le",
        "lt",
        "max_length",
        "min_length",
        "multiple_of",
    }
)

REMOVED_LORA_START_FIELDS = frozenset(
    {
        "checkpoint",
        "trigger_token",
        "model_family",
        "anima_qwen3",
        "anima_vae",
        "anima_t5_tokenizer_path",
        "sdxl",
        "allow_unverified_checkpoint",
        "epochs",
        "resolution",
        "batch_size",
        "learning_rate",
        "class_tokens",
        "keep_tokens",
        "num_repeats",
        "mixed_precision",
        "network_module",
        "network_dim",
        "network_alpha",
    }
)


def _safe_validation_errors(exc: ValidationError) -> list[dict[str, Any]]:
    """Keep field guidance while omitting submitted values and arbitrary context."""
    sanitized: list[dict[str, Any]] = []
    for entry in exc.errors(include_input=False, include_url=False):
        item = {
            key: entry[key]
            for key in ("loc", "msg", "type")
            if key in entry
        }
        if "loc" in item:
            item["loc"] = list(item["loc"])
        context = entry.get("ctx")
        if isinstance(context, dict):
            safe_context = {
                key: value
                for key, value in context.items()
                if key in _SAFE_VALIDATION_CONTEXT_KEYS
                and (
                    value is None
                    or isinstance(value, (bool, int, float, str))
                )
            }
            if safe_context:
                item["ctx"] = safe_context
        sanitized.append(item)
    return sanitized


class ContractFastMCP(FastMCP):
    """Return one envelope, including failures before a tool body executes."""

    def _convert_contract_result(
        self,
        name: str,
        result: dict[str, Any],
    ) -> Any:
        tool = self._tool_manager.get_tool(name)
        if tool is None:  # pragma: no cover - registration changed mid-call
            raise RuntimeError(f"tool disappeared during validation: {name}")
        return tool.fn_metadata.convert_result(envelope(result))

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        tool = self._tool_manager.get_tool(name)
        if tool is not None:
            unknown = sorted(set(arguments) - set(tool.parameters.get("properties", {})))
            # The presence check is deliberate: null/empty save requests must
            # never disappear into Pydantic's default extra-field handling.
            if name == "prompt_compose" and "save_as" in arguments:
                return self._validation_result(name, "Legacy save_as is not a composition input", "Compose then use prompt_write(action=save) with the returned positive/negative fragment arrays.", {"fields": ["save_as"]})
        if name == "lora_train_start":
            removed = sorted(
                set(arguments).intersection(REMOVED_LORA_START_FIELDS)
            )
            if removed:
                return self._convert_contract_result(
                    name,
                    {
                        "ok": False,
                        "tool": name,
                        "status_code": 422,
                        "error": {
                            "code": "legacy_training_fields_removed",
                            "message": (
                                "top-level training fields were removed; "
                                "use the versioned recipe container"
                            ),
                            "hint": (
                                "run decision preflight and submit its exact "
                                "start_payload"
                            ),
                            "details": {"fields": removed},
                        },
                    },
                )
        if tool is not None and unknown:
            return self._validation_result(name, "Unknown MCP tool arguments", "Remove unsupported fields and use the advertised tool schema.", {"fields": unknown})
        try:
            return await super().call_tool(name, arguments)
        except ToolError as exc:
            cause = exc.__cause__
            if not isinstance(cause, ValidationError):
                return self._convert_contract_result(name, backend_error_payload(name, exc, where="mcp"))

            result = {
                "ok": False,
                "tool": name,
                "status_code": 422,
                "error": {
                    "code": "request_validation_failed",
                    "message": "MCP tool argument validation failed",
                    "hint": "correct the listed fields and retry",
                    "details": {
                        "validation_errors": _safe_validation_errors(cause),
                    },
                },
            }
            return self._convert_contract_result(name, result)


    def _validation_result(self, name: str, message: str, hint: str, details: dict[str, Any]) -> Any:
        return self._convert_contract_result(name, {"ok": False, "error": {"code": "request_validation_failed", "message": message, "hint": hint, "details": details}})


mcp = ContractFastMCP(
    "AI Drawing",
    json_response=True,
)


# Catalog-driven registration keeps risk, schemas and names at the public
# boundary. Returning the original adapter from decorators is unnecessary:
# Python callers and tests can still exercise adapters directly.
def _register_catalog() -> None:
    from mcp_server.tool_catalog import INTENDED_TOOLS

    for entry in INTENDED_TOOLS:
        fn = getattr(import_module(entry.module), entry.function)
        def wrap(fn):
            @wraps(fn)
            async def invoke(**kwargs) -> dict[str, Any]:
                try:
                    result = fn(**kwargs)
                    if inspect.isawaitable(result):
                        result = await result
                    return envelope(result)
                except Exception as exc:
                    return envelope(backend_error_payload(fn.__name__, exc))
            invoke.__signature__ = inspect.signature(fn, eval_str=True).replace(return_annotation=dict[str, Any])
            return invoke
        mcp.add_tool(wrap(fn), name=entry.name, description=f"Risk: {entry.risk}. {inspect.getdoc(fn) or entry.name}")


_register_catalog()


def main() -> None:
    """Entry point: start with stdio transport (for Cursor and other MCP clients)"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
