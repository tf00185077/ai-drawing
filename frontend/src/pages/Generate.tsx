/**
 * Phase 1d: 基礎 UI（參數面板）
 * Checkpoint / LoRA 選單、prompt 輸入、seed / step / cfg
 * 對應 docs/api-contract.md 模組 1
 */
import { useCallback, useEffect, useState } from "react";
import type { GenerateRequest, GenerateResponse, QueueStatusResponse } from "../types/api";

const API = "/api";

const DEFAULT_STEPS = 20;
const DEFAULT_CFG = 7.0;

export default function Generate() {
  const [checkpoint, setCheckpoint] = useState("");
  const [lora, setLora] = useState("");
  const [prompt, setPrompt] = useState("");
  const [negativePrompt, setNegativePrompt] = useState("");
  const [seed, setSeed] = useState<string>("");
  const [steps, setSteps] = useState<string>(String(DEFAULT_STEPS));
  const [cfg, setCfg] = useState<string>(String(DEFAULT_CFG));

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<GenerateResponse | null>(null);

  const [queueStatus, setQueueStatus] = useState<QueueStatusResponse | null>(null);
  const [queueLoading, setQueueLoading] = useState(false);

  const fetchQueue = useCallback(async () => {
    setQueueLoading(true);
    try {
      const res = await fetch(`${API}/generate/queue`);
      if (res.ok) {
        const data: QueueStatusResponse = await res.json();
        setQueueStatus(data);
      }
    } catch {
      setQueueStatus(null);
    } finally {
      setQueueLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchQueue();
    const id = setInterval(fetchQueue, 3000);
    return () => clearInterval(id);
  }, [fetchQueue]);

  const handleSubmit = useCallback(async () => {
    const promptTrimmed = prompt.trim();
    if (!promptTrimmed) {
      setError("請輸入 Prompt");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setLastResult(null);

    try {
      const body: GenerateRequest = {
        prompt: promptTrimmed,
      };
      if (checkpoint.trim()) body.checkpoint = checkpoint.trim();
      if (lora.trim()) body.lora = lora.trim();
      if (negativePrompt.trim()) body.negative_prompt = negativePrompt.trim();
      const seedNum = parseInt(seed, 10);
      if (!Number.isNaN(seedNum)) body.seed = seedNum;
      const stepsNum = parseInt(steps, 10);
      if (!Number.isNaN(stepsNum) && stepsNum >= 1) body.steps = stepsNum;
      const cfgNum = parseFloat(cfg);
      if (!Number.isNaN(cfgNum) && cfgNum >= 1) body.cfg = cfgNum;

      const res = await fetch(`${API}/generate/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || `請求失敗: ${res.status}`);
      }

      setLastResult(data as GenerateResponse);
      fetchQueue();
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失敗");
    } finally {
      setIsSubmitting(false);
    }
  }, [prompt, checkpoint, lora, negativePrompt, seed, steps, cfg, fetchQueue]);

  const clearLastResult = useCallback(() => {
    setLastResult(null);
    setError(null);
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">生圖模組</h1>
      <p className="text-slate-400 mt-1">ComfyUI 參數面板、批次排程</p>

      <div className="mt-6 space-y-4 max-w-xl">
        <Field
          label="Checkpoint"
          value={checkpoint}
          onChange={setCheckpoint}
          placeholder="例如: v1-5-pruned-emaonly.safetensors"
        />
        <Field
          label="LoRA"
          value={lora}
          onChange={setLora}
          placeholder="例如: style.safetensors"
        />
        <Field
          label="Prompt"
          value={prompt}
          onChange={setPrompt}
          textarea
          placeholder="必填，例如: 1girl, solo, ..."
          required
        />
        <Field
          label="Negative Prompt"
          value={negativePrompt}
          onChange={setNegativePrompt}
          textarea
          placeholder="選填，例如: lowres, blur"
        />
        <div className="flex gap-4">
          <Field
            label="Seed"
            type="number"
            value={seed}
            onChange={setSeed}
            placeholder="留空則隨機"
          />
          <Field
            label="Steps"
            type="number"
            value={steps}
            onChange={setSteps}
            placeholder={String(DEFAULT_STEPS)}
          />
          <Field
            label="CFG"
            type="number"
            value={cfg}
            onChange={setCfg}
            placeholder={String(DEFAULT_CFG)}
          />
        </div>

        {error && (
          <div className="p-3 rounded-lg bg-red-500/20 border border-red-500/50 text-red-300 text-sm">
            {error}
          </div>
        )}

        {lastResult && (
          <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/50">
            <p className="text-emerald-300 font-medium">
              已加入佇列 · job_id: {lastResult.job_id.slice(0, 8)}…
            </p>
            <button
              type="button"
              onClick={clearLastResult}
              className="mt-2 text-sm text-slate-500 hover:text-slate-400"
            >
              關閉
            </button>
          </div>
        )}

        <button
          type="button"
          onClick={handleSubmit}
          disabled={isSubmitting}
          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-slate-600 disabled:cursor-not-allowed rounded-lg text-white transition-colors"
        >
          {isSubmitting ? "提交中…" : "生成"}
        </button>
      </div>

      <div className="mt-8 max-w-xl">
        <h2 className="text-lg font-semibold text-slate-300">佇列狀態</h2>
        {queueLoading && !queueStatus ? (
          <p className="mt-2 text-slate-500">載入中…</p>
        ) : queueStatus ? (
          <div className="mt-2 space-y-2">
            <p className="text-sm text-slate-400">
              執行中: {queueStatus.queue_running.length} · 等候中: {queueStatus.queue_pending.length}
            </p>
            {(queueStatus.queue_running.length > 0 || queueStatus.queue_pending.length > 0) && (
              <ul className="rounded-lg bg-slate-800/50 border border-slate-700 p-3 space-y-2 text-sm">
                {queueStatus.queue_running.map((item) => (
                  <li key={item.job_id} className="flex justify-between text-amber-300">
                    <span>{item.job_id.slice(0, 8)}…</span>
                    <span>執行中</span>
                  </li>
                ))}
                {queueStatus.queue_pending.map((item) => (
                  <li key={item.job_id} className="flex justify-between text-slate-400">
                    <span>{item.job_id.slice(0, 8)}…</span>
                    <span>等候中</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  type = "text",
  textarea = false,
  placeholder,
  required = false,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: string;
  textarea?: boolean;
  placeholder?: string;
  required?: boolean;
}) {
  const Input = textarea ? "textarea" : "input";
  const baseClass =
    "w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500";
  const inputClass = textarea ? `${baseClass} min-h-[80px] resize-y` : baseClass;

  return (
    <div>
      <label className="block text-sm text-slate-400 mb-1">
        {label}
        {required && <span className="text-amber-400 ml-1">*</span>}
      </label>
      <Input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className={inputClass}
        rows={textarea ? 3 : undefined}
      />
    </div>
  );
}
