import type { ExecutionTarget } from "../types/api";

export default function ExecutionTargetSelect({
  value,
  onChange,
  className = "",
}: {
  value: ExecutionTarget;
  onChange: (value: ExecutionTarget) => void;
  className?: string;
}) {
  return (
    <label className={`block text-sm text-slate-400 ${className}`}>
      執行位置
      <select
        aria-label="執行位置"
        value={value}
        onChange={(event) => onChange(event.target.value as ExecutionTarget)}
        className="mt-1 w-full rounded-lg border border-slate-600 bg-slate-800 px-3 py-2 text-white"
      >
        <option value="local">Mac 本機</option>
        <option value="worker">Windows Worker</option>
      </select>
    </label>
  );
}
