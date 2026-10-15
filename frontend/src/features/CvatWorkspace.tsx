import { useEffect, useState } from 'react';
import { api, postJSON } from '../api';

type Connection = { configured: boolean; url: string };
type RemoteTask = { ready: boolean; task_id: number; url: string | null; samples: { assignment_id: string; name: string; finalized: boolean }[] };

export default function CvatWorkspace({ assignmentId, onFinalized, onBlocked }: {
  assignmentId: string; onFinalized: () => Promise<void>; onBlocked: (value: boolean) => void;
}) {
  const [connection, setConnection] = useState<Connection>({configured: false, url: 'http://localhost:8080'});
  const [url, setUrl] = useState('http://localhost:8080'), [token, setToken] = useState('');
  const [task, setTask] = useState<RemoteTask | null>(null), [seconds, setSeconds] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false), [status, setStatus] = useState('');
  useEffect(() => {
    let active = true;
    api<Connection>('/cvat/connection').then(value => {
      if (active) { setConnection(value); setUrl(value.url); }
    }).catch(e => { if (active) setStatus(String(e)); });
    return () => { active = false; };
  }, []);
  useEffect(() => { onBlocked(busy); return () => onBlocked(false); }, [busy, onBlocked]);
  async function action(work: () => Promise<void>) {
    setBusy(true); setStatus('');
    try { await work(); } catch (e) { setStatus(String(e)); } finally { setBusy(false); }
  }
  async function prepare() {
    await action(async () => {
      const value = await postJSON<RemoteTask>(`/cvat/assignments/${assignmentId}/open`, {});
      setTask(value);
      setStatus(value.ready ? `Task ${value.samples.length} ảnh đã sẵn sàng. Mở CVAT để gán nhãn.` : 'CVAT đang xử lý ảnh. Chờ một chút rồi bấm Kiểm tra task.');
    });
  }
  return <section className="panel"><h3>Gán nhãn trên CVAT của bạn</h3>
    <p>CVAT cần chạy sẵn trên máy này. Tối đa 10 ảnh chưa chốt cùng lượt được gom vào một task; lượt sửa AI được nạp nhãn AI ban đầu. Task cũ vẫn được giữ nguyên.</p>
    {!connection.configured ? <fieldset disabled={busy}>
      <div className="fields">
        <label>Địa chỉ CVAT<input value={url} onChange={e => setUrl(e.target.value)} placeholder="http://localhost:8080" /></label>
        <label>Personal Access Token<input type="password" autoComplete="off" value={token} onChange={e => setToken(e.target.value)} /></label>
      </div>
      <p className="muted">Trong CVAT: User settings → Security → tạo token có quyền đọc/ghi. Token được lưu ở backend trên máy này.</p>
      <button disabled={!token.trim()} onClick={() => void action(async () => {
        setConnection(await postJSON<Connection>('/cvat/connection', {url, token}));
        setToken(''); setStatus('Đã kiểm tra kết nối CVAT.');
      })}>Kiểm tra và kết nối CVAT</button>
    </fieldset> : <>
      <p>Đã cấu hình: {connection.url}</p>
      <div className="fields">
        <button disabled={busy} onClick={() => void prepare()}>{task && !task.ready ? 'Kiểm tra task' : task?.ready ? 'Kiểm tra lại task' : 'Tạo task CVAT cho tối đa 10 ảnh'}</button>
        {task?.ready && task.url && <a href={task.url} target="_blank" rel="noreferrer">Mở task {task.task_id} trong CVAT</a>}
        <button className="secondary" disabled={busy} onClick={() => void action(async () => {
          setConnection(await postJSON<Connection>('/cvat/disconnect', {})); setTask(null);
        })}>Ngắt kết nối CVAT</button>
      </div>
    </>}
    {task?.ready && <fieldset disabled={busy}>
      <p>Trong CVAT, mở job của task và dùng Rectangle (2D) hoặc Polygon (SEG), chế độ Shape. Bấm <strong>Save</strong> trong CVAT trước khi lấy nhãn về.</p>
      {task.samples.filter(sample => !sample.finalized).map(sample => <label key={sample.assignment_id}>
        {sample.name} — thời gian làm ảnh này (giây)
        <input type="number" min="0.01" step="0.01" value={seconds[sample.assignment_id] ?? ''}
          onChange={e => setSeconds(previous => ({...previous, [sample.assignment_id]: e.target.value}))} />
      </label>)}
      <p className="muted">Thời gian do bạn nhập, gồm cả thời gian đã làm trong M49 nếu có. Không dùng số này để tính tăng tốc từ timer tự động. Nhãn rỗng vẫn được chốt và tính các đối tượng chuẩn là bỏ sót.</p>
      <button disabled={task.samples.filter(s => !s.finalized).some(s => !Number.isFinite(Number(seconds[s.assignment_id])) || Number(seconds[s.assignment_id]) <= 0)} onClick={() => void action(async () => {
        await postJSON(`/cvat/assignments/${assignmentId}/import-batch`, {
          samples: Object.fromEntries(task.samples.filter(s => !s.finalized).map(s => [s.assignment_id, {total_seconds: Number(seconds[s.assignment_id])}]))
        });
        await onFinalized();
      })}>Lấy nhãn đã lưu từ CVAT và chốt tất cả ảnh trong task</button>
    </fieldset>}
    <p role="status">{status}</p>
  </section>;
}
