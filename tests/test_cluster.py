import numpy as np

from bap.cluster import OUTLIER, cluster_labels
from cases import square


def labels(geoms, epsilon=10, min_samples=3):
    return cluster_labels(geoms, epsilon, min_samples).tolist()


def row(n, step, size=10):
    return [square(i * step, 0, size) for i in range(n)]


def test_empty_input():
    assert len(cluster_labels([], 10, 3)) == 0


def test_gap_equal_to_epsilon_is_a_neighbor():
    # squares 10 wide, 10 apart edge to edge
    assert labels(row(3, step=20), epsilon=10) == [0, 0, 0]


def test_gap_over_epsilon_is_not_a_neighbor():
    assert labels(row(3, step=20), epsilon=9.99) == [OUTLIER] * 3


def test_touching_and_overlapping_are_neighbors():
    geoms = [square(0, 0), square(10, 0), square(15, 0)]  # touch, then overlap
    assert labels(geoms, epsilon=0.001) == [0, 0, 0]


def test_min_samples_counts_the_polygon_itself():
    assert labels(row(2, step=15), min_samples=3) == [OUTLIER] * 2
    assert labels(row(3, step=15), min_samples=3) == [0, 0, 0]


def test_border_joins_core_but_does_not_extend_chain():
    # 0-3 are a tight core group. 4 is near 3 only (border). 5 is near 4 only: outlier.
    xs = [0, 12, 24, 36, 71, 106]
    geoms = [square(x, 0) for x in xs]
    assert labels(geoms, epsilon=30, min_samples=4) == [0, 0, 0, 0, 0, OUTLIER]


def test_chain_forms_one_cluster():
    assert labels(row(10, step=80), epsilon=70) == [0] * 10


def test_two_groups_get_separate_labels_in_first_row_order():
    geoms = row(3, step=12) + [square(1000 + i * 12, 0) for i in range(3)]
    assert labels(geoms, epsilon=5) == [0, 0, 0, 1, 1, 1]


def test_all_outliers():
    geoms = [square(i * 1000, 0) for i in range(5)]
    assert labels(geoms) == [OUTLIER] * 5


def test_returns_int_array():
    assert cluster_labels(row(3, 12), 5, 3).dtype == np.dtype(int)
