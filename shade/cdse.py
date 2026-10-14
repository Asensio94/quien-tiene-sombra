"""Copernicus Data Space Ecosystem: find a product by name and download it to the cache.

Searching the catalogue is open; downloading needs a free CDSE account, read from the
CDSE_USER and CDSE_PASSWORD environment variables (GitHub secrets in the workflow).
"""
from __future__ import annotations

import os
import time
import zipfile
from pathlib import Path

import requests

from . import config

TIMEOUT = 300
_token: dict = {}


def find(prefix: str, contains: str = "") -> list[dict]:
    """Products whose name starts with `prefix` (and contains `contains`), newest release first."""
    flt = f"startswith(Name,'{prefix}')"
    if contains:
        flt += f" and contains(Name,'{contains}')"
    r = requests.get(config.CDSE_ODATA, params={"$filter": flt, "$top": 100,
                                                "$select": "Id,Name,ContentLength"}, timeout=60)
    r.raise_for_status()
    return sorted(r.json()["value"], key=lambda p: p["Name"], reverse=True)


def footprint_search(prefix: str, wkt: str) -> list[dict]:
    """Products starting with `prefix` that intersect a WGS84 WKT geometry."""
    flt = (f"startswith(Name,'{prefix}') and "
           f"OData.CSC.Intersects(area=geography'SRID=4326;{wkt}')")
    r = requests.get(config.CDSE_ODATA, params={"$filter": flt, "$top": 100,
                                                "$select": "Id,Name,ContentLength"}, timeout=60)
    r.raise_for_status()
    return r.json()["value"]


def _load_dotenv() -> None:
    """For local runs: KEY=value lines in a .env at the repo root (git-ignored)."""
    path = config.ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"'))


def _access_token() -> str:
    if _token and _token["expires"] > time.time() + 30:
        return _token["access"]
    _load_dotenv()
    user, pwd = os.environ.get("CDSE_USER"), os.environ.get("CDSE_PASSWORD")
    if not user or not pwd:
        raise SystemExit("CDSE_USER and CDSE_PASSWORD are needed to download Copernicus Land data "
                         "(free account at dataspace.copernicus.eu)")
    r = requests.post(config.CDSE_TOKEN_URL, timeout=60, data={
        "grant_type": "password", "client_id": "cdse-public", "username": user, "password": pwd})
    r.raise_for_status()
    j = r.json()
    _token.update(access=j["access_token"], expires=time.time() + j["expires_in"])
    return _token["access"]


def download(product: dict, folder: str) -> Path:
    """Download once into the cache. Multi-file products come zipped and are unpacked; the
    path returned is the single data file (or the folder when there are several)."""
    dest = config.CACHE_DIR / folder / product["Name"]
    done = dest.with_suffix(dest.suffix + ".done")
    if done.exists():
        return Path(done.read_text(encoding="utf-8"))
    dest.parent.mkdir(parents=True, exist_ok=True)
    url = config.CDSE_DOWNLOAD.format(id=product["Id"])
    tmp = dest.with_suffix(".part")
    # The download host redirects to a storage node; requests drops the Authorization header
    # on cross-host redirects, so the redirect is followed by hand.
    with requests.Session() as s:
        s.headers["Authorization"] = f"Bearer {_access_token()}"
        r = s.get(url, allow_redirects=False, timeout=TIMEOUT)
        while r.status_code in (301, 302, 303, 307, 308):
            r = s.get(r.headers["Location"], allow_redirects=False, timeout=TIMEOUT, stream=True)
        if r.status_code != 200:
            r = s.get(url, timeout=TIMEOUT, stream=True)
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    with open(tmp, "rb") as f:
        is_zip = f.read(4) == b"PK\x03\x04"
    if is_zip:
        dest.mkdir(exist_ok=True)
        with zipfile.ZipFile(tmp) as z:
            z.extractall(dest)
        tmp.unlink()
        data = [p for p in dest.rglob("*") if p.is_file()
                and p.suffix.lower() in (".fgb", ".gpkg", ".tif", ".tiff", ".shp")]
        out = data[0] if len(data) == 1 else dest
    else:
        out = dest.with_suffix(_suffix(product["Name"], tmp))
        tmp.replace(out)
    done.write_text(str(out), encoding="utf-8")
    return out


def _suffix(name: str, path: Path) -> str:
    with open(path, "rb") as f:
        magic = f.read(8)
    if magic[:3] == b"fgb":
        return ".fgb"
    if magic[:4] in (b"II*\x00", b"MM\x00*", b"II+\x00"):
        return ".tif"
    if magic[:6] == b"SQLite":
        return ".gpkg"
    return Path(name).suffix or ".bin"
