# BAP

Clusters nearby polygons and wraps each cluster in a tight orthogonal boundary.

## Language

**Cluster**:
A group of polygons connected by chains of neighbors within epsilon, sharing the same key value. Has one cluster ID.
_Avoid_: component

**Neighbor**:
Two polygons whose shortest edge-to-edge gap is at most epsilon. Touching or overlapping polygons have a gap of 0, so they are always neighbors.

**Outlier**:
A polygon that joins no cluster. It stays in the output with a null cluster ID.
_Avoid_: noise, singleton

**Core polygon**:
A polygon with at least `min_samples` polygons (counting itself) within epsilon. Default `min_samples` is 3.

**Border polygon**:
A non-core polygon within epsilon of a core polygon. It joins that core's cluster.

**Boundary**:
The square-cornered dissolved wrapper built around a cluster. Not a rounded buffer.

**Part**:
One piece of a boundary that splits into disjoint polygons. Each part gets a part ID under its cluster, so a boundary is never a MultiPolygon.
_Avoid_: subset, component
