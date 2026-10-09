import type { Vec3 } from '../../types';

export function parsePointCloud(buffer: ArrayBuffer, name: string): Vec3[] {
  const points: Vec3[] = [];
  const add = (x: number, y: number, z: number) => {
    if ([x, y, z].every(Number.isFinite)) points.push([x, y, z]);
  };
  if (name.toLowerCase().endsWith('.bin')) {
    if (buffer.byteLength % 16) throw new Error('BIN cần float32 x,y,z,intensity (16 byte/điểm).');
    const view = new DataView(buffer), stride = Math.max(1, Math.ceil(buffer.byteLength/16/60000));
    for (let i = 0; i < buffer.byteLength; i += 16*stride) add(view.getFloat32(i, true), view.getFloat32(i+4, true), view.getFloat32(i+8, true));
    return points;
  }
  const bytes = new Uint8Array(buffer);
  const headerText = new TextDecoder().decode(bytes.subarray(0, Math.min(bytes.length, 65536)));
  const match = /^DATA\s+(\w+)\s*\r?$/m.exec(headerText);
  if (!match) throw new Error('PCD thiếu header DATA.');
  const end = headerText.indexOf('\n', match.index);
  if (end < 0) throw new Error('Header PCD chưa kết thúc.');
  const header = headerText.slice(0, end), offset = new TextEncoder().encode(headerText.slice(0, end+1)).length;
  const fields: Record<string, string[]> = {};
  for (const line of header.split(/\r?\n/)) {
    const [key, ...values] = line.trim().split(/\s+/); fields[key] = values;
  }
  const names = fields.FIELDS || fields.FIELD || [];
  const xyz = ['x', 'y', 'z'].map(key => names.indexOf(key));
  if (xyz.some(i => i < 0)) throw new Error('PCD cần fields x, y, z.');
  const sizes = (fields.SIZE || []).map(Number), types = fields.TYPE || [];
  const counts = fields.COUNT ? fields.COUNT.map(Number) : names.map(() => 1);
  if (sizes.length !== names.length || types.length !== names.length || counts.length !== names.length || counts.some(n => !Number.isInteger(n) || n < 1)) throw new Error('Header SIZE/TYPE/COUNT của PCD không hợp lệ.');
  const columnOffsets = names.map((_, i) => counts.slice(0, i).reduce((a, b) => a+b, 0));
  if (match[1] === 'ascii') {
    const lines = new TextDecoder().decode(bytes.subarray(offset)).trim().split(/\r?\n/);
    const stride = Math.max(1, Math.ceil(lines.length/60000));
    for (let i = 0; i < lines.length; i += stride) {
      const values = lines[i].trim().split(/\s+/).map(Number);
      add(values[columnOffsets[xyz[0]]], values[columnOffsets[xyz[1]]], values[columnOffsets[xyz[2]]]);
    }
  } else if (match[1] === 'binary') {
    const offsets = names.map((_, i) => sizes.slice(0, i).reduce((sum, size, k) => sum+size*counts[k], 0));
    const length = sizes.reduce((sum, size, i) => sum+size*counts[i], 0);
    if (!length || (buffer.byteLength-offset) % length) throw new Error('Kích thước PCD binary không hợp lệ.');
    const view = new DataView(buffer), total = (buffer.byteLength-offset)/length;
    const read = (base: number, i: number) => {
      const at = base+offsets[i], size = sizes[i], type = types[i];
      if (type === 'F' && size === 4) return view.getFloat32(at, true);
      if (type === 'F' && size === 8) return view.getFloat64(at, true);
      if (type === 'I' && size === 4) return view.getInt32(at, true);
      if (type === 'U' && size === 4) return view.getUint32(at, true);
      if (type === 'I' && size === 2) return view.getInt16(at, true);
      if (type === 'U' && size === 2) return view.getUint16(at, true);
      if (type === 'I' && size === 1) return view.getInt8(at);
      if (type === 'U' && size === 1) return view.getUint8(at);
      throw new Error('Kiểu số của tọa độ PCD chưa được hỗ trợ.');
    };
    for (let i = 0; i < total; i += Math.max(1, Math.ceil(total/60000))) add(...xyz.map(k => read(offset+i*length, k)) as Vec3);
  } else throw new Error('PCD binary_compressed chưa hỗ trợ; hãy xuất ASCII hoặc binary.');
  return points;
}
