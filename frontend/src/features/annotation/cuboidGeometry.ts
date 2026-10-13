import type { Annotation, Point, Vec3 } from '../../types';

export type Cuboid = Extract<Annotation['geometry'], { kind: 'cuboid3d' }>;
export type Plane = 'top' | 'front' | 'side';
export type Handle = 'move' | 'length' | 'width' | 'height' | 'yaw';
export const cuboidEdges = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];

export function corners(g: Cuboid): Vec3[] {
  const [l, w, h] = g.size_lwh, [x, y, z] = g.center;
  return [-h/2, h/2].flatMap(dz => ([[-l/2,-w/2],[l/2,-w/2],[l/2,w/2],[-l/2,w/2]])
    .map(([u,v]): Vec3 => [x+u*Math.cos(g.yaw)-v*Math.sin(g.yaw), y+u*Math.sin(g.yaw)+v*Math.cos(g.yaw), z+dz]));
}

export function projectPoint([x,y,z]: Vec3, angle: number, tilt: number, zoom: number, pan: Point): Point {
  const u = x*Math.cos(angle)-y*Math.sin(angle), v = x*Math.sin(angle)+y*Math.cos(angle);
  return [500+pan[0]+u*zoom, 300+pan[1]-(v*Math.sin(tilt)+z*Math.cos(tilt))*zoom];
}

export function planeDelta([dx,dy]: Point, plane: Plane, zoom: number): Vec3 {
  if (plane === 'top') return [dy/zoom, dx/zoom, 0];
  if (plane === 'front') return [0, -dx/zoom, -dy/zoom];
  return [dx/zoom, 0, -dy/zoom];
}

export function editCuboid(g: Cuboid, handle: Handle, start: Point, end: Point, plane: Plane,
  zoom: number, screenCenter: Point): Cuboid {
  const delta = planeDelta([end[0]-start[0], end[1]-start[1]], plane, zoom);
  if (handle === 'move') return { ...g, center: g.center.map((v,i) => v+delta[i]) as Vec3 };
  if (handle === 'yaw') {
    if (plane !== 'top') return g;
    const a = planeDelta([start[0]-screenCenter[0],start[1]-screenCenter[1]], plane, zoom);
    const b = planeDelta([end[0]-screenCenter[0],end[1]-screenCenter[1]], plane, zoom);
    if (Math.hypot(b[0],b[1])*zoom < 3) return g;
    const yaw = g.yaw + Math.atan2(b[1],b[0])-Math.atan2(a[1],a[0]);
    return { ...g, yaw: Math.atan2(Math.sin(yaw),Math.cos(yaw)) };
  }
  if ((handle === 'height' && plane === 'top') || (handle !== 'height' && plane !== 'top')) return g;
  const index = handle === 'length' ? 0 : handle === 'width' ? 1 : 2;
  const change = index === 0 ? delta[0]*Math.cos(g.yaw)+delta[1]*Math.sin(g.yaw)
    : index === 1 ? -delta[0]*Math.sin(g.yaw)+delta[1]*Math.cos(g.yaw) : delta[2];
  const size = [...g.size_lwh] as Vec3;
  size[index] = Math.max(0.05, size[index]+2*change);
  return { ...g, size_lwh: size };
}

export function handles(g: Cuboid, plane: Plane, zoom: number): { kind: Handle; point: Vec3; label: string }[] {
  const [x,y,z] = g.center, [l,w,h] = g.size_lwh, c = Math.cos(g.yaw), s = Math.sin(g.yaw);
  const result: { kind: Handle; point: Vec3; label: string }[] = [{ kind: 'move', point: g.center, label: 'Tâm' }];
  if (plane === 'top') result.push(
    { kind: 'length', point: [x+l/2*c,y+l/2*s,z], label: 'Dài' },
    { kind: 'width', point: [x-w/2*s,y+w/2*c,z], label: 'Rộng' },
    { kind: 'yaw', point: [x+(l/2+28/zoom)*c,y+(l/2+28/zoom)*s,z], label: 'Xoay' });
  else result.push({ kind: 'height', point: [x,y,z+h/2], label: 'Cao' });
  return result;
}

export function segmentDistance(p: Point, a: Point, b: Point): number {
  const dx=b[0]-a[0], dy=b[1]-a[1], len=dx*dx+dy*dy;
  const t=len ? Math.max(0,Math.min(1,((p[0]-a[0])*dx+(p[1]-a[1])*dy)/len)) : 0;
  return Math.hypot(p[0]-a[0]-t*dx,p[1]-a[1]-t*dy);
}
