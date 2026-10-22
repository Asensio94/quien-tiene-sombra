"""France: IRIS outlines (IGN), median disposable income (INSEE Filosofi) and residents (census).

The IRIS is the French counterpart of the Spanish census section: about 2,000 residents,
drawn by INSEE for the census. Filosofi gives the median disposable income per consumption
unit of each IRIS, after taxes and benefits; the census gives its residents. IRIS with too
few tax households are left blank by INSEE ("ns", "nd"): they keep their residents but no
income, and drop out of the ranking like the Spanish sections without income.
"""
from __future__ import annotations

import zipfile
from functools import lru_cache

import geopandas as gpd
import pandas as pd
import requests

from . import config

TIMEOUT = 300


def _cached(name: str, url: str, **params):
    path = config.CACHE_DIR / "insee" / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, params=params or None, timeout=TIMEOUT)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path


def _zipped_csv(path, usecols) -> pd.DataFrame:
    with zipfile.ZipFile(path) as z:  # the data file, not the meta_… dictionary next to it
        name = next(n for n in z.namelist() if n.lower().endswith(".csv") and "meta" not in n.lower())
        return pd.read_csv(z.open(name), sep=";", dtype=str, usecols=usecols)


# --- Outlines ------------------------------------------------------------------------------

def iris(city: config.City) -> gpd.GeoDataFrame:
    """IRIS polygons of one city, in the project CRS, indexed by IRIS code, with the
    arrondissement or municipality code as `district`."""
    codes = ",".join(f"'{c}'" for c in city.codes)
    path = _cached(f"iris_{city.slug}.geojson", config.IRIS_WFS, service="WFS", version="2.0.0",
                   request="GetFeature", typeNames=config.IRIS_LAYER, outputFormat="application/json",
                   count=10000, CQL_FILTER=f"code_insee IN ({codes})",
                   propertyName="code_iris,code_insee,type_iris,geometrie")
    gdf = gpd.read_file(path)
    if gdf.empty:
        path.unlink()
        raise ValueError(f"no IRIS for {city.name}")
    gdf = gdf.rename(columns={"code_iris": "IRIS", "code_insee": "district"})
    return gdf.to_crs(config.CRS).set_index("IRIS")[["district", "geometry"]].sort_index()


# --- Income and residents ------------------------------------------------------------------

@lru_cache(maxsize=1)
def _filosofi() -> pd.Series:
    df = _zipped_csv(_cached("filosofi_iris_2021_disp.zip", config.FILOSOFI_URL),
                     ["IRIS", config.FILOSOFI_INCOME])
    return pd.Series(number(df[config.FILOSOFI_INCOME]).values, index=df.IRIS.values)


@lru_cache(maxsize=1)
def _census() -> pd.Series:
    df = _zipped_csv(_cached(f"census_iris_{config.CENSUS_YEAR}.zip", config.CENSUS_URL),
                     ["IRIS", config.CENSUS_POPULATION])
    return pd.Series(number(df[config.CENSUS_POPULATION]).values, index=df.IRIS.values)


def number(s: pd.Series) -> pd.Series:
    """INSEE CSV numbers: decimal comma; "ns" / "nd" / "s" where secret or not significant."""
    return pd.to_numeric(s.str.replace(",", ".", regex=False), errors="coerce")


def by_iris(index: pd.Index) -> pd.DataFrame:
    """Income per consumption unit and residents of the given IRIS (NaN income if secret).
    Census residents are estimates with decimals; they are rounded to whole people."""
    out = pd.DataFrame({"population": _census().reindex(index).round(),
                        "income": _filosofi().reindex(index)}, index=index)
    out.index.name = "IRIS"
    return out
