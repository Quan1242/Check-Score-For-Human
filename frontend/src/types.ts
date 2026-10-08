export type Task = 'detection_2d' | 'instance_segmentation' | 'detection_3d';
export type Project = { id: string; name: string; task: Task; classes: string[] };
export type Asset = { id: string; name: string; kind: string; url: string; width: number | null; height: number | null };
export type LabelSet = { id: string; source: string; name: string; parent_id: string | null };
export const taskNames: Record<Task, string> = { detection_2d: 'Bounding box 2D', instance_segmentation: 'Instance segmentation', detection_3d: 'Bounding box 3D' };
