/**
 * Phase 2c: 圖片 Gallery 瀏覽器
 * 搜尋、篩選（checkpoint / LoRA / 日期）、查看完整參數
 */
import { useEffect, useState } from "react";
import type { GalleryItem, GalleryListResponse } from "../types/api";

const API = "/api";

export default function Gallery() {
  const [items, setItems] = useState<GalleryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<GalleryItem | null>(null);
  const [filters, setFilters] = useState({
    checkpoint: "",
    lora: "",
    from_date: "",
    to_date: "",
  });
  const [page, setPage] = useState(0);
  const limit = 20;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(page * limit));
    if (filters.checkpoint) params.set("checkpoint", filters.checkpoint);
    if (filters.lora) params.set("lora", filters.lora);
    if (filters.from_date) params.set("from_date", filters.from_date);
    if (filters.to_date) params.set("to_date", filters.to_date);
    fetch(`${API}/gallery/?${params}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: GalleryListResponse) => {
        if (!cancelled) {
          setItems(data.items);
          setTotal(data.total);
        }
      })
      .catch((e) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : "載入失敗");
          setItems([]);
          setTotal(0);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [page, filters.checkpoint, filters.lora, filters.from_date, filters.to_date]);

  const handleFilterChange = (key: keyof typeof filters, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(0);
  };

  const imageUrl = (item: GalleryItem) =>
    item.image_url || `/gallery/${encodeURIComponent(item.image_path)}`;

  const totalPages = Math.ceil(total / limit) || 1;

  return (
    <div>
      <h1 className="text-2xl font-bold text-white">圖庫</h1>
      <p className="text-slate-400 mt-1">瀏覽、篩選生成圖片與參數</p>

      <div className="mt-6 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="篩選 Checkpoint"
          value={filters.checkpoint}
          onChange={(e) => handleFilterChange("checkpoint", e.target.value)}
          className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500 w-40"
        />
        <input
          type="text"
          placeholder="篩選 LoRA"
          value={filters.lora}
          onChange={(e) => handleFilterChange("lora", e.target.value)}
          className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white placeholder-slate-500 w-40"
        />
        <input
          type="date"
          placeholder="從日期"
          value={filters.from_date}
          onChange={(e) => handleFilterChange("from_date", e.target.value)}
          className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white w-40"
        />
        <input
          type="date"
          placeholder="至日期"
          value={filters.to_date}
          onChange={(e) => handleFilterChange("to_date", e.target.value)}
          className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-600 text-white w-40"
        />
        <button
          onClick={() => setFilters({ checkpoint: "", lora: "", from_date: "", to_date: "" })}
          className="px-3 py-2 rounded-lg border border-slate-600 text-slate-400 hover:text-white hover:border-slate-500"
        >
          清除篩選
        </button>
      </div>

      {loading && <p className="mt-4 text-slate-500">載入中...</p>}
      {error && <p className="mt-4 text-amber-500">{error}</p>}

      {!loading && !error && (
        <>
          <p className="mt-4 text-slate-400">共 {total} 張</p>
          <div className="mt-4 grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
            {items.map((item) => (
              <button
                key={item.id}
                onClick={() => setSelected(item)}
                className="block text-left rounded-lg overflow-hidden border border-slate-700 bg-slate-900/50 hover:border-emerald-500/50 transition-colors"
              >
                <div className="aspect-square bg-slate-800 relative">
                  <img
                    src={imageUrl(item)}
                    alt=""
                    className="w-full h-full object-cover"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100'%3E%3Crect fill='%23334155' width='100' height='100'/%3E%3Ctext fill='%2394a3b8' x='50%25' y='50%25' dominant-baseline='middle' text-anchor='middle' font-size='12'%3E無預覽%3C/text%3E%3C/svg%3E";
                    }}
                  />
                </div>
                <div className="p-2 truncate text-sm text-slate-400">
                  {item.prompt?.slice(0, 40) || `#${item.id}`}...
                </div>
              </button>
            ))}
          </div>

          {totalPages > 1 && (
            <div className="mt-6 flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1 rounded border border-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                上一頁
              </button>
              <span className="py-1 text-slate-400">
                {page + 1} / {totalPages}
              </span>
              <button
                onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                disabled={page >= totalPages - 1}
                className="px-3 py-1 rounded border border-slate-600 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                下一頁
              </button>
            </div>
          )}

          {items.length === 0 && (
            <div className="mt-8 text-center text-slate-500 py-12 border border-dashed border-slate-700 rounded-lg">
              尚無圖片。生圖完成後會自動記錄至此。
            </div>
          )}
        </>
      )}

      {selected && (
        <DetailModal item={selected} onClose={() => setSelected(null)} imageUrl={imageUrl(selected)} />
      )}
    </div>
  );
}

function DetailModal({
  item,
  onClose,
  imageUrl,
}: {
  item: GalleryItem;
  onClose: () => void;
  imageUrl: string;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70"
      onClick={onClose}
    >
      <div
        className="max-w-2xl w-full mx-4 max-h-[90vh] overflow-auto rounded-lg bg-slate-900 border border-slate-700 p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex justify-between items-start gap-4">
          <img
            src={imageUrl}
            alt=""
            className="max-h-80 rounded object-contain bg-slate-800"
          />
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-white">#{item.id}</h3>
            <dl className="mt-3 space-y-1 text-sm">
              <ParamRow label="Checkpoint" value={item.checkpoint} />
              <ParamRow label="LoRA" value={item.lora} />
              <ParamRow label="Seed" value={item.seed?.toString()} />
              <ParamRow label="Steps" value={item.steps?.toString()} />
              <ParamRow label="CFG" value={item.cfg?.toString()} />
              <ParamRow label="建立時間" value={item.created_at?.slice(0, 19).replace("T", " ")} />
            </dl>
          </div>
        </div>
        <div className="mt-4 space-y-2">
          <div>
            <span className="text-slate-400 text-sm">Prompt:</span>
            <p className="text-white text-sm break-words mt-0.5">{item.prompt || "-"}</p>
          </div>
          {item.negative_prompt && (
            <div>
              <span className="text-slate-400 text-sm">Negative:</span>
              <p className="text-slate-300 text-sm break-words mt-0.5">{item.negative_prompt}</p>
            </div>
          )}
        </div>
        <button
          onClick={onClose}
          className="mt-4 px-4 py-2 rounded-lg border border-slate-600 hover:bg-slate-800"
        >
          關閉
        </button>
      </div>
    </div>
  );
}

function ParamRow({ label, value }: { label: string; value?: string | null }) {
  if (value == null || value === "") return null;
  return (
    <div>
      <dt className="text-slate-500 inline">{label}: </dt>
      <dd className="inline text-slate-200">{value}</dd>
    </div>
  );
}
