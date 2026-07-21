import { useState } from "react";

export interface GenerationForm { id: string; display_name: string }

export default function GenerationPanel({ forms, positivePrompt, negativePrompt }: { forms: GenerationForm[]; positivePrompt: string; negativePrompt: string }) {
  const [workflow, setWorkflow] = useState("");
  const [seedMode, setSeedMode] = useState("random");
  const [job, setJob] = useState("");
  const [error, setError] = useState("");
  async function generate() {
    setError("");
    const response = await fetch("/api/generate/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ template: workflow, prompt: positivePrompt, negative_prompt: negativePrompt, use_workflow_defaults: true, seed_mode: seedMode }) });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) { setError(data?.detail?.message || `HTTP ${response.status}`); return; }
    setJob(data.job_id || "");
  }
  return (
    <section className="rounded-xl border border-slate-700 bg-slate-900/70 p-5">
      <h2 className="text-lg font-semibold text-white">Workflow 生圖</h2>
      <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,1fr)_220px_auto]">
        <label className="text-sm text-slate-400">Workflow<select aria-label="Workflow" value={workflow} onChange={(event) => setWorkflow(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white"><option value="">選擇 workflow</option>{forms.map((form) => <option key={form.id} value={form.id}>{form.display_name}</option>)}</select></label>
        <label className="text-sm text-slate-400">Seed 模式<select aria-label="Seed 模式" value={seedMode} onChange={(event) => setSeedMode(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white"><option value="random">隨機</option><option value="workflow_default">Workflow 預設</option></select></label>
        <button type="button" disabled={!workflow || !positivePrompt.trim()} onClick={generate} className="self-end rounded-lg bg-violet-600 px-5 py-2.5 font-medium text-white disabled:bg-slate-700">開始生圖</button>
      </div>
      {error && <p role="alert" className="mt-3 text-sm text-red-300">{error}</p>}
      {job && <p role="status" className="mt-3 text-sm text-emerald-300">已建立 Job：{job}</p>}
    </section>
  );
}
