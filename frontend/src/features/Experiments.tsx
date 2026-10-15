import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { Experiment, Project } from '../types';
import GroundTruthComparison from './GroundTruthComparison';
import './results.css';

type Metrics = { tp: number; fp: number; fn: number; precision: number | null; recall: number | null; f1: number | null; mean_iou: number | null };
type ScoreRow = { assignment_id: string | null; label_set_id: string | null; source: string; annotator: string; asset_name: string; time_source: string | null; completed: boolean; metrics: (Metrics & { by_class: Record<string, Metrics>; pairs: { prediction_id: string; ground_truth_id: string; category: string; iou: number; dice: number | null }[] }) | null };
type TimeComparison = { annotator: string; paired: number; expected: number; manual_seconds: number; assisted_seconds: number; saved_seconds: number | null; speedup: number | null; reduction: number | null };
type Report = { iou_threshold: number; ground_truth_id: string; rows: ScoreRow[]; time_comparison: TimeComparison[]; ai_runs: { id: string; name: string; model: string | null; gpu: string | null; inference_seconds: number | null; checkpoint: string | null }[]; summary: (Metrics & { source: string; annotator: string; run_id: string | null; assigned: number; expected: number; completed: number; completion_rate: number })[] };
const metric = (value: number | null | undefined) => value == null ? 'N/A' : `${(value*100).toFixed(1)}%`;
const methodName = (source: string) => ({ manual: 'Người tự gán nhãn', ai: 'AI', assisted: 'Người sửa nhãn AI' })[source] ?? source;
function MetricHeaders() {
  return <><th title="Số tìm đúng / số đối tượng chuẩn">Đúng / chuẩn</th><th title="Nhãn vẽ thừa hoặc sai">Thừa/sai</th><th>Bỏ sót</th><th title="Tỷ lệ nhãn đúng">Precision</th><th title="Mức độ đầy đủ">Recall</th><th>F1</th><th title="IoU trung bình trên các cặp ghép đúng">IoU</th></>;
}
function MetricCells({ value }: { value: Metrics }) {
  return <><td>{value.tp} / {value.tp + value.fn}</td><td>{value.fp}</td><td>{value.fn}</td><td>{metric(value.precision)}</td><td><strong>{metric(value.recall)}</strong></td><td>{metric(value.f1)}</td><td>{metric(value.mean_iou)}</td></>;
}
export function ExperimentResults({ project, initialExperimentId = '', autoScore = false }: { project: Project; initialExperimentId?: string; autoScore?: boolean }) {
  const scoreLock = useRef(false);
  const [compare, setCompare] = useState(false);
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
  return <section className="panel results-panel"><h2>Kết quả M49</h2><div className="fields"><label>Thử nghiệm<select disabled={busy} value={selected} onChange={e => { setSelected(e.target.value); setReport(null); setCompare(false); }}><option value="">Chọn thử nghiệm</option>{experiments.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}</select></label><button disabled={busy || !selected} onClick={() => void score()}>Tính / cập nhật điểm</button>
    {report && <a href={`/api/experiments/${selected}/results.csv`} download>Xuất CSV</a>}</div>
    <p role="status">{status}</p>
    {report && <>
      <details className="results-extra"><summary>Thông tin AI từ Colab</summary>
      {report.ai_runs.map(run => <p key={run.id}><strong>{run.name}</strong> · {run.model ?? 'Chưa có model'} · {run.gpu ?? 'Chưa có thiết bị'} · Inference: {run.inference_seconds == null ? 'Chưa đo' : `${run.inference_seconds.toFixed(2)}s`}<br/><small>{run.checkpoint}</small></p>)}
      <p className="muted">Thời gian inference tính cho toàn lượt AI, tách riêng thời gian gán nhãn của người và thời gian truyền dữ liệu.</p>
      </details>
      <h3>Thời gian thực hiện</h3>
      {report.rows.some(r => r.time_source?.startsWith('declared_')) && <p className="notice">Có lượt CVAT dùng thời gian nhập tay. Các cặp đó không được tính tăng tốc. CSV giữ nguồn thời gian để đối chiếu.</p>}
      <p className="muted">Cùng người, cùng mẫu đã chốt · Chỉ tính thời gian thao tác · Số âm nghĩa là sửa AI chậm hơn.</p>
      <div className="results-table-scroll"><table><thead><tr><th>Người / cặp mẫu</th><th>Manual</th><th>Người + AI</th><th>Tiết kiệm</th><th>Tăng tốc</th></tr></thead><tbody>{report.time_comparison.map(r => <tr key={r.annotator}><td>{r.annotator} · {r.paired}/{r.expected}</td><td>{r.manual_seconds.toFixed(1)}s</td><td>{r.assisted_seconds.toFixed(1)}s</td><td>{r.saved_seconds == null ? 'N/A' : `${r.saved_seconds.toFixed(1)}s (${metric(r.reduction)})`}</td><td>{r.speedup == null ? 'N/A' : `${r.speedup.toFixed(2)}×`}</td></tr>)}</tbody></table></div>
      <h3>Đánh giá tổng cả bộ mẫu</h3>
      <p className="muted">Đối chiếu nhãn chuẩn · Ngưỡng IoU {metric(report.iou_threshold)} · Chỉ tính mẫu đã hoàn thành.</p>
      <div className="results-table-scroll"><table><thead><tr><th>Phương pháp</th><th>Mẫu</th><MetricHeaders /></tr></thead><tbody>{report.summary.map((r, i) => <tr key={i}><td><strong>{methodName(r.source)}</strong><small className="result-person">{r.annotator}{r.run_id && <> · {r.run_id.slice(0,8)}</>}</small></td><td>{r.completed}/{r.expected}{r.completed < r.expected && <small> · Tạm tính</small>}</td><MetricCells value={r} /></tr>)}</tbody></table></div>
      <details className="results-extra"><summary>Cách đọc kết quả</summary>
      <p className="muted">Cộng số tìm đúng, thừa/sai và bỏ sót trên các mẫu đã chấm rồi tính tỷ lệ. Một nhãn được ghép đúng khi cùng lớp và IoU ít nhất {metric(report.iou_threshold)}; mỗi đối tượng chỉ ghép một lần.</p>
      <p className="muted"><strong>Mức độ đầy đủ</strong> = số tìm đúng / số đối tượng chuẩn trong các mẫu đã chấm. <strong>Tỷ lệ nhãn đúng</strong> = số tìm đúng / số nhãn đã vẽ. <strong>Điểm F1</strong> tính cả bỏ sót và vẽ thừa hoặc sai. <strong>Độ khớp các nhãn đúng</strong> là IoU trung bình chỉ trên các cặp ghép đúng, không thể hiện mức độ đầy đủ của cả bộ mẫu.</p>
      <p className="muted">Chỉ nhãn người đã chốt được chấm; mẫu chưa hoàn thành không tính là nhãn rỗng. N/A nghĩa là mẫu số bằng 0 hoặc chưa có kết quả. Điểm này theo giao thức M49, chưa có COCO/KITTI AP.</p>
      </details>
      {report.summary.some(r => r.completed < r.expected) && <p className="notice">Chưa hoàn thành đủ mẫu của thử nghiệm. Điểm hiện tại chỉ tính trên các mẫu đã hoàn thành; các phương pháp có thể đang được chấm trên tập mẫu khác nhau.</p>}
      <details className="results-extra"><summary>Chi tiết từng mẫu và lớp ({report.rows.length})</summary>
      <p className="muted">Các số bên dưới chỉ tính riêng từng mẫu, không phải kết quả cả lượt.</p>
      {report.rows.map((r, i) => <details key={i} className="score-detail"><summary>{r.asset_name} · {methodName(r.source)} · {r.annotator} · {r.completed && r.metrics ? `Tìm đúng ${r.metrics.tp}/${r.metrics.tp + r.metrics.fn} đối tượng · Bỏ sót ${r.metrics.fn} · Vẽ thừa hoặc sai ${r.metrics.fp}` : 'Chưa hoàn thành / thiếu kết quả'}</summary>
        {r.metrics && <><div className="results-table-scroll"><table><thead><tr><th>Lớp</th><MetricHeaders /></tr></thead><tbody>{Object.entries(r.metrics.by_class).map(([c,m]) => <tr key={c}><td>{c}</td><MetricCells value={m} /></tr>)}</tbody></table></div>
          <div className="results-table-scroll"><table><thead><tr><th>Nhãn dự đoán ↔ nhãn chuẩn</th><th>Lớp</th><th>Độ chồng khớp (IoU)</th><th>Độ tương đồng vùng (Dice)</th></tr></thead><tbody>{r.metrics.pairs.map(p => <tr key={p.prediction_id}><td>{p.prediction_id} ↔ {p.ground_truth_id}</td><td>{p.category}</td><td>{metric(p.iou)}</td><td>{metric(p.dice)}</td></tr>)}</tbody></table></div></>}
      </details>)}
      </details>
      <button className="secondary comparison-toggle" aria-expanded={compare} onClick={() => setCompare(value => !value)}>{compare ? 'Đóng đối chiếu ground truth' : 'Đối chiếu với ground truth'}</button>
      {compare && <GroundTruthComparison key={selected} project={project} groundTruthId={report.ground_truth_id} rows={report.rows}/>}
    </>}
  </section>;
}
