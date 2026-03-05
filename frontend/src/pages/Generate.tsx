/**
 * Phase 1d: 基礎 UI（參數面板）
 * Checkpoint / LoRA 選單、prompt 輸入、seed / step / cfg
 */
export default function Generate() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-white">生圖模組</h1>
      <div className="mt-6 space-y-4 max-w-xl">
        <Field label="Checkpoint" />
        <Field label="LoRA" />
        <Field label="Prompt" textarea />
        <div className="flex gap-4">
          <Field label="Seed" type="number" />
          <Field label="Steps" type="number" />
          <Field label="CFG" type="number" />
        </div>
        <button className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg text-white">
          生成
        </button>
      </div>
    </div>
  );
}

function Field({ label, type = "text", textarea = false }: { label: string; type?: string; textarea?: boolean }) {
  const Input = textarea ? "textarea" : "input";
  return (
    <div>
      <label className="block text-sm text-slate-400 mb-1">{label}</label>
      <Input
        type={type}
        className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white"
      />
    </div>
  );
}
