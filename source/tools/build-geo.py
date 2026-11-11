#!/usr/bin/env python3
"""Build draft/assets/geo.json - the Philippine region geometry inlined into the map.

Why this tool exists
--------------------
The map on the page draws one SVG path per region. The first version of that
geometry came from the low-resolution files of `faeldon/philippines-json-maps`
(0.1% of the source vertices): the Cordillera Administrative Region (CAR) had
only 36 points across its six provinces and read as a straight-edged box.
This tool rebuilds the geometry from the *high-resolution* files of the same
project and simplifies it for the map's render size, with reproducible inputs
(pinned release + pinned SHA-256) and recorded provenance.

Source
------
`faeldon/philippines-json-maps` release **v1.1.1** (PSGC 2026-3q), TopoJSON,
level `regions`, resolution `hires` (10% of the source vertices) - one file per
region holding its provinces / NCR districts as ADM2 features. The repository's
code and maps are MIT; the boundaries are CC BY 3.0 IGO (CC BY-IGO), derived
from OCHA's Philippines COD-AB (NAMRIA / PSA). See SOURCE / geo-sources.json.

The medium-resolution files (`geojson/regions/medres/*.0.01.json`, 1% of the
vertices) were evaluated first and rejected: they leave CAR with 98 outer-ring
points (16 per province), still visibly polygonal at this map's size. Their
pinned hashes are recorded under `evaluated_alternatives` in geo-sources.json.

What the pipeline does
----------------------
1. Fetch the release zip (cached under the system temp dir) and verify its
   pinned SHA-256; extract the 18 region files and verify each file's SHA-256.
2. Decode the TopoJSON (shared arcs), project WGS84 lon/lat to the map frame:
   x = lon, y = -mercator(lat), then scale so the land extent is 1000 units
   wide; height follows the Mercator aspect ratio.
3. Simplify **at the TopoJSON arc level** with Douglas-Peucker. Shared province
   borders are one arc, so they are simplified once and reused: no internal
   slivers between provinces. Tolerance is in final viewBox units, i.e. it is a
   screen-space tolerance (0.6 units = 0.54 px at a 900 px-wide render).
4. Keep outer rings by area only (small islets below ~4 km2 are dropped; inner
   rings / holes are dropped, as the previous geometry did) and emit the
   existing schema unchanged:
   {width, height, regions: {psgc: {name, short, full, island, path,
    label_x, label_y, bbox, rings}}}.

Determinism: geo.json is a pure function of the pinned inputs and the constants
below. Re-running twice produces byte-identical output (the tool prints the
output SHA-256, and geo-sources.json records it). geo-sources.json carries the
run/fetch timestamps, so it is the only file whose bytes change between runs.

Usage
-----
    python3 tools/build-geo.py                 # build (downloads once, then cached)
    python3 tools/build-geo.py --refresh       # re-download the release zip
    python3 tools/build-geo.py --archive FILE  # use an already-downloaded zip
    python3 tools/build-geo.py --cache-dir DIR # put the cache elsewhere

The page itself never fetches anything: tools/build-map-page.py inlines geo.json
into draft/map-table-prototype.html as SVG path data.
"""
import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO_OUT = os.path.join(ROOT, "draft", "assets", "geo.json")
SOURCES_OUT = os.path.join(ROOT, "draft", "assets", "geo-sources.json")
LGU_GEO_OUT = os.path.join(ROOT, "draft", "assets", "coverage-geo.json")
RELATIVE_GEO_OUT = "draft/assets/geo.json"
RELATIVE_SOURCES_OUT = "draft/assets/geo-sources.json"
RELATIVE_LGU_GEO_OUT = "draft/assets/coverage-geo.json"

# ---------------------------------------------------------------------------
# Pinned source (verified before anything is read; see verify_archive)
# ---------------------------------------------------------------------------
SOURCE = {
    "name": "faeldon/philippines-json-maps",
    "release": "v1.1.1",
    "released": "2026-11-07",
    "psgc": "2026-3q",
    "psgc_codes": "18 regions of the PSGC 3Q 2026, including NIR (1800000000) "
                  "and BARMM (1900000000); NIR holds Negros Occidental, Negros "
                  "Oriental and Siquijor, and Sulu is part of Region IX",
    "release_url": "https://github.com/faeldon/philippines-json-maps/releases/tag/v1.1.1",
    "asset": "topojson-hires.zip",
    "url": "https://github.com/faeldon/philippines-json-maps/releases/download/"
           "v1.1.1/topojson-hires.zip",
    "sha256": "e7a00ff5a65c525557ff716658b579dab5c20322bd6b710495bf74e6cf2377d3",
    "bytes": 23551262,
    "sha256sums_url": "https://github.com/faeldon/philippines-json-maps/releases/"
                      "download/v1.1.1/SHA256SUMS",
    "sha256sums_sha256": "200f0ce6b85420d8a2c777da0e8d23946c58832c115ad67eecadc861050fa364",
    "upstream": "faeldon/philippines-psgc-shapefiles v1.0.1",
    "upstream_url": "https://github.com/faeldon/philippines-psgc-shapefiles/"
                    "releases/tag/v1.0.1",
    "format": "TopoJSON, level `regions`, resolution `hires` (10% of the source "
              "vertices; one file per region, features are provinces / NCR districts)",
    "license": "MIT (repository scripts and maps); boundaries CC BY 3.0 IGO (CC BY-IGO)",
    "attribution": "Province boundaries: (c) NAMRIA and the Philippine Statistics "
                   "Authority, via OCHA's Philippines Common Operational Dataset "
                   "for Administrative Boundaries (COD-AB), licensed CC BY 3.0 IGO.",
}

# File inside the zip -> (extracted file name, size, sha256) for the 18 regions
# of PSGC 3Q 2026. Codes are the 10-digit PSGC region codes used in geo.json;
# the dataset writes codes as integers, so leading zeros are dropped in filenames.
REGION_FILES = {
    "0100000000": ("topojson/regions/hires/provdists-region-100000000.topo.0.1.json",
                   208463, "b17806b9eb77b6e884e05f0f40649cdb7c35c0826e238600c46466b6ce54dd4e"),
    "0200000000": ("topojson/regions/hires/provdists-region-200000000.topo.0.1.json",
                   344477, "51ff4b0dbc7520147c25f78b68fd3122cb859a997c7724cebaed3890694965b3"),
    "0300000000": ("topojson/regions/hires/provdists-region-300000000.topo.0.1.json",
                   280617, "28e31d4675aaa667a2337bd659804c42ca7b8230de6d4dca420a9b9994d1103d"),
    "0400000000": ("topojson/regions/hires/provdists-region-400000000.topo.0.1.json",
                   613942, "b5b259e178c9331d0cf8675097b47b09df0f6787e93d17f2f9ef8b7bac159c27"),
    "0500000000": ("topojson/regions/hires/provdists-region-500000000.topo.0.1.json",
                   1287708, "6283f043086289c0f3a2cdb5ece15e02433ec689fd811943793433facfe7362b"),
    "0600000000": ("topojson/regions/hires/provdists-region-600000000.topo.0.1.json",
                   531910, "7ac49338aecc4bd7bf4930cb4b412f458f4d0956e42bb471aa1f44e004093e73"),
    "0700000000": ("topojson/regions/hires/provdists-region-700000000.topo.0.1.json",
                   721810, "918e36f1d02364beecf64fc21a3e693d66d2a707e2c258a645d07672fef77cd7"),
    "0800000000": ("topojson/regions/hires/provdists-region-800000000.topo.0.1.json",
                   1549363, "00b700cf21ba98c9743c9c12a5783702eea3287c78d6c6965eee6a2714424a25"),
    "0900000000": ("topojson/regions/hires/provdists-region-900000000.topo.0.1.json",
                   1395363, "a081b0ea0ebec3b5eee9c0b58b0669b8f70edf798b28883c224e4e196b8d452e"),
    "1000000000": ("topojson/regions/hires/provdists-region-1000000000.topo.0.1.json",
                   236248, "31e16250a121552f4a2f98456f9256fdd3edd4a8d3682859b48690c595286d42"),
    "1100000000": ("topojson/regions/hires/provdists-region-1100000000.topo.0.1.json",
                   350324, "68ee1e1b372de6a4e1d289b65b1188deadff780844f8d45f025e41e6ce3220e8"),
    "1200000000": ("topojson/regions/hires/provdists-region-1200000000.topo.0.1.json",
                   83322, "27c360fb63a77439aedfd994b8e83b0eeba8ee372413f813733d9e0f31db2281"),
    "1300000000": ("topojson/regions/hires/provdists-region-1300000000.topo.0.1.json",
                   26221, "dced50b3ecdff5586cf5caa23b57dc3f0ef8eae0948bfd70fdd1d8bc03375ca8"),
    "1400000000": ("topojson/regions/hires/provdists-region-1400000000.topo.0.1.json",
                   6838, "5e1295603b23eba7994d90bc3e0db7733ea6d53e0197871a91cfeea7926b6e39"),
    "1600000000": ("topojson/regions/hires/provdists-region-1600000000.topo.0.1.json",
                   787158, "f97eb81f65e3cfb0d94325b8d5da3de2b8881db4e07343b892be870dbd2945e4"),
    "1700000000": ("topojson/regions/hires/provdists-region-1700000000.topo.0.1.json",
                   2274801, "512b36337d345f3b54980fe3d70c7fb54da6eb880f557b0af73aa446cab51f54"),
    "1800000000": ("topojson/regions/hires/provdists-region-1800000000.topo.0.1.json",
                   374983, "a470d79f5319ef9f3a62bdf3ee6d7a3fa9b03a40dd91d5ac54aa23576c658fe2"),
    "1900000000": ("topojson/regions/hires/provdists-region-1900000000.topo.0.1.json",
                   750234, "bcc7bafdcdb341a1ccfc0ad818880fe37123f092f011ec7bf13f1a04d6cb579a"),
}

# Region presentation metadata. Identical to the previous geo.json (and to the
# page's region list) so page labels do not change.
META = {
    "0100000000": ("Region I", "I", "Ilocos Region", "luzon"),
    "0200000000": ("Region II", "II", "Cagayan Valley", "luzon"),
    "0300000000": ("Region III", "III", "Central Luzon", "luzon"),
    "0400000000": ("Region IV-A", "IV-A", "CALABARZON", "luzon"),
    "0500000000": ("Region V", "V", "Bicol Region", "luzon"),
    "0600000000": ("Region VI", "VI", "Western Visayas", "visayas"),
    "0700000000": ("Region VII", "VII", "Central Visayas", "visayas"),
    "0800000000": ("Region VIII", "VIII", "Eastern Visayas", "visayas"),
    "0900000000": ("Region IX", "IX", "Zamboanga Peninsula", "mindanao"),
    "1000000000": ("Region X", "X", "Northern Mindanao", "mindanao"),
    "1100000000": ("Region XI", "XI", "Davao Region", "mindanao"),
    "1200000000": ("Region XII", "XII", "SOCCSKSARGEN", "mindanao"),
    "1300000000": ("NCR", "NCR", "National Capital Region", "luzon"),
    "1400000000": ("CAR", "CAR", "Cordillera Administrative Region", "luzon"),
    "1600000000": ("Region XIII", "XIII", "Caraga", "mindanao"),
    "1700000000": ("MIMAROPA", "MIMAROPA", "Southwestern Tagalog Region", "luzon"),
    "1800000000": ("NIR", "NIR", "Negros Island Region", "visayas"),
    "1900000000": ("BARMM", "BARMM", "Bangsamoro Autonomous Region in Muslim Mindanao", "mindanao"),
}
CODES = list(META)

# ---------------------------------------------------------------------------
# Projection and simplification parameters (the tuning knobs)
# ---------------------------------------------------------------------------
WIDTH = 1000.0                 # output width in viewBox units; height follows
KM2_PER_DEG2 = 111.32 ** 2     # rough scale for area thresholds below
DP_TOLERANCE = 0.6             # Douglas-Peucker tolerance, viewBox units
MIN_RING_AREA = 3.5            # units^2 (~4 km2): drop smaller islets
EXTENT_MIN_RING_AREA_KM2 = 2.0  # frame is set by rings at least this big, so
                                # sub-pixel outlying islets (the Kalayaan group)
                                # neither appear nor stretch the frame

# Coverage layer (one polygon set per municipality / city, drawn when a user
# filters the map by distribution utility). This layer is deliberately lighter
# than the region geometry: it is only used as a filled overlay over a dimmed
# base map, so a coarser, integer-encoded path is enough. Path data uses
# relative integer commands ("M..l.."), which is ~35% smaller than the absolute
# one-decimal format used for the regions.
LGU_DP_TOLERANCE = 1.4         # Douglas-Peucker tolerance, viewBox units
LGU_MIN_RING_AREA_KM2 = 0.05   # keep even tiny islands (e.g. Pateros, 2.1 km2)
LGU_FORMAT_DECIMALS = 0        # integer path coordinates
PROVDIST_PREFIX = "topojson/provdists/hires/"

PROJECTION = {
    "name": "Mercator latitude x linear longitude, normalised to width 1000",
    "formula": "x = lon; y = -ln(tan(pi/4 + lat*pi/360)) * 180/pi; "
               "then translate by the land extent and scale x to 1000.0",
    "units": "viewBox units (width 1000.0, height computed)",
    "crs_in": "WGS84 lon/lat (EPSG:4326)",
    "normalisation": "the extent is the bounding box of rings with area >= "
                     "%.1f km2, so outlying sub-pixel islets do not stretch the frame"
                     % EXTENT_MIN_RING_AREA_KM2,
}

# The previous geometry this tool replaces (measured from the committed
# draft/assets/geo.json before the first run) - kept for the provenance record.
SUPERSEDES = {
    "source": "faeldon/philippines-json-maps latest/geojson/regions/lowres/"
              "provdists-region-<psgc>.0.001.json (0.1% of vertices, PSGC 3Q 2026)",
    "simplification": "ring-level Douglas-Peucker tolerance 0.9, min ring area 5.0; "
                      "ring format M/L/Z, 79,699 bytes",
    "issue": "CAR had only 36 points across six provinces and looked boxy/straight-edged "
             "at the map's render size.",
    "points": {
        "0100000000": 203, "0200000000": 292, "0300000000": 305, "0400000000": 435,
        "0500000000": 535, "0600000000": 329, "0700000000": 217, "0800000000": 590,
        "0900000000": 541, "1000000000": 206, "1100000000": 304, "1200000000": 126,
        "1300000000": 46, "1400000000": 36, "1600000000": 423, "1700000000": 886,
        "1800000000": 152, "1900000000": 447,
    },
    "points_total": 6073,
}

# Medium-resolution GeoJSON examined as the lighter alternative, and why it was
# not good enough. `latest/` is mutable upstream, so these are the hashes of the
# files fetched while evaluating them (recorded 2026-11-10), and the CAR count
# that ruled them out.
MEDRES_EVALUATED = {
    "format": "GeoJSON, level `regions`, resolution `medres` (1% of the source vertices)",
    "url_template": "https://raw.githubusercontent.com/faeldon/philippines-json-maps/"
                    "master/latest/geojson/regions/medres/"
                    "provdists-region-<psgc-as-integer>.0.01.json",
    "fetched": "2026-11-10",
    "finding": "All 18 current PSGC region files are present (NIR and BARMM included), "
               "but CAR has only 98 outer-ring points (16 per province) and other "
               "regions are correspondingly coarse; still boxy at the map's render size.",
    "sha256": {
        "0100000000": "83ad8f70e3ac918898cd9a92e29be260634e5b920fef741135fa1202f76f0edf",
        "0200000000": "9165f31c382085e8a3f6842b2b4321422d203e2a1707c6cf9e5a17548ec659e0",
        "0300000000": "0ff66cbb388f48c913c50616f6b38a2a11e972319bb1d2dc07a856eff02919c9",
        "0400000000": "5c627064fa78571bcffd1f65733ddb903d05c582b6dc735cfdd0b9090914edb7",
        "0500000000": "6ee084d16416ccfa6f65a595840a1da3b7e5e98e7bdd7ed4f10d21e5d28ee90c",
        "0600000000": "1ca1a286b4353431c4322e63dc0e15228757a8be4d26de97fe59a1f133ca666b",
        "0700000000": "bfefcbabe3f45384273c96e7b476bbefad2a4f5a4e9cde09ec438091837e010f",
        "0800000000": "2d30a40daf08866a63f29f17baab543c00354d065b45b2496c9a47af9f55a017",
        "0900000000": "8441dd7bc2df458258abc4ca9f9dd0844f290c22494abf05be07cf1aaf9680e0",
        "1000000000": "2bd0a763623c625b763df4ed5cd7d4f00373565343641184648f0132e100783a",
        "1100000000": "44df94f5c585ebb288ea78970846a6f19046aa371d11f04421f8688ac8536ea0",
        "1200000000": "3851878146a5441f3640d0bb76334d6d773676f81baea29bef89ff79b2a727e9",
        "1300000000": "c4b46546085966ad9e79f0b524785366c09fd95f86e8f58c290925c81e3ea5de",
        "1400000000": "0c49b2fd063e9857dbdfc551354621f7ed8e7e62c3b8378386dd1219625567c4",
        "1600000000": "e1c9c3396fe82fe9a15938b19557fb600dd27b3a1fc78a55ce2e40d0a3b7b675",
        "1700000000": "d5895b5c5d7f200eca3813d3dc9277ddf80bd8d98cef39ad18ffe2510de62e10",
        "1800000000": "a91cb549ff5d6a7249f34539f6a00d27fb11b3f6ad9081015562b6e6b039ec64",
        "1900000000": "2933ba759e6c24495dd5ab4cc7a794be10e3c1d687c1d2720607cd76fbed5581",
    },
    "fetch_note": "These hashes verify the files fetched for the evaluation only; the "
                  "build reads the pinned release archive above, never `latest/`.",
}

# ---------------------------------------------------------------------------
# Download / verify / extract
# ---------------------------------------------------------------------------
def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def default_cache_dir():
    return os.environ.get(
        "GEO_BUILD_CACHE",
        os.path.join(tempfile.gettempdir(), "philippines-json-maps-cache"),
    )


def archive_name():
    return "%s-%s.zip" % (SOURCE["asset"].rsplit(".zip", 1)[0], SOURCE["release"])


def download_archive(url, dest, expected_sha256, timeout=180, attempts=3):
    """Stream `url` to `dest`, verifying SHA-256. Retries a few times."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    part = dest + ".part"
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            request = urllib.request.Request(
                url, headers={"User-Agent": "bettergov-geo-build/1.0 (+tools/build-geo.py)"}
            )
            hasher = hashlib.sha256()
            received = 0
            with urllib.request.urlopen(request, timeout=timeout) as response, \
                    open(part, "wb") as out:
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
                    hasher.update(chunk)
                    received += len(chunk)
            actual = hasher.hexdigest()
            if actual != expected_sha256:
                os.remove(part)
                raise SystemExit(
                    "download of %s failed integrity check: expected sha256 %s, got %s "
                    "(%d bytes)" % (url, expected_sha256, actual, received)
                )
            os.replace(part, dest)
            fetched_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            with open(dest + ".fetched.json", "w", encoding="utf-8") as fh:
                json.dump({"url": url, "sha256": actual, "bytes": received,
                           "retrieved_at": fetched_at}, fh, indent=1)
                fh.write("\n")
            print("  downloaded %s (%d bytes, sha256 verified)" % (url, received))
            return
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            last_error = exc
            if os.path.exists(part):
                os.remove(part)
            if attempt < attempts:
                print("  download attempt %d/%d failed (%s); retrying in %ds"
                      % (attempt, attempts, exc, attempt * 2), file=sys.stderr)
                time.sleep(attempt * 2)
    raise SystemExit(
        "could not download %s after %d attempts: %s\n"
        "Pass --archive /path/to/%s to build from a local copy."
        % (url, attempts, last_error, archive_name())
    )


def ensure_archive(cache_dir, refresh=False, archive=None):
    """Return a verified path to the release zip."""
    if archive:
        archive = os.path.abspath(archive)
        if not os.path.isfile(archive):
            raise SystemExit("--archive file not found: %s" % archive)
        actual = sha256_file(archive)
        if actual != SOURCE["sha256"]:
            raise SystemExit(
                "archive %s has sha256 %s, expected %s (release %s)"
                % (archive, actual, SOURCE["sha256"], SOURCE["release"])
            )
        print("using local archive %s (sha256 verified)" % archive)
        return archive

    dest = os.path.join(cache_dir, archive_name())
    if os.path.isfile(dest) and not refresh:
        actual = sha256_file(dest)
        if actual == SOURCE["sha256"]:
            print("using cached archive %s (sha256 verified)" % dest)
            return dest
        print("  cached archive has sha256 %s, expected %s; re-downloading"
              % (actual, SOURCE["sha256"]), file=sys.stderr)
    elif refresh and os.path.exists(dest):
        os.remove(dest)
    print("fetching %s (%s, %.1f MB) - cached after this run ..."
          % (SOURCE["asset"], SOURCE["release"], SOURCE["bytes"] / 1e6))
    download_archive(SOURCE["url"], dest, SOURCE["sha256"])
    return dest


def fetch_timestamp(archive):
    """Best-effort retrieval time for the provenance record."""
    meta = archive + ".fetched.json"
    if os.path.isfile(meta):
        try:
            with open(meta, encoding="utf-8") as fh:
                return json.load(fh).get("retrieved_at")
        except (OSError, ValueError):
            pass
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(os.path.getmtime(archive)))
    except OSError:
        return None


def ensure_region_files(archive, cache_dir):
    """Extract and verify the 18 region files; return a map code -> local path."""
    regions_dir = os.path.join(cache_dir, "regions", "hires")
    os.makedirs(regions_dir, exist_ok=True)
    paths = {}
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        missing = [rel for rel, _, _ in REGION_FILES.values() if rel not in names]
        if missing:
            raise SystemExit(
                "release archive %s is missing %d expected region file(s): %s"
                % (archive, len(missing), ", ".join(sorted(missing)[:3]))
            )
        for code, (rel, size, digest) in REGION_FILES.items():
            target = os.path.join(regions_dir, os.path.basename(rel))
            if os.path.isfile(target) and os.path.getsize(target) == size \
                    and sha256_file(target) == digest:
                paths[code] = target
                continue
            data = zf.read(rel)
            if len(data) != size or sha256_bytes(data) != digest:
                raise SystemExit(
                    "extracted %s does not match its pinned size/sha256; the release "
                    "archive may be corrupt - delete the cache and retry" % rel
                )
            with open(target, "wb") as fh:
                fh.write(data)
            paths[code] = target
    print("  %d region files verified (sha256) in %s"
          % (len(paths), os.path.relpath(regions_dir, cache_dir)))
    return paths


def ensure_provdist_files(archive, cache_dir):
    """Extract the 88 province/district files used by the coverage layer.

    The release archive is already verified against its pinned SHA-256, and the
    88 files come from that same archive; per-file hashes are recorded in
    geo-sources.json so the coverage layer is auditable too.
    """
    target_dir = os.path.join(cache_dir, "provdists", "hires")
    os.makedirs(target_dir, exist_ok=True)
    entries = []
    with zipfile.ZipFile(archive) as zf:
        names = sorted(n for n in zf.namelist() if n.startswith(PROVDIST_PREFIX))
        if not names:
            raise SystemExit("release archive has no %s files" % PROVDIST_PREFIX)
        for rel in names:
            data = zf.read(rel)
            digest = sha256_bytes(data)
            target = os.path.join(target_dir, os.path.basename(rel))
            if not (os.path.isfile(target) and os.path.getsize(target) == len(data)
                    and sha256_file(target) == digest):
                with open(target, "wb") as fh:
                    fh.write(data)
            entries.append({
                "file": os.path.basename(rel),
                "bytes": len(data),
                "sha256": digest,
            })
    print("  %d province/district files extracted (sha256 recorded) in %s"
          % (len(entries), os.path.relpath(target_dir, cache_dir)))
    return entries


# ---------------------------------------------------------------------------
# TopoJSON decoding and geometry
# ---------------------------------------------------------------------------
def decode_topology(path):
    """Return (arcs, features) with arcs as lists of (lon, lat)."""
    with open(path, encoding="utf-8") as fh:
        topo = json.load(fh)
    transform = topo.get("transform")
    arcs = []
    for delta_arc in topo["arcs"]:
        points = []
        x = y = 0
        for dx, dy in delta_arc:
            x += dx
            y += dy
            points.append((x, y))
        if transform:
            sx, sy = transform["scale"]
            tx, ty = transform["translate"]
            points = [(x * sx + tx, y * sy + ty) for x, y in points]
        arcs.append(points)
    objects = topo["objects"]
    if len(objects) != 1:
        raise SystemExit("unexpected TopoJSON: %d objects in %s" % (len(objects), path))
    obj = objects[list(objects)[0]]
    geometries = obj["geometries"] if obj.get("type") == "GeometryCollection" else [obj]
    features = []
    for geometry in geometries:
        kind = geometry["type"]
        if kind == "Polygon":
            polygons = [geometry["arcs"]]
        elif kind == "MultiPolygon":
            polygons = geometry["arcs"]
        else:
            raise SystemExit("unexpected TopoJSON geometry %r in %s" % (kind, path))
        properties = geometry.get("properties") or {}
        features.append((properties, polygons))
    return arcs, features


def compose_ring(arcs, arc_indexes):
    """Concatenate topojson arcs (following +/- orientation) into one closed ring."""
    points = []
    for index in arc_indexes:
        segment = arcs[index] if index >= 0 else list(reversed(arcs[-index - 1]))
        points.extend(segment if not points else segment[1:])
    return points


def ring_area(points):
    """Unsigned planar polygon area (absolute shoelace)."""
    total = 0.0
    count = len(points)
    for i in range(count):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % count]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def simplify_douglas_peucker(points, tolerance):
    """Douglas-Peucker; keeps the first and last point (required by arcs)."""
    count = len(points)
    if count < 3:
        return points
    keep = [False] * count
    keep[0] = keep[-1] = True
    stack = [(0, count - 1)]
    while stack:
        first, last = stack.pop()
        ax, ay = points[first]
        bx, by = points[last]
        dx = bx - ax
        dy = by - ay
        segment_sq = dx * dx + dy * dy
        worst = -1.0
        worst_index = -1
        for i in range(first + 1, last):
            px, py = points[i]
            if segment_sq == 0:
                distance = math.hypot(px - ax, py - ay)
            else:
                t = ((px - ax) * dx + (py - ay) * dy) / segment_sq
                if t < 0.0:
                    t = 0.0
                elif t > 1.0:
                    t = 1.0
                distance = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
            if distance > worst:
                worst = distance
                worst_index = i
        if worst > tolerance and worst_index != -1:
            keep[worst_index] = True
            stack.append((first, worst_index))
            stack.append((worst_index, last))
    return [point for point, kept in zip(points, keep) if kept]


def mercator_y(latitude):
    return -math.log(math.tan(math.pi / 4.0 + math.radians(latitude) / 2.0)) * 180.0 / math.pi


def area_centroid(points):
    """Area-weighted centroid; falls back to the vertex mean for degenerate rings."""
    twice_area = 0.0
    cx = 0.0
    cy = 0.0
    count = len(points)
    for i in range(count):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % count]
        cross = x1 * y2 - x2 * y1
        twice_area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if abs(twice_area) < 1e-9:
        return (sum(p[0] for p in points) / count, sum(p[1] for p in points) / count)
    factor = 1.0 / (3.0 * twice_area)
    return (cx * factor, cy * factor)


def point_in_ring(point, ring):
    """Ray-casting test (the ring may repeat its first point at the end)."""
    x, y = point
    inside = False
    count = len(ring)
    j = count - 1
    for i in range(count):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            x_cross = (xj - xi) * (y - yi) / (yj - yi) + xi
            if x < x_cross:
                inside = not inside
        j = i
    return inside


def label_point(ring):
    """A point inside the ring, for a future region label overlay.

    Uses the area centroid where that is inside; for concave shapes (e.g.
    Quezon, the largest ring of CALABARZON) falls back to the widest interior
    interval of a scanline through the centroid.
    """
    centroid = area_centroid(ring)
    if point_in_ring(centroid, ring):
        return centroid
    mean = (sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring))
    if point_in_ring(mean, ring):
        return mean
    y = centroid[1]
    crossings = []
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y):
            crossings.append((xj - xi) * (y - yi) / (yj - yi) + xi)
        j = i
    crossings.sort()
    best_width = -1.0
    best_midpoint = mean
    for k in range(0, len(crossings) - 1, 2):
        width = crossings[k + 1] - crossings[k]
        if width > best_width:
            best_width = width
            best_midpoint = ((crossings[k] + crossings[k + 1]) / 2.0, y)
    return best_midpoint


def format_ring(points):
    parts = ["M%.1f,%.1f" % (points[0][0], points[0][1])]
    parts.extend("L%.1f,%.1f" % (p[0], p[1]) for p in points[1:])
    return "".join(parts) + "Z"


def format_ring_relative(points):
    """Compact relative path data: M x y l dx dy dx dy ... Z (integer).

    The coverage layer is a filled overlay, not a labelled choropleth, so
    integer coordinates are visually indistinguishable at this render size and
    shrink the inlined path data by about a third.
    """
    points = [(round(p[0]), round(p[1])) for p in points]
    parts = ["M%d %d" % points[0]]
    if len(points) > 1:
        tokens = []
        prev_x, prev_y = points[0]
        for x, y in points[1:]:
            dx, dy = x - prev_x, y - prev_y
            prev_x, prev_y = x, y
            tokens.append("%d%s%d" % (dx, " " if dy >= 0 else "", dy))
        parts.append("l" + " ".join(tokens).replace(" -", "-"))
    return "".join(parts) + "Z"


def compute_frame(topologies):
    """Frame extent from rings that are big enough to matter (raw lon/lat).

    Returns the exact projection parameters shared by the region layer and the
    coverage layer, so both line up in the same viewBox.
    """
    min_x = min_y = math.inf
    max_x = max_y = -math.inf
    for code in CODES:
        arcs, features = topologies[code]
        for _properties, polygons in features:
            for polygon in polygons:
                ring = compose_ring(arcs, polygon[0])  # outer ring only
                if ring_area(ring) * KM2_PER_DEG2 < EXTENT_MIN_RING_AREA_KM2:
                    continue
                for lon, lat in ring:
                    y = mercator_y(lat)
                    if lon < min_x:
                        min_x = lon
                    if lon > max_x:
                        max_x = lon
                    if y < min_y:
                        min_y = y
                    if y > max_y:
                        max_y = y
    if not (math.isfinite(min_x) and math.isfinite(max_y)):
        raise SystemExit("no polygons found - the source files look empty")
    scale = WIDTH / (max_x - min_x)
    return {
        "lon_min": min_x,
        "mercator_min": min_y,
        "lon_max": max_x,
        "mercator_max": max_y,
        "scale": scale,
        "height": (max_y - min_y) * scale,
    }


def project_point(lon, lat, frame):
    return ((lon - frame["lon_min"]) * frame["scale"],
            (mercator_y(lat) - frame["mercator_min"]) * frame["scale"])


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------
def build_document(topologies, detail_codes=(), frame=None):
    """Turn decoded topologies into (geo document, build metadata).

    `topologies` maps region code -> (arcs, features) as decoded by
    decode_topology. `detail_codes` optionally keeps per-province paths for the
    listed regions (used by the render-proof script; not written to geo.json).
    `frame` is the projection frame from compute_frame(); computed when omitted.
    """
    if frame is None:
        frame = compute_frame(topologies)
    min_x = frame["lon_min"]
    min_y = frame["mercator_min"]
    scale = frame["scale"]
    height = frame["height"]

    def project(lon, lat):
        return project_point(lon, lat, frame)

    def clamp_unit(value):
        # Keep -0.0 out of the path data and absorb float dust at the frame edge.
        if -0.05 < value < 0.05:
            return 0.0
        return value

    # 2. Project + simplify each referenced arc once (topology-aware), then
    #    compose the province rings out of the simplified arcs.
    region_docs = {}
    region_meta = {}
    for code in CODES:
        arcs, features = topologies[code]
        simplified = {}

        def simplified_arc(index):
            """Simplified, projected form of topojson arc `index` (as stored)."""
            if index not in simplified:
                projected = [project(lon, lat) for lon, lat in arcs[index]]
                simplified[index] = simplify_douglas_peucker(projected, DP_TOLERANCE)
            return simplified[index]

        def simplified_ring(ring_indexes):
            points = []
            for i, index in enumerate(ring_indexes):
                # Simplify the arc in its stored direction, then reverse for
                # negative references: shared borders stay identical between
                # the provinces that use them.
                segment = simplified_arc(abs(index) - 1 if index < 0 else index)
                if index < 0:
                    segment = list(reversed(segment))
                points.extend(segment if i == 0 else segment[1:])
            return points

        rings = []
        province_details = []
        for properties, polygons in features:
            province_rings = []
            for polygon in polygons:
                points = simplified_ring(polygon[0])  # outer ring only; holes dropped
                area = ring_area(points[:-1] if points and points[0] == points[-1] else points) \
                    if len(points) >= 4 else 0.0
                if area < MIN_RING_AREA:
                    continue
                rings.append((area, points))
                province_rings.append((area, points))
            if code in detail_codes and province_rings:
                province_rings.sort(key=lambda item: -item[0])
                province_details.append({
                    "adm2_psgc": properties.get("adm2_psgc"),
                    "name": properties.get("adm2_en") or str(properties.get("adm2_psgc")),
                    "area": sum(area for area, _points in province_rings),
                    "path": "".join(format_ring(points) for _area, points in province_rings),
                    "label": label_point(province_rings[0][1]),
                })
        if not rings:
            raise SystemExit("region %s produced no rings - check the source" % code)
        rings.sort(key=lambda item: -item[0])
        path = "".join(format_ring(points) for _area, points in rings)
        label_x, label_y = label_point(rings[0][1])
        xs = [p[0] for _area, points in rings for p in points]
        ys = [p[1] for _area, points in rings for p in points]
        name, short, full, island = META[code]
        region_docs[code] = {
            "name": name,
            "short": short,
            "full": full,
            "island": island,
            "path": path,
            "label_x": round(clamp_unit(label_x), 1),
            "label_y": round(clamp_unit(label_y), 1),
            "bbox": [round(clamp_unit(min(xs)), 1), round(clamp_unit(min(ys)), 1),
                     round(clamp_unit(max(xs)), 1), round(clamp_unit(max(ys)), 1)],
            "rings": len(rings),
        }
        region_meta[code] = {
            "features": [
                {"adm2_psgc": properties.get("adm2_psgc"),
                 "name": properties.get("adm2_en") or str(properties.get("adm2_psgc"))}
                for properties, _polygons in features
            ],
            "rings": len(rings),
            "points": sum(len(points) for _area, points in rings),
            "path_bytes": len(path),
        }
        if code in detail_codes:
            province_details.sort(key=lambda item: -item["area"])
            for detail in province_details:
                detail.pop("area")
                detail["label"] = [round(detail["label"][0], 1),
                                   round(detail["label"][1], 1)]
            region_meta[code]["provinces"] = province_details

    document = {
        "width": round(WIDTH, 1),
        "height": round(height, 1),
        "regions": region_docs,
    }
    extent = {
        "lon_min": round(min_x, 6),
        "lon_max": round(frame["lon_max"], 6),
        "lat_min": round(inverse_mercator(frame["mercator_max"]), 6),
        "lat_max": round(inverse_mercator(min_y), 6),
        "scale_units_per_degree_lon": round(scale, 6),
    }
    return document, region_meta, extent


def display_lgu_name(name):
    """Human display name for a municipality/city."""
    name = (name or "").strip()
    if name.startswith("City of "):
        return name[len("City of "):]
    return name


def province_registry(topologies):
    """Map padded adm2 PSGC -> {name, region_psgc} from the region topologies."""
    registry = {}
    for code in CODES:
        _arcs, features = topologies[code]
        for properties, _polygons in features:
            adm2 = properties.get("adm2_psgc")
            if adm2 in (None, ""):
                continue
            name = properties.get("adm2_en") or ""
            if code == "1300000000":
                name = "Metro Manila"
            elif "Not a Province" in name:
                name = name.split(" (")[0]
            registry[str(adm2).zfill(10)] = {
                "name": name,
                "region_psgc": str(properties.get("adm1_psgc") or code).zfill(10),
            }
    return registry


def build_coverage_document(provdist_entries, frame, provdist_dir, prov_registry=None):
    """Build the LGU coverage layer: one simplified polygon set per LGU.

    The layer is drawn only as a filled overlay when the map is filtered by
    distribution utility, so it is simplified more aggressively than the region
    choropleth and stored as relative integer path data.
    """
    prov_registry = prov_registry or {}
    lgus = {}
    duplicates = []
    skipped = []
    points_total = 0
    min_ring_units2 = LGU_MIN_RING_AREA_KM2 / KM2_PER_DEG2 * frame["scale"] ** 2
    for entry in provdist_entries:
        source_path = os.path.join(provdist_dir, entry["file"])
        arcs, features = decode_topology(source_path)
        simplified = {}
        projected_arcs = {}

        def projected_arc(index):
            if index not in projected_arcs:
                projected_arcs[index] = [project_point(lon, lat, frame)
                                         for lon, lat in arcs[index]]
            return projected_arcs[index]

        def simplified_arc(index):
            if index not in simplified:
                simplified[index] = simplify_douglas_peucker(
                    projected_arc(index), LGU_DP_TOLERANCE)
            return simplified[index]

        def compose(ring_indexes, segment_for):
            points = []
            for i, index in enumerate(ring_indexes):
                segment = segment_for(abs(index) - 1 if index < 0 else index)
                if index < 0:
                    segment = list(reversed(segment))
                points.extend(segment if i == 0 else segment[1:])
            return points

        def ring_points(ring_indexes):
            return compose(ring_indexes, simplified_arc)

        for properties, polygons in features:
            adm3 = properties.get("adm3_psgc")
            if adm3 in (None, ""):
                skipped.append("feature without adm3_psgc in %s" % entry["file"])
                continue
            key = str(adm3).zfill(10)
            rings = []
            for polygon in polygons:
                points = ring_points(polygon[0])
                if len(points) < 4:
                    continue
                clean = points[:-1] if points[0] == points[-1] else points
                area_units2 = ring_area(clean)
                if area_units2 < min_ring_units2:
                    continue
                rings.append((area_units2, points))
            if not rings:
                # Tiny islands can collapse under the overlay tolerance (e.g.
                # Limasawa simplifies to a 3-point sliver). Retry the largest
                # original ring for this LGU, unsimplified, and keep it only if
                # it is big enough to see.
                raw_rings = []
                for polygon in polygons:
                    points = compose(polygon[0], projected_arc)
                    if len(points) < 4:
                        continue
                    clean = points[:-1] if points[0] == points[-1] else points
                    raw_rings.append((ring_area(clean), points))
                raw_rings.sort(key=lambda item: -item[0])
                if raw_rings and raw_rings[0][0] >= min_ring_units2:
                    rings = [raw_rings[0]]
            if not rings:
                skipped.append("no ring for %s (%s)" % (properties.get("adm3_en"), key))
                continue
            rings.sort(key=lambda item: -item[0])
            path_data = "".join(format_ring_relative(points) for _area, points in rings)
            if key in lgus:
                # Keep the largest depiction if an LGU appears in two files.
                duplicates.append(key)
                if len(path_data) <= len(lgus[key]["path"]):
                    continue
                points_total -= lgus[key]["_points"]
            region_psgc = str(properties.get("adm1_psgc")).zfill(10)
            province_psgc = str(properties.get("adm2_psgc")).zfill(10)
            ring_points_total = sum(len(points) for _area, points in rings)
            lgus[key] = {
                "name": display_lgu_name(properties.get("adm3_en")),
                "province_psgc": province_psgc,
                "path": path_data,
                "_points": ring_points_total,
            }
            points_total += ring_points_total
    provinces = {}
    for key, item in lgus.items():
        province = prov_registry.get(item["province_psgc"], {})
        if province:
            provinces[item["province_psgc"]] = province
    for item in lgus.values():
        item.pop("_points", None)
    document = {
        "layer": "lgu-coverage",
        "width": round(WIDTH, 1),
        "height": round(frame["height"], 1),
        "tolerance_units": LGU_DP_TOLERANCE,
        "min_ring_area_km2": LGU_MIN_RING_AREA_KM2,
        "path_format": "relative integer path data (M x y, then l dx dy pairs, Z)",
        "note": "Municipality/city polygons are used only as a coverage overlay "
                "for the provider filter; the region choropleth in geo.json is "
                "the canonical geometry for rates.",
        "provinces": {key: provinces[key] for key in sorted(provinces)},
        "lgus": {key: lgus[key] for key in sorted(lgus)},
    }
    stats = {
        "lgus": len(lgus),
        "provinces": len(provinces),
        "points": points_total,
        "path_bytes": sum(len(item["path"]) for item in lgus.values()),
        "duplicates": duplicates,
        "skipped": skipped,
    }
    return document, stats


def inverse_mercator(y):
    """Inverse of mercator_y (which stores -mercator(lat))."""
    return math.degrees(2.0 * math.atan(math.exp(math.radians(-y))) - math.pi / 2.0)


# ---------------------------------------------------------------------------
# Reporting / writing
# ---------------------------------------------------------------------------
def existing_point_counts():
    """Point counts of the geo.json currently on disk (for the before/after report)."""
    if not os.path.isfile(GEO_OUT):
        return None
    try:
        with open(GEO_OUT, encoding="utf-8") as fh:
            current = json.load(fh)
        regions = current.get("regions", {})
        counts = {code: region["path"].count("M") + region["path"].count("L")
                  for code, region in regions.items()}
        return counts
    except (OSError, ValueError, KeyError):
        return None


def report(document, region_meta, before_counts):
    total = sum(meta["points"] for meta in region_meta.values())
    print("")
    print("  region      short       points before -> after   rings   path bytes")
    print("  %s" % ("-" * 74))
    for code in CODES:
        meta = region_meta[code]
        before = before_counts.get(code) if before_counts else None
        change = ("%4d -> %4d" % (before, meta["points"])) if before is not None \
            else "     -> %4d" % meta["points"]
        print("  %-11s %-10s %17s %7d %11d"
              % (code, META[code][1], change, meta["rings"], meta["path_bytes"]))
    print("  %s" % ("-" * 74))
    print("  %-11s %-10s %17s %7d %11d"
          % ("all", "", ("%4d -> %4d" % (sum(before_counts.values()), total))
             if before_counts else ("     -> %4d" % total),
             sum(meta["rings"] for meta in region_meta.values()),
             sum(meta["path_bytes"] for meta in region_meta.values())))
    print("")
    print("  viewBox: %.1f x %.1f" % (document["width"], document["height"]))
    print("  geo.json: %d bytes (%.1f KB), %d points, %d regions"
          % (os.path.getsize(GEO_OUT), os.path.getsize(GEO_OUT) / 1024.0,
             total, len(document["regions"])))


def sources_record(document, region_meta, extent, archive,
                   coverage_doc=None, coverage_stats=None, provdist_entries=None):
    with open(GEO_OUT, "rb") as fh:
        geo_bytes = fh.read()
    coverage_bytes = b""
    if coverage_doc is not None:
        coverage_bytes = json.dumps(coverage_doc, separators=(",", ":")).encode("utf-8")
        coverage_stats = dict(coverage_stats or {})
    total = sum(meta["points"] for meta in region_meta.values())
    tolerance_deg = DP_TOLERANCE / (WIDTH / (extent["lon_max"] - extent["lon_min"]))
    lgu_tolerance_deg = LGU_DP_TOLERANCE / (WIDTH / (extent["lon_max"] - extent["lon_min"]))
    regions = {}
    for code in CODES:
        meta = region_meta[code]
        regions[code] = {
            "name": META[code][0],
            "short": META[code][1],
            "island": META[code][3],
            "features": meta["features"],
            "rings": meta["rings"],
            "points": meta["points"],
        }
    output = {
        "geo_json": {
            "path": RELATIVE_GEO_OUT,
            "sha256": sha256_bytes(geo_bytes),
            "bytes": len(geo_bytes),
            "width": document["width"],
            "height": document["height"],
            "regions": len(document["regions"]),
            "points": total,
            "region_stats": {
                code: {
                    "rings": region_meta[code]["rings"],
                    "points": region_meta[code]["points"],
                    "bbox": document["regions"][code]["bbox"],
                    "label_x": document["regions"][code]["label_x"],
                    "label_y": document["regions"][code]["label_y"],
                }
                for code in CODES
            },
        },
    }
    if coverage_doc is not None:
        output["coverage_geo_json"] = {
            "path": RELATIVE_LGU_GEO_OUT,
            "sha256": sha256_bytes(coverage_bytes),
            "bytes": len(coverage_bytes),
            "width": coverage_doc["width"],
            "height": coverage_doc["height"],
            "lgus": coverage_stats.get("lgus"),
            "provinces": coverage_stats.get("provinces"),
            "points": coverage_stats.get("points"),
            "path_bytes": coverage_stats.get("path_bytes"),
        }
    return {
        "asset": "geo.json",
        "consumer": "tools/build-map-page.py inlines `path` for each region into "
                    "draft/map-table-prototype.html; the page fetches nothing at runtime.",
        "generated_by": "tools/build-geo.py",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "source": dict(SOURCE),
        "retrieved_at": fetch_timestamp(archive),
        "extent": extent,
        "projection": dict(PROJECTION),
        "simplification": {
            "algorithm": "Douglas-Peucker applied to TopoJSON arcs (shared borders "
                         "simplified once and reused, so provinces stay gap-free)",
            "tolerance_units": DP_TOLERANCE,
            "tolerance_degrees": round(tolerance_deg, 6),
            "min_ring_area_units2": MIN_RING_AREA,
            "min_ring_area_km2": round(MIN_RING_AREA / (WIDTH / (extent["lon_max"] - extent["lon_min"])) ** 2 * KM2_PER_DEG2, 2),
            "extent_min_ring_area_km2": EXTENT_MIN_RING_AREA_KM2,
            "inner_rings": "dropped (only outer rings are drawn, as before)",
            "render_scale_note": "0.6 units is 0.54 px at a 900 px-wide render "
                                 "(the map card renders at ~660 px, ~406 px of map).",
        },
        "coverage_layer": {
            "asset": RELATIVE_LGU_GEO_OUT,
            "consumer": "tools/build-map-page.py inlines the LGU paths into the page's "
                        "provider-coverage lens; the page fetches nothing at runtime.",
            "what": "Municipality/city polygons (adm3) for all 1,6xx LGUs in PSGC 3Q "
                    "2026, used as a filled coverage overlay when the map is filtered "
                    "by distribution utility.",
            "source_files": PROVDIST_PREFIX + "municities-provdist-<adm2>.topo.0.1.json "
                            "(%d files, same pinned release archive)" % len(provdist_entries or []),
            "source_files_sha256": provdist_entries or [],
            "simplification": {
                "algorithm": "Douglas-Peucker on TopoJSON arcs, applied per province/"
                             "district topology so shared borders stay gap-free",
                "tolerance_units": LGU_DP_TOLERANCE,
                "tolerance_degrees": round(lgu_tolerance_deg, 6),
                "min_ring_area_km2": LGU_MIN_RING_AREA_KM2,
                "path_format": coverage_doc["path_format"] if coverage_doc else None,
            },
            "stats": coverage_stats or {},
        },
        "output": output,
        "regions": regions,
        "supersedes": dict(SUPERSEDES),
        "evaluated_alternatives": [dict(MEDRES_EVALUATED)],
        "verify": [
            "python3 tools/build-geo.py --archive <topojson-hires.zip>  # rebuild",
            "sha256sum draft/assets/geo.json draft/assets/coverage-geo.json  # compare to output.sha256",
        ],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Rebuild draft/assets/geo.json and draft/assets/coverage-geo.json "
                    "from pinned philippines-json-maps high-resolution geometry."
    )
    parser.add_argument("--cache-dir", default=default_cache_dir(),
                        help="where the release archive/region files are cached "
                             "(default: $GEO_BUILD_CACHE or %(default)s)")
    parser.add_argument("--archive", default=None,
                        help="use this local topojson-hires.zip instead of downloading")
    parser.add_argument("--refresh", action="store_true",
                        help="re-download the release archive even if cached")
    args = parser.parse_args()

    cache_dir = os.path.abspath(os.path.expanduser(args.cache_dir))
    print("build-geo: %s %s (PSGC %s)"
          % (SOURCE["name"], SOURCE["release"], SOURCE["psgc"]))
    archive = ensure_archive(cache_dir, refresh=args.refresh, archive=args.archive)
    paths = ensure_region_files(archive, cache_dir)

    topologies = {code: decode_topology(paths[code]) for code in CODES}
    frame = compute_frame(topologies)
    document, region_meta, extent = build_document(topologies, frame=frame)
    geo_json = json.dumps(document, separators=(",", ":"))
    before_counts = existing_point_counts()
    with open(GEO_OUT, "w", encoding="utf-8") as fh:
        fh.write(geo_json)

    provdist_entries = ensure_provdist_files(archive, cache_dir)
    coverage_doc, coverage_stats = build_coverage_document(
        provdist_entries, frame, os.path.join(cache_dir, "provdists", "hires"),
        province_registry(topologies))
    coverage_json = json.dumps(coverage_doc, separators=(",", ":"))
    with open(LGU_GEO_OUT, "w", encoding="utf-8") as fh:
        fh.write(coverage_json)

    sources = sources_record(document, region_meta, extent, archive,
                             coverage_doc=coverage_doc,
                             coverage_stats=coverage_stats,
                             provdist_entries=provdist_entries)
    with open(SOURCES_OUT, "w", encoding="utf-8") as fh:
        json.dump(sources, fh, indent=1, ensure_ascii=False)
        fh.write("\n")
    report(document, region_meta, before_counts)
    print("  coverage layer: %d LGUs in %d provinces, %d points, %d bytes path data"
          % (coverage_stats["lgus"], coverage_stats["provinces"],
             coverage_stats["points"], coverage_stats["path_bytes"]))
    if coverage_stats["duplicates"]:
        print("  duplicate adm3 features merged: %s"
              % ", ".join(coverage_stats["duplicates"][:5]))
    if coverage_stats["skipped"]:
        print("  skipped features: %d (first: %s)"
              % (len(coverage_stats["skipped"]), coverage_stats["skipped"][0]))
    print("  sha256 geo.json          %s" % sha256_bytes(geo_json.encode("utf-8")))
    print("  sha256 coverage-geo.json %s" % sha256_bytes(coverage_json.encode("utf-8")))
    print("  wrote %s and %s"
          % (RELATIVE_GEO_OUT, RELATIVE_SOURCES_OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
