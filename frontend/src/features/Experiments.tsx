import { useEffect, useState } from 'react';
import { api, postJSON } from '../api';
import type { Asset, Experiment, LabelSet, Project } from '../types';

export function ExperimentSetup({ project, assets, labels }: { project: Project; assets: Asset[]; labels: LabelSet[] }) {
  const [name, setName] = useState(''), [truth, setTruth] = useState(''), [threshold, setThreshold] = useState(0.5);
  const [selected, setSelected] = useState<string[]>([]), [status, setStatus] = useState(''), [busy, setBusy] = useState(false);
  const eligible = assets.filter(a => project.task === 'detection_3d' ? a.kind === 'pointcloud' : a.kind === 'image');
  async function create() {
    setBusy(true);
    try {
      await postJSON(`/projects/${project.id}/experiments`, { name, ground_truth_id: truth, asset_ids: selected, iou_threshold: threshold });
      setStatus('Đã tạo thử nghiệm. Mở tab Gán nhãn để giao nhiệm vụ.'); setName('');
    } catch (e) { setStatus(String(e)); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>Thiết lập thử nghiệm</h2><p className="muted">Khóa phiên bản ground truth, danh sách mẫu và ngưỡng IoU. Mỗi thử nghiệm chỉ chấm một loại tác vụ.</p>
    <fieldset disabled={busy}><div className="fields"><label>Tên thử nghiệm<input value={name} onChange={e => setName(e.target.value)}/></label>
      <label>Ground truth<select value={truth} onChange={e => setTruth(e.target.value)}><option value="">Chọn bộ nhãn chuẩn</option>{labels.filter(l => l.source === 'ground_truth').map(l => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label>
      <label>Ngưỡng IoU<input type="number" min={0.01} max={1} step={0.05} value={threshold} onChange={e => setThreshold(e.target.valueAsNumber)}/></label></div>
      <div className="editor-toolbar"><button className="secondary" onClick={() => setSelected(eligible.map(a => a.id))}>Chọn tất cả mẫu</button><button className="secondary" onClick={() => setSelected([])}>Bỏ chọn</button></div>
      <div className="sample-picker">{eligible.map(a => <label key={a.id}><input type="checkbox" checked={selected.includes(a.id)} onChange={e => setSelected(ids => e.target.checked ? [...ids, a.id] : ids.filter(id => id !== a.id))}/>{a.name}</label>)}</div>
      <button disabled={!name.trim() || !truth || !selected.length || !Number.isFinite(threshold) || threshold <= 0 || threshold > 1} onClick={() => void create()}>Tạo thử nghiệm · {selected.length} mẫu</button>
    </fieldset><p role="status">{status}</p></section>;
}

type Metrics = { tp: number; fp: number; fn: number; precision: number | null; recall: number | null; f1: number | null; mean_iou: number | null };
type ScoreRow = { assignment_id: string | null; label_set_id: string | null; source: string; annotator: string; asset_name: string; completed: boolean; metrics: (Metrics & { by_class: Record<string, Metrics>; pairs: { prediction_id: string; ground_truth_id: string; category: string; iou: number; dice: number | null }[] }) | null };
type Report = { iou_threshold: number; ground_truth_id: string; rows: ScoreRow[]; summary: (Metrics & { source: string; annotator: string; run_id: string | null; assigned: number; completed: number; completion_rate: number })[] };
const metric = (value: number | null | undefined) => value == null ? 'N/A' : `${(value*100).toFixed(2)}%`;
export function ExperimentResults({ project }: { project: Project }) {
  const [experiments, setExperiments] = useState<Experiment[]>([]), [selected, setSelected] = useState('');
  const [report, setReport] = useState<Report | null>(null), [status, setStatus] = useState(''), [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; api<Experiment[]>(`/projects/${project.id}/experiments`).then(rows => { if (active) setExperiments(rows); }).catch(e => { if (active) setStatus(String(e)); }); return () => { active = false; }; }, [project.id]);
  async function score() {
    setBusy(true); setReport(null); setStatus('Đang chấm…');
    try { setReport(await api<Report>(`/experiments/${selected}/score`)); setStatus('Đã tính điểm.'); }
    catch (e) { setStatus(String(e)); } finally { setBusy(false); }
  }
  return <section className="panel"><h2>Kết quả M49</h2><div className="fields"><label>Thử nghiệm<select disabled={busy} value={selected} onChange={e => { setSelected(e.target.value); setReport(null); }}><option value="">Chọn thử nghiệm</option>{experiments.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></label><button disabled={busy || !selected} onClick={() => void score()}>Tính / cập nhật điểm</button>
    {report && <a href={`/api/experiments/${selected}/results.csv`} download>Xuất CSV</a>}</div>
    <p role="status">{status}</p>
    {report && <>
      <p className="notice">IoU ≥ {report.iou_threshold}. Chỉ nhãn người đã chốt được chấm; mẫu chưa hoàn thành được báo riêng và không tính là nhãn rỗng. N/A nghĩa là mẫu số bằng 0 hoặc chưa có kết quả. Điểm này theo giao thức M49, chưa có COCO/KITTI AP.</p>
      <table><thead><tr><th>Phương pháp / người hoặc AI run</th><th>Hoàn thành</th><th>TP / FP / FN</th><th>Precision</th><th>Recall</th><th>F1 micro</th><th>IoU cặp ghép</th></tr></thead><tbody>{report.summary.map((r, i) => <tr key={i}><td>{r.source} · {r.annotator}{r.run_id && <small> · {r.run_id.slice(0,8)}</small>}</td><td>{r.completed}/{r.assigned} ({metric(r.completion_rate)})</td><td>{r.tp} / {r.fp} / {r.fn}</td><td>{metric(r.precision)}</td><td>{metric(r.recall)}</td><td>{metric(r.f1)}</td><td>{metric(r.mean_iou)}</td></tr>)}</tbody></table>
      <h3>Chi tiết theo mẫu và lớp</h3>
      {report.rows.map((r, i) => <details key={i} className="score-detail"><summary>{r.asset_name} · {r.source} · {r.annotator} · {r.completed ? `F1 ${metric(r.metrics?.f1)}` : 'Chưa hoàn thành / thiếu kết quả'}</summary>
        {r.metrics && <><table><thead><tr><th>Lớp</th><th>TP / FP / FN</th><th>Precision</th><th>Recall</th><th>F1</th><th>IoU</th></tr></thead><tbody>{Object.entries(r.metrics.by_class).map(([c,m]) => <tr key={c}><td>{c}</td><td>{m.tp}/{m.fp}/{m.fn}</td><td>{metric(m.precision)}</td><td>{metric(m.recall)}</td><td>{metric(m.f1)}</td><td>{metric(m.mean_iou)}</td></tr>)}</tbody></table>
          <table><thead><tr><th>Nhãn dự đoán ↔ ground truth</th><th>Lớp</th><th>IoU</th><th>Dice mask</th></tr></thead><tbody>{r.metrics.pairs.map(p => <tr key={p.prediction_id}><td>{p.prediction_id} ↔ {p.ground_truth_id}</td><td>{p.category}</td><td>{metric(p.iou)}</td><td>{metric(p.dice)}</td></tr>)}</tbody></table></>}
      </details>)}
    </>}
  </section>;
}
