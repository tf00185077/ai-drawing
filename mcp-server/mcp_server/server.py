"""
AI Drawing MCP Server

Uses FastMCP, communicates with Cursor and other MCP clients via stdio.
Tools are defined in the mcp_server.tools module.
"""
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import ValidationError

# ``python -m mcp_server.server`` executes this file as ``__main__``.  Tool
# modules import ``mcp_server.server`` to obtain the shared FastMCP instance;
# without this alias Python loads a second copy and registers every non-ping
# tool on an instance that is never served.
if __name__ == "__main__":
    sys.modules["mcp_server.server"] = sys.modules[__name__]

from mcp_server.client import HttpBackendClient
from mcp_server.config import get_mcp_settings


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
    """Return redacted structured results for LoRA Start argument failures."""

    def _convert_contract_result(
        self,
        name: str,
        result: dict[str, Any],
    ) -> Any:
        tool = self._tool_manager.get_tool(name)
        if tool is None:  # pragma: no cover - registration changed mid-call
            raise RuntimeError(f"tool disappeared during validation: {name}")
        return tool.fn_metadata.convert_result(result)

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
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
        try:
            return await super().call_tool(name, arguments)
        except ToolError as exc:
            cause = exc.__cause__
            if name != "lora_train_start" or not isinstance(cause, ValidationError):
                raise

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


mcp = ContractFastMCP(
    "AI Drawing",
    json_response=True,
)


def _get_client() -> HttpBackendClient:
    """Get the Backend API Client (injectable for testing)"""
    settings = get_mcp_settings()
    return HttpBackendClient(base_url=f"{settings.backend_api_url}/api")


@mcp.tool()
def mcp_ping() -> str:
    """Check MCP Server and Backend connection status. Returns an error if the Backend is not running."""
    try:
        # Use the /health endpoint, independent of DB or gallery
        settings = get_mcp_settings()
        client = HttpBackendClient(base_url=settings.backend_api_url, timeout=5.0)
        client.get("health")
        return "ok: Backend 連線正常"
    except Exception as e:
        return f"error: {e}"


# Register tools modules (importing triggers @mcp.tool() decorators)
from mcp_server.tools import (  # noqa: E402, F401
    civitai,
    comfyui,
    comfyui_nodes,
    gallery,
    generate,
    lora_train,
    prompt_library,
    style_presets,
)


def main() -> None:
    """Entry point: start with stdio transport (for Cursor and other MCP clients)"""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
