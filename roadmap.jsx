import { useState } from "react";

const phases = [
  {
    id: 1,
    title: "Phase 1",
    subtitle: "ComfyUI 自動化核心",
    duration: "Week 1–3",
    color: "#00FFB2",
    icon: "⚡",
    tasks: [
      {
        id: "1a",
        title: "ComfyUI API 串接",
        desc: "透過 ComfyUI 的 WebSocket / REST API 實現遠端觸發圖片生成",
        tags: ["Python", "ComfyUI API"],
        done: false,
      },
      {
        id: "1b",
        title: "Workflow JSON 管理",
        desc: "設計可動態替換參數的 workflow 模板（checkpoint、LoRA、prompt、seed、steps）",
        tags: ["JSON", "Template Engine"],
        done: false,
      },
      {
        id: "1c",
        title: "批次生圖排程器",
        desc: "支援佇列式批次生成，可設定並發數量與優先順序",
        tags: ["Queue", "Async"],
        done: false,
      },
      {
        id: "1d",
        title: "基礎 UI（參數面板）",
        desc: "Checkpoint / LoRA 選單、prompt 輸入、seed / step / cfg 設定欄位",
        tags: ["React", "UI"],
        done: false,
      },
    ],
  },
  {
    id: 2,
    title: "Phase 2",
    subtitle: "參數與圖片記錄系統",
    duration: "Week 4–6",
    color: "#FF6B6B",
    icon: "🗄️",
    tasks: [
      {
        id: "2a",
        title: "資料庫設計",
        desc: "建立 SQLite / PostgreSQL schema：圖片路徑、checkpoint、LoRA、seed、steps、prompt、生成時間",
        tags: ["SQLite", "Schema"],
        done: false,
      },
      {
        id: "2b",
        title: "自動記錄 Pipeline",
        desc: "每次生成後自動寫入所有參數，並將圖片存至結構化資料夾",
        tags: ["Python", "Automation"],
        done: false,
      },
      {
        id: "2c",
        title: "圖片 Gallery 瀏覽器",
        desc: "可搜尋、篩選（依 checkpoint / LoRA / 日期）的圖庫介面，點擊查看完整參數",
        tags: ["React", "Filter/Search"],
        done: false,
      },
      {
        id: "2d",
        title: "一鍵重現 / 參數匯出",
        desc: "從任一歷史圖片重新載入參數再次生成，或匯出為 JSON / CSV",
        tags: ["Export", "Re-run"],
        done: false,
      },
    ],
  },
  {
    id: 3,
    title: "Phase 3",
    subtitle: "LoRA 訓練文件與自動 .txt 產生",
    duration: "Week 7–9",
    color: "#A78BFA",
    icon: "✍️",
    tasks: [
      {
        id: "3a",
        title: "資料夾監聽與即時 .txt 產生",
        desc: "監聽指定訓練資料夾，新圖一丟入即觸發 WD Tagger / BLIP2 自動產生同名 .txt，無需手動上傳",
        tags: ["watchdog", "File Watcher", "WD Tagger"],
        done: false,
      },
      {
        id: "3b",
        title: "圖片上傳介面（選用）",
        desc: "拖曳上傳多張訓練圖片，上傳後即自動產生 .txt，支援批次預覽與刪除",
        tags: ["Upload", "UI"],
        done: false,
      },
      {
        id: "3c",
        title: "Caption 編輯器",
        desc: "可手動編輯每張圖片的 .txt 內容，支援批次加入 trigger word 前綴",
        tags: ["Editor", "Batch Edit"],
        done: false,
      },
      {
        id: "3d",
        title: "打包下載",
        desc: "將圖片 + .txt 文件按 LoRA 訓練資料夾結構打包成 ZIP 下載",
        tags: ["ZIP", "Export"],
        done: false,
      },
    ],
  },
  {
    id: 4,
    title: "Phase 4",
    subtitle: "LoRA 訓練執行與產圖串接",
    duration: "Week 10–12",
    color: "#22D3EE",
    icon: "🔄",
    tasks: [
      {
        id: "4a",
        title: "LoRA 訓練執行器",
        desc: "整合 Kohya sd-scripts 或等效訓練腳本，可指定資料夾、checkpoint、epoch 等參數執行訓練",
        tags: ["sd-scripts", "Python", "Subprocess"],
        done: false,
      },
      {
        id: "4b",
        title: "訓練觸發邏輯",
        desc: "條件一：資料夾圖片數量達可設定門檻（如 ≥10 張）自動觸發；條件二：UI 手動按鈕或 API 訊號觸發",
        tags: ["Trigger", "Config", "API"],
        done: false,
      },
      {
        id: "4c",
        title: "LoRA 訓練完成 → ComfyUI 產圖 Pipeline",
        desc: "訓練完成後自動選用新產出 LoRA，觸發 ComfyUI 生圖 workflow，並將產圖參數寫入記錄系統",
        tags: ["Pipeline", "ComfyUI", "Automation"],
        done: false,
      },
      {
        id: "4d",
        title: "訓練狀態與佇列管理",
        desc: "顯示訓練進度、失敗重試、產圖佇列狀態，避免重複觸發",
        tags: ["Queue", "Status", "UI"],
        done: false,
      },
    ],
  },
  {
    id: 5,
    title: "Phase 5",
    subtitle: "整合優化與進階功能",
    duration: "Week 13–15",
    color: "#FBBF24",
    icon: "🚀",
    tasks: [
      {
        id: "5a",
        title: "統一儀表板",
        desc: "將四大模組整合進單一介面：生圖 / 圖庫 / LoRA 文件工具 / LoRA 訓練與產圖串接",
        tags: ["Dashboard", "UX"],
        done: false,
      },
      {
        id: "5b",
        title: "Prompt 模板庫",
        desc: "儲存常用 prompt 組合，支援變數替換（如人物名稱、風格）",
        tags: ["Templates", "Prompt"],
        done: false,
      },
      {
        id: "5c",
        title: "生成統計分析",
        desc: "視覺化常用參數分佈、最佳 seed 紀錄、各 checkpoint / LoRA 使用頻率",
        tags: ["Analytics", "Charts"],
        done: false,
      },
      {
        id: "5d",
        title: "部署 & 文件",
        desc: "Docker 容器化部署，撰寫使用說明與 API 文件",
        tags: ["Docker", "Docs"],
        done: false,
      },
    ],
  },
];

const techStack = [
  { label: "後端", value: "Python + FastAPI" },
  { label: "前端", value: "React + Tailwind" },
  { label: "資料庫", value: "SQLite / PostgreSQL" },
  { label: "AI 標註", value: "WD Tagger / BLIP2" },
  { label: "圖片引擎", value: "ComfyUI API" },
  { label: "LoRA 訓練", value: "Kohya sd-scripts" },
  { label: "資料夾監聽", value: "watchdog" },
  { label: "部署", value: "Docker" },
];

export default function Roadmap() {
  const [taskState, setTaskState] = useState(() => {
    const init = {};
    phases.forEach((p) => p.tasks.forEach((t) => (init[t.id] = false)));
    return init;
  });
  const [activePhase, setActivePhase] = useState(null);

  const toggle = (id) => setTaskState((s) => ({ ...s, [id]: !s[id] }));

  const phaseProgress = (phase) => {
    const total = phase.tasks.length;
    const done = phase.tasks.filter((t) => taskState[t.id]).length;
    return { done, total, pct: Math.round((done / total) * 100) };
  };

  const totalDone = Object.values(taskState).filter(Boolean).length;
  const totalTasks = Object.values(taskState).length;
  const totalPct = Math.round((totalDone / totalTasks) * 100);

  return (
    <div style={{ fontFamily: "'JetBrains Mono', 'Courier New', monospace", background: "#0A0A0F", minHeight: "100vh", color: "#E2E8F0", padding: "2rem 1.5rem" }}>
      {/* Header */}
      <div style={{ maxWidth: 860, margin: "0 auto 2.5rem" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.5rem" }}>
          <span style={{ fontSize: "1.5rem" }}>🎨</span>
          <span style={{ color: "#00FFB2", fontSize: "0.75rem", letterSpacing: "0.2em", textTransform: "uppercase" }}>Development Roadmap</span>
        </div>
        <h1 style={{ fontSize: "clamp(1.6rem, 4vw, 2.4rem)", fontWeight: 700, margin: "0 0 0.25rem", color: "#fff", letterSpacing: "-0.02em" }}>
          AI 自動化出圖系統
        </h1>
        <p style={{ color: "#64748B", fontSize: "0.85rem", margin: "0 0 1.5rem" }}>資料夾監聽自動 .txt · LoRA 訓練觸發 · ComfyUI 產圖 · 參數記錄</p>

        {/* Overall progress */}
        <div style={{ background: "#13131A", border: "1px solid #1E293B", borderRadius: 12, padding: "1rem 1.25rem", display: "flex", alignItems: "center", gap: "1.5rem" }}>
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
              <span style={{ fontSize: "0.75rem", color: "#94A3B8" }}>整體進度</span>
              <span style={{ fontSize: "0.75rem", color: "#00FFB2" }}>{totalDone} / {totalTasks} 完成</span>
            </div>
            <div style={{ height: 6, background: "#1E293B", borderRadius: 99, overflow: "hidden" }}>
              <div style={{ height: "100%", width: `${totalPct}%`, background: "linear-gradient(90deg, #00FFB2, #A78BFA)", borderRadius: 99, transition: "width 0.4s ease" }} />
            </div>
          </div>
          <div style={{ fontSize: "1.6rem", fontWeight: 700, color: "#00FFB2", minWidth: 52, textAlign: "right" }}>{totalPct}%</div>
        </div>
      </div>

      {/* Phases */}
      <div style={{ maxWidth: 860, margin: "0 auto", display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        {phases.map((phase) => {
          const { done, total, pct } = phaseProgress(phase);
          const open = activePhase === phase.id;
          return (
            <div key={phase.id} style={{ border: `1px solid ${open ? phase.color + "55" : "#1E293B"}`, borderRadius: 14, overflow: "hidden", background: "#0D0D14", transition: "border-color 0.3s" }}>
              {/* Phase header */}
              <button
                onClick={() => setActivePhase(open ? null : phase.id)}
                style={{ width: "100%", background: "none", border: "none", cursor: "pointer", padding: "1rem 1.25rem", display: "flex", alignItems: "center", gap: "1rem", textAlign: "left" }}
              >
                <div style={{ width: 40, height: 40, borderRadius: 10, background: phase.color + "22", border: `1px solid ${phase.color}44`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: "1.1rem", flexShrink: 0 }}>
                  {phase.icon}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem" }}>
                    <span style={{ color: phase.color, fontSize: "0.7rem", letterSpacing: "0.15em", textTransform: "uppercase" }}>{phase.title}</span>
                    <span style={{ color: "#fff", fontWeight: 600, fontSize: "0.95rem" }}>{phase.subtitle}</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginTop: 5 }}>
                    <div style={{ flex: 1, height: 3, background: "#1E293B", borderRadius: 99, overflow: "hidden", maxWidth: 140 }}>
                      <div style={{ height: "100%", width: `${pct}%`, background: phase.color, borderRadius: 99, transition: "width 0.4s" }} />
                    </div>
                    <span style={{ fontSize: "0.7rem", color: "#64748B" }}>{done}/{total}</span>
                    <span style={{ fontSize: "0.7rem", color: "#475569", marginLeft: "auto" }}>{phase.duration}</span>
                  </div>
                </div>
                <span style={{ color: "#475569", fontSize: "1rem", transition: "transform 0.3s", transform: open ? "rotate(180deg)" : "rotate(0deg)" }}>▾</span>
              </button>

              {/* Tasks */}
              {open && (
                <div style={{ borderTop: `1px solid #1E293B`, padding: "0.75rem 1.25rem 1.25rem" }}>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
                    {phase.tasks.map((task) => (
                      <div
                        key={task.id}
                        onClick={() => toggle(task.id)}
                        style={{ display: "flex", alignItems: "flex-start", gap: "0.75rem", padding: "0.75rem 1rem", background: taskState[task.id] ? phase.color + "0D" : "#13131A", border: `1px solid ${taskState[task.id] ? phase.color + "44" : "#1E293B"}`, borderRadius: 10, cursor: "pointer", transition: "all 0.2s" }}
                      >
                        <div style={{ width: 20, height: 20, borderRadius: 6, border: `2px solid ${taskState[task.id] ? phase.color : "#334155"}`, background: taskState[task.id] ? phase.color : "transparent", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0, marginTop: 1, transition: "all 0.2s" }}>
                          {taskState[task.id] && <span style={{ color: "#000", fontSize: "0.65rem", fontWeight: 700 }}>✓</span>}
                        </div>
                        <div style={{ flex: 1 }}>
                          <div style={{ fontWeight: 600, fontSize: "0.875rem", color: taskState[task.id] ? "#94A3B8" : "#E2E8F0", textDecoration: taskState[task.id] ? "line-through" : "none", marginBottom: 3 }}>{task.title}</div>
                          <div style={{ fontSize: "0.775rem", color: "#64748B", lineHeight: 1.5 }}>{task.desc}</div>
                          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.3rem", marginTop: "0.4rem" }}>
                            {task.tags.map((tag) => (
                              <span key={tag} style={{ fontSize: "0.65rem", padding: "2px 7px", background: phase.color + "18", border: `1px solid ${phase.color}33`, borderRadius: 99, color: phase.color, letterSpacing: "0.05em" }}>{tag}</span>
                            ))}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Tech Stack */}
      <div style={{ maxWidth: 860, margin: "2rem auto 0" }}>
        <div style={{ borderTop: "1px solid #1E293B", paddingTop: "1.5rem" }}>
          <div style={{ fontSize: "0.7rem", color: "#475569", letterSpacing: "0.15em", textTransform: "uppercase", marginBottom: "0.75rem" }}>Tech Stack</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem" }}>
            {techStack.map((t) => (
              <div key={t.label} style={{ background: "#13131A", border: "1px solid #1E293B", borderRadius: 8, padding: "0.4rem 0.8rem", fontSize: "0.75rem" }}>
                <span style={{ color: "#64748B" }}>{t.label}: </span>
                <span style={{ color: "#E2E8F0" }}>{t.value}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
