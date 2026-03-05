/**
 * Phase 2c: 圖片 Gallery 瀏覽器
 * 搜尋、篩選（checkpoint / LoRA / 日期）、查看完整參數
 */
export default function Gallery() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-white">圖庫</h1>
      <div className="mt-6 flex gap-4">
        <input
          type="text"
          placeholder="搜尋..."
          className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-600"
        />
        <select className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-600">
          <option>篩選 Checkpoint</option>
        </select>
        <select className="px-3 py-2 rounded-lg bg-slate-800 border border-slate-600">
          <option>篩選 LoRA</option>
        </select>
      </div>
      <div className="mt-6 text-slate-500">TODO: 圖庫列表</div>
    </div>
  );
}
