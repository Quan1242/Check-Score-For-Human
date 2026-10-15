import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Annotation, Asset, Project } from '../types';
import CloudEditor from './annotation/CloudEditor';

type Row = { asset_name: string; source: string; annotator: string; label_set_id: string | null; completed: boolean };
type Bundle = { samples: { asset_name: string; objects: Annotation[] }[] };
const methods = [['manual', 'Người tự gán nhãn'], ['ai', 'AI'], ['assisted', 'Người sửa nhãn AI']] as const;
const noop = () => {};

function Preview({ asset, objects, title, color }: { asset: Asset; objects: Annotation[]; title: string; color: string }) {
  if (asset.kind !== 'image') return <CloudEditor asset={asset} objects={objects} category="" selected="" onSelect={noop} onChange={noop} disabled viewOnly annotationColor={color}/>;
  return <svg className="comparison-image" viewBox={`0 0 ${asset.width || 1} ${asset.height || 1}`} role="img" aria-label={title}>
    <image href={asset.url} width={asset.width || 1} height={asset.height || 1}/>
    {objects.map(object => {
      const geometry = object.geometry;
      const points = geometry.kind === 'bbox2d' ? [[geometry.xyxy[0], geometry.xyxy[1]], [geometry.xyxy[2], geometry.xyxy[1]], [geometry.xyxy[2], geometry.xyxy[3]], [geometry.xyxy[0], geometry.xyxy[3]]] : geometry.kind === 'polygon' ? geometry.points : [];
      return <g key={object.id}><title>{object.category} · {object.id}</title><polygon points={points.map(point => point.join(',')).join(' ')} fill={color} fillOpacity={0.12} stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke"/></g>;
    })}
  </svg>;
}

function LabelPreview({ row, labelId, asset, title, color }: { row?: Row; labelId?: string; asset: Asset; title: string; color: string }) {
  const id = labelId ?? (row?.completed ? row.label_set_id : null);
  const [result, setResult] = useState<{ objects: Annotation[] } | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    const controller = new AbortController();
    setResult(null); setError('');
    if (id) api<Bundle>(`/label-sets/${id}`, { signal: controller.signal }).then(bundle => {
      if (controller.signal.aborted) return;
      const sample = bundle.samples.find(item => item.asset_name === asset.name);
      if (!sample) setError('Bộ nhãn không có mẫu này.');
      else setResult({ objects: sample.objects });
    }).catch(e => { if (!controller.signal.aborted) setError(String(e)); });
    return () => controller.abort();
  }, [id, asset.name]);
  return <article className="comparison-card"><div className="comparison-card-heading"><h4><span style={{ background: color }}/>{title}</h4><small>{result ? `${result.objects.length} đối tượng` : ''}</small></div>
    {row && <small className="comparison-author">{row.annotator}</small>}
    {!id ? <p className="muted">Chưa có kết quả đã chốt cho mẫu này.</p> : error ? <p role="alert">{error}</p> : !result ? <p role="status">Đang tải nhãn…</p> : <><Preview asset={asset} objects={result.objects} title={`${title} · ${asset.name}`} color={color}/>{!result.objects.length && <p className="muted">Nhãn rỗng: không có đối tượng.</p>}</>}
  </article>;
}

export default function GroundTruthComparison({ project, groundTruthId, rows }: { project: Project; groundTruthId: string; rows: Row[] }) {
  const names = [...new Set(rows.map(row => row.asset_name))];
  const [selected, setSelected] = useState(names[0] ?? '');
  const [assets, setAssets] = useState<Asset[] | null>(null), [error, setError] = useState('');
  const index = names.indexOf(selected), asset = assets?.find(item => item.name === selected);
  useEffect(() => {
    const controller = new AbortController();
    api<Asset[]>(`/projects/${project.id}/assets`, { signal: controller.signal }).then(value => { if (!controller.signal.aborted) setAssets(value); }).catch(e => { if (!controller.signal.aborted) setError(String(e)); });
    return () => controller.abort();
  }, [project.id]);
  return <section className="ground-truth-comparison" aria-label="Đối chiếu nhãn theo từng mẫu"><h3>Đối chiếu với ground truth</h3>
    <p className="muted">Chỉ xem · Ba phương pháp và nhãn chuẩn của cùng một mẫu. Việc xem đối chiếu không thay đổi nhãn hoặc điểm.</p>
    <div className="comparison-navigation"><button className="secondary" disabled={index <= 0} onClick={() => setSelected(names[index - 1])}>← Trước</button>
      <label>{project.task === 'detection_3d' ? 'Chọn mẫu' : 'Chọn ảnh'}<select value={selected} onChange={e => setSelected(e.target.value)}>{names.map((name, i) => <option key={name} value={name}>{i + 1}. {name}</option>)}</select></label>
      <span>{names.length ? index + 1 : 0}/{names.length}</span><button className="secondary" disabled={index < 0 || index >= names.length - 1} onClick={() => setSelected(names[index + 1])}>Tiếp →</button></div>
    {error ? <p role="alert">{error}</p> : !assets ? <p role="status">Đang tải mẫu…</p> : !asset ? <p className="muted">Không tìm thấy dữ liệu của mẫu này.</p> : <div className="comparison-layout" key={asset.id}>
      <div className="comparison-methods">{methods.map(([source, title]) => {
        const matches = rows.filter(row => row.asset_name === selected && row.source === source);
        return <div key={source}>{matches.length ? matches.map((row, i) => <LabelPreview key={`${row.label_set_id}-${i}`} row={row} asset={asset} title={title} color="#53e0b4"/>) : <LabelPreview asset={asset} title={title} color="#53e0b4"/>}</div>;
      })}</div>
      <div className="comparison-truth"><LabelPreview labelId={groundTruthId} asset={asset} title="Ground truth · Nhãn chuẩn" color="#ffc857"/></div>
    </div>}
  </section>;
}
