"""Summer land surface temperature from Landsat 8/9 Collection 2 Level-2 (band ST_B10).

Planetary Computer serves the scenes as cloud-optimised GeoTIFFs; `planetary_computer.sign`
adds an anonymous read token, so no key is needed. Each pixel gets the median of its clear
July–August observations over the last few summers; one hot afternoon or one hazy scene
then does not decide a section's place in the ranking.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import planetary_computer
import pystac_client
import xarray as xr
from odc.stac import load

from . import config


def summers(last: int | None = None) -> list[int]:
    """The last config.LST_SUMMERS complete July–August seasons."""
    today = dt.date.today()
    last = last or (today.year if today.month >= 9 else today.year - 1)
    return list(range(last - config.LST_SUMMERS + 1, last + 1))


def search(bbox_wgs84, years: list[int]) -> list:
    cat = pystac_client.Client.open(config.STAC_URL, modifier=planetary_computer.sign_inplace)
    m0, m1 = config.LST_MONTHS
    items = []
    for y in years:
        last_day = 31 if m1 in (1, 3, 5, 7, 8, 10, 12) else 30
        items += cat.search(
            collections=[config.STAC_COLLECTION], bbox=bbox_wgs84,
            datetime=f"{y}-{m0:02d}-01/{y}-{m1:02d}-{last_day}",
            query={"eo:cloud_cover": {"lt": config.LST_MAX_SCENE_CLOUD},
                   "platform": {"in": ["landsat-8", "landsat-9"]}},
        ).item_collection().items
    return items


def _clear(qa: xr.DataArray) -> xr.DataArray:
    q = qa.astype("uint16")
    bad = sum(((q >> b) & 1) for b in config.QA_REJECT_BITS)
    return (bad == 0) & (q != 1)  # bit 0 = fill


def median_lst(geobox, years: list[int] | None = None) -> tuple[xr.DataArray, dict]:
    """Median clear-sky surface temperature (°C) on `geobox`, plus a note of what went in."""
    years = years or summers()
    bbox = geobox.extent.to_crs("EPSG:4326").boundingbox
    items = search((bbox.left, bbox.bottom, bbox.right, bbox.top), years)
    if not items:
        raise RuntimeError("no Landsat scenes for this city and these summers")
    ds = load(items, bands=["lwir11", "qa_pixel"], geobox=geobox, groupby="solar_day",
              resampling={"lwir11": "bilinear", "qa_pixel": "nearest"}, chunks={})
    t = ds.lwir11.where(ds.lwir11 > 0).astype("float32") * config.ST_SCALE + config.ST_OFFSET - 273.15
    t = t.where(_clear(ds.qa_pixel))
    n = t.notnull().sum("time")
    med = t.median("time", skipna=True).where(n >= config.LST_MIN_CLEAR).compute()
    meta = {"summers": years, "scenes": len(items), "days": int(ds.sizes["time"]),
            "clear_median": int(np.nanmedian(n.where(n > 0).values))}
    return med, meta
