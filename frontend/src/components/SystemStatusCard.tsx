export type ComfyUIState =
  | "connected"
  | "not_configured"
  | "unreachable"
  | "no_models"
  | "degraded";

export type ComfyUIStatus = {
  mode: "disabled" | "external" | "managed";
  state: ComfyUIState;
  configured: boolean;
  reachable: boolean;
  model_count: number;
  checkpoint_count: number;
  diffusion_model_count: number;
  warnings: string[];
  hint: string;
};

type StatePresentation = {
  icon: string;
  label: string;
  className: string;
};

function assertNever(value: never): never {
  throw new Error(`Unsupported ComfyUI state: ${value}`);
}

function presentationFor(state: ComfyUIState): StatePresentation {
  switch (state) {
    case "connected":
      return { icon: "✓", label: "ComfyUI 已就緒", className: "border-emerald-500/50" };
    case "not_configured":
      return { icon: "○", label: "ComfyUI 尚未設定", className: "border-slate-600" };
    case "unreachable":
      return { icon: "!", label: "ComfyUI 無法連線", className: "border-rose-500/50" };
    case "no_models":
      return { icon: "!", label: "ComfyUI 已連線，但尚無模型", className: "border-amber-500/50" };
    case "degraded":
      return { icon: "!", label: "ComfyUI 可使用，但需要注意", className: "border-amber-500/50" };
    default:
      return assertNever(state);
  }
}

export default function SystemStatusCard({ status }: { status: ComfyUIStatus }) {
  const presentation = presentationFor(status.state);

  return (
    <section
      aria-label="ComfyUI 狀態"
      aria-live="polite"
      className={`mt-6 rounded-lg border bg-slate-900/50 p-4 ${presentation.className}`}
      role="status"
    >
      <div className="flex items-center gap-2">
        <span aria-hidden="true" className="text-lg font-bold">{presentation.icon}</span>
        <h2 className="font-semibold text-white">{presentation.label}</h2>
      </div>
      <p className="mt-2 text-sm text-slate-300">{status.hint}</p>
      <dl className="mt-3 grid gap-1 text-sm text-slate-400 sm:grid-cols-3">
        <div><dt className="sr-only">設定</dt><dd>設定：{status.configured ? "是" : "否"}</dd></div>
        <div><dt className="sr-only">可連線</dt><dd>可連線：{status.reachable ? "是" : "否"}</dd></div>
        <div>
          <dt className="sr-only">模型數量</dt>
          <dd>模型：{status.model_count}（Checkpoint {status.checkpoint_count}、Diffusion Model {status.diffusion_model_count}）</dd>
        </div>
      </dl>
      {status.warnings.length > 0 && (
        <ul aria-label="ComfyUI 警告" className="mt-3 list-disc space-y-1 pl-5 text-sm text-amber-200">
          {status.warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}
        </ul>
      )}
    </section>
  );
}
