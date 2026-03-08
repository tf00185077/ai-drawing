/**
 * Phase 4d: LoRA 訓練與產圖串接
 * 訓練狀態、佇列、手動觸發、trigger-check
 * 對應 docs/api-contract.md 模組 4
 */
import { useCallback, useEffect, useState } from "react";
import type {
  FolderItem,
  TrainFoldersResponse,
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
  help,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: "text" | "number";
  help?: string;
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
      {help && <p className="mt-0.5 text-xs text-slate-500">{help}</p>}
    </div>
  );
}

export default function LoraTrain() {
  const [status, setStatus] = useState<TrainStatusResponse | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);

  const [folders, setFolders] = useState<FolderItem[]>([]);
  const [foldersLoading, setFoldersLoading] = useState(false);
  const [selectedFolders, setSelectedFolders] = useState<Set<string>>(new Set());
  const [checkpoint, setCheckpoint] = useState("");
  const [sdxl, setSdxl] = useState(true);
  const [epochs, setEpochs] = useState<string>(String(DEFAULT_EPOCHS));
  const [resolution, setResolution] = useState("");
  const [batchSize, setBatchSize] = useState("");
  const [learningRate, setLearningRate] = useState("");
  const [classTokens, setClassTokens] = useState("");
  const [numRepeats, setNumRepeats] = useState("");
  const [networkDim, setNetworkDim] = useState("");
  const [networkAlpha, setNetworkAlpha] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [startError, setStartError] = useState<string | null>(null);
  const [lastStart, setLastStart] = useState<{
    queued: number;
    skipped: string[];
    failed: string[];
  } | null>(null);

  const [triggerResult, setTriggerResult] =
    useState<TriggerCheckResponse | null>(null);
  const [triggerLoading, setTriggerLoading] = useState(false);
  const [triggerError, setTriggerError] = useState<string | null>(null);

  const [clearLoading, setClearLoading] = useState(false);

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

  const fetchFolders = useCallback(async () => {
    setFoldersLoading(true);
    try {
      const res = await fetch(`${API}/lora-train/folders`);
      if (res.ok) {
        const data: TrainFoldersResponse = await res.json();
        setFolders(data.folders);
      }
    } catch {
      setFolders([]);
    } finally {
      setFoldersLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const id = setInterval(fetchStatus, 3000);
    return () => clearInterval(id);
  }, [fetchStatus]);

  useEffect(() => {
    fetchFolders();
  }, [fetchFolders]);

  useEffect(() => {
    fetch(`${API}/lora-train/config`)
      .then((r) => r.ok ? r.json() : null)
      .then((cfg) => cfg?.sdxl != null && setSdxl(cfg.sdxl))
      .catch(() => {});
  }, []);

  const toggleFolder = useCallback((folder: string) => {
    setSelectedFolders((prev) => {
      const next = new Set(prev);
      if (next.has(folder)) next.delete(folder);
      else next.add(folder);
      return next;
    });
  }, []);

  const selectAllFolders = useCallback(() => {
    setSelectedFolders(new Set(folders.map((f) => f.folder)));
  }, [folders]);

  const deselectAllFolders = useCallback(() => {
    setSelectedFolders(new Set());
  }, []);

  const handleStart = useCallback(async () => {
    const toProcess = Array.from(selectedFolders);
    if (toProcess.length === 0) {
      setStartError("請至少選擇一個訓練資料夾");
      return;
    }

    setIsSubmitting(true);
    setStartError(null);
    setLastStart(null);

    const buildBody = (folder: string): TrainStartRequest => {
      const body: TrainStartRequest = { folder };
      if (checkpoint.trim()) body.checkpoint = checkpoint.trim();
      body.sdxl = sdxl;
      const epochsNum = parseInt(epochs, 10);
      if (!Number.isNaN(epochsNum) && epochsNum >= 1) body.epochs = epochsNum;
      const resNum = parseInt(resolution, 10);
      if (!Number.isNaN(resNum) && resNum >= 256 && resNum <= 2048)
        body.resolution = resNum;
      const bsNum = parseInt(batchSize, 10);
      if (!Number.isNaN(bsNum) && bsNum >= 1 && bsNum <= 32)
        body.batch_size = bsNum;
      if (learningRate.trim()) body.learning_rate = learningRate.trim();
      if (classTokens.trim()) body.class_tokens = classTokens.trim();
      const nrNum = parseInt(numRepeats, 10);
      if (!Number.isNaN(nrNum) && nrNum >= 1 && nrNum <= 100)
        body.num_repeats = nrNum;
      const dimNum = parseInt(networkDim, 10);
      if (!Number.isNaN(dimNum) && dimNum >= 1 && dimNum <= 128)
        body.network_dim = dimNum;
      const alphaNum = parseInt(networkAlpha, 10);
      if (!Number.isNaN(alphaNum) && alphaNum >= 1 && alphaNum <= 128)
        body.network_alpha = alphaNum;
      return body;
    };

    const queued: number[] = [];
    const skipped: string[] = [];
    const failed: string[] = [];

    for (const folder of toProcess) {
      try {
        const res = await fetch(`${API}/lora-train/start`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(buildBody(folder)),
        });
        const data = await res.json().catch(() => ({}));

        if (res.ok) {
          queued.push(1);
        } else if (res.status === 409) {
          skipped.push(folder);
        } else {
          failed.push(
            `${folder}: ${typeof data.detail === "string" ? data.detail : res.status}`
          );
        }
      } catch {
        failed.push(`${folder}: 網路錯誤`);
      }
    }

    setLastStart({
      queued: queued.length,
      skipped,
      failed,
    });
    if (failed.length > 0) {
      setStartError(`${failed.length} 個資料夾提交失敗`);
    }
    fetchStatus();
    setIsSubmitting(false);
  }, [
    selectedFolders,
    checkpoint,
    sdxl,
    epochs,
    resolution,
    batchSize,
    learningRate,
    classTokens,
    numRepeats,
    networkDim,
    networkAlpha,
    fetchStatus,
  ]);

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
              {status?.last_result && (
                <div
                  className={`mt-2 p-2 rounded text-sm ${
                    status.last_result.success ? "bg-green-900/30 text-green-300" : "bg-red-900/30 text-red-300"
                  }`}
                >
                  <p className="font-medium">
                    {status.last_result.success ? "✓ 上次完成" : "✗ 上次失敗"}：{status.last_result.folder}
                  </p>
                  {status.last_result.success && status.last_result.path && (
                    <p className="mt-0.5 text-xs break-all">輸出：{status.last_result.path}</p>
                  )}
                  {!status.last_result.success && status.last_result.error && (
                    <p className="mt-0.5 text-xs whitespace-pre-wrap">{status.last_result.error}</p>
                  )}
                </div>
              )}
              {(status?.status === "queued" || status?.status === "running") && (
                <div className="mt-3">
                  <button
                    type="button"
                    onClick={async () => {
                      setClearLoading(true);
                      try {
                        const res = await fetch(`${API}/lora-train/clear`, { method: "POST" });
                        if (res.ok) {
                          fetchStatus();
                        }
                      } finally {
                        setClearLoading(false);
                      }
                    }}
                    disabled={clearLoading}
                    className="text-sm px-2 py-1 rounded bg-red-900/50 hover:bg-red-800/50 text-red-300 disabled:opacity-50"
                  >
                    {clearLoading ? "清除中..." : "清除佇列"}
                  </button>
                  <span className="ml-2 text-xs text-slate-500">
                    卡住時可強制清除，清空後可重新提交
                  </span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* 手動觸發 */}
        <div className="p-4 rounded-lg bg-slate-800/50 border border-slate-700">
          <h2 className="font-semibold text-slate-200 mb-3">手動觸發訓練</h2>
          <div className="space-y-3">
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium text-slate-300">
                  訓練資料夾（可多選）
                </label>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={selectAllFolders}
                    className="text-xs px-2 py-0.5 rounded bg-slate-600 hover:bg-slate-500 text-slate-200"
                  >
                    全選
                  </button>
                  <button
                    type="button"
                    onClick={deselectAllFolders}
                    className="text-xs px-2 py-0.5 rounded bg-slate-600 hover:bg-slate-500 text-slate-200"
                  >
                    全不選
                  </button>
                  <button
                    type="button"
                    onClick={fetchFolders}
                    disabled={foldersLoading}
                    className="text-xs px-2 py-0.5 rounded bg-slate-600 hover:bg-slate-500 text-slate-200 disabled:opacity-50"
                  >
                    {foldersLoading ? "載入中..." : "重新載入"}
                  </button>
                </div>
              </div>
              <p className="text-xs text-slate-500 mb-2">
                點擊按鈕選擇要訓練的資料夾（可多選）。僅顯示含至少 1 張圖+對應 .txt 的子資料夾。
              </p>
              {foldersLoading && folders.length === 0 ? (
                <p className="text-slate-500 text-sm py-2">載入資料夾中...</p>
              ) : folders.length === 0 ? (
                <p className="text-slate-500 text-sm py-2">
                  無可訓練資料夾。請在 lora_train 目錄下建立子資料夾並上傳含 .txt 的圖片。
                </p>
              ) : (
                <div className="max-h-48 overflow-y-auto rounded-lg border border-slate-600 bg-slate-900/50 p-2 flex flex-wrap gap-2">
                  {folders.map((f) => {
                    const isSelected = selectedFolders.has(f.folder);
                    return (
                      <button
                        key={f.folder}
                        type="button"
                        onClick={() => toggleFolder(f.folder)}
                        className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                          isSelected
                            ? "bg-cyan-600 hover:bg-cyan-500 text-white"
                            : "bg-slate-600 hover:bg-slate-500 text-slate-200"
                        }`}
                        title={`${f.folder}（${f.image_count} 張）`}
                      >
                        {f.folder}
                        <span className="ml-1.5 opacity-80">({f.image_count})</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
            <Field
              label="Checkpoint（選填）"
              value={checkpoint}
              onChange={setCheckpoint}
              placeholder="incursiosMemeDiffusion_v16PDXL.safetensors"
              help="基礎模型檔名，會自動加上 .env 的 LORA_CHECKPOINT_DIRS 路徑。留空則使用 LORA_DEFAULT_CHECKPOINT。"
            />
            <div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={sdxl}
                  onChange={(e) => setSdxl(e.target.checked)}
                  className="rounded bg-slate-800 border-slate-600 text-cyan-500 focus:ring-cyan-500"
                />
                <span className="text-sm font-medium text-slate-300">SDXL / PDXL 模型</span>
              </label>
              <p className="mt-0.5 text-xs text-slate-500">
                勾選時使用 sdxl_train_network.py。若 checkpoint 為 SDXL（如 PDXL、SDXL base）則必須勾選。
              </p>
            </div>
            <Field
              label="Epochs"
              value={epochs}
              onChange={setEpochs}
              placeholder="10"
              type="number"
              help="總訓練輪數。越多越容易過擬合，通常 10～20。"
            />
            <Field
              label="Resolution（解析度）"
              value={resolution}
              onChange={setResolution}
              placeholder="512"
              type="number"
              help="P2 · 訓練圖片裁切解析度。512 為常見值，768 需較多 VRAM。留空使用預設 512。"
            />
            <Field
              label="Batch size（批次大小）"
              value={batchSize}
              onChange={setBatchSize}
              placeholder="4"
              type="number"
              help="P2 · 每次迭代的圖片數量。越大越穩定但吃 VRAM。留空使用預設 4。"
            />
            <Field
              label="Learning rate（學習率）"
              value={learningRate}
              onChange={setLearningRate}
              placeholder="1e-4"
              help="P1 · LoRA 建議 1e-4～1e-3。過大會發散，過小收斂慢。留空使用預設 1e-4。"
            />
            <Field
              label="Class tokens（Trigger word）"
              value={classTokens}
              onChange={setClassTokens}
              placeholder="sks"
              help="P1 · 觸發 LoRA 效果的關鍵詞，生圖時需在 prompt 中加上。例如 sks girl、ohwx。"
            />
            <Field
              label="Num repeats（重複次數）"
              value={numRepeats}
              onChange={setNumRepeats}
              placeholder="10"
              type="number"
              help="P1 · 每個 epoch 中每張圖重複訓練的次數。影響訓練強度，通常 5～15。"
            />
            <Field
              label="Network dim（LoRA rank）"
              value={networkDim}
              onChange={setNetworkDim}
              placeholder="16"
              type="number"
              help="P0 · LoRA 矩陣的秩。8 較輕量，16/32 表達力較強，64+ 易過擬合。留空使用預設 16。"
            />
            <Field
              label="Network alpha"
              value={networkAlpha}
              onChange={setNetworkAlpha}
              placeholder="16"
              type="number"
              help="P0 · 與 dim 比決定 LoRA 強度，通常與 dim 同值。alpha/dim 越大生圖時效果越強。"
            />
            {startError && (
              <p className="text-red-400 text-sm">{startError}</p>
            )}
            {lastStart && (
              <div className="text-sm space-y-1">
                {lastStart.queued > 0 && (
                  <p className="text-green-400">
                    已加入佇列：{lastStart.queued} 個資料夾
                  </p>
                )}
                {lastStart.skipped.length > 0 && (
                  <p className="text-amber-400">
                    跳過（已在佇列或訓練中）：{lastStart.skipped.join(", ")}
                  </p>
                )}
                {lastStart.failed.length > 0 && (
                  <p className="text-red-400">
                    失敗：{lastStart.failed.join("；")}
                  </p>
                )}
              </div>
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
