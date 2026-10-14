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
