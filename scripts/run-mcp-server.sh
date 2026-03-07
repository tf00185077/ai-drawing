#!/bin/bash
# MCP Server 啟動腳本（供 Cursor 使用）
# 從專案根目錄執行時，會切換到 mcp-server 並啟動
cd "$(dirname "$0")/../mcp-server" && uv run ai-drawing-mcp
