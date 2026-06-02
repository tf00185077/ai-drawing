---
name: comfyui-api-client
description: ComfyUI REST/WebSocket API - endpoints, workflow submission, queue, history, object_info. Use when building Python clients to trigger ComfyUI workflows, manage queue, or fetch generated images.
---

# ComfyUI API Client Reference

ComfyUI exposes a REST + WebSocket API for external clients. Base URL for self-hosted: `http://127.0.0.1:8188` (default port 8188).

## Quick Start

```python
import json
import requests

BASE = "http://127.0.0.1:8188"

# Load API-formatted workflow (File → Export (API) in ComfyUI)
prompt = json.load(open("workflow_API.json", encoding="utf-8"))

# Submit workflow
res = requests.post(f"{BASE}/prompt", json={"prompt": prompt}).json()
# {"prompt_id": "uuid...", "number": 1} or {"error": "...", "node_errors": {...}}

prompt_id = res["prompt_id"]

# Get results (poll or use WebSocket for real-time)
history = requests.get(f"{BASE}/history/{prompt_id}").json()
# Extract output image paths from history[prompt_id]["outputs"]
```

## Core REST Endpoints

| Path | Method | Purpose |
|------|--------|---------|
| `/prompt` | POST | Submit workflow, returns `prompt_id` and `number` (queue position) |
| `/prompt` | GET | Current queue status and execution info |
| `/history` | GET | Queue history |
| `/history/{prompt_id}` | GET | Results for a specific prompt |
| `/history` | POST | Clear history or delete item |
| `/queue` | GET | Current execution queue state |
| `/queue` | POST | Manage queue (clear pending/running) |
| `/interrupt` | POST | Stop current workflow execution |
| `/object_info` | GET | All node types and input/output specs |
| `/object_info/{node_class}` | GET | Single node type details |
| `/view` | GET | Fetch image by filename, subfolder, type |
| `/upload/image` | POST | Upload image |
| `/upload/mask` | POST | Upload mask |
| `/embeddings` | GET | List embedding names |
| `/models` | GET | List model types |
| `/models/{folder}` | GET | Models in folder (e.g. checkpoints, loras) |
| `/system_stats` | GET | Python version, devices, VRAM, etc. |
| `/features` | GET | Server capabilities |
| `/free` | POST | Unload models to free memory |

## Workflow Submission

### POST /prompt

```python
# Request body
{
    "prompt": { ... },        # API-formatted workflow (required)
    "client_id": "optional",  # Optional client ID for WebSocket correlation
    "extra_data": {}          # Optional metadata
}

# Success response
{"prompt_id": "uuid-string", "number": 1}

# Error response
{"error": "error message", "node_errors": {"node_id": "error detail"}}
```

### API Workflow Format

- Use **File → Export (API)** in ComfyUI to get API-formatted JSON (strips UI-only data).
- Structure: node IDs as string keys, each node has `class_type` and `inputs`.

```json
{
  "3": {
    "inputs": { "ckpt_name": "model.safetensors" },
    "class_type": "CheckpointLoaderSimple"
  },
  "6": {
    "inputs": {
      "text": "positive prompt",
      "clip": ["4", 1]
    },
    "class_type": "CLIPTextEncode"
  }
}
```

- `inputs` values: direct value or link `[node_id, output_index]`.
- Modify params before POST: e.g. `prompt["6"]["inputs"]["text"] = new_prompt`.

## Getting Results

### GET /history/{prompt_id}

```python
history = requests.get(f"{BASE}/history/{prompt_id}").json()
# history = { prompt_id: { "outputs": { node_id: { "images": [...], "gifs": [...] } }, "status": {...} } }

outputs = history[prompt_id]["outputs"]
for node_id, node_out in outputs.items():
    for img in node_out.get("images", []):
        filename = img["filename"]
        subfolder = img.get("subfolder", "")
        ftype = img.get("type", "output")
        # Fetch via /view
```

### GET /view

```
GET /view?filename={filename}&subfolder={subfolder}&type={output|input|temp}
```

Returns image bytes. Use to download generated images.

## Queue Management

### GET /queue

Returns current queue state (running, pending).

### POST /queue

```python
# Clear all pending
requests.post(f"{BASE}/queue", json={"clear": True})

# Clear running
requests.post(f"{BASE}/queue", json={"clear_running": True})
```

## Object Info (Node Schemas)

### GET /object_info

Returns all registered node types with input/output definitions. Use to:
- Discover available nodes and their `class_type` names.
- Build or validate workflow JSON.
- Map widget names to types for parameter replacement.

```python
obj = requests.get(f"{BASE}/object_info").json()
# obj["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"] → [["model1.safetensors", ...]]
```

## WebSocket /ws

Real-time bidirectional communication. Connect to `ws://127.0.0.1:8188/ws`.

### Message Types (server → client)

| Type | Description |
|------|-------------|
| `execution_start` | Prompt execution began |
| `executing` | Node execution updates |
| `executed` | Node completed |
| `execution_cached` | Cached result used |
| `progress` | Long-running progress (value, max, node) |
| `status` | System status (queue info, etc.) |

### Example (Python)

```python
import asyncio
import websockets
import json

async def listen():
    async with websockets.connect("ws://127.0.0.1:8188/ws") as ws:
        async for msg in ws:
            data = json.loads(msg)
            if data.get("type") == "executed":
                print("Node done:", data)
            elif data.get("type") == "progress":
                print("Progress:", data.get("data"))
```

## Common Patterns

### Replace prompt in workflow

```python
prompt = json.load(open("workflow_API.json"))
# Find CLIPTextEncode node (inspect JSON for node IDs)
prompt["6"]["inputs"]["text"] = "new positive prompt"
prompt["7"]["inputs"]["text"] = "new negative prompt"
requests.post(f"{BASE}/prompt", json={"prompt": prompt})
```

### Replace checkpoint / LoRA

```python
# CheckpointLoaderSimple
prompt["3"]["inputs"]["ckpt_name"] = "other_model.safetensors"

# LoraLoader
prompt["8"]["inputs"]["lora_name"] = "style.safetensors"
prompt["8"]["inputs"]["strength_model"] = 0.8
```

### Replace seed

```python
# KSampler
prompt["9"]["inputs"]["seed"] = 12345
```

### Download output image

```python
def get_image(filename, subfolder="", ftype="output"):
    r = requests.get(f"{BASE}/view", params={
        "filename": filename, "subfolder": subfolder, "type": ftype
    })
    return r.content

# After history fetch:
for img in outputs[node_id]["images"]:
    data = get_image(img["filename"], img.get("subfolder", ""), img.get("type", "output"))
    with open("out.png", "wb") as f:
        f.write(data)
```

## Reference URLs

- Routes: https://docs.comfy.org/development/comfyui-server/comms_routes
- Server overview: https://docs.comfy.org/development/comfyui-server/comms_overview
- Tutorial: https://comfyui.nomadoor.net/en/data-utilities/api-run-workflow/

## See Also

- `comfyui-node-datatypes` - Data types (IMAGE, LATENT, etc.) when interpreting workflow structure
- Project `backend/app/core/comfyui.py` - Implementation target for auto-draw
