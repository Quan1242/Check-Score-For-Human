"""M49 final-label metrics. No COCO/KITTI AP is implied by these scores."""
from math import cos, sin

from PIL import Image, ImageChops, ImageDraw


def area(points):
    return abs(sum(a[0] * b[1] - b[0] * a[1]
                   for a, b in zip(points, points[1:] + points[:1]))) / 2


def convex_intersection(subject, clip):
    """Sutherland-Hodgman; the clipping polygon is counter-clockwise."""
    output = subject
    for a, b in zip(clip, clip[1:] + clip[:1]):
        previous, output = output, []
        if not previous:
            break
        def side(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        s = previous[-1]
        for e in previous:
            ds, de = side(s), side(e)
            if (ds >= 0) != (de >= 0):
                t = ds / (ds - de)
                output.append((s[0] + t * (e[0] - s[0]), s[1] + t * (e[1] - s[1])))
            if de >= 0:
                output.append(e)
            s = e
    return output


def footprint(g):
    x, y, _ = g['center']
    length, width, _ = g['size_lwh']
    c, s = cos(g['yaw']), sin(g['yaw'])
    return [(x + u*c - v*s, y + u*s + v*c) for u, v in
            [(-length/2, -width/2), (length/2, -width/2),
             (length/2, width/2), (-length/2, width/2)]]


def geometry_iou(a, b):
    if a['kind'] == 'bbox2d':
        x1, y1, x2, y2 = a['xyxy']
        u1, v1, u2, v2 = b['xyxy']
        intersection = max(0, min(x2, u2)-max(x1, u1)) * max(0, min(y2, v2)-max(y1, v1))
        union = (x2-x1)*(y2-y1) + (u2-u1)*(v2-v1) - intersection
    elif a['kind'] == 'cuboid3d':
        z1, z2 = a['center'][2], b['center'][2]
        l1, w1, h1 = a['size_lwh']
        l2, w2, h2 = b['size_lwh']
        height = max(0, min(z1+h1/2, z2+h2/2)-max(z1-h1/2, z2-h2/2))
        intersection = area(convex_intersection(footprint(a), footprint(b))) * height
        union = l1*w1*h1 + l2*w2*h2 - intersection
    else:
        raise ValueError('Polygon IoU requires rasterized masks')
    return max(0.0, min(1.0, intersection / union)) if union > 0 else 0.0


def rasterize(g, size):
    # Pixel-center, even/odd scan conversion. Boundary coordinates remain in
    # the original continuous image frame; no resize or bounding-box proxy.
    from math import ceil
    mask = Image.new('1', size)
    draw = ImageDraw.Draw(mask)
    points = g['points']
    edges = list(zip(points, points[1:] + points[:1]))
    start = max(0, ceil(min(p[1] for p in points)-0.5))
    stop = min(size[1], ceil(max(p[1] for p in points)-0.5))
    for row in range(start, stop):
        y = row + 0.5
        xs = sorted(a[0] + (y-a[1])*(b[0]-a[0])/(b[1]-a[1])
                    for a, b in edges if (a[1] <= y < b[1]) or (b[1] <= y < a[1]))
        for left, right in zip(xs[::2], xs[1::2]):
            lo, hi = max(0, ceil(left-0.5)), min(size[0]-1, ceil(right-0.5)-1)
            if lo <= hi:
                draw.line((lo, row, hi, row), fill=1)
    return mask


def optimal_matching(matrix, threshold):
    """Successive shortest augmenting paths: max cardinality, then max IoU."""
    n, m = len(matrix), len(matrix[0]) if matrix else 0
    source, sink = n+m, n+m+1
    graph = [[] for _ in range(n+m+2)]
    def edge(u, v, cost):
        graph[u].append([v, len(graph[v]), 1, cost])
        graph[v].append([u, len(graph[u])-1, 0, -cost])
    for i in range(n):
        edge(source, i, 0)
    for j in range(m):
        edge(n+j, sink, 0)
    refs = []
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            if value >= threshold:
                refs.append((i, j, len(graph[i])))
                edge(i, n+j, -value)
    while True:
        dist, parent = [float('inf')]*len(graph), [None]*len(graph)
        dist[source] = 0
        for _ in range(len(graph)-1):
            changed = False
            for u, edges in enumerate(graph):
                for k, (v, _, capacity, cost) in enumerate(edges):
                    if capacity and dist[u]+cost < dist[v]-1e-12:
                        dist[v], parent[v] = dist[u]+cost, (u, k)
                        changed = True
            if not changed:
                break
        if parent[sink] is None:
            break
        v = sink
        while v != source:
            u, k = parent[v]
            e = graph[u][k]
            e[2] -= 1
            graph[v][e[1]][2] += 1
            v = u
    return [(i, j, matrix[i][j]) for i, j, k in refs if graph[i][k][2] == 0]


def counts(tp, fp, fn, iou_sum=0):
    return dict(tp=tp, fp=fp, fn=fn,
                precision=tp/(tp+fp) if tp+fp else None,
                recall=tp/(tp+fn) if tp+fn else None,
                f1=2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,
                mean_iou=iou_sum/tp if tp else None)


def score_sample(predictions, truth, classes, threshold, size=None):
    if len(predictions) > 300 or len(truth) > 300:
        raise ValueError('Tối đa 300 đối tượng/mẫu cho bộ chấm hiện tại')
    polygons = [o for o in predictions + truth if o['geometry']['kind'] == 'polygon']
    if polygons and (not size or size[0]*size[1] > 25_000_000 or size[0]*size[1]*len(polygons) > 128_000_000):
        raise ValueError('Mask vượt giới hạn bộ nhớ: tối đa 25 triệu pixel/ảnh và 128 triệu pixel cho tổng mask/mẫu')
    masks = {}
    for obj in polygons:
        mask = rasterize(obj['geometry'], size)
        count = sum(mask.histogram()[1:])
        if not count:
            raise ValueError('Polygon tạo mask rỗng ở độ phân giải ảnh gốc')
        masks[id(obj)] = mask, count
    def overlap(p, g):
        if p['geometry']['kind'] != 'polygon':
            return geometry_iou(p['geometry'], g['geometry'])
        if not size or size[0]*size[1] > 25_000_000:
            raise ValueError('Chấm mask cần ảnh gốc, tối đa 25 triệu pixel')
        (a, sa), (b, sb) = masks[id(p)], masks[id(g)]
        intersection = sum(ImageChops.logical_and(a, b).histogram()[1:])
        return intersection/(sa+sb-intersection)
    by_class, pairs = {}, []
    for category in classes:
        p = [o for o in predictions if o['category'] == category]
        g = [o for o in truth if o['category'] == category]
        matched = optimal_matching([[overlap(a, b) for b in g] for a in p], threshold)
        by_class[category] = counts(len(matched), len(p)-len(matched), len(g)-len(matched), sum(q for _, _, q in matched))
        for i, j, q in matched:
            pairs.append(dict(prediction_id=p[i]['id'], ground_truth_id=g[j]['id'], category=category,
                              iou=q, dice=2*q/(1+q) if p[i]['geometry']['kind'] == 'polygon' else None))
    totals = counts(sum(v['tp'] for v in by_class.values()), sum(v['fp'] for v in by_class.values()),
                    sum(v['fn'] for v in by_class.values()), sum(p['iou'] for p in pairs))
    return dict(**totals, by_class=by_class, pairs=pairs)
