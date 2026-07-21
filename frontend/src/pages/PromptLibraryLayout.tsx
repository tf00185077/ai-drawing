import { NavLink, Outlet } from "react-router-dom";

const linkClass = ({ isActive }: { isActive: boolean }) =>
  `block rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
    isActive ? "bg-emerald-600 text-white" : "text-slate-300 hover:bg-slate-800 hover:text-white"
  }`;

export default function PromptLibraryLayout() {
  return (
    <div className="mx-auto grid gap-6 lg:grid-cols-[220px_minmax(0,1fr)]">
      <aside aria-label="Prompt Library" className="h-fit rounded-xl border border-slate-800 bg-slate-900/60 p-3 lg:sticky lg:top-4">
        <p className="px-3 pb-2 text-xs font-semibold uppercase tracking-wider text-slate-500">Prompt Library</p>
        <nav className="space-y-1">
          <NavLink end to="workbench" className={linkClass}>Prompt Workbench</NavLink>
          <NavLink end to="categories" className={linkClass}>分類管理</NavLink>
        </nav>
      </aside>
      <main className="min-w-0"><Outlet /></main>
    </div>
  );
}
