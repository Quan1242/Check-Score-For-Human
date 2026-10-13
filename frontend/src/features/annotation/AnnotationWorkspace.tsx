import { useEffect, useReducer, useRef, useState } from 'react';
import { api, postJSON } from '../../api';
import type { Annotation, Asset, Assignment, Experiment, LabelSet, Project } from '../../types';
import ImageEditor from './ImageEditor';
import CloudEditor from './CloudEditor';
import { historyReducer } from './history';

type EditorData = { assignment: Assignment; asset: Asset; objects: Annotation[] };
type Props = { project: Project; assets: Asset[]; labels: LabelSet[]; onSaved: () => Promise<void>; onBlocked: (value: boolean) => void; fixedAssignmentId?: string; onFinalized?: () => Promise<void> };
export default function AnnotationWorkspace({ project, assets, labels, onSaved, onBlocked, fixedAssignmentId, onFinalized }: Props) {
  const [experiments, setExperiments] = useState<Experiment[]>([]), [experimentId, setExperimentId] = useState('');
  const [assignments, setAssignments] = useState<Assignment[]>([]), [data, setData] = useState<EditorData | null>(null);
  const [annotator, setAnnotator] = useState('demo'), [mode, setMode] = useState<'manual' | 'assisted'>('manual');
  const [assetId, setAssetId] = useState(''), [parentId, setParentId] = useState('');
  const [selected, setSelected] = useState(''), [category, setCategory] = useState(project.classes[0]);
  const [history, dispatch] = useReducer(historyReducer, { past: [], present: [], future: [] });
  const [status, setStatus] = useState(''), [busy, setBusy] = useState(false), [saved, setSaved] = useState('[]');
  const [clock, setClock] = useState(0);
  const [timerFault, setTimerFault] = useState(false);
  const lock = useRef(false), latest = useRef(data), objectsRef = useRef(history.present);
  const saveRef = useRef<() => Promise<boolean>>(async () => false);
  latest.current = data; objectsRef.current = history.present;
  const fingerprint = JSON.stringify(history.present), dirty = fingerprint !== saved;
  const exp = experiments.find(e => e.id === experimentId);
  const choices = assets.filter(a => exp?.asset_ids.includes(a.id));
  const blocked = busy || dirty || !!data?.assignment.running;
  useEffect(() => { onBlocked(blocked); return () => onBlocked(false); }, [blocked, onBlocked]);
  useEffect(() => {
    let active = true;
    api<Experiment[]>(`/projects/${project.id}/experiments`).then(rows => { if (active) setExperiments(rows); }).catch(e => { if (active) setStatus(String(e)); });
    return () => { active = false; };
  }, [project.id]);
  useEffect(() => {
    let active = true; setAssignments([]); setData(null); setAssetId(''); dispatch({ type: 'reset', objects: [] }); setSaved('[]');
    if (experimentId) api<Assignment[]>(`/experiments/${experimentId}/assignments`).then(rows => { if (active) setAssignments(rows); }).catch(e => { if (active) setStatus(String(e)); });
    return () => { active = false; };
  }, [experimentId]);
  useEffect(() => { if (fixedAssignmentId) void load(fixedAssignmentId); }, [fixedAssignmentId]);
  useEffect(() => {
    if (!data?.assignment.running) return;
    const timer = window.setInterval(() => setClock(c => c+1), 1000);
    return () => window.clearInterval(timer);
  }, [data?.assignment.running]);
  useEffect(() => {
    async function tick() {
      const current = latest.current;
      if (!current?.assignment.running || lock.current) return;
      const pause = document.hidden || !navigator.onLine;
      lock.current = true;
      try {
        const row = await postJSON<Assignment>(`/assignments/${current.assignment.id}/events`,
          { revision: current.assignment.revision, kind: pause ? 'pause' : 'heartbeat' }, { signal: AbortSignal.timeout(8000) });
        update(row);
        if (!row.running) setStatus('Timer đã dừng. Bấm tiếp tục khi sẵn sàng làm việc.');
      } catch (e) {
        // Server expires the lease even when pause cannot reach it.
        setTimerFault(true);
        setStatus(`Mất đồng bộ timer: ${String(e)}. Tải lại nhiệm vụ sau khi lưu nhãn để kiểm tra thời gian.`);
      } finally { lock.current = false; }
    }
    const timer = window.setInterval(() => { void tick(); }, 10000);
    const visibility = () => { if (document.hidden || !navigator.onLine) void tick(); };
    document.addEventListener('visibilitychange', visibility);
    window.addEventListener('offline', visibility);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', visibility);
      window.removeEventListener('offline', visibility);
    };
  }, []);
  useEffect(() => {
    function beforeUnload(e: BeforeUnloadEvent) { if (dirty || busy || latest.current?.assignment.running) { e.preventDefault(); e.returnValue = ''; } }
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [dirty, busy]);
  function update(row: Assignment) {
    setTimerFault(false);
    setClock(0); setData(d => d ? { ...d, assignment: row } : d);
    if (latest.current) latest.current = { ...latest.current, assignment: row };
    setAssignments(rows => rows.map(a => a.id === row.id ? row : a));
  }
  async function load(id: string) {
    if (lock.current) return; lock.current = true; setBusy(true);
    try {
      const next = await api<EditorData>(`/assignments/${id}/editor`);
      if (!next.assignment.final_id && !next.assignment.running) next.assignment = await postJSON<Assignment>(`/assignments/${id}/events`, { revision: next.assignment.revision, kind: 'resume' });
      setData(next); latest.current = next; setTimerFault(false); dispatch({ type: 'reset', objects: next.objects });
      setSaved(JSON.stringify(next.objects)); setSelected(''); setClock(0); setStatus('Đã tải nhiệm vụ.');
    } catch (e) { setStatus(String(e)); } finally { lock.current = false; setBusy(false); }
  }
  async function create() {
    if (lock.current) return; lock.current = true; setBusy(true);
    try {
      const row = await postJSON<Assignment>(`/experiments/${experimentId}/assignments`, { asset_id: assetId || choices[0]?.id, annotator, mode, parent_id: mode === 'assisted' ? parentId : null });
      setAssignments(rows => [...rows, row]);
      const next = await api<EditorData>(`/assignments/${row.id}/editor`);
      next.assignment = await postJSON<Assignment>(`/assignments/${row.id}/events`, { revision: next.assignment.revision, kind: 'resume' });
      setData(next); latest.current = next; setTimerFault(false); dispatch({ type: 'reset', objects: next.objects }); setSaved(JSON.stringify(next.objects)); setSelected(''); setClock(0); setStatus('Đã tạo nhiệm vụ và bắt đầu đo thời gian gán nhãn.');
    } catch (e) { setStatus(String(e)); } finally { lock.current = false; setBusy(false); }
  }
  async function save() {
    const current = latest.current;
    if (!current || current.assignment.final_id || lock.current) return false;
    lock.current = true; setBusy(true); setStatus('Đang lưu…');
    const snapshot = objectsRef.current;
    try {
      const row = await postJSON<Assignment>(`/assignments/${current.assignment.id}/draft`, { revision: current.assignment.revision, objects: snapshot });
      update(row); setSaved(JSON.stringify(snapshot)); setStatus('Đã lưu bản nháp.');
      void onSaved().catch(() => {});
      return true;
    } catch (e) { setStatus(`Lưu thất bại: ${String(e)}. Nội dung vẫn ở editor; hãy lưu lại hoặc tải lại nhiệm vụ.`); return false; }
    finally { lock.current = false; setBusy(false); }
  }
  saveRef.current = save;
  useEffect(() => {
    if (!dirty || !data || data.assignment.final_id) return;
    function attempt() {
      if (lock.current) { timer = window.setTimeout(attempt, 250); return; }
      void saveRef.current();
    }
    let timer = window.setTimeout(attempt, 900);
    return () => window.clearTimeout(timer);
  }, [fingerprint, dirty, data?.assignment.id]);
  async function event(kind: 'pause' | 'resume' | 'finalize') {
    if (lock.current) return;
    if (kind === 'finalize' && (dirty || !latest.current?.assignment.draft_id)) {
      if (!await save()) return;
    }
    const current = latest.current;
    if (!current || lock.current) return;
    lock.current = true; setBusy(true);
    try {
      const row = await postJSON<Assignment>(`/assignments/${current.assignment.id}/${kind === 'finalize' ? 'finalize' : 'events'}`,
        { revision: current.assignment.revision, ...(kind === 'finalize' ? {} : { kind }) });
      setTimerFault(false); update(row); setStatus(kind === 'finalize' ? 'Đã chốt phiên bản để chấm điểm.' : kind === 'pause' ? 'Đã tạm dừng.' : 'Đang tính thời gian.');
      if (kind === 'finalize') await onFinalized?.();
    } catch (e) { setStatus(String(e)); } finally { lock.current = false; setBusy(false); }
  }
  const readOnly = busy || !!data?.assignment.final_id;
  const editDisabled = readOnly || timerFault || !data?.assignment.running || clock >= data.assignment.timer_remaining_seconds;
  const active = history.present.find(o => o.id === selected);
  useEffect(() => {
    function shortcut(e: KeyboardEvent) {
      if (editDisabled || lock.current || !(e.target instanceof HTMLElement) ||
          e.target.closest('input, textarea, select, [contenteditable="true"]')) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z') {
        e.preventDefault(); dispatch({ type: e.shiftKey ? 'redo' : 'undo' });
      } else if (e.key === 'Delete' && selected) {
        e.preventDefault(); dispatch({ type: 'change', objects: objectsRef.current.filter(o => o.id !== selected) }); setSelected('');
      }
    }
    window.addEventListener('keydown', shortcut);
    return () => window.removeEventListener('keydown', shortcut);
  }, [editDisabled, selected]);
  return <section className="panel">
    <h2>Không gian gán nhãn</h2>
    {!fixedAssignmentId && <><p className="muted">Tạo thử nghiệm tại tab Dữ liệu, sau đó giao từng mẫu. Chốt bản nháp để đưa vào kết quả.</p>
    <div className="fields"><label>Thử nghiệm<select value={experimentId} disabled={blocked} onChange={e => setExperimentId(e.target.value)}><option value="">Chọn thử nghiệm</option>{experiments.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></label>
      <label>Nhiệm vụ<select value={data?.assignment.id || ''} disabled={blocked} onChange={e => { if (e.target.value) void load(e.target.value); }}><option value="">Chọn nhiệm vụ</option>{assignments.map(a => <option key={a.id} value={a.id}>{a.annotator} · {a.mode} · {assets.find(v => v.id === a.asset_id)?.name} {a.final_id ? '✓' : ''}</option>)}</select></label></div>
    {exp && <details><summary>Giao nhiệm vụ mới</summary><fieldset disabled={blocked}><div className="fields">
      <label>Người thực hiện<input value={annotator} onChange={e => setAnnotator(e.target.value)}/></label>
      <label>Mẫu<select value={assetId || choices[0]?.id || ''} onChange={e => setAssetId(e.target.value)}>{choices.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      <label>Chế độ<select value={mode} onChange={e => setMode(e.target.value as 'manual' | 'assisted')}><option value="manual">Manual</option><option value="assisted">Assisted</option></select></label>
      {mode === 'assisted' && <label>Nhãn AI<select value={parentId} onChange={e => setParentId(e.target.value)}><option value="">Chọn bản AI</option>{labels.filter(l => l.source === 'ai').map(l => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label>}
      <button disabled={!annotator.trim() || !choices.length || (mode === 'assisted' && !parentId)} onClick={() => void create()}>Tạo nhiệm vụ</button>
    </div></fieldset></details>}</>}
    {data && <>
      <div className="editor-toolbar">
        <label>Lớp cho đối tượng mới<select disabled={readOnly} value={category} onChange={e => setCategory(e.target.value)}>{project.classes.map(c => <option key={c}>{c}</option>)}</select></label>
        <button disabled={editDisabled || !history.past.length} onClick={() => dispatch({ type: 'undo' })}>Undo</button>
        <button disabled={editDisabled || !history.future.length} onClick={() => dispatch({ type: 'redo' })}>Redo</button>
        <button disabled={editDisabled || !active} onClick={() => { dispatch({ type: 'change', objects: history.present.filter(o => o.id !== selected) }); setSelected(''); }}>Xóa đối tượng</button>
        <button disabled={readOnly} onClick={() => void save()}>Lưu ngay</button>
        <button disabled={readOnly} onClick={() => void event(data.assignment.running ? 'pause' : 'resume')}>{data.assignment.running ? 'Tạm dừng' : 'Bắt đầu / tiếp tục'} · {Math.floor(data.assignment.active_seconds+(data.assignment.running ? Math.min(clock,data.assignment.timer_remaining_seconds) : 0))}s</button>
        <button disabled={readOnly} onClick={() => void event('finalize')}>{fixedAssignmentId ? 'Chốt và sang mẫu tiếp theo' : 'Lưu và chốt phiên bản'}</button>
      </div>
      {data.assignment.final_id && <p className="notice">Nhiệm vụ đã chốt, chỉ xem.</p>}
      {!data.assignment.final_id && <p className="muted">Thời gian tự bắt đầu khi mở nhiệm vụ, gồm vẽ/sửa và quan sát nhãn. Tạm dừng khi nghỉ; ẩn tab sẽ tự dừng, chốt nhãn sẽ kết thúc. Không nhập số giây bằng tay. Mất kết nối chỉ cộng tối đa 30 giây từ heartbeat cuối. Delete: xóa; Ctrl/Cmd+Z: hoàn tác; Ctrl/Cmd+Shift+Z: làm lại.</p>}
      {data.asset.kind === 'image' ? <ImageEditor key={data.assignment.id} asset={data.asset} objects={history.present} category={category} polygon={project.task === 'instance_segmentation'} selected={selected} onSelect={setSelected} disabled={editDisabled} onChange={objects => dispatch({ type: 'change', objects })}/>
        : <CloudEditor key={data.assignment.id} asset={data.asset} objects={history.present} category={category} selected={selected} onSelect={setSelected} disabled={editDisabled} onChange={objects => dispatch({ type: 'change', objects })}/>}
      <div className="fields"><label>Đối tượng ({history.present.length})<select value={selected} onChange={e => setSelected(e.target.value)}><option value="">Chọn đối tượng</option>{history.present.map((o, i) => <option key={o.id} value={o.id}>{i+1}. {o.category} · {o.id.slice(0,8)}</option>)}</select></label>
        {active && <label>Đổi lớp<select disabled={editDisabled} value={active.category} onChange={e => dispatch({ type: 'change', objects: history.present.map(o => o.id === active.id ? { ...o, category: e.target.value } : o) })}>{project.classes.map(c => <option key={c}>{c}</option>)}</select></label>}
      </div>
      <details><summary>Xem JSON nhãn hiện tại</summary><pre className="json-preview">{JSON.stringify(history.present, null, 2)}</pre></details>
      <button className="secondary" disabled={busy} onClick={() => { if (!dirty || window.confirm('Bỏ thay đổi chưa lưu và tải lại bản trên server?')) void load(data.assignment.id); }}>Tải lại nhiệm vụ</button>
      {blocked && <p className="muted">Lưu thay đổi và tạm dừng timer trước khi chuyển tab hoặc dự án.</p>}
    </>}
    <p role="status">{dirty ? 'Có thay đổi chưa lưu. ' : ''}{status}</p>
  </section>;
}
