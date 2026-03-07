/**
 * Phase 3: LoRA 訓練文件工具
 * 上傳、Caption 編輯、打包下載
 */
import { useCallback, useState } from "react";
import type { UploadResponse } from "../types/api";

const IMAGE_ACCEPT = ".png,.jpg,.jpeg,.webp,.bmp,.gif";

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

        <div className="text-slate-500 text-sm">TODO: Caption 編輯器、打包下載</div>
      </div>
    </div>
  );
}
