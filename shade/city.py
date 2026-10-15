"""One city, start to finish: sections × income × shade × heat, and the city's summary."""
from __future__ import annotations

import json
import logging

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from odc.geo.geobox import GeoBox
from odc.geo.geom import BoundingBox
from rasterio.features import rasterize

from . import config, copernicus, ine, insee, landsat, stats

log = logging.getLogger(__name__)
COLUMNS = ["district", "population", "income", "area_ha", "urban_share", "canopy_stl_pct",
           "canopy_tcd_pct", "lst_c", "ranked"]


def area_by_section(secs: gpd.GeoDataFrame, layer: gpd.GeoDataFrame) -> pd.Series:
    """Area (m²) of `layer` inside each section. The layer's polygons must not overlap."""
    if layer.empty:
        return pd.Series(0.0, index=secs.index)
    s_idx, l_idx = secs.sindex.query(layer.geometry.values, predicate="intersects")[::-1]
    a = shapely.area(shapely.intersection(secs.geometry.values[s_idx], layer.geometry.values[l_idx]))
    out = pd.Series(a).groupby(s_idx).sum()
    return pd.Series(out.reindex(range(len(secs)), fill_value=0.0).values, index=secs.index)


def labels(secs: gpd.GeoDataFrame, shape, transform) -> np.ndarray:
    """Raster of section numbers (1..n, 0 outside) on a given grid."""
    return rasterize(((g, i + 1) for i, g in enumerate(secs.geometry.values)),
                     out_shape=shape, transform=transform, fill=0, dtype="int32")


def zonal_mean(values: np.ndarray, lab: np.ndarray, n: int) -> np.ndarray:
    ok = (lab > 0) & np.isfinite(values)
    s = np.bincount(lab[ok], weights=values[ok], minlength=n + 1)[1:]
    c = np.bincount(lab[ok], minlength=n + 1)[1:]
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c > 0, s / c, np.nan)


def income_year_for(city: config.City, es_year: int | None = None) -> int:
    """The income year a city is computed with: the ADRH year asked for in Spain, Filosofi's
    last (and only remaining) vintage in France."""
    return config.FILOSOFI_YEAR if city.country == "FR" else (es_year or config.INCOME_YEAR)


def units(city: config.City, income_year: int) -> gpd.GeoDataFrame:
    """The statistical units of a city (census sections in Spain, IRIS in France), indexed by
    their code, with a `district` column."""
    if city.country == "FR":
        return insee.iris(city)
    secs = ine.sections(city.municipality, config.sections_year(income_year))
    return secs.rename(columns={"CDIS": "district"})


def units_with_income(city: config.City, income_year: int) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    secs = units(city, income_year)
    base = secs.drop(columns="geometry")
    if city.country == "FR":
        return secs, base.join(insee.by_iris(secs.index))
    return secs, base.join(ine.by_section(city.municipality, income_year))


def process(city: config.City, income_year: int = config.INCOME_YEAR) -> tuple[pd.DataFrame, dict]:
    secs, df = units_with_income(city, income_year)
    missing = df.income.isna().sum()
    bbox = tuple(np.round(secs.total_bounds + [-100, -100, 100, 100], -1))
    df["area_ha"] = secs.area / 1e4

    log.info("%s: %d sections (%d without income)", city.name, len(df), missing)

    # Shade from the Street Tree Layer, plus the urban forest that the STL leaves to the
    # Urban Atlas (class 31000): the STL only maps trees over artificial surfaces.
    ua = copernicus.urban_atlas(city.fua, bbox)
    stl = copernicus.street_trees(city.fua, bbox)
    trees = pd.concat([stl, ua[ua.code == config.UA_FOREST][["geometry"]]], ignore_index=True)
    trees = gpd.GeoDataFrame(trees, geometry="geometry", crs=config.CRS)
    df["canopy_stl_pct"] = 100 * area_by_section(secs, trees) / secs.area
    urban = ua[ua.code.astype(str).str.startswith("1")]
    df["urban_share"] = area_by_section(secs, urban) / secs.area

    # Tree Cover Density 2024: per section, and the Restoration Regulation indicator.
    tcd, tf = copernicus.tree_cover_density(bbox)
    lab = labels(secs, tcd.shape, tf)
    df["canopy_tcd_pct"] = zonal_mean(tcd, lab, len(secs))
    urban_mask = rasterize(((g, 1) for g in urban.geometry.values), out_shape=tcd.shape,
                           transform=tf, fill=0, dtype="uint8").astype(bool) & (lab > 0)
    canopy_urban = float(np.nanmean(tcd[urban_mask]))
    canopy_municipality = float(np.nanmean(tcd[lab > 0]))

    # Summer surface temperature.
    gb = GeoBox.from_bbox(BoundingBox(*bbox, crs=config.CRS), resolution=config.LST_RESOLUTION_M,
                          tight=True)
    lst, lst_meta = landsat.median_lst(gb)
    lab30 = labels(secs, gb.shape, gb.affine)
    df["lst_c"] = zonal_mean(lst.values.astype("float32"), lab30, len(secs))

    df["ranked"] = (df.income.notna() & (df.population >= config.MIN_POPULATION)
                    & (df.urban_share >= config.MIN_URBAN_SHARE) & df.lst_c.notna())
    summary = summarise(city, df, income_year)
    summary.update(canopy_urban_tcd_pct=round(canopy_urban, 2),
                   canopy_municipality_tcd_pct=round(canopy_municipality, 2),
                   urban_area_ha=round(float(urban_mask.sum()) * abs(tf.a * tf.e) / 1e4),
                   lst=lst_meta, sections_without_income=int(missing))
    return df[COLUMNS], summary


def summarise(city: config.City, df: pd.DataFrame, income_year: int) -> dict:
    r = df[df.ranked]
    q = stats.income_quintiles(r.income, r.population)
    by_q = {}
    for k in range(1, 6):
        g = r[q == k]
        by_q[k] = {"income": stats.weighted_mean(g.income, g.population),
                   "canopy": stats.weighted_mean(g.canopy_stl_pct, g.population),
                   "canopy_tcd": stats.weighted_mean(g.canopy_tcd_pct, g.population),
                   "lst": stats.weighted_mean(g.lst_c, g.population)}
    rnd = lambda x, d=2: None if x is None or not np.isfinite(x) else round(float(x), d)  # noqa: E731
    return {
        "slug": city.slug, "name": city.name, "country": city.country,
        "municipality": city.municipality, "fua": city.fua,
        "income_year": income_year, "sections": int(len(df)), "ranked": int(len(r)),
        "population": int(df.population.sum()), "population_ranked": int(r.population.sum()),
        "ci_canopy": rnd(stats.concentration_index(r.canopy_stl_pct, r.income, r.population), 3),
        "ci_canopy_tcd": rnd(stats.concentration_index(r.canopy_tcd_pct, r.income, r.population), 3),
        "rho_canopy": rnd(stats.spearman(r.income, r.canopy_stl_pct), 3),
        "rho_lst": rnd(stats.spearman(r.income, r.lst_c), 3),
        "rho_stl_tcd": rnd(stats.spearman(r.canopy_stl_pct, r.canopy_tcd_pct), 3),
        "canopy_pct": rnd(stats.weighted_mean(r.canopy_stl_pct, r.population)),
        "quintiles": {k: {kk: rnd(vv) for kk, vv in v.items()} for k, v in by_q.items()},
        "canopy_gap": rnd(by_q[5]["canopy"] - by_q[1]["canopy"]),
        "lst_gap": rnd(by_q[1]["lst"] - by_q[5]["lst"]),
    }


def save(city: config.City, df: pd.DataFrame, summary: dict) -> None:
    config.SECTIONS_DIR.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    for c, d in (("area_ha", 2), ("urban_share", 3), ("canopy_stl_pct", 2), ("canopy_tcd_pct", 2),
                 ("lst_c", 2), ("income", 0)):
        out[c] = out[c].round(d)
    out["population"] = out.population.astype("Int64")
    out.to_csv(config.SECTIONS_DIR / f"{city.slug}.csv")
    (config.SECTIONS_DIR / f"{city.slug}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
