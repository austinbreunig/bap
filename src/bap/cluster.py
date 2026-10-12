"""Group polygons by edge-to-edge gap (DBSCAN rules, no scikit-learn).

Works on one key value at a time. Geometries must be in a projected CRS so that
epsilon is in meters.
"""

import numpy as np
from shapely import STRtree

OUTLIER = -1


def _find(parent, i):
    while parent[i] != i:
        parent[i] = parent[parent[i]]
        i = parent[i]
    return i


def cluster_labels(geoms, epsilon, min_samples):
    """Return one integer label per geometry. -1 means outlier.

    Neighbor: gap <= epsilon (touching or overlapping is gap 0).
    Core: at least `min_samples` neighbors, counting itself.
    Cores that are neighbors share a cluster. A non-core neighbor of a core joins
    the cluster of its lowest-index core neighbor, and does not link clusters.
    Labels count up from 0 in order of each cluster's first row.
    """
    n = len(geoms)
    labels = np.full(n, OUTLIER, dtype=int)
    if n == 0:
        return labels

    left, right = STRtree(geoms).query(geoms, predicate="dwithin", distance=epsilon)
    is_core = np.bincount(left, minlength=n) >= min_samples

    parent = list(range(n))
    for a, b in zip(left, right, strict=True):
        if is_core[a] and is_core[b]:
            ra, rb = _find(parent, a), _find(parent, b)
            parent[max(ra, rb)] = min(ra, rb)

    # Each member points at the root of its cluster: itself if core, else its
    # lowest-index core neighbor.
    root = {}
    for a, b in sorted(zip(left, right, strict=True)):
        if is_core[b] and a not in root and not is_core[a]:
            root[a] = _find(parent, b)
    for i in np.flatnonzero(is_core):
        root[i] = _find(parent, i)

    next_label = {}
    for i in range(n):
        if i in root:
            labels[i] = next_label.setdefault(root[i], len(next_label))
    return labels
