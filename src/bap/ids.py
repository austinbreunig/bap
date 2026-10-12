"""Final cluster and part IDs. Run once, after every pass has finished."""


def assign_ids(parts):
    """Return one (cluster_id, part_id) per part, in the same order as `parts`.

    Each part is a dict with `group` (any hashable; parts sharing it are one cluster),
    `key` (the key value) and `source_ids` (its polygons' IDs).

    Clusters are numbered C0001, C0002, ... in key order, then by lowest source ID. The
    zero-pad width grows once there are more than 9999 clusters. Parts of a cluster are
    numbered 1..n by lowest source ID. The result does not depend on input order.
    """
    lowest = [min(p["source_ids"]) for p in parts]

    cluster_first = {}  # group -> (key, lowest source ID over all its parts)
    for p, low in zip(parts, lowest, strict=True):
        sort_key = (p["key"], low)
        if p["group"] not in cluster_first or low < cluster_first[p["group"]][1]:
            cluster_first[p["group"]] = sort_key
    ordered = sorted(cluster_first, key=cluster_first.get)
    width = max(4, len(str(len(ordered))))
    cluster_ids = {g: f"C{n:0{width}d}" for n, g in enumerate(ordered, start=1)}

    part_numbers = {}
    by_group = {}
    for i, p in enumerate(parts):
        by_group.setdefault(p["group"], []).append(i)
    for indices in by_group.values():
        for n, i in enumerate(sorted(indices, key=lowest.__getitem__), start=1):
            part_numbers[i] = n

    return [(cluster_ids[p["group"]], part_numbers[i]) for i, p in enumerate(parts)]
