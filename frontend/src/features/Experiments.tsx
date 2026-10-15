import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import type { Experiment, Project } from '../types';

type Metrics = { tp: number; fp: number; fn: number; precision: number | null; recall: number | null; f1: number | null; mean_iou: number | null };
type ScoreRow = { assignment_id: string | null; label_set_id: string | null; source: string; annotator: string; asset_name: string; time_source: string | null; completed: boolean; metrics: (Metrics & { by_class: Record<string, Metrics>; pairs: { prediction_id: string; ground_truth_id: string; category: string; iou: number; dice: number | null }[] }) | null };
type TimeComparison = { annotator: string; paired: number; expected: number; manual_seconds: number; assisted_seconds: number; saved_seconds: number | null; speedup: number | null; reduction: number | null };
type Report = { iou_threshold: number; ground_truth_id: string; rows: ScoreRow[]; time_comparison: TimeComparison[]; ai_runs: { id: string; name: string; model: string | null; gpu: string | null; inference_seconds: number | null; checkpoint: string | null }[]; summary: (Metrics & { source: string; annotator: string; run_id: string | null; assigned: number; expected: number; completed: number; completion_rate: number })[] };
const metric = (value: number | null | undefined) => value == null ? 'N/A' : `${(value*100).toFixed(2)}%`;
const methodName = (source: string) => ({ manual: 'Người tự gán nhãn', ai: 'AI', assisted: 'Người sửa nhãn AI' })[source] ?? source;
function MetricHeaders() {
  return <><th>Tìm đúng / đối tượng chuẩn</th><th>Vẽ thừa hoặc sai</th><th>Bỏ sót</th><th>Tỷ lệ nhãn đúng</th><th>Mức độ đầy đủ</th><th>Điểm F1</th><th>Độ khớp các nhãn đúng</th></>;
}
function MetricCells({ value }: { value: Metrics }) {
  return <><td>{value.tp} / {value.tp + value.fn}</td><td>{value.fp}</td><td>{value.fn}</td><td>{metric(value.precision)}</td><td><strong>{metric(value.recall)}</strong></td><td>{metric(value.f1)}</td><td>{metric(value.mean_iou)}</td></>;
}
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
      {report.rows.some(r => r.time_source?.startsWith('declared_')) && <p className="notice">Có lượt CVAT dùng thời gian nhập tay. Các cặp đó không được tính tăng tốc. CSV giữ nguồn thời gian để đối chiếu.</p>}
      <p className="muted">So sánh thời gian thao tác trên cùng mẫu, cùng người, cả hai bản đã chốt. Chưa bao gồm thời gian AI chạy trên Colab, truyền dữ liệu hoặc thiết lập. Số âm là assisted chậm hơn.</p>
      <table><thead><tr><th>Người / cặp mẫu</th><th>Manual</th><th>Người + AI</th><th>Tiết kiệm</th><th>Tăng tốc</th></tr></thead><tbody>{report.time_comparison.map(r => <tr key={r.annotator}><td>{r.annotator} · {r.paired}/{r.expected}</td><td>{r.manual_seconds.toFixed(1)}s</td><td>{r.assisted_seconds.toFixed(1)}s</td><td>{r.saved_seconds == null ? 'N/A' : `${r.saved_seconds.toFixed(1)}s (${metric(r.reduction)})`}</td><td>{r.speedup == null ? 'N/A' : `${r.speedup.toFixed(2)}×`}</td></tr>)}</tbody></table>
      <h3>Đánh giá tổng cả bộ mẫu</h3>
      <p className="muted">Cộng số đối tượng tìm đúng, vẽ thừa hoặc sai và bỏ sót trên tất cả mẫu đã chấm rồi tính tỷ lệ. Khi đủ mẫu, đây là kết quả của toàn bộ lượt thử nghiệm.</p>
      <p className="notice">Một nhãn được tính là tìm đúng khi cùng lớp và có độ chồng khớp (IoU) ít nhất {metric(report.iou_threshold)} với một đối tượng chuẩn; mỗi đối tượng chỉ được ghép một lần. Nhãn không ghép được tính là vẽ thừa hoặc sai; đối tượng chuẩn không được ghép tính là bỏ sót.</p>
      <table><thead><tr><th>Phương pháp / người thực hiện</th><th>Số mẫu đã chấm / tổng mẫu</th><MetricHeaders /></tr></thead><tbody>{report.summary.map((r, i) => <tr key={i}><td>{methodName(r.source)} · {r.annotator}{r.run_id && <small> · {r.run_id.slice(0,8)}</small>}</td><td>{r.completed}/{r.expected} ({metric(r.completion_rate)}){r.completed < r.expected && <small> · Tạm tính</small>}</td><MetricCells value={r} /></tr>)}</tbody></table>
      <p className="muted"><strong>Mức độ đầy đủ</strong> = số tìm đúng / số đối tượng chuẩn trong các mẫu đã chấm. <strong>Tỷ lệ nhãn đúng</strong> = số tìm đúng / số nhãn đã vẽ. <strong>Điểm F1</strong> tính cả bỏ sót và vẽ thừa hoặc sai. <strong>Độ khớp các nhãn đúng</strong> là IoU trung bình chỉ trên các cặp ghép đúng, không thể hiện mức độ đầy đủ của cả bộ mẫu.</p>
      <p className="muted">Chỉ nhãn người đã chốt được chấm; mẫu chưa hoàn thành không tính là nhãn rỗng. N/A nghĩa là mẫu số bằng 0 hoặc chưa có kết quả. Điểm này theo giao thức M49, chưa có COCO/KITTI AP.</p>
      {report.summary.some(r => r.completed < r.expected) && <p className="notice">Chưa hoàn thành đủ mẫu của thử nghiệm. Điểm hiện tại chỉ tính trên các mẫu đã hoàn thành; các phương pháp có thể đang được chấm trên tập mẫu khác nhau.</p>}
      <h3>Chi tiết từng mẫu và lớp</h3>
      <p className="muted">Các số bên dưới chỉ tính riêng từng mẫu, không phải kết quả cả lượt.</p>
      {report.rows.map((r, i) => <details key={i} className="score-detail"><summary>{r.asset_name} · {methodName(r.source)} · {r.annotator} · {r.completed && r.metrics ? `Tìm đúng ${r.metrics.tp}/${r.metrics.tp + r.metrics.fn} đối tượng · Bỏ sót ${r.metrics.fn} · Vẽ thừa hoặc sai ${r.metrics.fp}` : 'Chưa hoàn thành / thiếu kết quả'}</summary>
        {r.metrics && <><table><thead><tr><th>Lớp</th><MetricHeaders /></tr></thead><tbody>{Object.entries(r.metrics.by_class).map(([c,m]) => <tr key={c}><td>{c}</td><MetricCells value={m} /></tr>)}</tbody></table>
          <table><thead><tr><th>Nhãn dự đoán ↔ nhãn chuẩn</th><th>Lớp</th><th>Độ chồng khớp (IoU)</th><th>Độ tương đồng vùng (Dice)</th></tr></thead><tbody>{r.metrics.pairs.map(p => <tr key={p.prediction_id}><td>{p.prediction_id} ↔ {p.ground_truth_id}</td><td>{p.category}</td><td>{metric(p.iou)}</td><td>{metric(p.dice)}</td></tr>)}</tbody></table></>}
      </details>)}
    </>}
  </section>;
}
