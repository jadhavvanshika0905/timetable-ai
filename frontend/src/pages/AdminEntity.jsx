import { useCallback, useEffect, useState } from "react";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom";
import * as ad from "../api/adminData";
import { Alert, Empty, PageHeader, Spinner } from "../components/Bits";
import { btnGhost, btnPrimary, card, input, label } from "../lib/ui";
import { CFG, blank, pretty } from "../lib/adminConfig";

/** /admin/:resource  ->  three tabs: Add one, Upload file (Excel/CSV), List. */
export default function AdminEntity() {
  const { resource } = useParams();
  const cfg = CFG[resource];
  const [params, setParams] = useSearchParams();
  const [refresh, setRefresh] = useState(0);
  if (!cfg) return <Navigate to="/admin" replace />;

  const tabs = cfg.uploadOnly ? [["upload", "Upload file"]] : [["add", "Add one"], ["upload", "Upload file"], ["list", "List"]];
  const tab = tabs.some(([id]) => id === params.get("tab")) ? params.get("tab") : tabs[0][0];
  const go = (t) => setParams({ tab: t });
  const bump = () => setRefresh((n) => n + 1);

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title={cfg.label}>
        <Link to="/admin" className={btnGhost}>Back to all data</Link>
      </PageHeader>
      <p className="-mt-2 mb-4 text-sm text-ink-soft">{cfg.blurb}</p>

      <div className="mb-4 flex flex-wrap gap-2" role="tablist">
        {tabs.map(([id, text]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id} onClick={() => go(id)}
            className={`rounded-md border px-4 py-2 text-sm font-medium ${tab === id ? "border-brand bg-brand-tint text-brand-dark" : "border-line bg-surface hover:bg-paper"}`}>{text}</button>
        ))}
      </div>

      <section className={`${card} p-5`}>
        {tab === "add" && <AddForm key={resource} resource={resource} cfg={cfg} onSaved={bump} onList={() => go("list")} />}
        {tab === "upload" && <UploadBox key={resource} cfg={cfg} onSaved={() => { bump(); if (!cfg.uploadOnly) go("list"); }} />}
        {tab === "list" && <DataList key={resource} resource={resource} cfg={cfg} refreshKey={refresh} onAdd={() => go("add")} onUpload={() => go("upload")} />}
      </section>
    </div>
  );
}

/* ---------------- Add one ---------------- */
function useOptions(cfg) {
  const [opts, setOpts] = useState({});
  const [err, setErr] = useState("");
  useEffect(() => {
    let off = false;
    (async () => {
      try {
        const o = {};
        for (const f of (cfg.fields || []).filter((x) => x.t === "fk")) o[f.fk] = (await ad.list(f.fk, { limit: 2000 })).results;
        if (!off) setOpts(o);
      } catch (e) { if (!off) setErr(e.message); }
    })();
    return () => { off = true; };
  }, [cfg]);
  return [opts, err];
}

function AddForm({ resource, cfg, onSaved, onList }) {
  const [form, setForm] = useState(blank(cfg));
  const [opts, optErr] = useOptions(cfg);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ok, setOk] = useState("");
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  async function submit(e) {
    e.preventDefault();
    setError(""); setOk(""); setBusy(true);
    const body = {};
    for (const f of cfg.fields) {
      const v = form[f.k];
      body[f.k] = (f.t === "number" || f.t === "fk") ? (v === "" ? null : Number(v))
        : ((f.t === "date" || f.t === "time") && v === "") ? null : v;
    }
    try {
      await ad.create(resource, body);
      setOk(`Saved. Add the next ${cfg.one} or open the list.`);
      setForm(blank(cfg)); onSaved();
    } catch (err) { setError(err.message); } finally { setBusy(false); }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <p className="text-sm text-ink-soft">Adding many {cfg.label.toLowerCase()}? Use the <span className="font-medium text-ink">Upload file</span> tab with an Excel or CSV sheet instead.</p>
      {(error || optErr) && <Alert>{error || optErr}</Alert>}
      {ok && <Alert kind="success">{ok}</Alert>}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {cfg.fields.map((f) => (
          <div key={f.k} className={f.t === "bool" ? "flex items-end" : ""}>
            {f.t === "bool" ? (
              <label className="flex items-center gap-2 pb-2 text-sm">
                <input type="checkbox" className="accent-brand" checked={form[f.k]} onChange={(e) => set(f.k, e.target.checked)} />
                <span>{pretty(f.k)}{f.hint && <span className="block text-xs text-ink-soft">{f.hint}</span>}</span>
              </label>
            ) : (
              <>
                <label htmlFor={`f-${f.k}`} className={label}>{pretty(f.k)}{f.opt ? " (optional)" : ""}</label>
                {f.t === "select" || f.t === "fk" ? (
                  <select id={`f-${f.k}`} className={input} value={form[f.k]} onChange={(e) => set(f.k, e.target.value)}>
                    {f.t === "fk" && <option value="">{f.opt ? "None" : "Choose"}</option>}
                    {f.t === "select"
                      ? f.options.map(([v, t]) => <option key={v} value={v}>{t}</option>)
                      : (opts[f.fk] || []).map((o) => <option key={o.id} value={o.id}>{CFG[f.fk].name(o)}</option>)}
                  </select>
                ) : (
                  <input id={`f-${f.k}`} className={input} required={!f.opt && f.t === "text"}
                    type={{ number: "number", date: "date", time: "time" }[f.t] || "text"}
                    placeholder={f.t === "text" ? f.hint || "" : ""} value={form[f.k]} onChange={(e) => set(f.k, e.target.value)} />
                )}
              </>
            )}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        <button type="submit" className={btnPrimary} disabled={busy}>{busy && <Spinner />} Save {cfg.one}</button>
        <button type="button" className={btnGhost} onClick={onList}>Open list</button>
      </div>
    </form>
  );
}

/* ---------------- Upload Excel / CSV ---------------- */
function UploadBox({ cfg, onSaved }) {
  const [file, setFile] = useState(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [errors, setErrors] = useState([]);
  const [warnings, setWarnings] = useState([]);
  const [ok, setOk] = useState("");
  const [checked, setChecked] = useState(false);
  const [inputKey, setInputKey] = useState(0); // changing this clears the file input, so the same file can be chosen again

  const pick = (f) => { setFile(f || null); setChecked(false); setOk(""); setError(""); setErrors([]); setWarnings([]); };

  const removeFile = () => { pick(null); setInputKey((k) => k + 1); };

  async function run(dry) {
    setError(""); setErrors([]); setWarnings([]); setOk(""); setBusy(dry ? "check" : "save");
    try {
      const r = await ad.importFile(file, cfg.imp, dry);
      setWarnings(r.warnings || []);
      if (dry) { setChecked(true); setOk(`All ${r.total_rows} rows are valid. Nothing is saved yet.`); }
      else { setOk(`${r.total_rows} rows saved: ${r.created} new, ${r.updated} updated.`); setFile(null); setChecked(false); onSaved(); }
    } catch (err) {
      setChecked(false); setError(err.message); setErrors(err.data?.errors || []); setWarnings(err.data?.warnings || []);
    } finally { setBusy(""); }
  }

  return (
    <div className="space-y-4">
      <ol className="list-decimal space-y-1 pl-5 text-sm text-ink-soft">
        <li>Download the template and fill one row per {cfg.one}. Paste all 50 or 500 rows in one go.</li>
        <li>Choose the file, then check it. If any row is wrong, you will see which row and column.</li>
        <li>When the check passes, save. Uploading the same file again updates records, it does not duplicate them.</li>
      </ol>
      <button type="button" className={btnGhost} onClick={() => ad.downloadTemplate(cfg.imp).catch((e) => setError(e.message))}>
        Download {cfg.label.toLowerCase()} template (.xlsx)
      </button>

      <label htmlFor="up-file"
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files[0]); }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-10 text-center transition ${drag ? "border-brand bg-brand-tint" : "border-line bg-paper hover:border-brand"}`}>
        <span className="font-medium">{file ? file.name : "Drop an Excel or CSV file here, or click to choose"}</span>
        <span className="mt-1 text-xs text-ink-soft">{file ? `${(file.size / 1024).toFixed(1)} KB` : ".xlsx, .xlsm or .csv"}</span>
        <input key={inputKey} id="up-file" type="file" accept=".csv,.xlsx,.xlsm" className="sr-only" onChange={(e) => pick(e.target.files[0])} />
      </label>

      {file && (
        <div className="flex items-center justify-between gap-3 rounded-md border border-line px-3 py-2 text-sm">
          <span className="truncate"><span className="font-medium">{file.name}</span> <span className="text-ink-soft">selected</span></span>
          <button type="button" onClick={removeFile} disabled={!!busy} className="shrink-0 font-medium text-bad underline">Remove file</button>
        </div>
      )}

      {error && <Alert>{error}</Alert>}
      {ok && <Alert kind="success">{ok}</Alert>}
      {warnings.length > 0 && <ul className="list-disc pl-5 text-sm text-ink-soft">{warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>}
      {errors.length > 0 && (
        <div className="max-h-64 overflow-auto rounded-md border border-line">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-paper text-left"><tr><th className="p-2">Row</th><th className="p-2">Column</th><th className="p-2">Problem</th></tr></thead>
            <tbody>{errors.map((x, i) => <tr key={i} className="border-t border-line"><td className="p-2">{x.row}</td><td className="p-2">{x.column}</td><td className="p-2">{x.message}</td></tr>)}</tbody>
          </table>
        </div>
      )}

      <div className="flex flex-wrap gap-3">
        <button type="button" className={checked ? btnGhost : btnPrimary} disabled={!file || !!busy} onClick={() => run(true)}>
          {busy === "check" && <Spinner />} Check file
        </button>
        <button type="button" className={btnPrimary} disabled={!file || !checked || !!busy} onClick={() => run(false)}>
          {busy === "save" && <Spinner />} Save all rows
        </button>
      </div>
    </div>
  );
}

/* ---------------- List ---------------- */
function DataList({ resource, cfg, refreshKey, onAdd, onUpload }) {
  const [rows, setRows] = useState([]);
  const [count, setCount] = useState(0);
  const [q, setQ] = useState("");
  const [opts, optErr] = useOptions(cfg);
  const [state, setState] = useState("loading");
  const [error, setError] = useState("");
  const [wiping, setWiping] = useState(null); // null | { done, total }
  const [note, setNote] = useState(null); // { kind, text }

  const load = useCallback(async () => {
    try { const d = await ad.list(resource, { q }); setRows(d.results); setCount(d.count); setState("ready"); }
    catch (e) { setError(e.message); setState("error"); }
  }, [resource, q]);
  useEffect(() => { const t = setTimeout(load, q ? 300 : 0); return () => clearTimeout(t); }, [load, refreshKey, q]);

  const cell = (r, k) => {
    const f = cfg.fields.find((x) => x.k === k);
    if (f?.t === "fk") { const o = opts[f.fk]?.find((x) => x.id === r[k]); return o ? CFG[f.fk].name(o) : r[k] ?? ""; }
    if (f?.t === "bool") return r[k] ? "Yes" : "No";
    return String(r[k] ?? "");
  };

  async function del(r) {
    if (!window.confirm(`Delete ${cfg.name(r)}?`)) return;
    try { await ad.remove(resource, r.id); load(); } catch (e) { setError(e.message); setState("error"); }
  }

  async function deleteAll() {
    const what = q ? `all ${count} ${cfg.label.toLowerCase()} matching "${q}"` : `ALL ${count} ${cfg.label.toLowerCase()}`;
    if (!window.confirm(`Delete ${what}? This cannot be undone.`)) return;
    if (!q && count > 20 && window.prompt(`Type DELETE to confirm removing ${count} records.`) !== "DELETE") return;
    setNote(null); setWiping({ done: 0, total: count });
    let done = 0; const failed = []; const bad = new Set();
    try {
      for (let round = 0; round < 50; round++) {
        const rest = (await ad.list(resource, { q, limit: 5000 })).results.filter((r) => !bad.has(r.id));
        if (!rest.length) break;
        for (let i = 0; i < rest.length; i += 8) {
          await Promise.all(rest.slice(i, i + 8).map((r) =>
            ad.remove(resource, r.id).then(() => { done++; }).catch((e) => { bad.add(r.id); failed.push(e.message); })));
          setWiping({ done: done + bad.size, total: count });
        }
      }
    } catch (e) { failed.push(e.message); }
    setWiping(null);
    setNote(failed.length
      ? { kind: "error", text: `Deleted ${done}. ${failed.length} could not be deleted (they are probably used by other data, so delete that first). ${failed[0]}` }
      : { kind: "success", text: `Deleted ${done} ${cfg.label.toLowerCase()}.` });
    load();
  }

  function csv() {
    const head = cfg.show.map(pretty).join(",");
    const body = rows.map((r) => cfg.show.map((k) => `"${cell(r, k).replaceAll('"', '""')}"`).join(",")).join("\n");
    const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([head + "\n" + body], { type: "text/csv" })), download: `${resource}.csv` });
    a.click(); URL.revokeObjectURL(a.href);
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-lg font-semibold">{cfg.label} <span className="tabular-nums text-ink-soft">({count})</span></h2>
        <div className="flex flex-wrap items-center gap-2">
          <input className={`${input} w-56`} placeholder="Search" aria-label="Search" value={q} onChange={(e) => setQ(e.target.value)} />
          <button type="button" className={btnGhost} onClick={csv} disabled={!rows.length || !!wiping}>Download CSV</button>
          <button type="button" onClick={deleteAll} disabled={!count || !!wiping}
            className="rounded-md border border-bad px-3 py-2 text-sm font-medium text-bad transition hover:bg-bad hover:text-white disabled:opacity-50">
            {wiping ? `Deleting ${wiping.done} of ${wiping.total}` : q ? "Delete matching" : "Delete all"}
          </button>
        </div>
      </div>
      {note && <div className="mb-3"><Alert kind={note.kind === "success" ? "success" : undefined}>{note.text}</Alert></div>}
      {(state === "error" || optErr) && <Alert>{error || optErr}</Alert>}
      {state === "loading" && <p className="flex items-center gap-2 text-sm text-ink-soft"><Spinner /> Loading</p>}
      {state === "ready" && rows.length === 0 && (
        <Empty title={q ? "Nothing matches your search." : `No ${cfg.label.toLowerCase()} yet.`}>
          {!q && <><button type="button" className="font-medium text-brand underline" onClick={onAdd}>Add one</button> or <button type="button" className="font-medium text-brand underline" onClick={onUpload}>upload a file</button>.</>}
        </Empty>
      )}
      {rows.length > 0 && (
        <div className="max-h-[32rem] overflow-auto rounded-md border border-line">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-paper text-left"><tr>{cfg.show.map((k) => <th key={k} className="p-2">{pretty(k)}</th>)}<th className="p-2" /></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-t border-line hover:bg-paper">
                  {cfg.show.map((k) => <td key={k} className="p-2">{cell(r, k)}</td>)}
                  <td className="p-2 text-right"><button type="button" className="text-bad underline" onClick={() => del(r)}>Delete</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {count > rows.length && <p className="mt-1 text-xs text-ink-soft">Showing the first {rows.length}. Use search to find others.</p>}
    </div>
  );
}