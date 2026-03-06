# 對接文件索引

> 並行開發時，各軌道依此索引取得所需契約與介面。完成後對接驗證亦以此為準。  
> **分工對應**：見 [agent-assignment.md](./agent-assignment.md)

---

## 文件清單

| 文件 | 用途 | 讀者 |
|------|------|------|
| [agent-assignment.md](./agent-assignment.md) | 代理人 A–F 分工、並行步驟、介面引用 | **全員** |
| [api-contract.md](./api-contract.md) | REST API 完整契約（Request/Response） | 前端、後端、MCP |
| [internal-interfaces.md](./internal-interfaces.md) | 後端模組間函式簽名與回呼 | 後端各軌道 |
| [comfyui-di-design.md](./comfyui-di-design.md) | ComfyUI 模組 DI 與 Protocol 設計 | 生圖軌道 |

---

## 程式碼對應

| 契約 | 對應程式碼 |
|------|------------|
| API Request/Response | `backend/app/schemas/*.py` |
| API 型別（前端） | `frontend/src/types/api.ts` |
| 資料庫模型 | `backend/app/db/models.py` |

---

## 使用方式

1. **前端開發**：依 `api-contract.md` 與 `frontend/src/types/api.ts` 呼叫 API；可用 MSW 或後端 mock 模式先行開發。
2. **後端 API**：依 `api-contract.md` 實作，使用 `app/schemas` 的 Pydantic 模型。
3. **後端內部模組**：依 `internal-interfaces.md` 定義的函式簽名實作，對接時直接匯入呼叫。
