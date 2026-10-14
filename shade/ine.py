"""INE census sections (boundaries) and household income by section (ADRH)."""
from __future__ import annotations

import io
import json
import zipfile
from collections import Counter
from functools import lru_cache

import geopandas as gpd
import pandas as pd
import requests

from . import config

TIMEOUT = 120
INCOME_TABLE = "Indicadores de renta media y mediana"
DEMOGRAPHY_TABLE = "Indicadores demográficos"


def _get(url: str, **kw) -> requests.Response:
    r = requests.get(url, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


# --- Boundaries ----------------------------------------------------------------------------

def sections_zip(year: int):
    path = config.CACHE_DIR / "ine" / f"seccionado_{year}.zip"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_get(config.SECTIONS_URL.format(year=year)).content)
    return path


def sections(municipality: str, year: int | None = None) -> gpd.GeoDataFrame:
    """Section polygons of one municipality, in the project CRS, indexed by CUSEC."""
    year = year or config.sections_year()
    path = sections_zip(year)
    with zipfile.ZipFile(path) as z:  # 2024 is flat, 2025 has a folder: find the .shp
        shp = next(n for n in z.namelist() if n.lower().endswith(".shp"))
    gdf = gpd.read_file(f"zip://{path}!{shp}", where=f"CUMUN = '{municipality}'",
                        columns=["CUSEC", "CUMUN", "CDIS"])
    if gdf.empty:
        raise ValueError(f"no sections for {municipality} in {year}")
    return gdf.to_crs(config.CRS).set_index("CUSEC")[["CDIS", "geometry"]]


# --- ADRH tables ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _tables() -> list[dict]:
    return _get(f"{config.TEMPUS}/TABLAS_OPERACION/{config.ADRH_OPERATION}").json()


def _province_of(table_id: int) -> str:
    """The ADRH publishes one table per province and indicator group; the name doesn't say
    which province, the rows do. The most common code prefix in the first rows decides: the
    first row alone can mislead (the Balearic table opens with a misfiled Alicante section)."""
    cache = config.CACHE_DIR / "ine" / "adrh_provinces.json"
    known = json.loads(cache.read_text()) if cache.exists() else {}
    if str(table_id) not in known:
        head = _get(config.JAXI_CSV.format(table=table_id), headers={"Range": "bytes=0-30000"}).content
        rows = head.decode("utf-8", "replace").splitlines()[1:-1]
        codes = Counter(r[:2] for r in rows if r[:2].isdigit())
        known[str(table_id)] = codes.most_common(1)[0][0] if codes else ""
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(known, indent=0, sort_keys=True))
    return known[str(table_id)]


def table_id(group: str, province: str) -> int:
    for t in _tables():
        if t["Nombre"].strip() == group and _province_of(t["Id"]) == province:
            return t["Id"]
    raise LookupError(f"no ADRH table '{group}' for province {province}")


def _table(table: int, year: int | None = None, fresh: bool = False) -> pd.DataFrame:
    """One ADRH table. The cached copy is replaced when asked, or when it lacks `year`."""
    path = config.CACHE_DIR / "ine" / f"adrh_{table}.csv"

    def read():
        df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig", encoding_errors="replace")
        # Some tables come in English format despite the /es/ URL: "Period" header, 1,276 and 42.6.
        english = df.columns[4] == "Period"
        df.columns = ["municipality", "district", "section", "indicator", "period", "value"]
        df["number"] = _number(df.value, english)
        return df

    if path.exists() and not fresh:
        df = read()
        if year is None or str(year) in set(df.period):
            return df
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_get(config.JAXI_CSV.format(table=table)).content)
    return read()


def _number(s: pd.Series, english: bool = False) -> pd.Series:
    # Spanish format: 14.105 or 1.234,5; English: 14,105 or 1,234.5; ".." or empty when suppressed.
    if english:
        return pd.to_numeric(s.str.replace(",", "", regex=False), errors="coerce")
    return pd.to_numeric(s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False),
                         errors="coerce")


def by_section(municipality: str, year: int = config.INCOME_YEAR) -> pd.DataFrame:
    """Income per consumption unit and residents of every section of a municipality."""
    prov = municipality[:2]
    frames = {}
    for group, indicator, col in ((INCOME_TABLE, config.INCOME_INDICATOR, "income"),
                                  (DEMOGRAPHY_TABLE, "Población", "population")):
        df = _table(table_id(group, prov), year)
        df = df[df.section.notna() & (df.period == str(year)) & (df.indicator == indicator)
                & df.municipality.str.startswith(municipality)]
        frames[col] = pd.Series(df.number.values, index=df.section.str[:10].values)
    out = pd.DataFrame(frames)
    out.index.name = "CUSEC"
    return out.dropna(subset=["income"])


def latest_income_year() -> int:
    """Last period that the ADRH publishes, read from a small table (Ceuta)."""
    df = _table(table_id(INCOME_TABLE, "51"), fresh=True)
    return int(df.period.dropna().astype(int).max())
