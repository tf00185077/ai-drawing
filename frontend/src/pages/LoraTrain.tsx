/**
 * Phase 4d: LoRA 訓練與產圖串接
 * 訓練狀態、佇列、手動觸發、trigger-check
 * 對應 docs/api-contract.md 模組 4
 */
import { useCallback, useEffect, useState } from "react";
import type {
  TrainStartRequest,
  TrainStartResponse,
  TrainStatusResponse,
  TriggerCheckResponse,
} from "../types/api";

const API = "/api";

const DEFAULT_EPOCHS = 10;

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: "text" | "number";
}) {
  return (
    <div>
      <label className="block text-sm font-medium text-slate-300 mb-1">
        {label}
      </label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500"
      />
    </div>
  );
}

export default function LoraTrain() {
  const [status, setStatus] = useState<TrainStatusResponse | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const [folder, setFolder] = useState("");
  const [checkpoint, setCheckpoint] = useState("");
  const [epochs, setEpochs] = useState<string>(String(DEFAULT_EPOCHS));
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [lastStart, setLastStart] = useState<TrainStartResponse | null>(null);

  const [triggerResult, setTriggerResult] =
    useState<TriggerCheckResponse | null>(null);
  const [triggerLoading, setTriggerLoading] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const fetchStatus = useCallback(async () => {
    setStatusLoading(true);
    try {
      const res = await fetch(`${API}/lora-train/status`);
      if (res.ok) {
        const data: TrainStatusResponse = await res.json();
        setStatus(data);
      }
    } catch {
      setStatus(null);
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 3000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  const handleStart = useCallback(async () => {
    const folderTrimmed = folder.trim();
    if (!folderTrimmed) {
      setStartError("請輸入訓練資料夾");
      return;
    }

    setIsSubmitting(true);
    setStartError(null);
    setLastStart(null);

    try {
      const body: TrainStartRequest = {
        folder: folderTrimmed,
      };
      if (checkpoint.trim()) body.checkpoint = checkpoint.trim();
      const epochsNum = parseInt(epochs, 10);
      if (!Number.isNaN(epochsNum) && epochsNum >= 1) body.epochs = epochsNum;

      const res = await fetch(`${API}/lora-train/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : Array.isArray(data.detail)
              ? data.detail.map((d: { msg?: string }) => d.msg).join(", ")
              : `請求失敗: ${res.status}`
        );
      }

      setLastStart(data as TrainStartResponse);
      fetchStatus();
    } catch (err) {
      setStartError(err instanceof Error ? err.message : "提交失敗");
    } finally {
      setIsSubmitting(false);
    }
  }, [folder, checkpoint, epochs, fetchStatus]);

  const handleTriggerCheck = useCallback(async () => {
    setTriggerLoading(true);
    setTriggerError(null);
    setTriggerResult(null);
    try {
      const res = await fetch(`${API}/lora-train/trigger-check`, {
        method: "POST",
      });
      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(data.detail || `請求失敗: ${res.status}`);
      }

      setTriggerResult(data as TriggerCheckResponse);
      fetchStatus();
    } catch (err) {
      setTriggerError(err instanceof Error ? err.message : "檢查失敗");
    } finally {
      setTriggerLoading(false);
    }
  }, [fetchStatus]);

  const clearLastStart = useCallback(() => {
    setLastStart(null);
    setStartError(null);
  }, []);

  const statusLabel =
    status?.status === "idle"
      ? "閒置"
      : status?.status === "running"
        ? "訓練中"
        : status?.status === "queued"
          ? "佇列中"
          : "-";

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">
        LoRA 訓練與產圖串接
      </h1>
      <p className="text-slate-400 mt-1">
        訓練執行 · 自動觸發 · Pipeline 產圖
      </p>

      <div className="mt-6 space-y-6 max-w-2xl">
        {/* 訓練狀態 */}
        <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
          <h2 className="font-semibold text-slate-200 mb-3">訓練狀態</h2>
          {statusLoading && !status ? (
            <p className="text-slate-500 text-sm">載入中...</p>
          ) : (
            <div className="space-y-2">
              <p className="text-slate-300">
                狀態：{" "}
                <span
                  className={
                    status?.status === "running"
                      ? "text-amber-400"
                      : status?.status === "queued"
                        ? "text-cyan-400"
                        : "text-slate-400"
                  }
                >
                  {statusLabel}
                </span>
              </p>
              {status?.current_job && (
                <div className="mt-2 p-2 rounded bg-slate-900/50 text-sm">
                  <p className="text-slate-300">
                    目前：{status.current_job.folder}
                    {status.current_job.progress != null && (
                      <span className="ml-2 text-cyan-400">
                        {Math.round(status.current_job.progress * 100)}%
                      </span>
                    )}
                    {status.current_job.epoch != null &&
                      status.current_job.total_epochs != null && (
                        <span className="ml-2 text-slate-400">
                          epoch {status.current_job.epoch}/
                          {status.current_job.total_epochs}
                        </span>
                      )}
                  </p>
                </div>
              )}
              {status?.queue && status.queue.length > 0 && (
                <div className="mt-2">
                  <p className="text-slate-400 text-sm">等候中：</p>
                  <ul className="mt-1 space-y-0.5 text-sm text-slate-300">
                    {status.queue.map((q) => (
                      <li key={q.job_id}>
                        {q.folder} <span className="text-slate-500">({q.job_id.slice(0, 8)})</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 手動觸發 */}
        <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
          <h2 className="font-semibold text-slate-200 mb-3">手動觸發訓練</h2>
          <div className="space-y-3">
            <Field
              label="訓練資料夾（相對 lora_train_dir）"
              value={folder}
              onChange={setFolder}
              placeholder="例如: my_lora 或 chars/hero"
            />
            <Field
              label="Checkpoint（選填，不填則用 config 預設）"
              value={checkpoint}
              onChange={setCheckpoint}
              placeholder="例如: v1-5-pruned-emaonly.safetensors"
            />
            <Field
              label="Epochs"
              value={epochs}
              onChange={setEpochs}
              placeholder="10"
              type="number"
            />
            {startError && (
              <p className="text-red-400 text-sm">{startError}</p>
            )}
            {lastStart && (
              <p className="text-green-400 text-sm">
                已加入佇列：{lastStart.job_id.slice(0, 8)}...
              </p>
            )}
            <div className="flex gap-2">
              <button
                onClick={handleStart}
                disabled={isSubmitting}
                className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-white"
              >
                {isSubmitting ? "提交中..." : "開始訓練"}
              </button>
              {lastStart && (
                <button
                  onClick={clearLastStart}
                  className="px-4 py-2 bg-slate-600 hover:bg-slate-500 rounded-lg text-slate-200"
                >
                  清除
                </button>
              )}
            </div>
          </div>
        </div>

        {/* 自動觸發檢查 */}
        <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
          <h2 className="font-semibold text-slate-200 mb-3">
            自動觸發檢查（圖片數 ≥ 門檻）
          </h2>
          <p className="text-slate-400 text-sm mb-3">
            檢查各資料夾是否符合訓練門檻，符合者自動加入佇列
          </p>
          {triggerError && (
            <p className="text-red-400 text-sm mb-2">{triggerError}</p>
          )}
          {triggerResult && (
            <div className="mb-3 p-2 rounded bg-slate-900/50 text-sm">
              {triggerResult.should_trigger ? (
                <div>
                  <p className="text-cyan-400">符合條件：</p>
                  <ul className="mt-1 space-y-0.5 text-slate-300">
                    {triggerResult.candidates.map((c) => (
                      <li key={c.folder}>
                        {c.folder}（{c.image_count} 張）
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="text-slate-400">目前無資料夾達門檻</p>
              )}
            </div>
          )}
          <button
            onClick={handleTriggerCheck}
            disabled={triggerLoading}
            className="px-4 py-2 bg-slate-600 hover:bg-slate-500 disabled:opacity-50 rounded-lg text-white"
          >
            {triggerLoading ? "檢查中..." : "執行檢查"}
          </button>
        </div>
      </div>
    </div>
  );
}
