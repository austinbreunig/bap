# Prototype results: mitre close (issue #3)

Method: `buffer(+eps, mitre, mitre_limit=100)` then `buffer(-eps, mitre, mitre_limit=100)`.
Ran with shapely on Python 3.12 (real runs, not docs). Script: `orthogonal_boundary_PROTOTYPE.py`.
Ratio = boundary area / union-of-originals area. eps = 0.1 everywhere.

| Case | Result | Ratio |
|---|---|---|
| 2x2 grid, shared edges | ONE Polygon, 4 vertices, equals the union and the 2x2 square | 1.000 |
| Two squares, gap 0.15 (< 2 eps) | merge into ONE Polygon; bridge is a plain rectangle (gap x 1.0) | 1.075 |
| Two squares, gap 0.20 (= 2 eps) | still merges (edge case: exactly 2 eps counts) | 1.100 |
| Two squares, gap 0.30 (> 2 eps) | stays MultiPolygon, identical to input | 1.000 |
| Staggered pair, gap 0.15 | merges; bridge only spans the overlap of the facing sides, and the stagger step stays (8 vertices) | 1.038 |
| U-shape, notch 0.15 | notch filled, result is a plain rectangle | 1.055 |
| U-shape, notch 1.0 | notch kept, unchanged | 1.000 |
| Plain L (concave corner) | unchanged, corner stays sharp | 1.000 |
| Square with hole 0.15 | hole filled | 1.003 |
| Square with hole 1.0 | hole kept, unchanged | 1.000 |
| Pair rotated 45 deg, gap 0.15 | merges; corners stay square, edges stay at 45 deg (rotating back gives the same rectangle) | 1.075 |

## What this tells us
- The close only changes things closer than `2 * eps`. Features wider than that are untouched.
  So eps is directly "the biggest gap/notch/hole to fill".
- It is not axis-snapping. Edges keep the input's angles. Axis-aligned inputs stay axis-aligned;
  rotated inputs stay rotated. Corners are NOT clipped (with a big mitre_limit).
- It does not square off diagonal or irregular inputs. If the inputs are not rectilinear, the output is not.
- Bridges are tight: they only fill the overlap of facing sides, not a full bounding rectangle.
- Concave notches wider than 2 eps are kept (tight wrap), narrower ones are filled.
- Ratio stays near 1.0 in all cases here (max 1.10). A gate on ratio would be a "did we add too much area" check.
- Tiny floating-point leftovers can appear (a duplicated collinear vertex in the rotated case);
  a `simplify(0)` or similar cleanup may be wanted.
- Not tested: non-rectangular inputs (diamonds, circles), huge mitre spikes at sharp angles, performance.
