import { useEffect, useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import type { Annotation, Asset, Vec3 } from '../../types';
import { parsePointCloud } from './pointcloud';
import { corners, cuboidEdges as edges, editCuboid, handles, projectPoint, segmentDistance } from './cuboidGeometry';
import type { Cuboid, Handle, Plane } from './cuboidGeometry';

type Props = { asset: Asset; objects: Annotation[]; selected: string; onSelect: (id: string) => void;
  onChange: (objects: Annotation[]) => void; category: string; disabled: boolean; viewOnly?: boolean; annotationColor?: string };
export default function CloudEditor({ asset, objects, selected, onSelect, onChange, category, disabled, viewOnly = false, annotationColor = '#53e0b4' }: Props) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const [points, setPoints] = useState<Vec3[]>([]), [status, setStatus] = useState('Đang đọc point cloud…');
  const [angle, setAngle] = useState(0.6), [tilt, setTilt] = useState(0.7), [zoom, setZoom] = useState(8);
  const [pan, setPan] = useState<[number, number]>([0, 0]);
  const [plane, setPlane] = useState<Plane | null>(null);
  const [tool, setTool] = useState<'pan' | 'edit'>('edit');
  const [draft, setDraft] = useState<Annotation[] | null>(null);
  const draftRef = useRef<Annotation[] | null>(null);
  const drag = useRef<{ start: [number,number]; pan: [number,number]; original: Annotation[];
    id?: string; geometry?: Cuboid; handle?: Handle } | null>(null);
  const shown = draft ?? objects;
  const project = (p: Vec3) => projectPoint(p, angle, tilt, zoom, pan);
  function cancel() { drag.current = null; draftRef.current = null; setDraft(null); }
  useEffect(() => { if (disabled) cancel(); }, [disabled]);
  useEffect(() => { cancel(); }, [objects]); // Undo/delete during a gesture must not restore stale objects.
  function view(next: Plane | null) {
    cancel(); setPlane(next);
    if (next === 'top') { setAngle(-Math.PI/2); setTilt(Math.PI/2); }
    else if (next === 'front') { setAngle(Math.PI/2); setTilt(0); }
    else if (next === 'side') { setAngle(0); setTilt(0); }
    else { setAngle(0.6); setTilt(0.7); }
  }
  function pointer(e: ReactPointerEvent<HTMLCanvasElement>): [number,number] {
    const rect = e.currentTarget.getBoundingClientRect();
    return [(e.clientX-rect.left)*1000/rect.width,(e.clientY-rect.top)*600/rect.height];
  }
  function start(e: ReactPointerEvent<HTMLCanvasElement>) {
    if (e.button !== 0 || drag.current) return;
    const p=pointer(e), tolerance=10*1000/e.currentTarget.getBoundingClientRect().width;
    const base = { start:p, pan, original:objects };
    const active=objects.find(o => o.id===selected);
    if (!disabled && tool==='edit' && plane && active?.geometry.kind==='cuboid3d') {
      const handle=handles(active.geometry,plane,zoom).find(h => Math.hypot(project(h.point)[0]-p[0],project(h.point)[1]-p[1]) < tolerance);
      if (handle) drag.current={ ...base, id:active.id, geometry:active.geometry, handle:handle.kind };
    }
    if (!drag.current && tool==='edit') {
      const hit=[...objects].reverse().find(o => {
        if(o.geometry.kind!=='cuboid3d') return false;
        const vertices=corners(o.geometry).map(project), center=project(o.geometry.center);
        return Math.hypot(center[0]-p[0],center[1]-p[1])<tolerance || edges.some(([a,b]) => segmentDistance(p,vertices[a],vertices[b])<tolerance);
      });
      if(hit) {
        onSelect(hit.id);
        if(!disabled && plane && hit.geometry.kind==='cuboid3d') drag.current={ ...base, id:hit.id, geometry:hit.geometry, handle:'move' };
        else return;
      }
    }
    if (!drag.current) drag.current=base;
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function move(e: ReactPointerEvent<HTMLCanvasElement>) {
    const d=drag.current; if(!d) return;
    const p=pointer(e);
    if(!d.id) { setPan([d.pan[0]+p[0]-d.start[0],d.pan[1]+p[1]-d.start[1]]); return; }
    if(disabled || !plane || !d.geometry || !d.handle) { cancel(); return; }
    const next=editCuboid(d.geometry,d.handle,d.start,p,plane,zoom,project(d.geometry.center));
    const values=d.original.map(o => o.id===d.id ? { ...o, geometry:next } : o);
    draftRef.current=values; setDraft(values);
  }
  function finish(e: ReactPointerEvent<HTMLCanvasElement>) {
    if(drag.current && !disabled && draftRef.current) onChange(draftRef.current);
    cancel(); if(e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  }
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
    ctx.fillStyle = '#102332'; ctx.fillRect(0, 0, w, h);
    for (const p of points) {
      const [x, y] = project(p); if (x < 0 || y < 0 || x > w || y > h) continue;
      ctx.fillStyle = `hsl(${Math.max(20, Math.min(220, 160-p[2]*18))} 55% 58%)`;
      ctx.fillRect(x, y, 1.6, 1.6);
    }
    const axes: [Vec3, string, string][] = [[[5,0,0], '#ff8b8b', 'X tiến'], [[0,5,0], '#87e4a5', 'Y trái'], [[0,0,5], '#8bbaff', 'Z lên']];
    const origin = project([0,0,0]); ctx.font = '14px sans-serif';
    for (const [p, color, label] of axes) { const q = project(p); ctx.strokeStyle = color; ctx.fillStyle = color; ctx.beginPath(); ctx.moveTo(...origin); ctx.lineTo(...q); ctx.stroke(); ctx.fillText(label, q[0], q[1]); }
    for (const obj of shown) {
      if (obj.geometry.kind !== 'cuboid3d') continue;
      const g = obj.geometry, [l] = g.size_lwh, [x, y, z] = g.center;
      const vertices = corners(g);
      ctx.strokeStyle = obj.id === selected ? '#ffc857' : annotationColor; ctx.fillStyle = ctx.strokeStyle; ctx.lineWidth = obj.id === selected ? 3 : 1.5;
      for (const [a,b] of edges) { ctx.beginPath(); ctx.moveTo(...project(vertices[a])); ctx.lineTo(...project(vertices[b])); ctx.stroke(); }
      const center = project(g.center), nose = project([x+l/2*Math.cos(g.yaw), y+l/2*Math.sin(g.yaw), z]);
      ctx.beginPath(); ctx.moveTo(...center); ctx.lineTo(...nose); ctx.stroke(); ctx.fillText(obj.category, center[0]+5, center[1]-7);
      if(obj.id===selected && plane && tool==='edit' && !disabled) {
        for(const h of handles(g,plane,zoom)) {
          const p=project(h.point); ctx.fillStyle='#ffc857'; ctx.beginPath(); ctx.arc(p[0],p[1],6,0,2*Math.PI); ctx.fill();
          ctx.fillText(h.label,p[0]+9,p[1]+16);
        }
      }
    }
  }, [points, shown, selected, angle, tilt, zoom, pan, plane, tool, disabled, annotationColor]);
  const current = objects.find(o => o.id === selected), g = current?.geometry.kind === 'cuboid3d' ? current.geometry : null;
  function change(next: Cuboid) { if (current) onChange(objects.map(o => o.id === current.id ? { ...o, geometry: next } : o)); }
  return <div>
    <div className="editor-toolbar">
      {!viewOnly && <button disabled={disabled} onClick={() => { const id = crypto.randomUUID(); onChange([...objects, { id, category, geometry: { kind: 'cuboid3d', center: [0,0,0], size_lwh: [4,2,1.5], yaw: 0, frame: 'lidar' } }]); onSelect(id); }}>Thêm cuboid</button>}
      <button className="secondary" onClick={() => view('top')}>Trên</button>
      <button className="secondary" onClick={() => view('front')}>Trước</button>
      <button className="secondary" onClick={() => view('side')}>Bên</button>
      <button className="secondary" onClick={() => { view(null); setZoom(8); setPan([0,0]); }}>Phối cảnh</button>
      {!viewOnly && <button className={tool==='edit' ? '' : 'secondary'} onClick={() => { cancel(); setTool('edit'); }}>Chọn / chỉnh hộp</button>}
      <button className={tool==='pan' ? '' : 'secondary'} onClick={() => { cancel(); setTool('pan'); }}>Di chuyển khung nhìn</button>
    </div>
    <canvas ref={canvas} width={1000} height={600} className="cloud-editor" aria-label="Point cloud và cuboid LiDAR"
      onWheel={e => { if (!drag.current) setZoom(v => Math.max(0.2, Math.min(100, v*(e.deltaY > 0 ? 0.9 : 1.1)))); }}
      onPointerDown={start} onPointerMove={move} onPointerUp={finish} onPointerCancel={cancel} onLostPointerCapture={cancel}/>
    <p className="muted">{status}. {viewOnly ? 'Chỉ xem. Cuộn để zoom; kéo nền để di chuyển khung nhìn.' : 'Cuộn để zoom; kéo nền để di chuyển khung nhìn. Chọn cạnh hộp hoặc chọn trong danh sách. Ở góc Trên: kéo Tâm, Dài, Rộng, Xoay. Ở góc Trước/Bên: kéo Tâm hoặc Cao. Kích thước thay đổi quanh tâm; bắt đầu timer để chỉnh. Mỗi lần thả chuột là một bước Undo.'}</p>
    <div className="fields"><label>Góc nhìn<input type="range" min={-Math.PI} max={Math.PI} step={0.01} value={angle} onChange={e => { cancel(); setPlane(null); setAngle(Number(e.target.value)); }}/></label><label>Độ nghiêng<input type="range" min={-Math.PI/2} max={Math.PI/2} step={0.01} value={tilt} onChange={e => { cancel(); setPlane(null); setTilt(Number(e.target.value)); }}/></label></div>
    {g && <fieldset disabled={disabled}><legend>Cuboid được chọn · mét / radian</legend><div className="fields">
      {(['center', 'size_lwh'] as const).flatMap(key => g[key].map((value, i) => <label key={`${key}-${i}`}>{key === 'center' ? ['Tâm X','Tâm Y','Tâm Z'][i] : ['Dài','Rộng','Cao'][i]}<input type="number" step="0.1" min={key === 'size_lwh' ? 0.01 : undefined} value={value} onChange={e => { const n = e.target.valueAsNumber; if (!Number.isFinite(n) || (key === 'size_lwh' && n <= 0)) return; const v = [...g[key]] as Vec3; v[i] = n; change({ ...g, [key]: v }); }}/></label>))}
      <label>Yaw<input type="number" step="0.05" value={g.yaw} onChange={e => { if (Number.isFinite(e.target.valueAsNumber)) change({ ...g, yaw: e.target.valueAsNumber }); }}/></label>
    </div></fieldset>}
  </div>;
}
