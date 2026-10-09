import { useEffect, useRef, useState } from 'react';
import type { Annotation, Asset, Vec3 } from '../../types';
import { parsePointCloud } from './pointcloud';

type Props = { asset: Asset; objects: Annotation[]; selected: string; onSelect: (id: string) => void;
  onChange: (objects: Annotation[]) => void; category: string; disabled: boolean };
type Cuboid = Extract<Annotation['geometry'], { kind: 'cuboid3d' }>;
const edges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
export default function CloudEditor({ asset, objects, selected, onSelect, onChange, category, disabled }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [points, setPoints] = useState<Vec3[]>([]), [status, setStatus] = useState('Đang đọc point cloud…');
  const [angle, setAngle] = useState(0.6), [tilt, setTilt] = useState(0.7), [zoom, setZoom] = useState(8);
  const [pan, setPan] = useState<[number, number]>([0, 0]);
  const drag = useRef<{ x: number; y: number; pan: [number, number] } | null>(null);
  useEffect(() => {
    const controller = new AbortController(); setPoints([]); setStatus('Đang đọc point cloud…');
    fetch(asset.url, { signal: controller.signal }).then(r => { if (!r.ok) throw new Error('Không tải được point cloud'); return r.arrayBuffer(); })
      .then(buffer => { const p = parsePointCloud(buffer, asset.name); setPoints(p); setStatus(`${p.length.toLocaleString()} điểm hiển thị (lấy mẫu tối đa 60.000 điểm)`); })
      .catch(e => { if (!controller.signal.aborted) setStatus(String(e)); });
    return () => controller.abort();
  }, [asset.url, asset.name]);
  useEffect(() => {
    const c = canvas.current, ctx = c?.getContext('2d'); if (!c || !ctx) return;
    const w = c.width, h = c.height;
    const project = ([x, y, z]: Vec3): [number, number] => {
      const u = x*Math.cos(angle)-y*Math.sin(angle), v = x*Math.sin(angle)+y*Math.cos(angle);
      return [w/2+pan[0]+u*zoom, h/2+pan[1]-(v*Math.sin(tilt)+z*Math.cos(tilt))*zoom];
    };
    ctx.fillStyle = '#102332'; ctx.fillRect(0, 0, w, h);
    for (const p of points) {
      const [x, y] = project(p); if (x < 0 || y < 0 || x > w || y > h) continue;
      ctx.fillStyle = `hsl(${Math.max(20, Math.min(220, 160-p[2]*18))} 55% 58%)`;
      ctx.fillRect(x, y, 1.6, 1.6);
    }
    const axes: [Vec3, string, string][] = [[[5,0,0], '#ff8b8b', 'X tiến'], [[0,5,0], '#87e4a5', 'Y trái'], [[0,0,5], '#8bbaff', 'Z lên']];
    const origin = project([0,0,0]); ctx.font = '14px sans-serif';
    for (const [p, color, label] of axes) { const q = project(p); ctx.strokeStyle = color; ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(...origin); ctx.lineTo(...q); ctx.stroke(); ctx.fillText(label, q[0], q[1]); }
    for (const obj of objects) {
      if (obj.geometry.kind !== 'cuboid3d') continue;
      const g = obj.geometry, [l, b, height] = g.size_lwh, [x, y, z] = g.center;
      const corners: Vec3[] = [-height/2, height/2].flatMap(dz => ([[-l/2,-b/2],[l/2,-b/2],[l/2,b/2],[-l/2,b/2]]).map(([u,v]): Vec3 => [x+u*Math.cos(g.yaw)-v*Math.sin(g.yaw), y+u*Math.sin(g.yaw)+v*Math.cos(g.yaw), z+dz]));
      ctx.strokeStyle = obj.id === selected ? '#ffc857' : '#53e0b4'; ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = obj.id === selected ? 3 : 1.5;
      for (const [a,b] of edges) { ctx.beginPath(); ctx.moveTo(...project(corners[a])); ctx.lineTo(...project(corners[b])); ctx.stroke(); }
      const center = project(g.center), nose = project([x+l/2*Math.cos(g.yaw), y+l/2*Math.sin(g.yaw), z]);
      ctx.beginPath(); ctx.moveTo(...center); ctx.lineTo(...nose); ctx.stroke(); ctx.fillText(obj.category, center[0]+5, center[1]-7);
    }
  }, [points, objects, selected, angle, tilt, zoom, pan]);
  const current = objects.find(o => o.id === selected), g = current?.geometry.kind === 'cuboid3d' ? current.geometry : null;
  function change(next: Cuboid) { if (current) onChange(objects.map(o => o.id === current.id ? { ...o, geometry: next } : o)); }
  return <div>
    <div className="editor-toolbar">
      <button disabled={disabled} onClick={() => { const id = crypto.randomUUID(); onChange([...objects, { id, category, geometry: { kind: 'cuboid3d', center: [0,0,0], size_lwh: [4,2,1.5], yaw: 0, frame: 'lidar' } }]); onSelect(id); }}>Thêm cuboid</button>
      <button className="secondary" onClick={() => { setAngle(-Math.PI/2); setTilt(Math.PI/2); }}>Trên</button>
      <button className="secondary" onClick={() => { setAngle(Math.PI/2); setTilt(0); }}>Trước</button>
      <button className="secondary" onClick={() => { setAngle(0); setTilt(0); }}>Bên</button>
      <button className="secondary" onClick={() => { setAngle(0.6); setTilt(0.7); setZoom(8); setPan([0,0]); }}>Phối cảnh</button>
    </div>
    <canvas ref={canvas} width={1000} height={600} className="cloud-editor" aria-label="Point cloud và cuboid LiDAR"
      onWheel={e => setZoom(v => Math.max(0.2, Math.min(100, v*(e.deltaY > 0 ? 0.9 : 1.1))))}
      onPointerDown={e => { e.currentTarget.setPointerCapture(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, pan }; }}
      onPointerMove={e => { const d = drag.current; if (d) { const rect = e.currentTarget.getBoundingClientRect(); setPan([d.pan[0]+(e.clientX-d.x)*1000/rect.width, d.pan[1]+(e.clientY-d.y)*600/rect.height]); } }}
      onPointerUp={() => { drag.current = null; }} onPointerCancel={() => { drag.current = null; }}/>
    <p className="muted">{status}. Kéo để di chuyển, cuộn để zoom. Chọn đối tượng ở danh sách để chỉnh cuboid.</p>
    <div className="fields"><label>Góc nhìn<input type="range" min={-3.14} max={3.14} step={0.01} value={angle} onChange={e => setAngle(Number(e.target.value))}/></label><label>Độ nghiêng<input type="range" min={-1.57} max={1.57} step={0.01} value={tilt} onChange={e => setTilt(Number(e.target.value))}/></label></div>
    {g && <fieldset disabled={disabled}><legend>Cuboid được chọn · mét / radian</legend><div className="fields">
      {(['center', 'size_lwh'] as const).flatMap(key => g[key].map((value, i) => <label key={`${key}-${i}`}>{key === 'center' ? ['Tâm X','Tâm Y','Tâm Z'][i] : ['Dài','Rộng','Cao'][i]}<input type="number" step="0.1" min={key === 'size_lwh' ? 0.01 : undefined} value={value} onChange={e => { const n = e.target.valueAsNumber; if (!Number.isFinite(n) || (key === 'size_lwh' && n <= 0)) return; const v = [...g[key]] as Vec3; v[i] = n; change({ ...g, [key]: v }); }}/></label>))}
      <label>Yaw<input type="number" step="0.05" value={g.yaw} onChange={e => { if (Number.isFinite(e.target.valueAsNumber)) change({ ...g, yaw: e.target.valueAsNumber }); }}/></label>
    </div></fieldset>}
  </div>;
}
