import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { Experiment, Project } from '../types';

type Metrics = { tp: number; fp: number; fn: number; precision: number | null; recall: number | null; f1: number | null; mean_iou: number | null };
type ScoreRow = { assignment_id: string | null; label_set_id: string | null; source: string; annotator: string; asset_name: string; time_source: string | null; completed: boolean; metrics: (Metrics & { by_class: Record<string, Metrics>; pairs: { prediction_id: string; ground_truth_id: string; category: string; iou: number; dice: number | null }[] }) | null };
type TimeComparison = { annotator: string; paired: number; expected: number; manual_seconds: number; assisted_seconds: number; saved_seconds: number | null; speedup: number | null; reduction: number | null };
type Report = { iou_threshold: number; ground_truth_id: string; rows: ScoreRow[]; time_comparison: TimeComparison[]; ai_runs: { id: string; name: string; model: string | null; gpu: string | null; inference_seconds: number | null; checkpoint: string | null }[]; summary: (Metrics & { source: string; annotator: string; run_id: string | null; assigned: number; completed: number; completion_rate: number })[] };
const metric = (value: number | null | undefined) => value == null ? 'N/A' : `${(value*100).toFixed(2)}%`;
export function ExperimentResults({ project, initialExperimentId = '', autoScore = false }: { project: Project; initialExperimentId?: string; autoScore?: boolean }) {
  const scoreLock = useRef(false);
  const [experiments, setExperiments] = useState<Experiment[]>([]), [selected, setSelected] = useState(initialExperimentId);
  const [report, setReport] = useState<Report | null>(null), [status, setStatus] = useState(''), [busy, setBusy] = useState(false);
  useEffect(() => { let active = true; api<Experiment[]>(`/projects/${project.id}/experiments`).then(rows => { if (active) setExperiments(rows); }).catch(e => { if (active) setStatus(String(e)); }); return () => { active = false; }; }, [project.id]);
  async function score() {
    if (scoreLock.current) return;
    scoreLock.current = true;
    setBusy(true); setReport(null); setStatus('Đang chấm…');
    try { setReport(await api<Report>(`/experiments/${selected}/score`)); setStatus('Đã tính điểm.'); }
    catch (e) { setStatus(String(e)); } finally { scoreLock.current = false; setBusy(false); }
  }
  useEffect(() => { if (autoScore && initialExperimentId) void score(); }, [autoScore, initialExperimentId]);
  return <section className="panel"><h2>Kết quả M49</h2><div className="fields"><label>Thử nghiệm<select disabled={busy} value={selected} onChange={e => { setSelected(e.target.value); setReport(null); }}><option value="">Chọn thử nghiệm</option>{experiments.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></label><button disabled={busy || !selected} onClick={() => void score()}>Tính / cập nhật điểm</button>
    {report && <a href={`/api/experiments/${selected}/results.csv`} download>Xuất CSV</a>}</div>
    <p role="status">{status}</p>
    {report && <>
      <h3>Thông tin AI từ Colab</h3>
      {report.ai_runs.map(run => <p key={run.id}><strong>{run.name}</strong> · {run.model ?? 'Chưa có model'} · {run.gpu ?? 'Chưa có thiết bị'} · Inference: {run.inference_seconds == null ? 'Chưa đo' : `${run.inference_seconds.toFixed(2)}s`}<br/><small>{run.checkpoint}</small></p>)}
      <p className="muted">Thời gian inference tính cho toàn lượt AI, tách riêng thời gian gán nhãn của người và thời gian truyền dữ liệu.</p>
      <h3>Thời gian người làm chay và người + AI</h3>
      {report.rows.some(r => r.time_source === 'declared_total_uniformly_distributed') && <p className="notice">Có lượt CVAT dùng thời gian nhập tay. Các cặp đó không được tính tăng tốc. Dùng lượt thử nghiệm để đo trực tiếp. CSV giữ nguồn thời gian để đối chiếu lịch sử.</p>}
      <p className="muted">So sánh thời gian thao tác trên cùng mẫu, cùng người, cả hai bản đã chốt. Chưa bao gồm thời gian AI chạy trên Colab, truyền dữ liệu hoặc thiết lập. Số âm là assisted chậm hơn.</p>
      <table><thead><tr><th>Người / cặp mẫu</th><th>Manual</th><th>Người + AI</th><th>Tiết kiệm</th><th>Tăng tốc</th></tr></thead><tbody>{report.time_comparison.map(r => <tr key={r.annotator}><td>{r.annotator} · {r.paired}/{r.expected}</td><td>{r.manual_seconds.toFixed(1)}s</td><td>{r.assisted_seconds.toFixed(1)}s</td><td>{r.saved_seconds == null ? 'N/A' : `${r.saved_seconds.toFixed(1)}s (${metric(r.reduction)})`}</td><td>{r.speedup == null ? 'N/A' : `${r.speedup.toFixed(2)}×`}</td></tr>)}</tbody></table>
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
