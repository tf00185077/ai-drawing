/**
 * Phase 4: LoRA 訓練與產圖串接
 * 訓練觸發、狀態、佇列管理
 */
export default function LoraTrain() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-white">LoRA 訓練與產圖串接</h1>
      <p className="text-slate-400 mt-1">訓練執行 · 自動觸發 · Pipeline 產圖</p>
      <div className="mt-6 space-y-4">
        <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
          <h2 className="font-semibold text-slate-200">訓練狀態</h2>
          <p className="text-slate-500 text-sm mt-1">TODO: 訓練進度、佇列</p>
        </div>
        <button className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 rounded-lg text-white">
          手動觸發訓練
        </button>
      </div>
    </div>
  );
}
