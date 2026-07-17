import { useEffect, useMemo, useState } from "react";

type Polarity = "positive" | "negative";
type Category = { id: string; polarity: Polarity; name_zh: string; revision: number; etag: string; archived: boolean };
type Entry = { id: string; name_zh: string; description_zh: string; prompt: string; revision: number; archived: boolean };
type Fragment = { kind: "entry" | "literal"; ref?: { polarity: Polarity; category_id: string; entry_id: string }; snapshot: string; source_revision?: number; weight: number; order: number };
type Form = { id: string; display_name: string; fields: { name: string; default?: unknown; options: string[] }[] };

async function jsonFetch(url: string, init?: RequestInit) {
  const response = await fetch(url, init);
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data?.detail?.message || `HTTP ${response.status}`);
  return data;
}

export default function PromptWorkbench() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [category, setCategory] = useState<Category | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [query, setQuery] = useState("");
  const [positive, setPositive] = useState<Fragment[]>([]);
  const [negative, setNegative] = useState<Fragment[]>([]);
  const [literal, setLiteral] = useState("");
  const [result, setResult] = useState({ positive_prompt: "", negative_prompt: "" });
  const [saveId, setSaveId] = useState("");
  const [forms, setForms] = useState<Form[]>([]);
  const [workflow, setWorkflow] = useState("");
  const [seedMode, setSeedMode] = useState("random");
  const [job, setJob] = useState("");
  const [entryDraft, setEntryDraft] = useState({ id: "", name: "", prompt: "" });
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([jsonFetch("/api/prompt-library/catalog"), jsonFetch("/api/workflow-catalog/generation-forms")])
      .then(([catalog, descriptor]) => { setCategories(catalog.categories || []); setForms(descriptor.items || []); })
      .catch((e) => setError(String(e.message || e)));
  }, []);

  async function openCategory(item: Category) {
    const data = await jsonFetch(`/api/prompt-library/categories/${item.polarity}/${item.id}`);
    setCategory({ ...data.category, etag: data.etag });
    setEntries(data.category.entries || []);
  }

  function add(fragment: Fragment, polarity: Polarity) {
    const setter = polarity === "positive" ? setPositive : setNegative;
    setter((items) => [...items, { ...fragment, order: (items.length + 1) * 10 }]);
  }

  async function compose(save = false) {
    const body: Record<string, unknown> = { positive, negative };
    if (save && saveId.trim()) body.save_as = { id: saveId.trim(), name_zh: saveId.trim(), description_zh: "Prompt Workbench 儲存組合", expected_revision: 0, aliases: [], keywords: [], order: 10, positive, negative };
    const data = await jsonFetch("/api/prompt-library/compose", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    setPositive(data.positive); setNegative(data.negative); setResult(data);
  }

  async function createEntry() {
    if (!category) return;
    const data = await jsonFetch(`/api/prompt-library/categories/${category.polarity}/${category.id}/entries/${entryDraft.id}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name_zh: entryDraft.name, description_zh: `${entryDraft.name}提示詞`, prompt: entryDraft.prompt, aliases: [], keywords: [], order: (entries.length + 1) * 10, expected_revision: category.revision, expected_etag: category.etag }) });
    setCategory({ ...data.category.category, etag: data.category.etag }); setEntries(data.category.category.entries); setEntryDraft({ id: "", name: "", prompt: "" });
  }

  async function generate() {
    const data = await jsonFetch("/api/generate/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ template: workflow, prompt: result.positive_prompt, negative_prompt: result.negative_prompt, use_workflow_defaults: true, seed_mode: seedMode }) });
    setJob(data.job_id);
  }

  const visible = useMemo(() => entries.filter((e) => !e.archived && `${e.name_zh} ${e.prompt}`.toLowerCase().includes(query.toLowerCase())), [entries, query]);
  return <section className="mt-8 rounded-xl border border-slate-700 bg-slate-900/60 p-5">
    <h2 className="text-xl font-semibold text-white">Prompt Workbench</h2>
    {error && <p role="alert" className="text-red-300">{error}</p>}
    <div className="mt-4 grid gap-5 lg:grid-cols-3">
      <div><h3 className="font-medium">1. 瀏覽詞庫</h3><input aria-label="搜尋提示詞" value={query} onChange={(e) => setQuery(e.target.value)} className="my-2 w-full rounded bg-slate-800 p-2" placeholder="搜尋中文或英文" />
        <div className="flex flex-wrap gap-2">{categories.filter((c) => !c.archived).map((c) => <button key={`${c.polarity}-${c.id}`} onClick={() => openCategory(c)} className="rounded bg-slate-700 px-2 py-1">{c.name_zh}</button>)}</div>
        {category && <><div className="mt-3 grid grid-cols-3 gap-1"><input aria-label="詞條 ID" value={entryDraft.id} onChange={(e) => setEntryDraft({...entryDraft,id:e.target.value})} className="bg-slate-800 p-1" placeholder="id"/><input aria-label="詞條名稱" value={entryDraft.name} onChange={(e) => setEntryDraft({...entryDraft,name:e.target.value})} className="bg-slate-800 p-1" placeholder="名稱"/><input aria-label="英文 Prompt" value={entryDraft.prompt} onChange={(e) => setEntryDraft({...entryDraft,prompt:e.target.value})} className="bg-slate-800 p-1" placeholder="prompt"/></div><button onClick={createEntry} className="mt-1 rounded bg-emerald-700 px-2 py-1">新增詞條</button></>}
        <ul className="mt-3 space-y-1">{visible.map((e) => <li key={e.id} className="flex justify-between rounded bg-slate-800 p-2"><span>{e.name_zh} · {e.prompt}</span><button onClick={() => add({kind:"entry",ref:{polarity:category!.polarity,category_id:category!.id,entry_id:e.id},snapshot:e.prompt,source_revision:e.revision,weight:1,order:10}, category!.polarity)}>加入</button></li>)}</ul>
      </div>
      <div><h3 className="font-medium">2. 組合 Prompt</h3><input aria-label="自由文字" value={literal} onChange={(e)=>setLiteral(e.target.value)} className="my-2 w-full rounded bg-slate-800 p-2"/><div className="flex gap-2"><button onClick={()=>{add({kind:"literal",snapshot:literal,weight:1,order:10},"positive");setLiteral("")}}>加入正向</button><button onClick={()=>{add({kind:"literal",snapshot:literal,weight:1,order:10},"negative");setLiteral("")}}>加入負向</button></div>
        {([['正向',positive,setPositive],['負向',negative,setNegative]] as const).map(([label,items,setter])=><div key={label} className="mt-3"><b>{label}</b>{items.map((f,i)=><div key={i} className="flex gap-2"><span className="flex-1">{f.snapshot}</span><input aria-label={`${label}權重${i+1}`} type="number" step="0.1" value={f.weight} onChange={(e)=>setter(items.map((x,n)=>n===i?{...x,weight:Number(e.target.value)}:x))} className="w-16 bg-slate-800"/><button onClick={()=>setter(items.filter((_,n)=>n!==i))}>移除</button></div>)}</div>)}
        <button onClick={()=>compose(false)} className="mt-3 rounded bg-emerald-600 px-3 py-2">組合</button><input aria-label="組合 ID" value={saveId} onChange={(e)=>setSaveId(e.target.value)} className="ml-2 bg-slate-800 p-2"/><button onClick={()=>compose(true)} className="ml-2">儲存組合</button>
        <pre className="mt-3 whitespace-pre-wrap text-xs">{result.positive_prompt}{"\n"}{result.negative_prompt}</pre>
      </div>
      <div><h3 className="font-medium">3. Workflow 生圖</h3><select aria-label="Workflow" value={workflow} onChange={(e)=>setWorkflow(e.target.value)} className="my-2 w-full bg-slate-800 p-2"><option value="">選擇 workflow</option>{forms.map((f)=><option key={f.id} value={f.id}>{f.display_name}</option>)}</select><select aria-label="Seed 模式" value={seedMode} onChange={(e)=>setSeedMode(e.target.value)} className="w-full bg-slate-800 p-2"><option value="random">隨機</option><option value="workflow_default">Workflow 預設</option></select><button disabled={!workflow || !result.positive_prompt} onClick={generate} className="mt-3 w-full rounded bg-violet-600 p-2 disabled:bg-slate-700">直接生圖</button>{job && <p role="status">已送出 Job：{job}</p>}</div>
    </div>
  </section>;
}
