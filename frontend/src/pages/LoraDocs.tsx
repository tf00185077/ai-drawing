/**
 * Phase 3: LoRA 訓練文件工具
 * 上傳、Caption 編輯、打包下載
 */
import { useCallback, useState } from "react";
import type { BatchPrefixResponse, UploadResponse } from "../types/api";

const IMAGE_ACCEPT = ".png,.jpg,.jpeg,.webp,.bmp,.gif";

interface FileItem {
  path: string;
  caption_path: string;
}

export default function LoraDocs() {
  const [folder, setFolder] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const items = Array.from(e.dataTransfer.files).filter((f) =>
      /\.(png|jpg|jpeg|webp|bmp|gif)$/i.test(f.name)
    );
    setFiles((prev) => [...prev, ...items]);
    setResult(null);
    setError(null);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files;
    if (!selected?.length) return;
    const items = Array.from(selected).filter((f) =>
      /\.(png|jpg|jpeg|webp|bmp|gif)$/i.test(f.name)
    );
    setFiles((prev) => [...prev, ...items]);
    setResult(null);
    setError(null);
    e.target.value = "";
  }, []);

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const upload = useCallback(async () => {
    if (files.length === 0) return;
    setIsUploading(true);
    setError(null);
    setResult(null);
    try {
      const formData = new FormData();
      files.forEach((f) => formData.append("files", f));
      if (folder.trim()) formData.append("folder", folder.trim());
      const res = await fetch("/api/lora-docs/upload", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `上傳失敗: ${res.status}`);
      }
      const data: UploadResponse = await res.json();
      setResult(data);
      setFiles([]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上傳失敗");
    } finally {
      setIsUploading(false);
    }
  }, [files, folder]);

  const clearResult = useCallback(() => {
    setResult(null);
    setError(null);
  }, []);

  const [downloadFolder, setDownloadFolder] = useState("");
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const [browseFolder, setBrowseFolder] = useState("");
  const [fileList, setFileList] = useState<FileItem[]>([]);
  const [browseError, setBrowseError] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [captionContent, setCaptionContent] = useState("");
  const [captionSaving, setCaptionSaving] = useState(false);
  const [captionError, setCaptionError] = useState<string | null>(null);
  const [batchPrefix, setBatchPrefix] = useState("");
  const [selectedForBatch, setSelectedForBatch] = useState<Set<string>>(new Set());
  const [batchResult, setBatchResult] = useState<BatchPrefixResponse | null>(null);

  const loadFolder = useCallback(async () => {
    const f = browseFolder.trim();
    if (!f) return;
    setBrowseError(null);
    try {
      const res = await fetch(`/api/lora-docs/files?folder=${encodeURIComponent(f)}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "載入失敗");
      }
      const data = await res.json();
      setFileList(data.items || []);
    } catch (err) {
      setBrowseError(err instanceof Error ? err.message : "載入失敗");
      setFileList([]);
    }
  }, [browseFolder]);

  const loadCaption = useCallback(async (path: string) => {
    setSelectedPath(path);
    setCaptionError(null);
    try {
      const res = await fetch(`/api/lora-docs/caption/${encodeURIComponent(path)}`);
      if (!res.ok) throw new Error("載入失敗");
      const data = await res.json();
      setCaptionContent(data.content ?? "");
    } catch (err) {
      setCaptionError(err instanceof Error ? err.message : "載入失敗");
      setCaptionContent("");
    }
  }, []);

  const saveCaption = useCallback(async () => {
    if (selectedPath === null) return;
    setCaptionSaving(true);
    setCaptionError(null);
    try {
      const res = await fetch(`/api/lora-docs/caption/${encodeURIComponent(selectedPath)}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: captionContent }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "儲存失敗");
      }
    } catch (err) {
      setCaptionError(err instanceof Error ? err.message : "儲存失敗");
    } finally {
      setCaptionSaving(false);
    }
  }, [selectedPath, captionContent]);

  const toggleBatchSelect = useCallback((path: string) => {
    setSelectedForBatch((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const applyBatchPrefix = useCallback(async () => {
    const paths = Array.from(selectedForBatch);
    const prefix = batchPrefix.trim();
    if (!paths.length || !prefix) return;
    try {
      const res = await fetch("/api/lora-docs/batch-prefix", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ images: paths, prefix }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "批次更新失敗");
      }
      const data: BatchPrefixResponse = await res.json();
      setBatchResult(data);
      if (selectedPath && selectedForBatch.has(selectedPath)) {
        loadCaption(selectedPath);
      }
    } catch (err) {
      setBrowseError(err instanceof Error ? err.message : "批次更新失敗");
    }
  }, [selectedForBatch, batchPrefix, selectedPath, loadCaption]);

  const handleDownload = useCallback(async () => {
    const folderName = downloadFolder.trim();
    if (!folderName) return;
    setDownloadError(null);
    try {
      const res = await fetch(`/api/lora-docs/download-zip?folder=${encodeURIComponent(folderName)}`);
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || "下載失敗");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${folderName.replace(/[/\\]/g, "_")}.zip`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setDownloadError(err instanceof Error ? err.message : "下載失敗");
    }
  }, [downloadFolder]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">LoRA 文件工具</h1>
      <p className="text-slate-400 mt-1">資料夾監聽 .txt · Caption 編輯 · 打包下載</p>

      <div className="mt-6 space-y-6 max-w-2xl">
        <div>
          <label className="block text-sm text-slate-400 mb-2">目標資料夾（選填）</label>
          <input
            type="text"
            placeholder="例如: my_lora"
            value={folder}
            onChange={(e) => setFolder(e.target.value)}
            className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500"
          />
        </div>

        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
            isDragging
              ? "border-amber-500 bg-amber-500/10"
              : "border-slate-600 hover:border-slate-500 bg-slate-800/50"
          }`}
        >
          <p className="text-slate-400 mb-2">拖曳圖片至此，或</p>
          <label className="inline-block px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white cursor-pointer transition-colors">
            選擇檔案
            <input
              type="file"
              accept={IMAGE_ACCEPT}
              multiple
              onChange={handleFileSelect}
              className="hidden"
            />
          </label>
        </div>

        {files.length > 0 && (
          <div className="space-y-2">
            <p className="text-sm text-slate-400">
              已選 {files.length} 張 ·{" "}
              <button
                type="button"
                onClick={upload}
                disabled={isUploading}
                className="text-amber-400 hover:text-amber-300 disabled:opacity-50"
              >
                {isUploading ? "上傳中…" : "上傳"}
              </button>
            </p>
            <ul className="max-h-40 overflow-y-auto rounded-lg bg-slate-800/50 border border-slate-700 p-2 space-y-1">
              {files.map((f, i) => (
                <li key={`${f.name}-${i}`} className="flex items-center justify-between text-sm text-slate-300">
                  <span className="truncate">{f.name}</span>
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    className="text-red-400 hover:text-red-300 ml-2 shrink-0"
                    aria-label="移除"
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {error && (
          <div className="p-3 rounded-lg bg-red-500/20 border border-red-500/50 text-red-300 text-sm">
            {error}
          </div>
        )}

        {result && (
          <div className="p-4 rounded-lg bg-emerald-500/10 border border-emerald-500/50">
            <p className="text-emerald-300 font-medium">成功上傳 {result.uploaded} 張</p>
            {result.items && result.items.length > 0 && (
              <ul className="mt-2 space-y-1 text-sm text-slate-400">
                {result.items.map((it, i) => (
                  <li key={i}>
                    {it.filename} → {it.caption_path}
                  </li>
                ))}
              </ul>
            )}
            <button
              type="button"
              onClick={clearResult}
              className="mt-3 text-sm text-slate-500 hover:text-slate-400"
            >
              關閉
            </button>
          </div>
        )}

        <div className="pt-4 border-t border-slate-700">
          <h3 className="text-slate-300 font-medium mb-2">打包下載</h3>
          <p className="text-slate-500 text-sm mb-2">輸入資料夾名稱，下載圖片與 .txt 為 ZIP</p>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="例如: my_lora"
              value={downloadFolder}
              onChange={(e) => {
                setDownloadFolder(e.target.value);
                setDownloadError(null);
              }}
              className="flex-1 px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500"
            />
            <button
              type="button"
              onClick={handleDownload}
              disabled={!downloadFolder.trim()}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg text-white transition-colors"
            >
              下載 ZIP
            </button>
          </div>
          {downloadError && (
            <p className="mt-2 text-sm text-red-400">{downloadError}</p>
          )}
        </div>

        <div className="pt-4 border-t border-slate-700">
          <h3 className="text-slate-300 font-medium mb-2">Caption 編輯器</h3>
          <p className="text-slate-500 text-sm mb-2">瀏覽資料夾、編輯 .txt、批次加入 trigger word</p>
          <div className="flex gap-2 mb-3">
            <input
              type="text"
              placeholder="資料夾名稱，如 my_lora"
              value={browseFolder}
              onChange={(e) => {
                setBrowseFolder(e.target.value);
                setBrowseError(null);
              }}
              className="flex-1 px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500"
            />
            <button
              type="button"
              onClick={loadFolder}
              className="px-4 py-2 bg-slate-700 hover:bg-slate-600 rounded-lg text-white"
            >
              載入
            </button>
          </div>
          {browseError && <p className="text-sm text-red-400 mb-2">{browseError}</p>}
          {fileList.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-sm text-slate-400 mb-1">選擇圖片（可多選以批次加前綴）</p>
                <ul className="max-h-48 overflow-y-auto rounded-lg bg-slate-800/50 border border-slate-700 p-2 space-y-1">
                  {fileList.map((it) => (
                    <li key={it.path} className="flex items-center gap-2 text-sm">
                      <input
                        type="checkbox"
                        checked={selectedForBatch.has(it.path)}
                        onChange={() => toggleBatchSelect(it.path)}
                      />
                      <button
                        type="button"
                        onClick={() => loadCaption(it.path)}
                        className={`text-left truncate flex-1 hover:text-amber-400 ${
                          selectedPath === it.path ? "text-amber-400" : "text-slate-300"
                        }`}
                      >
                        {it.path}
                      </button>
                    </li>
                  ))}
                </ul>
                <div className="flex gap-2 mt-2">
                  <input
                    type="text"
                    placeholder="前綴，如 sks "
                    value={batchPrefix}
                    onChange={(e) => setBatchPrefix(e.target.value)}
                    className="flex-1 px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white text-sm"
                  />
                  <button
                    type="button"
                    onClick={applyBatchPrefix}
                    disabled={selectedForBatch.size === 0 || !batchPrefix.trim()}
                    className="px-3 py-2 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 rounded-lg text-white text-sm"
                  >
                    批次加前綴
                  </button>
                </div>
                {batchResult && (
                  <p className="mt-2 text-sm text-emerald-400">
                    已更新 {batchResult.updated} 筆
                    {batchResult.failed?.length ? `，失敗 ${batchResult.failed.length} 筆` : ""}
                  </p>
                )}
              </div>
              <div>
                <p className="text-sm text-slate-400 mb-1">編輯 Caption</p>
                {selectedPath ? (
                  <>
                    <textarea
                      value={captionContent}
                      onChange={(e) => setCaptionContent(e.target.value)}
                      rows={8}
                      className="w-full px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white text-sm font-mono"
                      placeholder="1girl, solo, ..."
                    />
                    {captionError && <p className="text-sm text-red-400 mt-1">{captionError}</p>}
                    <button
                      type="button"
                      onClick={saveCaption}
                      disabled={captionSaving}
                      className="mt-2 px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-50 rounded-lg text-white text-sm"
                    >
                      {captionSaving ? "儲存中…" : "儲存"}
                    </button>
                  </>
                ) : (
                  <p className="text-slate-500 text-sm">點選左側圖片開始編輯</p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
