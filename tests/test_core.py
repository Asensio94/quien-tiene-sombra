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
