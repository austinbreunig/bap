"""Check the mitre limit on sharp corners (the open question in the spec).

For a thin triangle with a sharp tip, close it (grow, shrink) at several mitre limits and
report: area the close adds around the lone triangle, area of the polygon left uncovered,
and whether a square sitting `FAR` m past the tip (farther than 2 x epsilon) gets bridged.

Run by hand: python scripts/check_mitre.py
"""

import math

import shapely
from shapely.geometry import Polygon, box

from bap.bap import DEFAULT_EPSILONS
from bap.boundary import close

EPSILON = float(DEFAULT_EPSILONS[-1])
FAR = 3 * EPSILON  # gap from the tip to the other square
LIMITS = (2.0, 5.0, 100.0)


def triangle(tip_angle_deg, length=500.0):
    """Tip at (0, 0) pointing left; opens to the right."""
    half = length * math.tan(math.radians(tip_angle_deg / 2))
    return Polygon([(0, 0), (length, half), (length, -half)])


def notched_block(notch_angle_deg, depth=300.0):
    """A 400 x 400 block with a sharp V notch cut into its top edge."""
    half = depth * math.tan(math.radians(notch_angle_deg / 2))
    notch = Polygon([(200 - half, 400), (200, 400 - depth), (200 + half, 400)])
    return box(0, 0, 400, 400).difference(notch)


def main():
    print(f"epsilon {EPSILON} m")
    print("Sharp convex tip, with a square 3 x epsilon past it:")
    print("angle  limit  added_m2  uncovered_m2  bridged")
    for angle in (1, 2, 5, 10, 20, 45, 90):
        tri = triangle(angle)
        other = box(-FAR - 20, -10, -FAR, 10)
        for limit in LIMITS:
            alone = close(tri, EPSILON, limit)
            lost = tri.difference(alone).area
            both = close(shapely.union_all([tri, other]), EPSILON, limit)
            bridged = len(shapely.get_parts(both)) == 1
            added = alone.area - tri.area
            print(f"{angle:>5}  {limit:>5}  {added:>8.2f}  {lost:>12.2f}  {bridged}")
    print("Sharp V notch cut into a 400 m block (area the close fills in):")
    print("angle  limit  filled_m2  uncovered_m2")
    for angle in (1, 2, 5, 10, 20, 45, 90):
        block = notched_block(angle)
        for limit in LIMITS:
            closed = close(block, EPSILON, limit)
            print(
                f"{angle:>5}  {limit:>5}  {closed.area - block.area:>9.1f}"
                f"  {block.difference(closed).area:>12.2f}"
            )


if __name__ == "__main__":
    main()
