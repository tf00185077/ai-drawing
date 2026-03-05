import { Link } from "react-router-dom";

/**
 * Phase 5a: 統一儀表板
 * 四大模組整合介面
 */
export default function Dashboard() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-white">AI 自動化出圖系統</h1>
      <p className="text-slate-400 mt-1">資料夾監聽 · LoRA 訓練 · ComfyUI 產圖 · 參數記錄</p>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-8">
        <ModuleCard title="生圖" desc="ComfyUI 參數面板、批次排程" to="/generate" />
        <ModuleCard title="圖庫" desc="瀏覽、篩選、一鍵重現" to="/gallery" />
        <ModuleCard title="LoRA 文件" desc=".txt 產生、Caption 編輯" to="/lora-docs" />
        <ModuleCard title="LoRA 訓練" desc="訓練執行、產圖 Pipeline" to="/lora-train" />
      </div>
    </div>
  );
}

function ModuleCard({ title, desc, to }) {
  return (
    <Link
      to={to}
      className="block p-4 rounded-lg border border-slate-700 bg-slate-900/50 hover:border-emerald-500/50 transition-colors"
    >
      <h2 className="font-semibold text-emerald-400">{title}</h2>
      <p className="text-sm text-slate-400 mt-1">{desc}</p>
    </Link>
  );
}
