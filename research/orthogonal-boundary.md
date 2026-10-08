# Prior art: tight rectilinear boundaries around nearby polygons

Issue: austinbreunig/bap#2 (part of #1). Facts only. Each claim cites the page that owns it.
"Not stated" means the primary source does not say. I did not run any code
(no shapely in this environment), so every behavior below is from docs, not tests.

## Summary table

| Method | Square corners? | Concave notches | Holes | Orientation | Scale |
|---|---|---|---|---|---|
| Shapely buffer(+d, mitre) then buffer(-d, mitre) | Mitre joins make sharp corners; limited by `mitre_limit` | Not stated | Not stated | Follows input edges; no axis snapping | Not stated |
| Shapely `concave_hull` | No. Output edges are between input vertices | Controlled by `ratio` | `allow_holes` | None | Delaunay-based |
| Shapely `oriented_envelope` | Yes, but one rectangle only | None (convex) | None | Rotates to min area | Convex hull based |
| Shapely `envelope` | Yes, one axis-aligned box | None | None | Axis-aligned | Cheap |
| Orthogonal (rectilinear) convex hull | Yes, by definition | Fills notches only in x/y lines | Not a hole concept | Axis-dependent | O(n log n) |
| Raster/grid (rasterize + polygonize) | Yes, pixel-edge staircase | Set by cell size + closing | Raster holes become rings | Axis-aligned grid | Memory grows with cells |
| ArcGIS Aggregate Polygons (orthogonal) | Yes, option | Merges within distance | Min hole size | Not stated | Partitions for big data |
| ArcGIS Regularize Building Footprint | Yes (Right Angles) | Not a merge tool | Not stated | Not stated | GPU only for Any Angles |
| QGIS Orthogonalize | Pushes angles toward 90 | Not a merge tool | Not stated | Not stated | Iterative |

## 1. Shapely / GEOS

### Buffer out, then buffer in (a "closing")
- `buffer` has `join_style` of round, mitre or bevel. Mitre "results in a single vertex
  that is beveled depending on the mitre_limit parameter" (default 5.0). `mitre_limit`
  "crops of 'mitre'-style joins if the point is displaced from the buffered vertex by
  more than this limit." Source: https://shapely.readthedocs.io/en/stable/reference/shapely.buffer.html
- `cap_style` 'flat' or 'square' both give rectangular line ends; 'flat' ends at the
  original vertex, 'square' adds the buffer width. Same page. (Caps matter only for lines.)
- "A positive distance has an effect of dilation; a negative distance, erosion."
  Source: https://shapely.readthedocs.io/en/stable/manual.html
- Shapely does not document buffer-out/buffer-in as a named "closing" op. That use is
  the combination of the two documented behaviors above. Behavior on notches, holes
  and runtime is not stated in the docs.
- Not stated: whether the result is axis-aligned. Mitre keeps the direction of the
  input edges, so rotated inputs would give rotated edges. This is an inference
  from how mitre joins are described, not a documented guarantee.

### concave_hull
- `shapely.concave_hull(geometry, ratio=0.0, allow_holes=False)`. `ratio` in [0, 1];
  "Higher numbers will include fewer vertices in the hull." Needs GEOS >= 3.11.
  Source: https://shapely.readthedocs.io/en/stable/reference/shapely.concave_hull.html
- GEOS: hull is built by "removing border triangles of the Delaunay Triangulation of
  the points as long as their 'size' is larger than the target criterion." Criteria:
  max edge length ratio (preferred, "scale-free and local"), max area ratio, or alpha.
  Result is a single connected polygon unless degenerate. Holes optional.
  Source: https://libgeos.org/doxygen/classgeos_1_1algorithm_1_1hull_1_1ConcaveHull.html
- PostGIS wraps the same idea; for polygon inputs it encloses vertices and areas.
  Source: https://postgis.net/docs/ST_ConcaveHull.html
- Edges join input vertices at whatever angle. Nothing in the docs gives square
  corners.

### oriented_envelope / minimum_rotated_rectangle
- "The oriented envelope encloses an input geometry, such that the resulting rectangle
  has minimum area." Not tied to the axes. Degenerate convex hull (line/point) is
  returned as is. `minimum_rotated_rectangle` is the same function.
  Sources: https://shapely.readthedocs.io/en/stable/reference/shapely.oriented_envelope.html ,
  https://shapely.readthedocs.io/en/stable/reference/shapely.minimum_rotated_rectangle.html
- It is a single rectangle: it cannot follow concave notches or leave holes.

## 2. Orthogonal (rectilinear) convex hull
- A set is orthogonally convex if its intersection with every axis-parallel line is
  empty, a point, or one segment. Classical hull = smallest orthogonally convex
  superset; it "might be disconnected." Connected version = smallest connected
  orthogonally convex superset, "not unique" for most point sets.
  Source: https://en.wikipedia.org/wiki/Orthogonal_convex_hull (secondary; it cites
  Ottmann, Soisalon-Soininen & Wood, 1984, the original definition. I did not open
  the 1984 paper.)
- Orientation: depends on the chosen axes; not rotation invariant (same page).
- Cost: construction for n points in O(n log n) (same page).
- Min-area rectilinear hull over all rotations: O(n log n) time, O(n) space.
  Source: https://arxiv.org/pdf/1710.10888 (arXiv; summary seen via search, full
  paper not read).
- Only fills notches along axis lines. Not a "nearby polygons within distance d" tool.
- No shapely/GEOS function for it was found in the shapely docs.

## 3. Grid / raster approach
- `rasterio.features.rasterize(..., all_touched)`: if True "all pixels touched by
  geometries will be burned in"; else only pixels whose center is inside.
  `features.shapes` takes `connectivity` 4 or 8 and a `mask`.
  Source: https://rasterio.readthedocs.io/en/stable/api/rasterio.features.html
- `gdal_polygonize` "creates vector polygons for all connected regions of pixels
  in the raster sharing a common pixel value"; 4-connected by default, `-8` for 8.
  Source: https://gdal.org/en/stable/programs/gdal_polygonize.html
- Not stated in those pages: staircase boundaries, hole handling, memory use.
  That the output edges are pixel-aligned follows from the raster-to-polygon
  definition, not from a quoted sentence.
- Gap bridging, notch filling and tightness all depend on cell size, a choice the
  caller makes. Cost scales with cell count (area / cell^2), not feature count.

## 4. GIS tools
### ArcGIS Pro: Aggregate Polygons
- "combines polygons that are within a specified distance of each other into new
  polygons." Parameters: aggregation distance (> 0), minimum area, minimum hole
  size, preserve orthogonal shape, barrier features.
- Orthogonal mode "constructs rectangular-shaped results"; may produce fewer
  aggregations when features lack clear directional alignment.
- Holes: small ones removed by minimum hole size; larger kept.
- Scale: for data too large for memory, use cartographic partitions; split features
  get `IS_SPLIT` = 1. Needs ArcGIS Pro Advanced license.
  Source: https://doc.esri.com/en/arcgis-pro/latest/tool-reference/cartography/aggregate-polygons.html
- (Fetched through a summarizer; wording above is paraphrase, not verbatim, except
  quoted fragments.)

### ArcGIS Pro: Regularize Building Footprint
- "normalizes the footprint of building polygons by eliminating undesirable
  artifacts"; uses a polyline compression algorithm. Methods: Right Angles, Right
  Angles and Diagonals, Any Angles, Circle. Tolerance = max deviation from the
  boundary. Precision 0.05 to 0.25. Diagonal penalty. Failed features pass through
  with STATUS = 1. Any Angles can use NVIDIA GPU. Needs the 3D Analyst extension.
  Source: https://doc.esri.com/en/arcgis-pro/latest/tool-reference/3d-analyst/regularize-building-footprint.html
- Cleans one footprint at a time; it does not merge neighbors (inferred from the
  summary, which describes per-building processing).

### QGIS
- Orthogonalize: "adjusts line and polygon geometries to create right angles."
  Max angle tolerance default 15 degrees; max iterations default 1000.
- Minimum bounding geometry offers convex hull, envelope, circle, widest extent.
- Concave hull (by layer) takes a point layer, threshold 0-1 (default 0.3), allow holes.
  Source: https://docs.qgis.org/latest/en/docs/user_manual/processing_algs/qgis/vectorgeometry.html
- None of these merges nearby polygons into a square-cornered wrapper by itself.

## Gaps (not answered by primary docs)
- Real runtime of buffer-out/buffer-in at thousands of polygons: no benchmark found.
- Whether mitre buffer-out/in leaves holes or notches intact: not documented; needs a test.
- Whether any library ships an orthogonal hull of polygons: none found in shapely/GEOS docs.
