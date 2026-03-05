import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import Generate from "./pages/Generate";
import Gallery from "./pages/Gallery";
import LoraDocs from "./pages/LoraDocs";
import LoraTrain from "./pages/LoraTrain";

function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-slate-950 text-slate-200">
        <nav className="border-b border-slate-800 px-4 py-3">
          <div className="flex gap-4">
            <Link to="/" className="text-emerald-400 hover:underline">儀表板</Link>
            <Link to="/generate" className="hover:underline">生圖</Link>
            <Link to="/gallery" className="hover:underline">圖庫</Link>
            <Link to="/lora-docs" className="hover:underline">LoRA 文件</Link>
            <Link to="/lora-train" className="hover:underline">LoRA 訓練</Link>
          </div>
        </nav>
        <main className="p-4">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/generate" element={<Generate />} />
            <Route path="/gallery" element={<Gallery />} />
            <Route path="/lora-docs" element={<LoraDocs />} />
            <Route path="/lora-train" element={<LoraTrain />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
