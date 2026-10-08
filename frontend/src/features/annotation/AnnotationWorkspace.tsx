import { useState } from 'react';
import { api, postJSON } from '../../api';
import type { Asset, LabelSet, Project } from '../../types';

function example(project: Project) {
  const category = project.classes[0];
  const geometry = project.task === 'detection_2d' ? { kind: 'bbox2d', xyxy: [10, 10, 80, 80] }
    : project.task === 'instance_segmentation' ? { kind: 'polygon', points: [[10, 10], [80, 10], [40, 80]] }
    : { kind: 'cuboid3d', center: [10, 0, 0], size_lwh: [4, 2, 1.5], yaw: 0, frame: 'lidar' };
  return JSON.stringify([{ id: 'object-1', category, geometry }], null, 2);
}

export default function AnnotationWorkspace({ project, assets, labels, onSaved }: { project: Project; assets: Asset[]; labels: LabelSet[]; onSaved: () => Promise<void> }) {
  const eligible = assets.filter(a => project.task === 'detection_3d' ? a.kind === 'pointcloud' : a.kind === 'image');
  const [assetId, setAssetId] = useState('');
  const asset = eligible.find(a => a.id === assetId) ?? eligible[0];
  const [mode, setMode] = useState('manual');
  const [parentId, setParentId] = useState('');
  const [annotator, setAnnotator] = useState('');
  const [objects, setObjects] = useState('[]');
  const [seconds, setSeconds] = useState('');
  const [status, setStatus] = useState('');
  const [busy, setBusy] = useState(false);
  async function loadAI(id: string) {
    setParentId(id); setObjects('[]'); setStatus('');
    if (!id) return;
    setBusy(true);
    try {
      const data = await api<{ samples: { asset_name: string; objects: unknown[] }[] }>(`/label-sets/${id}`);
      const sample = data.samples.find(s => s.asset_name === asset?.name);
      if (!sample) throw new Error('Lần chạy AI không có mẫu này.');
      setObjects(JSON.stringify(sample.objects, null, 2));
    } catch (e) { setStatus(String(e)); setParentId(''); }
    finally { setBusy(false); }
  }
  async function save() {
    if (!asset) return;
    setBusy(true); setStatus('');
    try {
      await postJSON(`/projects/${project.id}/annotations/${mode}`, {
        schema_version: '1.0', task: project.task, name: `${mode} · ${asset.name}`,
        annotator, parent_id: mode === 'assisted' ? parentId : null,
        samples: [{ asset_name: asset.name, objects: JSON.parse(objects), active_seconds: seconds === '' ? null : Number(seconds) }],
      });
      setStatus('Đã lưu một phiên bản nhãn mới.'); await onSaved();
    } catch (e) { setStatus(String(e)); }
    finally { setBusy(false); }
  }
  return <section className="panel">
    <h2>Không gian gán nhãn</h2>
    <p className="notice">Khung phát triển: hiện sửa nhãn bằng JSON. Công cụ vẽ khung, polygon/brush và trình chỉnh hộp 3D chưa được triển khai. Ground truth không hiển thị ở đây.</p>
    {!asset ? <p>Hãy upload {project.task === 'detection_3d' ? 'point cloud' : 'ảnh'} trước.</p> : <>
      <div className="fields">
        <label>Mẫu<select disabled={busy} value={asset.id} onChange={e => {setAssetId(e.target.value); setObjects('[]'); setParentId(''); setSeconds('');}}>{eligible.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
        <label>Chế độ<select disabled={busy} value={mode} onChange={e => {setMode(e.target.value); setObjects('[]'); setParentId(''); setSeconds('');}}><option value="manual">Người gán nhãn</option><option value="assisted">Người sửa AI</option></select></label>
        <label>Người thực hiện<input value={annotator} onChange={e => setAnnotator(e.target.value)} placeholder="Tên hoặc mã người tham gia" /></label>
      </div>
      {mode === 'assisted' && <label>Lần chạy AI<select disabled={busy} value={parentId} onChange={e => void loadAI(e.target.value)}><option value="">Chọn để nạp bản sao nhãn AI</option>{labels.filter(l => l.source === 'ai').map(l => <option value={l.id} key={l.id}>{l.name}</option>)}</select></label>}
      <div className="workspace">
        <div className="preview">{asset.kind === 'image' ? <img src={asset.url} alt={asset.name} /> : <p>Point cloud: {asset.name}<br/>Vị trí tích hợp trình xem 3D.</p>}</div>
        <div><label>Danh sách đối tượng — JSON<textarea rows={17} value={objects} onChange={e => setObjects(e.target.value)} spellCheck={false}/></label>
          <button className="secondary" onClick={() => setObjects(example(project))}>Điền ví dụ cấu trúc</button>
          <p className="muted">Ví dụ chỉ minh họa schema; chỉnh tọa độ theo dữ liệu thật trước khi lưu.</p>
        </div>
      </div>
      <div className="fields"><label>Thời gian làm (giây, nhập thủ công)<input type="number" min="0" value={seconds} onChange={e => setSeconds(e.target.value)}/></label>
      <button disabled={busy || !annotator.trim() || (mode === 'assisted' && !parentId)} onClick={() => void save()}>Lưu phiên bản nhãn</button></div>
      <p role="status">{status}</p>
    </>}
  </section>;
}
