"""Cities, years, sources and thresholds. Everything the method depends on lives here."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CACHE_DIR = DATA_DIR / "cache"          # downloads; never committed
SECTIONS_DIR = DATA_DIR / "sections"     # one CSV per city, committed
VALIDATION_DIR = DATA_DIR / "validation"
DOCS_DIR = ROOT / "docs"

CRS = "EPSG:3035"  # ETRS89-LAEA: equal-area, native CRS of the Copernicus layers


@dataclass(frozen=True)
class City:
    slug: str
    name: str
    municipality: str   # INE (ES) or INSEE (FR) 5-character municipality code
    fua: str            # Urban Atlas Functional Urban Area code (2021 delineation)
    country: str = "ES"  # ISO 3166-1 alpha-2
    # INSEE codes the units are published under. Paris, Lyon and Marseille publish IRIS under
    # their arrondissements (751xx, 6938x, 132xx), not under the municipality code.
    parts: tuple[str, ...] = ()

    @property
    def unit(self) -> str:
        """Name of the statistical unit, also the index column of data/sections/<slug>.csv."""
        return UNIT[self.country]

    @property
    def codes(self) -> tuple[str, ...]:
        return self.parts or (self.municipality,)


# Municipalities over 200,000 inhabitants that sit in an Urban Atlas FUA. The unit is the core
# municipality, not the whole FUA: income and sections are municipal, and the commuter belt
# would mix very different towns into one ranking.
CITIES = [
    City("madrid", "Madrid", "28079", "ES001L3"),
    City("barcelona", "Barcelona", "08019", "ES002L2"),
    City("valencia", "València", "46250", "ES003L3"),
    City("sevilla", "Sevilla", "41091", "ES004L3"),
    City("zaragoza", "Zaragoza", "50297", "ES005L2"),
    City("malaga", "Málaga", "29067", "ES006L2"),
    City("murcia", "Murcia", "30030", "ES007L2"),
    City("palma", "Palma", "07040", "ES010L2"),
    City("las-palmas", "Las Palmas de Gran Canaria", "35016", "ES008L2"),
    City("bilbao", "Bilbao", "48020", "ES019L3"),
    City("alicante", "Alicante", "03014", "ES021L2"),
    City("cordoba", "Córdoba", "14021", "ES020L2"),
    City("valladolid", "Valladolid", "47186", "ES009L2"),
    City("vigo", "Vigo", "36057", "ES022L2"),
    City("gijon", "Gijón", "33024", "ES023L2"),
    City("hospitalet", "L'Hospitalet de Llobregat", "08101", "ES002L2"),
    City("vitoria", "Vitoria-Gasteiz", "01059", "ES012L2"),
    City("coruna", "A Coruña", "15030", "ES026L2"),
    City("granada", "Granada", "18087", "ES501L3"),
    City("elche", "Elche", "03065", "ES505L1"),
    # France: the six largest municipalities with a Street Tree Layer, unit IRIS.
    City("paris", "Paris", "75056", "FR001L1", "FR", tuple(f"751{i:02d}" for i in range(1, 21))),
    City("marseille", "Marseille", "13055", "FR203L2", "FR", tuple(f"132{i:02d}" for i in range(1, 17))),
    City("lyon", "Lyon", "69123", "FR003L2", "FR", tuple(f"6938{i}" for i in range(1, 10))),
    City("toulouse", "Toulouse", "31555", "FR004L2", "FR"),
    City("bordeaux", "Bordeaux", "33063", "FR007L2", "FR"),
    City("lille", "Lille", "59350", "FR009L2", "FR"),
]
CITY = {c.slug: c for c in CITIES}
COUNTRIES = ("ES", "FR")
UNIT = {"ES": "CUSEC", "FR": "IRIS"}


def cities(country: str | None = None) -> list[City]:
    return [c for c in CITIES if country is None or c.country == country]

# --- Income: INE Atlas de Distribución de Renta de los Hogares (ADRH) ----------------------
# Income of year N is linked to the population on 1 January N+1, so it is published on the
# section boundaries of that date (checked: ADRH 2023 matches SECC_CE_20240101 code for code).
INCOME_YEAR = 2023
ADRH_OPERATION = 353
TEMPUS = "https://servicios.ine.es/wstempus/js/ES"
JAXI_CSV = "https://www.ine.es/jaxiT3/files/t/es/csv_bdsc/{table}.csv?nocab=1"
INCOME_INDICATOR = "Media de la renta por unidad de consumo"
SECTIONS_URL = "https://www.ine.es/prodyser/cartografia/seccionado_{year}.zip"


def sections_year(income_year: int = INCOME_YEAR) -> int:
    return income_year + 1


# --- France: INSEE Filosofi income and census population by IRIS, IGN IRIS outlines ---------
# Filosofi 2021 is the last vintage: INSEE dropped 2022 because the end of the taxe
# d'habitation broke the link between tax households and dwellings. Its IRIS are those of
# 1 January 2022; the census and the IGN outlines in force today use the same codes in the six
# cities (checked IRIS by IRIS), so they are joined by code.
FILOSOFI_YEAR = 2021
FILOSOFI_URL = "https://www.insee.fr/fr/statistiques/fichier/8229323/BASE_TD_FILO_IRIS_2021_DISP_CSV.zip"
FILOSOFI_INCOME = "DISP_MED21"   # median disposable income per consumption unit (€)
CENSUS_YEAR = 2022
CENSUS_URL = "https://www.insee.fr/fr/statistiques/fichier/8647014/base-ic-evol-struct-pop-2022_csv.zip"
CENSUS_POPULATION = "P22_POP"
IRIS_WFS = "https://data.geopf.fr/wfs/ows"
IRIS_LAYER = "STATISTICALUNITS.IRIS:contours_iris"


# --- Copernicus Land, via the Copernicus Data Space Ecosystem (free account) ---------------
CDSE_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
CDSE_ODATA = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
CDSE_DOWNLOAD = "https://download.dataspace.copernicus.eu/odata/v1/Products({id})/$value"
STL_YEAR = 2021
STL_PREFIX = "CLMS_UA_STL_S2021_V005ha_"       # Street Tree Layer, 0.05 ha minimum patch
UA_PREFIX = "CLMS_UA_LCU_S2021_V025ha_"        # Urban Atlas land cover / land use
TCD_YEAR = 2024
TCD_PREFIX = "CLMS_HRLVLCC_TCD_S2024_R10m_"    # Tree Cover Density, 10 m, 100 km tiles
TCD_NODATA = (254, 255)

# Urban Atlas classes. Class 1 = artificial surfaces (built-up, roads, urban parks, sports…).
UA_FOREST = "31000"
# A section enters the ranking only if most of it is town: this drops the rural fringes of
# large municipalities (huerta de Murcia, montes de Zaragoza, El Pardo) whose few residents
# live next to fields, not streets.
MIN_URBAN_SHARE = 0.5
# Sections with fewer residents give noisy shares and the INE imputes part of their income.
MIN_POPULATION = 300

# --- Land surface temperature: Landsat 8/9 Collection 2 Level-2 ----------------------------
STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
STAC_COLLECTION = "landsat-c2-l2"
LST_SUMMERS = 3            # the last three July–August seasons, pooled
LST_MONTHS = (7, 8)
LST_MAX_SCENE_CLOUD = 30   # % of the scene; pixels are masked one by one afterwards
LST_MIN_CLEAR = 4          # clear observations a pixel needs to get a median
LST_RESOLUTION_M = 30
# ST_B10 is stored as DN; Collection 2 scale and offset give kelvin.
ST_SCALE, ST_OFFSET = 0.00341802, 149.0
# QA_PIXEL bits: 1 dilated cloud, 2 cirrus, 3 cloud, 4 cloud shadow, 5 snow, 7 water.
QA_REJECT_BITS = (1, 2, 3, 4, 5, 7)

# --- Outputs -------------------------------------------------------------------------------
SITE_URL = "https://asensio94.github.io/quien-tiene-sombra/"
PAGES = {"ES": "index.html", "FR": "france.html"}
REPO_URL = "https://github.com/Asensio94/quien-tiene-sombra"
