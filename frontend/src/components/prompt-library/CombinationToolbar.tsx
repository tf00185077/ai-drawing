import type { PromptCombinationSummary } from "../../types/api";

export interface CombinationDocumentStatus {
  id: string | null;
  revision: number | null;
  repaired: boolean;
  dirty: boolean;
}

interface Props {
  combinations: PromptCombinationSummary[];
  selectedId: string;
  onSelectedIdChange: (id: string) => void;
  onLoad: () => void;
  onBlank: () => void;
  document: CombinationDocumentStatus;
  targetId: string;
  onTargetIdChange: (id: string) => void;
  onUpdate: () => void;
  onSaveAs: () => void;
  busy: boolean;
  warnings: string[];
  success: string;
  error: string;
}

export default function CombinationToolbar({
  combinations,
  selectedId,
  onSelectedIdChange,
  onLoad,
  onBlank,
  document,
  targetId,
  onTargetIdChange,
  onUpdate,
  onSaveAs,
  busy,
  warnings,
  success,
  error,
}: Props) {
  const visibleCombinations = combinations.filter((item) => !item.archived);
  const saveDisabled = busy || (!document.id && !targetId.trim());

  return (
    <section aria-label="組合管理" className="rounded-xl border border-slate-700 bg-slate-900/70 p-4">
      <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-end">
        <label className="text-sm text-slate-400">已儲存組合
          <select aria-label="已儲存組合" value={selectedId} disabled={busy} onChange={(event) => onSelectedIdChange(event.target.value)} className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white">
            <option value="">請選擇組合</option>
            {visibleCombinations.map((item) => (
              <option key={item.id} value={item.id}>{item.name_zh.trim() || item.id}（{item.id}）</option>
            ))}
          </select>
        </label>
        <button type="button" disabled={busy || !selectedId} onClick={onLoad} className="rounded-lg bg-sky-700 px-4 py-2.5 font-medium text-white disabled:bg-slate-700">加入組合</button>
        <button type="button" disabled={busy} onClick={onBlank} className="rounded-lg bg-slate-700 px-4 py-2.5 font-medium text-white disabled:opacity-50">建立空白組合</button>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2 text-sm text-slate-300">
        {document.id ? (
          <span aria-label="目前組合版本">{document.id} · revision {document.revision}{document.repaired ? " · 已修復" : ""}</span>
        ) : <span>尚未儲存</span>}
        {document.dirty && <span className="rounded-full bg-amber-500/15 px-2 py-0.5 text-xs text-amber-300">尚未儲存變更</span>}
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_auto_auto] lg:items-end">
        <label className="text-sm text-slate-400">新組合 ID
          <input aria-label="新組合 ID" aria-describedby="combination-id-help" value={targetId} disabled={busy} onChange={(event) => onTargetIdChange(event.target.value)} placeholder="例如 niji基礎瑟瑟" className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 p-2 text-white" />
          <span id="combination-id-help" className="mt-1 block text-xs text-slate-500">允許 Unicode 字母、數字與連字號；不允許空白或路徑符號</span>
        </label>
        <button type="button" disabled={saveDisabled} onClick={onUpdate} className="rounded-lg bg-emerald-700 px-4 py-2.5 font-medium text-white disabled:bg-slate-700">更新目前組合</button>
        <button type="button" disabled={busy || !targetId.trim()} onClick={onSaveAs} className="rounded-lg bg-violet-700 px-4 py-2.5 font-medium text-white disabled:bg-slate-700">另存新組合</button>
      </div>

      {warnings.length > 0 && <div role="alert" className="mt-3 rounded-lg border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-200"><ul>{warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}</ul></div>}
      {error && <p role="alert" className="mt-3 rounded-lg border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
      {success && <p role="status" className="mt-3 text-sm text-emerald-300">{success}</p>}
    </section>
  );
}
