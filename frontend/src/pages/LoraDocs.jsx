/**
 * Phase 3: LoRA 訓練文件工具
 * 上傳、Caption 編輯、打包下載
 */
export default function LoraDocs() {
  return (
    <div>
      <h1 className="text-2xl font-bold text-white">LoRA 文件工具</h1>
      <p className="text-slate-400 mt-1">資料夾監聽 .txt · Caption 編輯 · 打包下載</p>
      <div className="mt-6 space-y-4">
        <div className="border-2 border-dashed border-slate-600 rounded-lg p-8 text-center text-slate-500">
          拖曳上傳訓練圖片（選用）
        </div>
        <div className="text-slate-500">TODO: Caption 編輯器、打包下載</div>
      </div>
    </div>
  );
}
