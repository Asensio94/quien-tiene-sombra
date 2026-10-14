"""Validation against the municipal tree inventories of Madrid and Barcelona.

Both cities publish every municipally managed tree with its coordinates. Counting them per
section gives an independent measure of shade, made on the ground and one tree at a time,
including the lone street trees the Street Tree Layer misses. Only counts per section are
kept; the tree points stay in the (git-ignored) cache.
"""
from __future__ import annotations

import io
import json
import logging
import zipfile

import geopandas as gpd
import numpy as np
import pandas as pd
import requests

from . import config, ine, stats

log = logging.getLogger(__name__)

BCN_CKAN = "https://opendata-ajuntament.barcelona.cat/data/api/3/action/package_show"
BCN_DATASETS = ("arbrat-viari", "arbrat-zona", "arbrat-parcs")  # street, square, park trees
MAD_CKAN = "https://datos.madrid.es/api/3/action/package_show"
MAD_DATASET = "300761-0-arbolado-especies"  # "Arbolado en parques y zonas verdes (detalle)"

SOURCES = {
    "madrid": "Inventario de arbolado del Ayuntamiento de Madrid (datos.madrid.es)",
    "barcelona": "Arbrat viari, de zona i de parcs de l'Ajuntament de Barcelona (Open Data BCN)",
}


def _cached(name: str, url: str) -> bytes:
    path = config.CACHE_DIR / "inventory" / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, timeout=600)
        r.raise_for_status()
        path.write_bytes(r.content)
    return path.read_bytes()


def _newest(resources: list[dict], suffix: str) -> dict:
    ok = [r for r in resources if r["url"].lower().endswith(suffix) or r["name"].lower().endswith(suffix)]
    return max(ok, key=lambda r: r.get("last_modified") or r.get("created") or "")


def barcelona() -> tuple[gpd.GeoDataFrame, str]:
    """Street, square and park trees, palms left out (Madrid's inventory has none)."""
    frames, editions = [], set()
    for ds in BCN_DATASETS:
        res = requests.get(BCN_CKAN, params={"id": ds}, timeout=60).json()["result"]["resources"]
        r = _newest(res, ".csv.zip")
        editions.add(r["name"][:7])  # e.g. 2026_3T
        with zipfile.ZipFile(io.BytesIO(_cached(f"bcn_{r['name']}", r["url"]))) as z:
            df = pd.read_csv(z.open(z.namelist()[0]), usecols=["x_etrs89", "y_etrs89", "tipus_element"])
        frames.append(df[~df.tipus_element.str.startswith("PALMERA")])
    df = pd.concat(frames)
    pts = gpd.GeoDataFrame(geometry=gpd.points_from_xy(df.x_etrs89, df.y_etrs89), crs="EPSG:25831")
    q = sorted(editions)[-1]
    return pts.to_crs(config.CRS), f"{q[5]}.º trimestre de {q[:4]}"


def madrid() -> tuple[gpd.GeoDataFrame, str]:
    res = requests.get(MAD_CKAN, params={"id": MAD_DATASET}, timeout=60).json()["result"]["resources"]
    r = _newest([x for x in res if (x.get("format") or "").upper() == "CSV"], ".csv")
    raw = _cached("madrid_" + r["url"].rsplit("/", 1)[-1], r["url"])
    df = pd.read_csv(io.BytesIO(raw), sep=";", encoding="utf-8-sig",
                     usecols=["X", "Y", "ESPECIE", "PERIMETRO"], dtype=str)
    df = df[~df.ESPECIE.fillna("").str.contains("PHOENIX|WASHINGTONIA|PALM|TRACHYCARPUS|CHAMAEROPS",
                                                 case=False)]
    x = pd.to_numeric(df.X.str.replace(",", "."), errors="coerce")
    y = pd.to_numeric(df.Y.str.replace(",", "."), errors="coerce")
    # Trunk cross-section (m²) from the perimeter at breast height (cm): a size measure, so a
    # big plane tree weighs more than a sapling. Capped at 6 m of perimeter against typos.
    p = pd.to_numeric(df.PERIMETRO.str.replace(",", "."), errors="coerce").clip(upper=600)
    ok = x.notna() & y.notna()
    pts = gpd.GeoDataFrame({"basal_m2": (p[ok] ** 2 / (4 * np.pi) / 1e4).fillna(0).values},
                           geometry=gpd.points_from_xy(x[ok], y[ok]), crs="EPSG:25830")
    edition = (r.get("last_modified") or r.get("created") or "")[:10]
    return pts.to_crs(config.CRS), edition


LOADERS = {"madrid": madrid, "barcelona": barcelona}


def trees_per_section(secs: gpd.GeoDataFrame, pts: gpd.GeoDataFrame) -> pd.DataFrame:
    """Trees per section and, where the inventory has trunk sizes, their summed basal area."""
    zones = gpd.GeoDataFrame({"section": secs.index}, geometry=secs.geometry.values, crs=secs.crs)
    j = gpd.sjoin(pts, zones, how="inner", predicate="within")
    out = pd.DataFrame({"trees": j.groupby("section").size()})
    if "basal_m2" in j:
        out["basal_m2"] = j.groupby("section").basal_m2.sum()
    return out.reindex(secs.index).fillna(0)


def validate(slug: str) -> dict:
    city = config.CITY[slug]
    summary = json.loads((config.SECTIONS_DIR / f"{slug}.json").read_text(encoding="utf-8"))
    df = pd.read_csv(config.SECTIONS_DIR / f"{slug}.csv", dtype={"CUSEC": str}).set_index("CUSEC")
    secs = ine.sections(city.municipality, config.sections_year(summary["income_year"]))
    pts, edition = LOADERS[slug]()
    per = trees_per_section(secs, pts).reindex(df.index).fillna(0)
    df["trees"] = per.trees.astype(int)
    df["trees_ha"] = df.trees / df.area_ha
    cols = ["trees", "trees_ha"]
    if "basal_m2" in per:
        df["basal_m2_ha"] = per.basal_m2 / df.area_ha
        cols.append("basal_m2_ha")
    r = df[df.ranked.astype(bool)]
    q = stats.income_quintiles(r.income, r.population)
    by_q = {k: stats.weighted_mean(g.trees_ha, g.population) for k, g in r.groupby(q)}

    out = {
        "slug": slug, "name": city.name, "source": SOURCES[slug], "edition": edition,
        "trees": int(len(pts)), "trees_in_sections": int(df.trees.sum()),
        "rho_stl": round(stats.spearman(r.trees_ha, r.canopy_stl_pct), 3),
        "rho_tcd": round(stats.spearman(r.trees_ha, r.canopy_tcd_pct), 3),
        "ci_trees": round(stats.concentration_index(r.trees_ha, r.income, r.population), 3),
        "ci_canopy": summary["ci_canopy"],
        "trees_ha_q1": round(by_q[1], 1), "trees_ha_q5": round(by_q[5], 1),
        "ci_trees_per_resident": round(stats.concentration_index(
            r.trees / r.population, r.income, r.population), 3),
    }
    if "basal_m2_ha" in df:
        out["rho_basal_stl"] = round(stats.spearman(r.basal_m2_ha, r.canopy_stl_pct), 3)
        out["ci_basal"] = round(stats.concentration_index(r.basal_m2_ha, r.income, r.population), 3)
    config.VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    df[cols].round(3).to_csv(config.VALIDATION_DIR / f"{slug}.csv")
    log.info("%s: %s trees, rho STL %s, rho TCD %s, C trees %s", city.name, out["trees"],
             out["rho_stl"], out["rho_tcd"], out["ci_trees"])
    return out


def run(slugs=tuple(LOADERS)) -> list[dict]:
    path = config.VALIDATION_DIR / "inventories.json"
    old = {x["slug"]: x for x in json.loads(path.read_text(encoding="utf-8"))["results"]} \
        if path.exists() else {}
    for s in slugs:
        old[s] = validate(s)
    results = [old[s] for s in LOADERS if s in old]
    path.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    return results
