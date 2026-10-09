import { useRef, useState } from 'react';
import type { PointerEvent as ReactPointerEvent } from 'react';
import type { Annotation, Asset, Point } from '../../types';

type Props = { asset: Asset; objects: Annotation[]; category: string; polygon: boolean;
  selected: string; onSelect: (id: string) => void; onChange: (objects: Annotation[]) => void; disabled: boolean };
type Gesture = { start: Point; original: Annotation[]; id?: string; vertex?: number; pan?: boolean; box?: boolean; view: number[] };
const clamp = (n: number, max: number) => Math.max(0, Math.min(max, n));

export default function ImageEditor({ asset, objects, category, polygon, selected, onSelect, onChange, disabled }: Props) {
  const width = asset.width || 1, height = asset.height || 1;
  const svg = useRef<SVGSVGElement>(null);
  const gesture = useRef<Gesture | null>(null);
  const [view, setView] = useState([0, 0, width, height]);
  const [tool, setTool] = useState<'select' | 'draw' | 'pan'>('select');
  const [draft, setDraft] = useState<Annotation[] | null>(null);
  const draftRef = useRef<Annotation[] | null>(null);
  const [vertices, setVertices] = useState<Point[]>([]);
  function preview(value: Annotation[] | null) { draftRef.current = value; setDraft(value); }
  function point(e: { clientX: number; clientY: number }): Point {
    const matrix = svg.current?.getScreenCTM();
    if (!matrix) return [0, 0];
    const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(matrix.inverse());
    return [p.x, p.y];
  }
  const bounded = (p: Point): Point => [clamp(p[0], width), clamp(p[1], height)];
  function start(e: ReactPointerEvent<SVGSVGElement>) {
    if (e.button !== 0 || disabled) return;
    const p = point(e), target = e.target as SVGElement;
    if (tool === 'draw' && polygon) { setVertices(v => [...v, bounded(p)]); return; }
    const id = target.dataset.object;
    if (tool === 'select' && !id) { onSelect(''); return; }
    const vertex = target.dataset.vertex === undefined ? undefined : Number(target.dataset.vertex);
    gesture.current = { start: p, original: objects, id, vertex, pan: tool === 'pan', box: tool === 'draw', view: [...view] };
    if (id) onSelect(id);
    svg.current?.setPointerCapture(e.pointerId);
  }
  function move(e: ReactPointerEvent<SVGSVGElement>) {
    const g = gesture.current;
    if (!g) return;
    const p = point(e), dx = p[0]-g.start[0], dy = p[1]-g.start[1];
    if (g.pan) { setView(v => [v[0]-dx, v[1]-dy, v[2], v[3]]); return; }
    if (g.box) {
      const a = bounded(g.start), b = bounded(p);
      preview([...g.original, { id: '__drawing__', category, geometry: { kind: 'bbox2d', xyxy: [Math.min(a[0], b[0]), Math.min(a[1], b[1]), Math.max(a[0], b[0]), Math.max(a[1], b[1])] } }]);
      return;
    }
    preview(g.original.map<Annotation>(obj => {
      if (obj.id !== g.id) return obj;
      const geometry = obj.geometry;
      if (geometry.kind === 'bbox2d') {
        const [x1, y1, x2, y2] = geometry.xyxy;
        if (g.vertex !== undefined) {
          const opposite: Point = [[x2, y2], [x1, y2], [x1, y1], [x2, y1]][g.vertex] as Point;
          const q = bounded(p);
          if (Math.abs(q[0]-opposite[0]) < 0.5 || Math.abs(q[1]-opposite[1]) < 0.5) return obj;
          return { ...obj, geometry: { ...geometry, xyxy: [Math.min(q[0], opposite[0]), Math.min(q[1], opposite[1]), Math.max(q[0], opposite[0]), Math.max(q[1], opposite[1])] } };
        }
        const tx = Math.max(-x1, Math.min(width-x2, dx)), ty = Math.max(-y1, Math.min(height-y2, dy));
        return { ...obj, geometry: { ...geometry, xyxy: [x1+tx, y1+ty, x2+tx, y2+ty] } };
      }
      if (geometry.kind === 'polygon') {
        if (g.vertex !== undefined) return { ...obj, geometry: { ...geometry, points: geometry.points.map((v, i) => i === g.vertex ? bounded(p) : v) } };
        const xs = geometry.points.map(v => v[0]), ys = geometry.points.map(v => v[1]);
        const tx = Math.max(-Math.min(...xs), Math.min(width-Math.max(...xs), dx));
        const ty = Math.max(-Math.min(...ys), Math.min(height-Math.max(...ys), dy));
        return { ...obj, geometry: { ...geometry, points: geometry.points.map(([x, y]): Point => [x+tx, y+ty]) } };
      }
      return obj;
    }));
  }
  function finish() {
    if (gesture.current && draftRef.current) {
      const next = draftRef.current.filter(o => o.id !== '__drawing__' || o.geometry.kind !== 'bbox2d' || (o.geometry.xyxy[2]-o.geometry.xyxy[0] >= 0.5 && o.geometry.xyxy[3]-o.geometry.xyxy[1] >= 0.5))
        .map(o => o.id === '__drawing__' ? { ...o, id: crypto.randomUUID() } : o);
      onChange(next);
    }
    gesture.current = null; preview(null);
  }
  function finishPolygon() {
    if (disabled || vertices.length < 3) return;
    const id = crypto.randomUUID();
    onChange([...objects, { id, category, geometry: { kind: 'polygon', points: vertices } }]);
    onSelect(id); setVertices([]); setTool('select');
  }
  const radius = view[2]/140;
  return <div>
    <div className="editor-toolbar">
      {(['select', 'draw', 'pan'] as const).map((t, i) => <button key={t} disabled={disabled} className={tool === t ? '' : 'secondary'} onClick={() => { setTool(t); setVertices([]); }}>{['Chọn / kéo', polygon ? 'Vẽ polygon' : 'Vẽ box', 'Di chuyển ảnh'][i]}</button>)}
      <button className="secondary" onClick={() => setView([0, 0, width, height])}>Vừa ảnh</button>
      {vertices.length > 0 && <><button disabled={disabled || vertices.length < 3} onClick={finishPolygon}>Đóng polygon ({vertices.length})</button><button disabled={disabled} onClick={() => setVertices(v => v.slice(0, -1))}>Bỏ điểm cuối</button><button disabled={disabled} onClick={() => setVertices([])}>Hủy</button></>}
    </div>
    <svg ref={svg} className="image-editor" viewBox={view.join(' ')} role="img" aria-label="Vùng chỉnh nhãn ảnh"
      onPointerDown={start} onPointerMove={move} onPointerUp={finish} onPointerCancel={() => { gesture.current = null; preview(null); }}
      onWheel={e => { const p = point(e), factor = e.deltaY > 0 ? 1.15 : 1/1.15; setView(v => { const w = Math.max(width/30, Math.min(width*4, v[2]*factor)), f = w/v[2]; return [p[0]-(p[0]-v[0])*f, p[1]-(p[1]-v[1])*f, w, v[3]*f]; }); }}>
      <image href={asset.url} width={width} height={height}/>
      {(draft || objects).map(o => {
        const g = o.geometry, active = o.id === selected, color = active ? '#ffc857' : '#53e0b4';
        const corners: Point[] = g.kind === 'bbox2d' ? [[g.xyxy[0], g.xyxy[1]], [g.xyxy[2], g.xyxy[1]], [g.xyxy[2], g.xyxy[3]], [g.xyxy[0], g.xyxy[3]]] : g.kind === 'polygon' ? g.points : [];
        return <g key={o.id}>
          <polygon data-object={o.id} points={corners.map(p => p.join(',')).join(' ')} fill={color} fillOpacity={0.15} stroke={color} strokeWidth={2} vectorEffect="non-scaling-stroke"/>
          {corners[0] && <text x={corners[0][0]} y={corners[0][1]-radius} fontSize={radius*2.5} fill={color} pointerEvents="none">{o.category}</text>}
          {active && tool === 'select' && corners.map((p, i) => <circle key={i} data-object={o.id} data-vertex={i} cx={p[0]} cy={p[1]} r={radius} fill={color} stroke="#142535"/>)}
        </g>;
      })}
      {vertices.length > 0 && <polyline points={vertices.map(p => p.join(',')).join(' ')} fill="none" stroke="#ffc857" strokeWidth={2} vectorEffect="non-scaling-stroke" pointerEvents="none"/>}
    </svg>
    <p className="muted">Cuộn chuột để zoom. Kéo các nút để sửa góc box hoặc đỉnh polygon. Tọa độ lưu theo ảnh gốc.</p>
  </div>;
}
