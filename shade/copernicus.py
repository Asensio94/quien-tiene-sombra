"""Copernicus Land layers for one city: Street Tree Layer, Urban Atlas and Tree Cover Density."""
from __future__ import annotations

import math
import re

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.merge import merge

from . import cdse, config


def _fua_product(prefix: str, fua: str) -> dict:
    found = cdse.find(prefix, f"_{fua}_")
    if not found:
        raise LookupError(f"no {prefix}* product for {fua}")
    return found[0]  # newest release (R02 > R01, later production date)


def _read(path, bbox) -> gpd.GeoDataFrame:
    gdf = gpd.read_file(path, bbox=tuple(bbox))
    return gdf.to_crs(config.CRS) if gdf.crs and gdf.crs.to_epsg() != 3035 else gdf


def street_trees(fua: str, bbox) -> gpd.GeoDataFrame:
    """STL polygons (tree patches ≥ 500 m² over artificial surfaces) inside `bbox` (EPSG:3035)."""
    path = cdse.download(_fua_product(config.STL_PREFIX, fua), "stl")
    return _read(path, bbox)[["geometry"]]


def urban_atlas(fua: str, bbox) -> gpd.GeoDataFrame:
    """Urban Atlas 2021 polygons inside `bbox`, with a `code` column (5-digit class)."""
    path = cdse.download(_fua_product(config.UA_PREFIX, fua), "urban_atlas")
    gdf = _read(path, bbox)
    col = next(c for c in gdf.columns if re.fullmatch(r"code_20\d\d", c.lower()))
    return gdf.rename(columns={col: "code"})[["code", "geometry"]]


def tcd_tiles(bounds) -> list[str]:
    """Names of the 100 km TCD tiles (E{x}N{y} in units of 100 km, EPSG:3035) covering bounds."""
    x0, y0, x1, y1 = bounds
    return [f"E{e:02d}N{n:02d}"
            for e in range(math.floor(x0 / 1e5), math.floor(x1 / 1e5) + 1)
            for n in range(math.floor(y0 / 1e5), math.floor(y1 / 1e5) + 1)]


def tree_cover_density(bounds) -> tuple[np.ndarray, rasterio.Affine]:
    """TCD 2024 (0–100 %, NaN where no data) mosaicked over bounds, at its native 10 m."""
    paths = []
    for tile in tcd_tiles(bounds):
        found = cdse.find(config.TCD_PREFIX, f"_{tile}_")
        if found:
            paths.append(cdse.download(found[0], "tcd"))
    if not paths:
        raise LookupError(f"no TCD tiles for {bounds}")
    srcs = [rasterio.open(p) for p in paths]
    try:
        arr, transform = merge(srcs, bounds=tuple(bounds), nodata=255)
    finally:
        for s in srcs:
            s.close()
    a = arr[0].astype("float32")
    a[np.isin(arr[0], config.TCD_NODATA)] = np.nan
    return a, transform
