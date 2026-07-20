import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import SystemStatusCard, { type ComfyUIStatus, type ComfyUIState } from "../components/SystemStatusCard";

type SystemStatusResponse = {
  application: "healthy";
  comfyui: ComfyUIStatus;
};

const states: readonly ComfyUIState[] = [
  "connected", "not_configured", "unreachable", "no_models", "degraded",
];

function isNonNegativeInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value >= 0;
}

function isSystemStatusResponse(value: unknown): value is SystemStatusResponse {
  if (!value || typeof value !== "object") return false;
  const response = value as Record<string, unknown>;
  const comfyui = response.comfyui;
  if (response.application !== "healthy" || !comfyui || typeof comfyui !== "object") return false;
  const status = comfyui as Record<string, unknown>;
  return (
    (status.mode === "disabled" || status.mode === "external" || status.mode === "managed")
    && typeof status.state === "string" && states.includes(status.state as ComfyUIState)
    && typeof status.configured === "boolean"
    && typeof status.reachable === "boolean"
    && isNonNegativeInteger(status.model_count)
    && isNonNegativeInteger(status.checkpoint_count)
    && isNonNegativeInteger(status.diffusion_model_count)
    && Array.isArray(status.warnings) && status.warnings.every((warning) => typeof warning === "string")
    && typeof status.hint === "string"
  );
}

export default function Dashboard() {
  const [status, setStatus] = useState<ComfyUIStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [statusError, setStatusError] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    let isMounted = true;

    async function loadStatus() {
      try {
        const response = await fetch("/api/system/status", { signal: controller.signal });
        if (!response.ok) throw new Error("System status request failed");
        const payload: unknown = await response.json();
        if (!isSystemStatusResponse(payload)) throw new Error("Malformed system status response");
        if (isMounted) setStatus(payload.comfyui);
      } catch {
        if (isMounted && !controller.signal.aborted) setStatusError(true);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    void loadStatus();
    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">AI 自動化出圖系統</h1>
      <p className="mt-1 text-slate-400">資料夾監聽 · LoRA 訓練 · ComfyUI 產圖 · 參數記錄</p>
      {isLoading && <p aria-live="polite" className="mt-6 text-sm text-slate-400">正在讀取 ComfyUI 狀態…</p>}
      {statusError && <p role="alert" className="mt-6 text-sm text-rose-300">無法讀取 ComfyUI 狀態。</p>}
      {status && <SystemStatusCard status={status} />}
      <div className="mt-8 grid grid-cols-2 gap-4 md:grid-cols-4">
        <ModuleCard title="生圖" desc="ComfyUI 參數面板、批次排程" to="/generate" />
        <ModuleCard title="圖庫" desc="瀏覽、篩選、一鍵重現" to="/gallery" />
        <ModuleCard title="LoRA 文件" desc=".txt 產生、Caption 編輯" to="/lora-docs" />
        <ModuleCard title="LoRA 訓練" desc="訓練執行、產圖 Pipeline" to="/lora-train" />
      </div>
    </div>
  );
}

function ModuleCard({ title, desc, to }: { title: string; desc: string; to: string }) {
  return (
    <Link
      to={to}
      className="block rounded-lg border border-slate-700 bg-slate-900/50 p-4 transition-colors hover:border-emerald-500/50"
    >
      <h2 className="font-semibold text-emerald-400">{title}</h2>
      <p className="mt-1 text-sm text-slate-400">{desc}</p>
    </Link>
  );
}
