export type Task = 'detection_2d' | 'instance_segmentation' | 'detection_3d';
export type Project = { id: string; name: string; task: Task; classes: string[] };
export type Asset = { id: string; name: string; kind: string; url: string; width: number | null; height: number | null };
export type LabelSet = { id: string; source: string; name: string; parent_id: string | null };
export const taskNames: Record<Task, string> = { detection_2d: 'Bounding box 2D', instance_segmentation: 'Instance segmentation', detection_3d: 'Bounding box 3D' };
export type Point = [number, number];
export type Vec3 = [number, number, number];
export type Geometry = { kind: 'bbox2d'; xyxy: [number, number, number, number] }
  | { kind: 'polygon'; points: Point[] }
  | { kind: 'cuboid3d'; center: Vec3; size_lwh: Vec3; yaw: number; frame: 'lidar' };
export type Annotation = { id: string; category: string; geometry: Geometry; confidence?: number | null };
export type Experiment = { id: string; name: string; ground_truth_id: string; asset_ids: string[]; iou_threshold: number };
export type Assignment = { id: string; experiment_id: string; asset_id: string; annotator: string;
  mode: 'manual' | 'assisted'; parent_id: string | null; draft_id: string | null; final_id: string | null;
  revision: number; active_seconds: number; running: boolean };
