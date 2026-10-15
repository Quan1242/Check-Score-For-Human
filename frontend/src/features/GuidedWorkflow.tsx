import { useCallback, useEffect, useRef, useState } from 'react';
import { api, postJSON, upload } from '../api';
import type { Project, Task } from '../types';
import { taskNames } from '../types';
import AnnotationWorkspace from './annotation/AnnotationWorkspace';
import { ExperimentResults } from './Experiments';
import '../guided.css';
import { waitForGoogleConnection } from './googleConsent';
import CvatWorkspace from './CvatWorkspace';

type Run = { id: string; dataset: string; project: Project; experiment_id: string; annotator: string; phase: 'manual'|'ai'|'assisted'|'results'; manual_completed: number; assisted_completed: number; total: number; assignment_id: string|null; job_id: string|null; job_status: string|null; error: string|null; colab_url: string|null; transport: 'google'|'desktop'|null };
type Catalog = { task: Task; available: boolean; reason: string };
const emptySave = async () => {};

export default function GuidedWorkflow({ onBlocked }: { onBlocked?: (value: boolean) => void }) {
  const [catalog, setCatalog] = useState<Catalog[]>([]), [runs,setRuns] = useState<Run[]>([]), [run,setRun] = useState<Run|null>(null);
  const [task,setTask] = useState<Task|null>(null), [annotator,setAnnotator] = useState('');
  const [busy,setBusy] = useState(false), [editing,setEditing] = useState(false), [status,setStatus] = useState('');
  const [preset,setPreset] = useState('auto'), [checkpoint,setCheckpoint] = useState(''), [confidence,setConfidence] = useState(0.25);
  const [checkpointName,setCheckpointName] = useState('');
  const [editorMode, setEditorMode] = useState<'m49'|'cvat'|null>(null);
  const [google,setGoogle] = useState<{ configured: boolean; connected: boolean }>({configured:false,connected:false});
  const [authUrl,setAuthUrl] = useState('');
  const consent = useRef<AbortController|null>(null);
  useEffect(() => () => consent.current?.abort(), []);
  const colabWindow = useRef<{window:Window; runId:string}|null>(null);
  useEffect(() => {
    if (run?.colab_url) {
      setStatus('Notebook đã được tải lên Drive. Mở Colab và bấm Run all để chạy AI.');
      if (colabWindow.current?.runId === run.id) {
        try {
          // OAuth returns to the backend origin; only the cross-origin location setter is safe.
          if (!colabWindow.current.window.closed) colabWindow.current.window.location.href = run.colab_url;
        } catch { /* The notebook link below remains available if navigation is blocked. */ }
        colabWindow.current = null;
      }
    }
  }, [run?.colab_url, run?.id]);
  useEffect(() => {
    if (run?.phase !== 'ai') return;
    let alive = true, timer: number|undefined;
    async function check() {
      try {
        const value = await api<{configured:boolean;connected:boolean}>('/colab/google/status');
        if (alive) { setGoogle(value); if (value.connected) setAuthUrl(''); }
      } catch { /* Keep the current state; actions surface connection errors. */ }
      finally { if (alive) timer = window.setTimeout(() => void check(), 3000); }
    }
    void check();
    return () => { alive = false; window.clearTimeout(timer); };
  }, [run?.phase]);
  useEffect(() => { onBlocked?.(busy || editing); return () => onBlocked?.(false); },[busy,editing,onBlocked]);
  useEffect(() => {
    Promise.all([api<Catalog[]>('/guided/catalog'),api<Run[]>('/guided'),api<{configured:boolean;connected:boolean}>('/colab/google/status')])
      .then(([c,r,d]) => { setCatalog(c);setRuns(r);setGoogle(d); }).catch(e => setStatus(String(e)));
  },[]);
  const runId = run?.id;
  const next = useCallback(async () => {
    if (runId) setRun(await postJSON<Run>(`/guided/${runId}/next`,{}));
  },[runId]);
  useEffect(() => {
    if (run?.phase !== 'ai' || !run.job_id) return;
    let alive=true, timer:number|undefined;
    async function poll() {
      try { const updated=await postJSON<Run>(`/guided/${runId}/next`,{}); if(alive)setRun(updated); }
      catch(e) { if(alive)setStatus(String(e)); }
      finally { if(alive)timer=window.setTimeout(() => void poll(),5000); }
    }
    void poll(); return () => { alive=false;window.clearTimeout(timer); };
  },[runId,run?.phase,run?.job_id]);
  async function action(work:()=>Promise<void>) {
    setBusy(true);setStatus('');try { await work(); }catch(e){setStatus(String(e));}finally{setBusy(false);}
  }
  async function start() {
    await action(async () => {
      const value=await postJSON<Run>('/guided',{task,annotator});
      setRun(value);setRuns(rows=>[value,...rows]);
    });
  }
  async function connectGoogle(sendNotebook = false) {
    if (!run || consent.current) return;
    const selectedRun = run.id;
    const model = {preset, checkpoint:preset==='custom'?checkpoint:null, confidence};
    const popup = window.open('about:blank', '_blank');
    if (popup) {
      popup.opener = null;
      popup.document.body.textContent = 'Đang chuẩn bị kết nối Google…';
    }
    const controller = new AbortController();
    consent.current = controller;
    await action(async () => {
      try {
        if (!google.connected) {
          const result = await postJSON<{url:string}>(`/colab/google/connect${sendNotebook ? `?run_id=${encodeURIComponent(selectedRun)}` : ''}`, {});
          setAuthUrl(result.url);
          if (popup) popup.location.replace(result.url);
          setStatus('Đang chờ bạn đồng ý cấp quyền Google. Web sẽ tự tiếp tục sau khi được cấp quyền.');
          await waitForGoogleConnection(() => api('/colab/google/status'), controller.signal);
          setGoogle({configured:true, connected:true});
          setAuthUrl('');
        }
        controller.signal.throwIfAborted();
        if (sendNotebook) {
          setStatus('Đã được cấp quyền. Đang tạo notebook và tự tải dữ liệu lên Drive…');
          colabWindow.current = popup ? {window:popup, runId:selectedRun} : null;
          setRun(await postJSON<Run>(`/guided/${selectedRun}/ai/google`, model));
        } else {
          popup?.close();
          setStatus('Đã kết nối Google. Bạn có thể tiếp tục lượt AI.');
        }
      } catch (error) {
        popup?.close();
        colabWindow.current = null;
        if (!controller.signal.aborted) throw error;
        setStatus('Đã hủy chờ cấp quyền; chưa gửi notebook.');
      } finally {
        consent.current = null;
        setAuthUrl('');
      }
    });
  }
  useEffect(() => { setPreset('auto'); setCheckpoint(''); setCheckpointName(''); setEditorMode(null); }, [run?.id]);
  const is3d = run?.project.task === 'detection_3d';
  const isSegmentation = run?.project.task === 'instance_segmentation';
  const step = !run ? 0 : ({manual:1,ai:2,assisted:3,results:4}[run.phase]);
  return <>
    <header className="studio-header"><div className="eyebrow"><span className="eyebrow-dot"/> MỘT LƯỢT · CÙNG 10 MẪU</div><h1>Người. AI.<br/><span>Cùng tạo nên khác biệt.</span></h1>
      <p className="muted">Gán nhãn từ đầu, chạy AI độc lập, rồi rà soát nhãn AI.<br/>So sánh cả ba phương pháp trên cùng bộ nhãn chuẩn.</p><div className="header-art" aria-hidden="true"><div className="scan-frame"><span/><span/><span/></div><b>COMPARE & CREATE</b></div></header>
    <ol className="flow-steps">{['Tác vụ','Người gán nhãn','AI gán nhãn','Người sửa AI','Kết quả'].map((label,i)=><li key={label} className={i===step?'current':i<step?'done':''} aria-current={i===step?'step':undefined}>{i+1}. {label}</li>)}</ol>
    <p role="status">{status}</p>
    {!run && <>
      {runs.length>0 && <section className="panel"><h2>Tiếp tục lượt đã lưu</h2><div className="fields">{runs.map(r=><button disabled={busy} className="secondary" key={r.id} onClick={()=>void action(async()=>setRun(await postJSON<Run>(`/guided/${r.id}/next`,{})))}>{r.dataset.toUpperCase()} · {r.annotator} · {r.id.slice(0,8)}</button>)}</div></section>}
      <section className="panel task-panel"><div className="section-heading"><div><span className="section-kicker">BẮT ĐẦU KHÁM PHÁ</span><h2>Chọn không gian gán nhãn</h2></div><span className="section-badge">01 / 05</span></div><div className="task-options">{catalog.map((t,i)=><article key={t.task} className={`task-card task-${i}${task===t.task?' selected':''}${!t.available?' unavailable':''}`}><div className="task-art" aria-hidden="true"><svg viewBox="0 0 100 64" fill="none">{i===0?<><rect x="12" y="12" width="48" height="35" rx="5"/><rect x="40" y="26" width="46" height="28" rx="5"/><path d="M9 7h12M9 7v12M91 57H79M91 57V45"/></>:i===1?<><path d="M14 39 27 12 60 8 85 27 73 54 38 58Z"/><path d="m27 12 11 46 22-50 13 46-59-15 71-12"/><circle cx="27" cy="12" r="3"/><circle cx="73" cy="54" r="3"/></>:<><path d="m50 5 32 17v27L50 62 18 46V20Z"/><path d="m18 20 32 17 32-15M50 37v25M50 5v26"/><path d="m26 16 31 17M65 13 33 29"/></>}</svg><span>0{i+1}</span></div><button disabled={busy||!t.available} aria-pressed={task===t.task} className={task===t.task?'':'secondary'} onClick={()=>setTask(t.task)}>{taskNames[t.task]}<span aria-hidden="true">{task===t.task?'✓':'↗'}</span></button><p className="muted">{t.reason}</p></article>)}</div>
        <label>Người thực hiện<input disabled={busy} value={annotator} onChange={e=>setAnnotator(e.target.value)} placeholder="Tên dùng cho cả hai lượt Manual/Assisted"/></label>
        <p className="muted">Tự lấy ngẫu nhiên 10 mẫu không trùng theo tác vụ, lớp car (ảnh hoặc point cloud LiDAR). Giữ nguyên 10 mẫu cho cả ba kiểu; tải lại trang không bốc mẫu lại. Timer tự đo trong editor.</p>
        <button disabled={busy||!task||!annotator.trim()} onClick={()=>void start()}>Lấy ngẫu nhiên 10 mẫu và bắt đầu</button></section>
    </>}
    {run && <section className="panel flow-progress"><strong>{taskNames[run.project.task as Task]} · {run.annotator}</strong>
      <span>Manual {run.manual_completed}/10 · AI {run.job_status==='imported'?'10/10':'chưa xong'} · Assisted {run.assisted_completed}/10</span>
      <button className="secondary" disabled={busy||editing} onClick={()=>{setRun(null);setTask(null);void api<Run[]>('/guided').then(setRuns).catch(e=>setStatus(String(e)));}}>Về danh sách lượt</button></section>}
    {is3d && <p className="notice">3D dùng dữ liệu KITTI và PointPillars, cần GPU Colab. Chấm xe có tâm hộp trong góc nhìn camera, khoảng phía trước 69,12 m và ngang ±39,68 m. Bộ mẫu này dùng thử quy trình, không phải đánh giá KITTI AP độc lập.</p>}
    {run && (run.phase==='manual'||run.phase==='assisted') && <>
      <h2>{run.phase==='manual'?'Người tự gán nhãn':'Người kiểm tra và sửa nhãn AI'} · mẫu {(run.phase==='manual'?run.manual_completed:run.assisted_completed)+1}/10</h2>
      <p className="muted">{run.phase==='manual'?'Gán nhãn từ dữ liệu gốc. Nhãn AI được mở sau khi hoàn thành đủ 10 mẫu.':'Kiểm tra nhãn AI trên cùng mẫu. Sửa nếu cần rồi chốt, kể cả khi giữ nguyên kết quả AI.'}</p>
      {!is3d && <div className="fields"><button disabled={busy||editing} className={editorMode==='m49'?'':'secondary'} onClick={()=>setEditorMode('m49')}>Dùng trình gán nhãn M49</button><button disabled={busy||editing} className={editorMode==='cvat'?'':'secondary'} onClick={()=>setEditorMode('cvat')}>Kết nối CVAT trên máy</button></div>}
      {run.assignment_id ? (!is3d && editorMode==='cvat' ? <CvatWorkspace key={run.assignment_id} assignmentId={run.assignment_id} onFinalized={next} onBlocked={setEditing}/> : (is3d || editorMode==='m49') ? <AnnotationWorkspace key={run.assignment_id} project={run.project} assets={[]} labels={[]} fixedAssignmentId={run.assignment_id} onSaved={emptySave} onBlocked={setEditing} onFinalized={next}/> : <p>Chọn công cụ gán nhãn để bắt đầu mẫu này.</p>) : <button onClick={()=>void action(next)}>Mở mẫu tiếp theo</button>}
    </>}
    {run?.phase==='ai' && <section className="panel"><h2>3 · AI gán nhãn độc lập</h2>
      {(!run.job_id || run.transport === 'google') && <div>
        <p>{google.connected ? 'Đã kết nối Google. Notebook và dữ liệu sẽ được lưu vào Drive của tài khoản đã kết nối.' : 'Đăng nhập Google và đồng ý cấp quyền. Web sẽ tự chuyển notebook và dữ liệu lên Drive của bạn, rồi mở Colab.'}</p>
        {!google.configured && <p role="alert">Kết nối Google chưa được quản trị viên cấu hình. Liên hệ người cung cấp ứng dụng để bật tính năng này.</p>}
        {!google.connected && (run.job_id || preset==='custom') && <button disabled={busy||!google.configured} onClick={()=>void connectGoogle()}>Kết nối Google để tiếp tục</button>}
        {authUrl && <p><button className="secondary" onClick={()=>consent.current?.abort()}>Hủy chờ cấp quyền</button> <a href={authUrl} target="_blank" rel="noreferrer">Mở cửa sổ cấp quyền nếu trình duyệt chặn popup</a></p>}
        {google.connected && <button className="secondary" disabled={busy} onClick={()=>void action(async()=>setGoogle(await postJSON('/colab/google/disconnect',{})))}>Ngắt kết nối trên máy này</button>}
      </div>}
      {!run.job_id ? <fieldset disabled={busy}><p>Ứng dụng sẽ gửi đúng {run.total} {is3d ? 'point cloud và calibration' : 'ảnh gốc'} cùng cấu hình model. Nhãn Manual và ground truth không được gửi lên Colab.</p>
        <div className="fields"><label>Model<select value={preset} onChange={e=>setPreset(e.target.value)}>{is3d ? <option value="auto">PointPillars · KITTI car · GPU</option> : <><option value="auto">Tự chọn · {isSegmentation ? 'YOLO11s-seg' : 'YOLO11s'}</option><option value="yolo11n">{isSegmentation ? 'YOLO11n-seg' : 'YOLO11n'} · nhỏ</option><option value="yolo11s">{isSegmentation ? 'YOLO11s-seg' : 'YOLO11s'}</option><option value="yolo11m">{isSegmentation ? 'YOLO11m-seg' : 'YOLO11m'} · lớn hơn</option><option value="custom">Tải checkpoint .pt của tôi</option></>}</select></label>
        <label>Ngưỡng confidence<input type="number" min={0.01} max={1} step={0.05} value={confidence} onChange={e=>setConfidence(e.target.valueAsNumber)}/></label></div>
        {!is3d && preset==='custom' && <label>Checkpoint Ultralytics phù hợp tác vụ (tối đa 512 MiB)<input disabled={!google.connected} type="file" accept=".pt" onChange={e=>{const file=e.target.files?.[0];e.target.value='';if(file)void action(async()=>{
          setCheckpoint('');setCheckpointName('');
          if(!file.name.toLowerCase().endsWith('.pt') || file.size===0 || file.size>512*1024*1024) throw new Error('Chọn checkpoint .pt không rỗng, tối đa 512 MiB.');
          setStatus('Đang tải model lên backend trên máy…');
          const result=await upload<{checkpoint:string}>('/colab/google/checkpoints',file);setCheckpoint(result.checkpoint);setCheckpointName(file.name);
          setStatus('Đã nhận model trên máy. Bấm Đồng ý tải notebook để gửi model cùng dữ liệu lên Drive. Colab sẽ kiểm tra model khi chạy.');
        });}}/>{checkpointName}</label>}
        <ol className="colab-instructions"><li>Bấm nút bên dưới, đăng nhập Google và đồng ý cấp quyền nếu được hỏi.</li><li>Web tự tải notebook và {run.total} mẫu, rồi mở Colab.</li><li>Trong Colab, bấm <strong>Runtime → Run all</strong> và xác nhận tài khoản Google khi được hỏi.</li><li>Chạy xong, kết quả tự về web để tiếp tục sửa nhãn AI.</li></ol>
        <p className="muted">Không cần tải tệp thủ công. Giữ web và backend đang chạy trong lúc chờ. Với checkpoint riêng, chỉ chọn tệp bạn tin cậy.</p>
        <button disabled={!google.configured||(preset==='custom'&&!checkpoint)||!Number.isFinite(confidence)||confidence<0.01||confidence>1} onClick={()=>void connectGoogle(true)}>{google.connected ? 'Tải dữ liệu và mở Colab' : 'Đăng nhập Google và mở Colab'}</button>
      </fieldset> : run.transport === 'google' ? <>
        <p>{run.colab_url ? 'Notebook đã sẵn sàng. Mở Colab, bấm Runtime → Run all và cấp quyền bằng cùng tài khoản Google đã kết nối.' : 'Đang tải ảnh và chuẩn bị notebook trên Drive…'}</p>
        {run.colab_url && <p><a href={run.colab_url} target="_blank" rel="noreferrer">Mở notebook của lượt này trên Colab</a></p>}
        <p>Giữ backend M49 đang chạy. Khi Colab gửi đủ kết quả, ứng dụng tự mở lượt Người sửa AI.</p>
      </> : <>
        <p>Lượt cũ dùng thư mục Drive đồng bộ. <a href={`/api/colab/notebooks/${run.project.task}`} download>Tải notebook</a> và dùng mã lượt <code>{run.job_id}</code>. Các lượt mới dùng kết nối Google tự động.</p>
      </>}
      {run.error && <p role="alert">{run.error} Ứng dụng tự thử lại khi kết nối sẵn sàng.</p>}
    </section>}
    {run?.phase==='results' && <><p className="notice">Đã hoàn thành 10 mẫu Manual và 10 mẫu Assisted. Kết quả dưới đây so sánh Người, AI và Người + AI.</p><ExperimentResults key={run.experiment_id} project={run.project} initialExperimentId={run.experiment_id} autoScore/></>}
  </>;
}
