from bap.ids import assign_ids


def part(group, key, source_ids):
    return {"group": group, "key": key, "source_ids": source_ids}


def test_clusters_are_numbered_by_key_then_lowest_source_id():
    parts = [
        part("g1", "b", [0, 1]),  # key b, lowest id 0
        part("g2", "a", [5, 6]),  # key a sorts first
        part("g3", "a", [2, 3]),  # key a, lower id than g2
    ]

    assert assign_ids(parts) == [("C0003", 1), ("C0002", 1), ("C0001", 1)]


def test_parts_are_numbered_by_lowest_source_id_with_no_gaps():
    parts = [
        part("g", "a", [9, 10]),
        part("g", "a", [1, 2]),
        part("g", "a", [4, 5]),
    ]

    assert assign_ids(parts) == [("C0001", 3), ("C0001", 1), ("C0001", 2)]


def test_cluster_order_uses_lowest_id_across_all_its_parts():
    parts = [
        part("x", "a", [7, 8]),
        part("y", "a", [3, 4]),
        part("x", "a", [0, 1]),  # x has the lowest id overall, so x is first
    ]

    assert assign_ids(parts) == [("C0001", 2), ("C0002", 1), ("C0001", 1)]


def test_one_counter_across_keys_and_string_ids():
    parts = [part(1, "a", ["p2"]), part(2, "b", ["p1"])]

    assert assign_ids(parts) == [("C0001", 1), ("C0002", 1)]


def test_width_grows_past_four_digits():
    parts = [part(i, "a", [i]) for i in range(10_000)]

    ids = [cid for cid, _ in assign_ids(parts)]

    assert ids[0] == "C00001"
    assert ids[-1] == "C10000"
    assert len(set(ids)) == 10_000


def test_empty_input():
    assert assign_ids([]) == []
