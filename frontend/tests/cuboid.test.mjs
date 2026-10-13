import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import ts from 'typescript';

const source = await readFile(new URL('../src/features/annotation/cuboidGeometry.ts', import.meta.url), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { projectPoint, planeDelta, editCuboid, handles, corners } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);
const box = { kind: 'cuboid3d', center: [1,2,3], size_lwh: [4,2,2], yaw: 0, frame: 'lidar' };
const near = (a,b) => assert.ok(Math.abs(a-b)<1e-9, `${a} != ${b}`);

test('orthographic drag is the inverse of screen projection at any zoom/pan', () => {
  for (const [plane, angle, tilt] of [['top',-Math.PI/2,Math.PI/2],['front',Math.PI/2,0],['side',0,0]]) {
    for (const zoom of [0.2,8,100]) {
      const original=projectPoint(box.center,angle,tilt,zoom,[20,30]);
      const delta=planeDelta([24,-37],plane,zoom);
      const moved=projectPoint(box.center.map((v,i)=>v+delta[i]),angle,tilt,zoom,[20,30]);
      near(moved[0]-original[0],24); near(moved[1]-original[1],-37);
    }
  }
});
test('move preserves hidden axis and original geometry', () => {
  const moved=editCuboid(box,'move',[0,0],[16,-8],'top',8,[0,0]);
  assert.deepEqual(moved.center,[0,4,3]); assert.deepEqual(box.center,[1,2,3]);
  assert.deepEqual(moved.size_lwh,box.size_lwh);
});
test('rotated resize follows local length/width axes, preserves center, clamps positive size', () => {
  const rotated={...box,yaw:Math.PI/2};
  const length=editCuboid(rotated,'length',[0,0],[8,0],'top',8,[0,0]);
  near(length.size_lwh[0],6); assert.deepEqual(length.center,box.center);
  const width=editCuboid(rotated,'width',[0,0],[0,-8],'top',8,[0,0]);
  near(width.size_lwh[1],4);
  const shrunk=editCuboid(box,'length',[0,0],[0,-800],'top',8,[0,0]);
  assert.equal(shrunk.size_lwh[0],0.05);
});
test('yaw rotates by a quarter turn and normalizes wraparound', () => {
  const result=editCuboid(box,'yaw',[0,32],[32,0],'top',8,[0,0]);
  near(result.yaw,Math.PI/2); assert.deepEqual(result.center,box.center);
  assert.equal(editCuboid(box,'yaw',[0,32],[32,0],'side',8,[0,0]),box);
});
test('height edit works in side/front views, top view offers yaw and footprint sizes', () => {
  for(const plane of ['side','front']) {
    const result=editCuboid(box,'height',[0,0],[0,-8],plane,8,[0,0]);
    assert.deepEqual(result.size_lwh,[4,2,4]);
    assert.deepEqual(handles(box,plane,8).map(h=>h.kind),['move','height']);
  }
  assert.deepEqual(handles(box,'top',8).map(h=>h.kind),['move','length','width','yaw']);
  assert.equal(corners(box).length,8);
});
