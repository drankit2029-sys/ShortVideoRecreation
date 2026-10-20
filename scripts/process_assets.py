#!/usr/bin/env python3
"""Build all heavy assets for the Indian Ocean recreation on a GitHub runner.

Downloads NASA satellite imagery, grades it to the reference palette, derives
the basin mask / coastline glow / Asia glow overlays, builds the US flag-map
cutout, fetches a moon texture, fonts, and extracts the reference audio.
"""
import json
import math
import subprocess
import sys
import zipfile
from io import BytesIO
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "assets" / "raw"
PROC = ROOT / "assets" / "processed"
FONTS = ROOT / "assets" / "fonts"
AUDIOP = PROC / "audio"
for d in (RAW, PROC, FONTS, AUDIOP):
    d.mkdir(parents=True, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) recreation-pipeline/1.0"}


def fetch(url: str, dest: Path, min_bytes: int = 2000) -> Path:
    if dest.exists() and dest.stat().st_size >= min_bytes:
        print(f"  cached {dest.name} ({dest.stat().st_size} bytes)")
        return dest
    print(f"  GET {url}")
    req = Request(url, headers=UA)
    with urlopen(req, timeout=300) as resp, open(dest, "wb") as f:
        f.write(resp.read())
    size = dest.stat().st_size
    if size < min_bytes:
        raise RuntimeError(f"download too small: {url} -> {size} bytes")
    print(f"  -> {dest.name} ({size} bytes)")
    return dest


def try_fetch(urls, dest: Path, min_bytes: int = 2000) -> Path:
    last = None
    for u in urls:
        try:
            return fetch(u, dest, min_bytes)
        except Exception as e:  # noqa: BLE001
            print(f"  !! {u}: {e}")
            last = e
    raise RuntimeError(f"all URLs failed for {dest.name}: {last}")


# ---------------------------------------------------------------- earth texture
print("[1/8] earth texture (topo relief + blue-marble tone)")
topo_path = try_fetch(
    [
        "https://eoimages.gsfc.nasa.gov/images/imagerecords/73000/73909/world.topo.bathy.200412.3x5400x2700.jpg",
        "https://eoimages.gsfc.nasa.gov/images/imagerecords/73000/73751/land_shallow_topo_2048.jpg",
        "https://unpkg.com/three-globe/example/img/earth-topo.png",
    ],
    RAW / "earth-raw.jpg",
    min_bytes=100_000,
)
bm_path = try_fetch(
    [
        "https://cdn.jsdelivr.net/gh/mrdoob/three.js@r181/examples/textures/planets/earth_atmos_2048.jpg",
        "https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg",
        "https://raw.githubusercontent.com/mrdoob/three.js/r181/examples/textures/planets/earth_atmos_2048.jpg",
    ],
    RAW / "blue-marble.jpg",
    min_bytes=200_000,
)

img = Image.open(topo_path).convert("RGB")
W, H = img.size
print(f"  topo {W}x{H}")
topo = np.asarray(img).astype(np.float32) / 255.0
tR, tG, tB = topo[..., 0], topo[..., 1], topo[..., 2]
tlum = 0.299 * tR + 0.587 * tG + 0.114 * tB

bm_img = Image.open(bm_path).convert("RGB").resize((W, H), Image.BICUBIC)
bma = np.asarray(bm_img).astype(np.float32) / 255.0
blum = 0.299 * bma[..., 0] + 0.587 * bma[..., 1] + 0.114 * bma[..., 2]
_bl = Image.fromarray((np.clip(blum, 0, 1) * 255).astype(np.uint8))
blum_s = np.asarray(_bl.filter(ImageFilter.GaussianBlur(2.0))).astype(np.float32) / 255.0

# ocean mask from topo colors (blue-dominant, not dark forests / not snow);
# deep ocean reads near-black in the topo bathy imagery, so also take very
# dark blue-marble pixels (otherwise the southern Indian Ocean is taken for
# land and the asia fill paints a hard olive cap)
ocean = (
    (((tB - tR) > 0.04) & (tlum < 0.45))
    | (blum < 0.14)
)
land = ~ocean
_li = Image.fromarray((land * 255).astype(np.uint8), "L")
_li = _li.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))
land = np.asarray(_li) > 127
ocean = ~land

# relief detail from topo (ratio vs local mean)
_blur_tl = Image.fromarray((np.clip(tlum, 0, 1) * 255).astype(np.uint8))
blur_tl = np.asarray(_blur_tl.filter(ImageFilter.GaussianBlur(10.0))).astype(np.float32) / 255.0
relief = tlum / np.maximum(blur_tl, 0.02)

# ---- land duotone warm ramp driven by blue-marble tone
stops = [
    (0.00, (84, 66, 52)),
    (0.16, (112, 90, 72)),
    (0.28, (148, 122, 98)),
    (0.40, (176, 150, 124)),
    (0.52, (196, 166, 138)),
    (0.64, (208, 178, 150)),
    (0.76, (220, 198, 175)),
    (0.88, (238, 234, 228)),
    (1.00, (246, 246, 248)),
]
xs = np.array([s[0] for s in stops], dtype=np.float32)
land_col = np.stack(
    [np.interp(blum_s, xs, np.array([s[1][c] for s in stops], dtype=np.float32) / 255.0)
     for c in range(3)],
    axis=-1,
)
land_col *= np.clip(0.86 + 0.14 * relief, 0.72, 1.22)[..., None]

# ---- ocean recolor -> reference flat teal with faint bathymetry
ocean_base = np.array([22 / 255, 80 / 255, 68 / 255], dtype=np.float32)
ocean_tone = 0.90 + 0.45 * np.clip(blum_s / 0.40, 0.0, 1.0)
ocean_col = ocean_base[None, None, :] * ocean_tone[..., None] * np.clip(0.93 + 0.14 * relief, 0, 1.4)[..., None]

out = np.where(land[..., None], land_col, ocean_col)
out = np.clip((out - 0.5) * 1.05 + 0.5, 0, 1)
# bright polar ice cap (reference shows a clean white Antarctica strip)
_lats = np.linspace(90.0, -90.0, out.shape[0])[:, None]
_ice = np.clip((-60.0 - _lats) / 6.0, 0.0, 1.0)[..., None]
_ice = _ice * _ice * (3 - 2 * _ice)
_ice_col = np.array([0.93, 0.955, 0.945], dtype=np.float32)[None, None, :]
out = out * (1 - _ice) + _ice_col * _ice
Image.fromarray((out * 255).astype(np.uint8)).save(
    PROC / "earth-graded.jpg", quality=93, subsampling=0
)
print(f"  saved earth-graded.jpg ({(PROC / 'earth-graded.jpg').stat().st_size} bytes)")
# water mask for selective ocean grading in the post shader
Image.fromarray((~land).astype(np.uint8) * 255, "L").save(PROC / "water-mask.png")
print("  saved water-mask.png")


# ------------------------------------------------------- basin crop helpers
# equirect: x = (lon+180)/360*W ; y = (90-lat)/180*H
def lon_to_x(lon: float) -> int:
    return int(round((lon + 180.0) / 360.0 * W))


def lat_to_y(lat: float) -> int:
    return int(round((90.0 - lat) / 180.0 * H))


BOX = dict(lon0=20.0, lon1=146.8, lat0=-60.0, lat1=26.0)
bx0, bx1 = lon_to_x(BOX["lon0"]), lon_to_x(BOX["lon1"])
by0, by1 = lat_to_y(BOX["lat1"]), lat_to_y(BOX["lat0"])  # y grows southward

basin = ocean[by0:by1, bx0:bx1].copy()
# artificial straight boundary strokes at crop edges (ocean-basin delimitation)
edge = np.zeros_like(basin)
edge[:-1, :] |= basin[:-1, :] != basin[1:, :]
edge[:, :-1] |= basin[:, :-1] != basin[:, 1:]
ch, cw = basin.shape
# bottom edge (lat -60 parallel): full width
edge[-3:, :] |= basin[-3:, :][:, :]  # stroke along bottom where ocean
# left edge (20E meridian) south of Cape Agulhas (lat -34.8 .. -60)
y_ag = lat_to_y(-34.8) - by0
edge[y_ag:, :3] |= basin[y_ag:, :3]
# right edge (146.8E meridian) south of Tasmania (lat -42 .. -60)
y_tas = lat_to_y(-42.0) - by0
edge[y_tas:, -3:] |= basin[y_tas:, -3:]


def glow_stack(edge_mask: np.ndarray, core="#FFE66E", mid="#FFB800",
               outer="#FF8C00") -> Image.Image:
    """edge_mask: bool HxW -> RGBA glow layer (blur-based bloom, bright core)."""
    m = Image.fromarray((edge_mask * 255).astype(np.uint8), "L")
    layers = []
    specs = (
        (outer, 150, 14.0, 0),
        (mid, 225, 5.0, 0),
        (core, 255, 0.0, 7),
    )
    for col, alpha, blur, dil in specs:
        d = m
        if dil >= 3:
            d = d.filter(ImageFilter.MaxFilter(dil if dil % 2 else dil + 1))
        if blur:
            d = d.filter(ImageFilter.GaussianBlur(blur))
        arr = np.asarray(d).astype(np.float32) / 255.0 * alpha
        rgba = np.zeros(edge_mask.shape + (4,), dtype=np.uint8)
        rgb = np.array(Image.new("RGB", (1, 1), col).getpixel((0, 0)), dtype=np.uint8)
        rgba[..., 0], rgba[..., 1], rgba[..., 2] = rgb[0], rgb[1], rgb[2]
        rgba[..., 3] = arr.astype(np.uint8)
        layers.append(Image.fromarray(rgba, "RGBA"))
    base = Image.new("RGBA", layers[0].size, (0, 0, 0, 0))
    for l in layers:
        base = Image.alpha_composite(base, l)
    return base


print("[2/8] basin coastline glow")
coast = glow_stack(edge)
coast.save(PROC / "coast-glow.png", optimize=True)
print(f"  coast-glow.png {coast.size} ({(PROC / 'coast-glow.png').stat().st_size} bytes)")


print("[3/8] basin grid overlay")
# ~3.5-degree lat/lng grid inside basin (aligned to meridians/parallels)
step_deg = 12.0
sx = W / 360.0 * step_deg
sy = H / 180.0 * step_deg
line_w = 2
grid = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
gd = ImageDraw.Draw(grid)
gx = 0.0
while gx < cw:
    gd.rectangle([gx, 0, gx + line_w, ch], fill=(213, 232, 220, 92))
    gx += sx
gy = 0.0
while gy < ch:
    gd.rectangle([0, gy, cw, gy + line_w], fill=(213, 232, 220, 104))
    gy += sy
# small nodes at intersections
gx = 0.0
while gx < cw:
    gy = 0.0
    while gy < ch:
        gd.ellipse([gx - 1.8, gy - 1.8, gx + 3.8, gy + 3.8], fill=(225, 240, 230, 150))
        gy += sy
    gx += sx
grid_arr = np.asarray(grid).astype(np.float32)
# subtle darker water fill inside basin
fill = np.zeros((ch, cw, 4), dtype=np.float32)
fill[..., 0], fill[..., 1], fill[..., 2] = 10, 46, 38
fill[..., 3] = basin.astype(np.float32) * 26
grid_arr[..., 3] *= basin
combined = np.maximum(fill, grid_arr)
Image.fromarray(combined.astype(np.uint8), "RGBA").save(
    PROC / "basin-grid.png", optimize=True
)
print(f"  basin-grid.png ({(PROC / 'basin-grid.png').stat().st_size} bytes)")

# also save basin mask crop (for JS fallbacks)
mask_img = Image.fromarray((basin * 255).astype(np.uint8), "L")
mask_img.save(PROC / "basin-mask.png", optimize=True)


print("[4/8] asia glow")
AX0, AX1 = lon_to_x(25.0), W  # up to 180E
AY0, AY1 = lat_to_y(78.0), lat_to_y(-11.0)
asia_land = ~ocean[AY0:AY1, AX0:AX1]
ah, aw = asia_land.shape
lons = np.linspace(25.0, 180.0, aw)
lats = np.linspace(78.0, -11.0, ah)
LON, LAT = np.meshgrid(lons, lats)
excl = (
    ((LAT < 12.0) & (LON < 52.0))              # Horn of Africa
    | ((LON > 110.0) & (LON < 156.0) & (LAT < -10.5))  # Australia
    | ((LON > 160.0) & (LAT < -30.0))          # NZ
    | ((LON < 36.2) & (LAT > 19.5))            # Egypt / Africa north of Suez
)
asia = asia_land & ~excl
# close snow-hole speckles, then open stray specks
_ai = Image.fromarray((asia * 255).astype(np.uint8), "L")
_ai = _ai.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.MinFilter(9))
_ai = _ai.filter(ImageFilter.MinFilter(5)).filter(ImageFilter.MaxFilter(5))
asia = (np.asarray(_ai) > 127) & ~excl
aedge = np.zeros_like(asia)
aedge[:-1, :] |= asia[:-1, :] != asia[1:, :]
aedge[:, :-1] |= asia[:, :-1] != asia[:, 1:]
asia_rgba = np.zeros((ah, aw, 4), dtype=np.float32)
fill_a = np.zeros((ah, aw, 4), dtype=np.float32)
fill_a[..., 0], fill_a[..., 1], fill_a[..., 2] = 255, 201, 60
fill_a[..., 3] = asia.astype(np.float32) * 24
# kill RGB outside the land mask so clamped/edge sampling can never wash the ocean
_soft = np.asarray(
    Image.fromarray((asia * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(1.2))
).astype(np.float32) / 255.0
fill_a[..., :3] *= _soft[..., None]
glow = np.asarray(glow_stack(aedge, core="#FFD24A", mid="#FFB300", outer="#FF9500")).astype(np.float32)
asia_rgba = np.maximum(fill_a, glow)
# feather the crop borders so the rectangle cut never shows a hard edge
_fy = np.clip(np.minimum(np.arange(ah), ah - 1 - np.arange(ah)) / (0.05 * ah), 0, 1)
_fx = np.clip(np.minimum(np.arange(aw), aw - 1 - np.arange(aw)) / (0.05 * aw), 0, 1)
_feather = np.minimum(_fy[:, None], _fx[None, :]).astype(np.float32) ** 1.5
asia_rgba[..., 3] *= _feather
Image.fromarray(asia_rgba.astype(np.uint8), "RGBA").save(
    PROC / "asia-glow.png", optimize=True
)
print(f"  asia-glow.png ({(PROC / 'asia-glow.png').stat().st_size} bytes)")


print("[5/8] usa flag-map")
states_path = try_fetch(
    ["https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json"],
    RAW / "us-states.json",
    min_bytes=50_000,
)
geo = json.loads(states_path.read_text())
# contiguous US only
US_BOX = dict(lon0=-128.0, lon1=-64.0, lat0=22.0, lat1=51.5)
fx0, fx1 = lon_to_x(US_BOX["lon0"]), lon_to_x(US_BOX["lon1"])
fy0, fy1 = lat_to_y(US_BOX["lat1"]), lat_to_y(US_BOX["lat0"])
fx0, fx1 = int(round(fx0)), int(round(fx1))
fy0, fy1 = int(round(fy0)), int(round(fy1))
fw, fh = fx1 - fx0, fy1 - fy0
us_mask = Image.new("L", (W, H), 0)
md = ImageDraw.Draw(us_mask)


def project_ring(ring):
    return [
        (
            (lon + 180.0) / 360.0 * W,
            (90.0 - lat) / 180.0 * H,
        )
        for lon, lat in ring
    ]


for feat in geo["features"]:
    name = feat.get("properties", {}).get("name", "")
    if name in ("Alaska", "Hawaii", "Puerto Rico"):
        continue
    geom = feat["geometry"]
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for poly in polys:
        ring = project_ring(poly[0])
        xs_ = [p[0] for p in ring]
        ys_ = [p[1] for p in ring]
        if max(xs_) < fx0 or min(xs_) > fx1 or max(ys_) < fy0 or min(ys_) > fy1:
            continue
        md.polygon(ring, fill=255)
us_crop_mask = us_mask.crop((fx0, fy0, fx1, fy1))

# US flag with official-ish proportions
FL, FH = 1520, 800
flag = Image.new("RGB", (FL, FH), (255, 255, 255))
fd = ImageDraw.Draw(flag)
RED = (178, 34, 52)
stripe_h = FH / 13.0
for i in range(13):
    if i % 2 == 0:
        fd.rectangle([0, i * stripe_h, FL, (i + 1) * stripe_h], fill=RED)
canton_w, canton_h = FL * 0.4, FH * 7.0 / 13.0
BLUE = (60, 59, 110)
fd.rectangle([0, 0, canton_w, canton_h], fill=BLUE)


def star_points(cx, cy, r):
    pts = []
    for k in range(10):
        ang = math.pi / 2 + k * math.pi / 5
        rad = r if k % 2 == 0 else r * 0.382
        pts.append((cx + rad * math.cos(ang), cy - rad * math.sin(ang)))
    return pts


star_r = FH * 0.0616 / 2
row_gap = canton_h / 10.0
col_gap = canton_w / 12.0
for row in range(9):
    y = (row + 1) * row_gap
    offset = 0.5 if row % 2 == 0 else 1.0
    cols = 6 if row % 2 == 0 else 5
    for c in range(cols):
        x = (c + offset) * col_gap
        fd.polygon(star_points(x, y, star_r), fill=(255, 255, 255))

# cloth fold shading
fx = np.linspace(0, 1, FL)[None, :]
fy = np.linspace(0, 1, FH)[:, None]
shade = 1.0 + 0.16 * np.sin(2 * np.pi * (fx * 2.1 + fy * 0.55) + 0.7)
shade += 0.07 * np.sin(2 * np.pi * (fx * 4.6 - fy * 1.2) + 2.1)
shade -= 0.10 * fy  # bottom slightly darker
farr = np.asarray(flag).astype(np.float32) * np.clip(shade, 0.72, 1.22)[..., None]
flag = Image.fromarray(np.clip(farr, 0, 255).astype(np.uint8))
flag = flag.resize((fw, fh), Image.LANCZOS)

flag_rgba = np.dstack(
    [np.asarray(flag), np.asarray(us_crop_mask)]
)
# drop shadow under flag
shadow = us_crop_mask.filter(ImageFilter.GaussianBlur(9))
sh = np.asarray(shadow).astype(np.float32) * 0.55
out_w, out_h = fw + 24, fh + 24
usa_out = np.zeros((out_h, out_w, 4), dtype=np.uint8)
# shadow offset (+10,+12)
usa_out[12:12 + fh, 10:10 + fw, 3] = np.maximum(
    usa_out[12:12 + fh, 10:10 + fw, 3].astype(np.float32), sh
).astype(np.uint8)
usa_out[12:12 + fh, 10:10 + fw, :3] = (10, 32, 28)
# flag over shadow
sub = usa_out[0:fh, 0:fw]
alpha = np.asarray(us_crop_mask).astype(np.float32) / 255.0
sub_rgb = np.asarray(flag).astype(np.float32)
sub[..., :3] = (sub_rgb * alpha[..., None] + sub[..., :3] * (1 - alpha[..., None])).astype(np.uint8)
sub[..., 3] = np.maximum(sub[..., 3].astype(np.float32), alpha * 255).astype(np.uint8)
usa_out[0:fh, 0:fw] = sub
Image.fromarray(usa_out, "RGBA").save(PROC / "usa-flag.png", optimize=True)
# lat/lon of the flag placement box (top-left of crop is lat1/lon0)
meta_usa = {
    "lon0": US_BOX["lon0"], "lon1": US_BOX["lon1"],
    "lat0": US_BOX["lat0"], "lat1": US_BOX["lat1"],
    "pad_px": 24, "w": out_w, "h": out_h,
}
(PROC / "usa-flag.json").write_text(json.dumps(meta_usa))
print(f"  usa-flag.png {out_w}x{out_h} ({(PROC / 'usa-flag.png').stat().st_size} bytes)")


print("[6/8] moon texture")
try_fetch(
    [
        "https://threejs.org/examples/textures/planets/moon_1024.jpg",
        "https://upload.wikimedia.org/wikipedia/commons/1/1b/Moonmap_from_clementine_data.png",
    ],
    PROC / "moon.jpg",
    min_bytes=30_000,
)

print("[7/8] font (Inter)")
try:
    zip_path = RAW / "inter.zip"
    try_fetch(
        [
            "https://github.com/rsms/inter/releases/download/v4.0/Inter-4.0.zip",
            "https://github.com/rsms/inter/releases/download/v4.1/Inter-4.1.zip",
        ],
        zip_path,
        min_bytes=200_000,
    )
    with zipfile.ZipFile(zip_path) as z:
        names = [n for n in z.namelist() if n.endswith("InterVariable.woff2")]
        if names:
            data = z.read(names[0])
            (FONTS / "InterVariable.woff2").write_bytes(data)
            print(f"  InterVariable.woff2 {len(data)} bytes")
        else:
            raise RuntimeError("InterVariable.woff2 not in zip")
except Exception as e:  # noqa: BLE001
    print(f"  font fallback: {e}")
    # last resort: any ttf from google fonts
    css = urlopen(Request(
        "https://fonts.googleapis.com/css2?family=Inter:wght@800&display=swap",
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"})).read().decode()
    import re
    urls = re.findall(r"url\((https://[^)]+)\)", css)
    if urls:
        data = urlopen(Request(urls[-1], headers=UA)).read()
        (FONTS / "Inter-var.woff2").write_bytes(data)
        print(f"  Inter-var.woff2 {len(data)} bytes")


print("[8/8] audio")
subprocess.run(
    ["ffmpeg", "-y", "-i", str(ROOT / "reference" / "target.mp4"),
     "-vn", "-c:a", "aac", "-b:a", "192k", str(AUDIOP / "track.m4a")],
    check=True,
)
print(f"  track.m4a {(AUDIOP / 'track.m4a').stat().st_size} bytes")

manifest = {
    "earth": {"w": W, "h": H},
    "basin_box": BOX,
    "asia_box": {"lon0": 25.0, "lon1": 180.0, "lat0": -11.0, "lat1": 78.0},
    "usa": meta_usa,
}
(PROC / "manifest.json").write_text(json.dumps(manifest, indent=2))
print("DONE")
sys.exit(0)
