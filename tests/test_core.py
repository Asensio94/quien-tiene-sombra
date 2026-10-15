import geopandas as gpd
import numpy as np
from shapely.geometry import box

from shade import city, config, copernicus, web


def test_tcd_tiles_cover_bounds():
    # Tiles are named by their lower-left corner in units of 100 km.
    assert copernicus.tcd_tiles((3_130_000, 2_010_000, 3_170_000, 2_060_000)) == ["E31N20"]
    assert copernicus.tcd_tiles((3_190_000, 1_990_000, 3_210_000, 2_010_000)) == [
        "E31N19", "E31N20", "E32N19", "E32N20"]


def test_area_by_section():
    secs = gpd.GeoDataFrame({"geometry": [box(0, 0, 10, 10), box(10, 0, 20, 10)]},
                            index=["a", "b"], crs=config.CRS)
    trees = gpd.GeoDataFrame({"geometry": [box(5, 0, 15, 10), box(18, 0, 19, 1)]}, crs=config.CRS)
    a = city.area_by_section(secs, trees)
    assert a["a"] == 50 and a["b"] == 51


def test_zonal_mean_ignores_nan_and_outside():
    lab = np.array([[1, 1, 0], [2, 2, 2]])
    v = np.array([[10.0, np.nan, 99.0], [1.0, 2.0, 3.0]])
    assert np.allclose(city.zonal_mean(v, lab, 2), [10.0, 2.0])


def test_numbers_in_spanish():
    assert web._es(1234.5, 1) == "1.234,5"
    assert web._es(-1.26, 1, signo=True) == "−1,3"
    assert web._es(None) == "—"


def test_adrh_numbers_in_both_formats():
    import pandas as pd
    from shade import ine
    s = pd.Series(["1.276", "42,6", ".."])
    assert ine._number(s).tolist()[:2] == [1276, 42.6]
    e = pd.Series(["1,276", "42.6", ".."])
    assert ine._number(e, english=True).tolist()[:2] == [1276, 42.6]


def test_trees_per_section_counts_and_basal_area():
    from shapely.geometry import Point
    from shade import inventory
    secs = gpd.GeoDataFrame({"geometry": [box(0, 0, 10, 10), box(10, 0, 20, 10)]},
                            index=["a", "b"], crs=config.CRS)
    pts = gpd.GeoDataFrame({"basal_m2": [1.0, 2.0, 4.0]},
                           geometry=[Point(1, 1), Point(2, 2), Point(50, 50)], crs=config.CRS)
    t = inventory.trees_per_section(secs, pts)
    assert t.trees.tolist() == [2, 0] and t.basal_m2.tolist() == [3.0, 0.0]


def test_insee_numbers_and_secret_cells():
    import pandas as pd
    from shade import insee
    out = insee.number(pd.Series(["21830", "1234,5", "ns", "nd", "s"]))
    assert out.tolist()[:2] == [21830, 1234.5] and out[2:].isna().all()


def test_french_numbers_and_typography():
    from shade import i18n
    nn = i18n.NNBSP
    assert i18n.num(1234567.5, "fr", 1) == f"1{nn}234{nn}567,5"
    assert i18n.num(1234.5, "es", 1) == "1.234,5"
    assert i18n.num(0.052, "fr", 2, sign=True) == "+0,05"
    assert i18n._fr_typography("« ombre » : 50 % et 3 °C, 2 000 habitants ?") == (
        f"«{nn}ombre{nn}»{nn}: 50{nn}% et 3{nn}°C, 2{nn}000 habitants{nn}?")


def test_every_language_has_every_string():
    from shade import i18n
    es, fr = set(i18n.UI["es"]), set(i18n.UI["fr"])
    # Spain-only and France-only paragraphs are the only allowed gaps.
    assert es - fr == {"inv_trunk"}
    assert fr - es == {"p_people", "p_people_v", "cav_filosofi", "cav_secret", "cav_scope"}
    assert all(" %" not in v and " :" not in v for v in i18n.UI["fr"].values())


def test_countries_and_units():
    assert {c.country for c in config.cities("FR")} == {"FR"}
    assert config.CITY["paris"].unit == "IRIS" and config.CITY["madrid"].unit == "CUSEC"
    assert len(config.CITY["paris"].codes) == 20 and config.CITY["lille"].codes == ("59350",)
    assert all(len(c.municipality) == 5 for c in config.CITIES)


def test_indicators_v2_carry_country():
    sums = [{"slug": "madrid", "name": "Madrid", "municipality": "28079", "canopy_urban_tcd_pct": 6.5},
            {"slug": "paris", "name": "Paris", "country": "FR", "municipality": "75056",
             "canopy_urban_tcd_pct": 9.1}]
    out = web.indicators(sums, "2026-10-15T00:00Z")
    assert out["version"] == 2 and out["coverage"]["countries"] == ["ES", "FR"]
    es, fr = out["indicators"]
    assert (es["country"], fr["country"]) == ("ES", "FR")
    assert fr["id"] == "urban_tree_canopy:FR:75056:2024" and fr["url"].endswith("france.html#paris")
    assert fr["title"].startswith("Couvert arboré urbain de Paris")
    assert es["url"].endswith("quien-tiene-sombra/#madrid")
