"""Validation against the municipal tree inventories of Madrid, Barcelona, Paris and Lyon.

These cities publish every municipally managed tree with its coordinates. Counting them per
section (IRIS in France) gives an independent measure of shade, made on the ground and one
tree at a time, including the lone street trees the Street Tree Layer misses. Only counts per
unit are kept; the tree points stay in the (git-ignored) cache.

The inventories do not cover the same trees: Madrid and Barcelona list street, square and
park trees; Paris lists street, garden, cemetery and facility trees but not the Bois de
Boulogne and de Vincennes; Lyon publishes street trees only.
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

from . import city as city_mod, config, stats

log = logging.getLogger(__name__)

BCN_CKAN = "https://opendata-ajuntament.barcelona.cat/data/api/3/action/package_show"
BCN_DATASETS = ("arbrat-viari", "arbrat-zona", "arbrat-parcs")  # street, square, park trees
MAD_CKAN = "https://datos.madrid.es/api/3/action/package_show"
MAD_DATASET = "300761-0-arbolado-especies"  # "Arbolado en parques y zonas verdes (detalle)"
PARIS_API = "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/les-arbres"
LYON_WFS = "https://data.grandlyon.com/geoserver/metropole-de-lyon/ows"
LYON_LAYER = "metropole-de-lyon:abr_arbres_alignement.abrarbre"
PALM_GENERA = ("Phoenix", "Washingtonia", "Trachycarpus", "Chamaerops", "Butia", "Livistona",
               "Brahea", "Sabal", "Syagrus")

SOURCES = {
    "madrid": "Inventario de arbolado del Ayuntamiento de Madrid (datos.madrid.es)",
    "barcelona": "Arbrat viari, de zona i de parcs de l'Ajuntament de Barcelona (Open Data BCN)",
    "paris": "Les arbres, Ville de Paris (opendata.paris.fr)",
    "lyon": "Arbres d'alignement de la Métropole de Lyon (data.grandlyon.com)",
}


def _cached(name: str, url: str, **params) -> bytes:
    path = config.CACHE_DIR / "inventory" / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get(url, params=params or None, timeout=600)
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


def _basal_m2(circumference_cm: pd.Series) -> np.ndarray:
    """Trunk cross-section (m²) from the circumference at breast height (cm), as in Madrid."""
    c = pd.to_numeric(circumference_cm, errors="coerce").clip(upper=600)
    return (c ** 2 / (4 * np.pi) / 1e4).fillna(0).values


def paris() -> tuple[gpd.GeoDataFrame, str]:
    meta = requests.get(PARIS_API, timeout=60).json()
    edition = (meta.get("data_processed") or meta.get("metas", {}).get("default", {}).get("modified") or "")[:10]
    raw = _cached(f"paris_les-arbres_{edition or 'latest'}.csv", f"{PARIS_API}/exports/csv",
                  select="genre,circonferenceencm,geo_point_2d", delimiter=";")
    df = pd.read_csv(io.BytesIO(raw), sep=";", encoding="utf-8-sig", dtype=str)
    df = df[~df.genre.fillna("").isin(PALM_GENERA) & df.geo_point_2d.notna()]
    lat, lon = (df.geo_point_2d.str.split(",", expand=True)[i].astype(float) for i in (0, 1))
    pts = gpd.GeoDataFrame({"basal_m2": _basal_m2(df.circonferenceencm)},
                           geometry=gpd.points_from_xy(lon, lat), crs="EPSG:4326")
    return pts.to_crs(config.CRS), edition


def lyon() -> tuple[gpd.GeoDataFrame, str]:
    raw = _cached("lyon_arbres_alignement.geojson", LYON_WFS, service="WFS", version="2.0.0",
                  request="GetFeature", typeNames=LYON_LAYER, outputFormat="application/json",
                  srsName="EPSG:4326", propertyName="genre,circonference_cm,datereleve,the_geom")
    gdf = gpd.read_file(io.BytesIO(raw))
    gdf = gdf[~gdf.genre.fillna("").isin(PALM_GENERA)]
    edition = str(pd.to_datetime(gdf.datereleve, errors="coerce").max())[:10]
    pts = gpd.GeoDataFrame({"basal_m2": _basal_m2(gdf.circonference_cm)},
                           geometry=gdf.geometry.values, crs=gdf.crs or "EPSG:4326")
    return pts.to_crs(config.CRS), edition


LOADERS = {"madrid": madrid, "barcelona": barcelona, "paris": paris, "lyon": lyon}


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
    df = pd.read_csv(config.SECTIONS_DIR / f"{slug}.csv", dtype={city.unit: str}).set_index(city.unit)
    secs = city_mod.units(city, summary["income_year"])
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
        "slug": slug, "name": city.name, "country": city.country, "source": SOURCES[slug], "edition": edition,
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
