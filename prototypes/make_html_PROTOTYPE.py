"""PROTOTYPE (throwaway): draws the mitre-close cases from issue #3 as one HTML page.
Run with a Python that has shapely: python prototypes/make_html_PROTOTYPE.py
"""
from pathlib import Path

from shapely import affinity
from shapely.geometry import MultiPolygon, box
from shapely.ops import unary_union

EPS = 0.1


def close(geom, dist=EPS):
    """Grow by dist, then shrink by the same dist. Input must be valid."""
    assert geom.is_valid
    grown = geom.buffer(dist, join_style="mitre", mitre_limit=100.0)
    out = grown.buffer(-dist, join_style="mitre", mitre_limit=100.0)
    assert out.is_valid
    return out


def path_d(geom, s, ox, oy, h):
    """SVG path for a (multi)polygon. Flip Y so world space is Y-up."""
    polys = getattr(geom, "geoms", [geom])
    parts = []
    for p in polys:
        for ring in [p.exterior, *p.interiors]:
            pts = [f"{ox + x * s:.1f},{oy + h - y * s:.1f}" for x, y in ring.coords]
            parts.append("M" + " L".join(pts) + " Z")
    return " ".join(parts)


def panel(title, note, geom):
    union = unary_union(geom)
    out = close(union)
    ratio = out.area / union.area
    minx, miny, maxx, maxy = union.buffer(EPS * 2).bounds
    s = 150 / max(maxx - minx, maxy - miny)
    w, h = (maxx - minx) * s, (maxy - miny) * s

    def shifted(g):
        return affinity.translate(g, -minx, -miny)

    d_in = path_d(shifted(union), s, 0, 0, h)
    d_out = path_d(shifted(out), s, 0, 0, h)
    kind = out.geom_type
    return f"""
  <figure>
    <svg viewBox="-4 -4 {w + 8:.0f} {h + 8:.0f}" role="img" aria-label="{title}">
      <path d="{d_out}" class="out" fill-rule="evenodd"/>
      <path d="{d_in}" class="in" fill-rule="evenodd"/>
    </svg>
    <figcaption><b>{title}</b><br>{note}<br>
      Result: <b>{kind}</b> &middot; area ratio <b>{ratio:.3f}</b></figcaption>
  </figure>"""


def main():
    grid = MultiPolygon([box(0, 0, 1, 1), box(1, 0, 2, 1), box(0, 1, 1, 2), box(1, 1, 2, 2)])
    pair = lambda gap: MultiPolygon([box(0, 0, 1, 1), box(1 + gap, 0, 2 + gap, 1)])
    stag = MultiPolygon([box(0, 0, 1, 1), box(1.15, 0.5, 2.15, 1.5)])
    u_narrow = MultiPolygon([box(0, 0, 1, 2), box(1.15, 0, 2.15, 2), box(0, 0, 2.15, 0.5)])
    u_wide = MultiPolygon([box(0, 0, 1, 2), box(2, 0, 3, 2), box(0, 0, 3, 0.5)])
    rot = affinity.rotate(pair(0.15), 45, origin=(0, 0))
    cases = [
        ("2x2 grid", "Four squares share edges. Inner lines vanish.", grid),
        ("Two squares, gap 0.15", "Gap is under 2 x eps, so a bridge fills it.", pair(0.15)),
        ("Two squares, gap 0.3", "Gap is over 2 x eps, so nothing changes.", pair(0.3)),
        ("Staggered pair", "Bridge only where the facing sides overlap.", stag),
        ("U shape, narrow notch", "Notch under 2 x eps gets filled.", u_narrow),
        ("U shape, wide notch", "Notch over 2 x eps is kept.", u_wide),
        ("Pair rotated 45 deg", "Corners stay square, but not axis-aligned.", rot),
    ]
    body = "".join(panel(*c) for c in cases)
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>BAP mitre close prototype</title>
<style>
  :root {{ --bg:#fff; --fg:#1a1a1a; --muted:#666; --in:#2b6cb0; --out:#f6ad55; --line:#ddd; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg:#16181d; --fg:#eee; --muted:#9aa; --in:#63b3ed; --out:#dd8a2b; --line:#333; }} }}
  body {{ font:15px/1.5 system-ui,sans-serif; background:var(--bg); color:var(--fg); margin:0; padding:16px; }}
  h1 {{ font-size:20px; margin:0 0 4px; }}
  p.sub {{ color:var(--muted); margin:0 0 16px; }}
  .legend span {{ display:inline-block; width:12px; height:12px; margin:0 4px 0 12px; vertical-align:middle; }}
  .grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:16px; }}
  figure {{ margin:0; border:1px solid var(--line); border-radius:8px; padding:12px; }}
  svg {{ width:100%; height:170px; }}
  figcaption {{ font-size:13px; color:var(--muted); margin-top:8px; }}
  .in {{ fill:var(--in); stroke:var(--fg); stroke-width:1; }}
  .out {{ fill:var(--out); stroke:var(--out); stroke-width:1; opacity:.55; }}
</style></head><body>
<h1>Mitre close: what the boundary looks like</h1>
<p class="sub">Close = grow by eps ({EPS}) with mitre joins, then shrink by eps. Real shapely output.</p>
<p class="legend"><span style="background:var(--in)"></span>input polygons
<span style="background:var(--out);opacity:.55"></span>boundary after close</p>
<div class="grid">{body}
</div>
<p class="sub">Rule of thumb: the close fills gaps, notches and holes narrower than 2 x eps. It does not snap to the x/y axes.</p>
</body></html>"""
    out = Path(__file__).with_name("orthogonal_boundary_PROTOTYPE.html")
    out.write_text(html)
    print("wrote", out)


main()
