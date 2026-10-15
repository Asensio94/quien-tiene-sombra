"""docs/: the page, one JSON per city with its sections, the open CSVs and indicators.json."""
from __future__ import annotations

import datetime as dt
import json
from html import escape
from pathlib import Path

import pandas as pd

from . import config, ine
from .logo import LOGO_SVG, favicon_link

COMMON_CSS = Path(__file__).with_name("common.css").read_text(encoding="utf-8").strip()
ACCENT, ACCENT_DARK = "#3f7d20", "#94d06c"
MAP_WIDTH = 800
SIMPLIFY_M = 6


def _es(x: float | None, decimales: int = 0, signo: bool = False) -> str:
    """Número a la española: 1.500 y 0,15; «—» si falta."""
    if x is None or pd.isna(x):
        return "—"
    s = f"{abs(x) if signo else x:,.{decimales}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return (("+" if x > 0 else "−" if x < 0 else "") + s) if signo else s.replace("-", "−")


# --- Data ----------------------------------------------------------------------------------

def summaries() -> list[dict]:
    out = []
    for c in config.CITIES:
        p = config.SECTIONS_DIR / f"{c.slug}.json"
        if p.exists():
            out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def _path(geom, tf) -> str:
    out = []
    for p in getattr(geom, "geoms", [geom]):
        for ring in [p.exterior, *p.interiors]:
            pts = [tf(x, y) for x, y in ring.coords]
            out.append("M" + "L".join(f"{a},{b}" for a, b in pts) + "Z")
    return "".join(out)


def city_json(s: dict) -> dict:
    """Sections of one city with their SVG outline, for the map and the scatter plot."""
    df = pd.read_csv(config.SECTIONS_DIR / f"{s['slug']}.csv", dtype={"CUSEC": str, "district": str})
    secs = ine.sections(s["municipality"], config.sections_year(s["income_year"]))
    x0, y0, x1, y1 = secs.total_bounds
    k = MAP_WIDTH / (x1 - x0)

    def tf(x, y):
        return round((x - x0) * k, 1), round((y1 - y) * k, 1)

    geoms = secs.geometry.simplify(SIMPLIFY_M)
    rows = []
    for r in df.itertuples():
        g = geoms.get(r.CUSEC)
        if g is None or g.is_empty:
            continue
        rows.append([r.CUSEC, _path(g, tf), None if pd.isna(r.population) else int(r.population),
                     None if pd.isna(r.income) else int(r.income),
                     None if pd.isna(r.canopy_stl_pct) else round(r.canopy_stl_pct, 1),
                     None if pd.isna(r.canopy_tcd_pct) else round(r.canopy_tcd_pct, 1),
                     None if pd.isna(r.lst_c) else round(r.lst_c, 1), int(bool(r.ranked))])
    return {"w": MAP_WIDTH, "h": round((y1 - y0) * k), "s": rows}


def open_csv(sums: list[dict]) -> None:
    frames = []
    for s in sums:
        df = pd.read_csv(config.SECTIONS_DIR / f"{s['slug']}.csv", dtype={"CUSEC": str, "district": str})
        frames.append(df.assign(city=s["name"]))
    if frames:
        cols = ["city", "CUSEC", "population", "income", "area_ha", "urban_share", "canopy_stl_pct",
                "canopy_tcd_pct", "lst_c", "ranked"]
        pd.concat(frames)[cols].to_csv(config.DOCS_DIR / "secciones.csv", index=False)
    keep = ["name", "municipality", "income_year", "sections", "ranked", "population_ranked", "ci_canopy",
            "ci_canopy_tcd", "rho_canopy", "rho_lst", "canopy_pct", "canopy_gap", "lst_gap",
            "canopy_urban_tcd_pct", "canopy_municipality_tcd_pct"]
    pd.DataFrame([{k: s.get(k) for k in keep} for s in sums]).to_csv(config.DOCS_DIR / "ciudades.csv", index=False)


def indicators(sums: list[dict], generated: str) -> dict:
    """Urban tree canopy per city, the quantity Article 8 of the Nature Restoration Regulation
    says must not fall below its 2024 level. Proposed format; estado-iba does not read it yet."""
    return {
        "source": "quien-tiene-sombra", "version": 1, "generated": generated,
        "coverage": {"label": f"{len(sums)} ciudades de más de 200.000 habitantes",
                     "note": "Cubierta arbórea media (HRL Tree Cover Density 2024, 10 m) sobre el suelo "
                             "artificial del Urban Atlas 2021 dentro del término municipal."},
        "indicators": [{
            "id": f"urban_tree_canopy:{s['municipality']}:{config.TCD_YEAR}",
            "kind": "urban_tree_canopy",
            "date": f"{config.TCD_YEAR}-12-31",
            "title": f"Cubierta arbórea urbana de {s['name']} en {config.TCD_YEAR}",
            "url": f"{config.SITE_URL}#{s['slug']}",
            "municipalities": [s["municipality"]],
            "value": {"amount": s["canopy_urban_tcd_pct"], "unit": "%"},
            "baseline": config.TCD_YEAR == 2024,
            "details": {"legal_basis": "Reglamento (UE) 2024/1991, art. 8",
                        "area_ha": s.get("urban_area_ha"),
                        "whole_municipality_pct": s.get("canopy_municipality_tcd_pct")},
        } for s in sums if s.get("canopy_urban_tcd_pct") is not None],
    }


# --- Page ----------------------------------------------------------------------------------

def _parametros(sums: list[dict]) -> str:
    lst = sums[0]["lst"] if sums else {}
    veranos = "–".join(str(y) for y in (lst.get("summers") or [])[::max(1, len(lst.get("summers") or []) - 1)])
    filas = [
        ("Renta", f"renta media por unidad de consumo, Atlas de Distribución de Renta de los Hogares del INE "
                  f"({sums[0]['income_year'] if sums else config.INCOME_YEAR}), por sección censal"),
        ("Secciones", "las del INE a 1 de enero del año siguiente al de la renta, que son las que usa el Atlas"),
        ("Sombra", "Street Tree Layer 2021 del Urban Atlas (manchas de árboles de 500 m² o más) y bosque urbano "
                   "(clase 31000 del Urban Atlas 2021), en % de la superficie de la sección"),
        ("Sombra, contraste", f"densidad de cubierta arbórea HRL Tree Cover Density {config.TCD_YEAR}, 10 m"),
        ("Calor", f"temperatura de superficie de Landsat 8 y 9 (Collection 2 nivel 2, banda térmica), julio y agosto "
                  f"de {veranos or 'los tres últimos veranos'}; mediana de las pasadas despejadas, al menos "
                  f"{config.LST_MIN_CLEAR} por píxel de {config.LST_RESOLUTION_M} m"),
        ("Secciones que cuentan", f"al menos {config.MIN_POPULATION} residentes y {int(config.MIN_URBAN_SHARE * 100)} % "
                                  "de superficie artificial según el Urban Atlas; las demás se ven en el mapa rayadas"),
        ("Quintiles", "cinco grupos de secciones ordenadas por renta, con la misma población cada uno"),
        ("Índice de concentración", "de −1 a 1, ponderado por población; positivo si la sombra se acumula en las "
                                    "secciones de más renta"),
        ("Cubierta arbórea urbana (art. 8)", f"media de la Tree Cover Density {config.TCD_YEAR} sobre el suelo "
                                             "artificial del Urban Atlas 2021 dentro del municipio"),
    ]
    return '<table class="params">' + "".join(
        f"<tr><th>{escape(a)}</th><td>{escape(b)}</td></tr>" for a, b in filas) + "</table>"


def _validacion(sums: list[dict]) -> str:
    v = config.VALIDATION_DIR / "inventories.json"
    filas = "".join(f"<tr><td>{escape(s['name'])}</td><td class='num'>{_es(s.get('rho_stl_tcd'), 2)}</td></tr>"
                    for s in sums if s.get("rho_stl_tcd") is not None)
    tabla = ('<table class="params valid"><tr><th>Ciudad</th><th class="num">Correlación de rangos entre '
             'STL y Tree Cover Density por sección</th></tr>' + filas + "</table>") if filas else ""
    inv = ""
    if v.exists():
        res = json.loads(v.read_text(encoding="utf-8")).get("results", [])
        filas = "".join(
            f"<tr><td>{escape(x['name'])}</td><td class='num'>{_es(x['trees'])}</td>"
            f"<td class='num'>{_es(x['rho_stl'], 2)}</td><td class='num'>{_es(x['rho_tcd'], 2)}</td>"
            f"<td class='num'>{_es(x['ci_canopy'], 2, signo=True)}</td>"
            f"<td class='num'>{_es(x['ci_trees'], 2, signo=True)}</td>"
            f"<td class='num'>{_es(x['ci_trees_per_resident'], 2, signo=True)}</td></tr>" for x in res)
        fuentes = "; ".join(f"{escape(x['source'])}, {escape(x['edition'])}" for x in res)
        mad = next((x for x in res if x["slug"] == "madrid" and "ci_basal" in x), None)
        tronco = (f" En Madrid, que mide el perímetro de cada tronco, la sección del tronco por hectárea sigue "
                  f"mejor a la Street Tree Layer (correlación de {_es(mad['rho_basal_stl'], 2)}) y tampoco "
                  f"cambia con la renta (índice {_es(mad['ci_basal'], 2, signo=True)}): los árboles municipales "
                  f"de los barrios ricos no son más grandes.") if mad else ""
        inv = (
            '<h3>Inventarios municipales de arbolado</h3>'
            '<table class="params valid"><tr><th>Ciudad</th><th class="num">Árboles</th>'
            '<th class="num">Correl. STL</th><th class="num">Correl. TCD</th>'
            '<th class="num">Índice sombra</th><th class="num">Índice árboles/ha</th>'
            '<th class="num">Índice árboles/vecino</th></tr>' + filas + "</table>"
            "<p>Los árboles municipales por hectárea de cada sección ordenan las secciones de forma parecida a "
            "las dos capas de satélite (correlaciones de rangos en torno a 0,4), así que las capas miden algo "
            "real en la calle." + tronco + " Pero esos árboles no se concentran en las secciones de más renta: "
            "por hectárea están repartidos casi por igual. La sombra de más que ve el satélite en los barrios "
            "ricos sale sobre todo de lo que no está en el inventario: jardines privados, patios de manzana y "
            "suelo de otras administraciones. Por vecino, en Madrid sí hay más árboles en los barrios ricos, "
            "porque están menos poblados.</p>"
            f'<p class="note">Sin palmeras. Fuentes: {fuentes}. Se guardan solo los recuentos por sección.</p>')
    else:
        inv = ('<p class="note">Pendiente: comparar la sombra de cada sección con los inventarios municipales de '
               'arbolado de Madrid y Barcelona (árboles por hectárea).</p>')
    return tabla + inv


PLANTILLA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
__FAVICON__
<title>¿Quién tiene sombra?</title>
<meta name="description" content="Cubierta arbórea y temperatura de superficie en verano por sección censal frente a la renta de los hogares, en las grandes ciudades españolas.">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
__COMMON_CSS__
:root{--accent:__ACCENT__;--accent-dark:__ACCENT_DARK__}
:root{--s0:#eef3e6;--s1:#c9dfb4;--s2:#93c16f;--s3:#5b9a35;--s4:#2f6614;
  --h0:#2f6fa3;--h1:#9cc3e0;--h2:#ece6dc;--h3:#eba27a;--h4:#b33a1b;
  --r0:#f1ecf4;--r1:#d4c3e0;--r2:#a98bc4;--r3:#7a57a3;--r4:#4a2c74}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){--s0:#24301c;--s1:#35522a;--s2:#4f7d38;--s3:#77ad54;--s4:#b4e08e;
    --h0:#6fa8d6;--h1:#3a5b77;--h2:#3a332d;--h3:#8a4a2e;--h4:#f08a5d;
    --r0:#2c2433;--r1:#4a3a5c;--r2:#6f5590;--r3:#9d7fc2;--r4:#d2bdf0}
}
:root[data-theme="dark"]{--s0:#24301c;--s1:#35522a;--s2:#4f7d38;--s3:#77ad54;--s4:#b4e08e;
  --h0:#6fa8d6;--h1:#3a5b77;--h2:#3a332d;--h3:#8a4a2e;--h4:#f08a5d;
  --r0:#2c2433;--r1:#4a3a5c;--r2:#6f5590;--r3:#9d7fc2;--r4:#d2bdf0}
.marca{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap}
.marca .label{color:var(--muted);font-size:14px}
.bloque{max-width:1440px;margin:0 auto;padding:24px 16px 0}
.bloque > h2{margin:0 0 8px;font:700 28px/1 var(--font-title);text-transform:uppercase;letter-spacing:.03em}
.tabla-wrap{overflow-x:auto}
table.ciudades{width:100%;border-collapse:collapse;font-size:14.5px;background:var(--paper)}
table.ciudades th,table.ciudades td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:middle}
table.ciudades th{font:600 13px var(--font-title);text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
table.ciudades td.num,table.ciudades th.num{text-align:right;font-family:var(--font-data);font-variant-numeric:tabular-nums;white-space:nowrap}
table.ciudades tbody tr{cursor:pointer}
table.ciudades tbody tr:hover,table.ciudades tbody tr.sel{background:color-mix(in srgb,var(--accent) 10%,var(--paper))}
.barra{position:relative;width:120px;height:12px;background:var(--ground)}
.barra::before{content:"";position:absolute;left:50%;top:-2px;bottom:-2px;border-left:1px solid var(--muted)}
.barra i{position:absolute;top:2px;bottom:2px;background:var(--accent)}
.barra i.neg{background:var(--h4)}
main{max-width:1440px;margin:0 auto;padding:0 16px;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(320px,1fr);gap:20px;align-items:start}
.controles{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;padding:10px 0;font-size:14px;color:var(--muted)}
.controles select{font:14px var(--font-text);background:var(--paper);color:var(--ink);border:1px solid var(--line);padding:4px 6px}
.mapa{background:var(--paper);border:1px solid var(--line);padding:8px}
.mapa svg{display:block;width:100%;height:auto;max-height:78vh}
.mapa path{stroke:var(--paper);stroke-width:.35}
.mapa path.nd{fill:url(#rayas)}
.mapa path:hover,.mapa path.sel{stroke:var(--ink);stroke-width:1.6}
.leyenda{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:12.5px;color:var(--muted);align-items:center;margin-top:6px}
.leyenda i{display:inline-block;width:14px;height:10px;margin-right:4px;vertical-align:-1px}
.panel{display:grid;gap:14px}
.panel h2{margin:0;font:600 26px/1.1 var(--font-title)}
.panel .sub{margin:0;color:var(--muted);font-size:14.5px}
dl.cifras{margin:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px 12px}
dl.cifras div{display:grid;gap:1px} dl.cifras dt{font-size:12px;color:var(--muted)}
dl.cifras dd{margin:0;font:500 16px var(--font-data);font-variant-numeric:tabular-nums}
.graf svg{width:100%;height:auto;display:block;overflow:visible}
.graf .eje{stroke:var(--line)} .graf text{font:11px var(--font-data);fill:var(--muted)}
.graf .pt{fill:var(--accent);fill-opacity:.35;stroke:var(--accent);stroke-opacity:.6;stroke-width:.5}
.graf .pt.sel{fill:var(--ink);fill-opacity:1}
.graf .q{fill:var(--accent)} .graf .qh{fill:var(--h4)}
.graf .tit{font:600 13px var(--font-title);fill:var(--ink);text-transform:uppercase;letter-spacing:.04em}
.dos{display:grid;grid-template-columns:1fr 1fr;gap:28px}
.dos p{margin:0 0 10px;max-width:72ch}
.method{border-top:1.5px solid var(--ink);display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:28px;margin-top:24px}
.method p{margin:0 0 10px} .method ol{margin:0 0 10px;padding-left:1.4em} .method ol li{margin-bottom:8px}
.method > div > h3:first-child{margin-top:0}
.method table.params th{white-space:normal;width:30%}
.method table.valid th{width:auto}
.aviso{border-left:3px solid var(--accent);padding:2px 0 2px 12px}
.site-footer p{margin:0}
@media (max-width:900px){main,.method,.dos{grid-template-columns:1fr}}
</style>
</head>
<body>
<header class="site-header">
  <div class="marca">
    <h1>__LOGO__¿Quién tiene <span>sombra</span>?</h1>
    <span class="label">__NCIU__ ciudades · sección censal · renta __ANIO__</span>
  </div>
  <p class="lede">Árboles y calor de verano, barrio a barrio, frente a la renta de los hogares. Con datos abiertos de Copernicus, Landsat y el INE se mide cuánta sombra tiene cada sección censal de las grandes ciudades y cuánto se calienta su suelo en julio y agosto, y se ordena por lo que ganan sus vecinos.</p>
  <div class="figures">
    <div><b>__NRICA__</b><span>ciudades donde la sombra se concentra en los barrios de más renta</span></div>
    <div><b>__BRECHA__</b><span>más de calor en el suelo de los barrios más pobres (mediana de las ciudades)</span></div>
    <div><b>__NSEC__</b><span>secciones censales</span></div>
    <div><b>__POB__</b><span>residentes</span></div>
  </div>
</header>

<section class="bloque" id="ciudades">
  <h2>Ciudad a ciudad</h2>
  <p class="note">El quintil más pobre y el más rico agrupan cada uno a la quinta parte de los residentes. Pulse una ciudad para ver su mapa.</p>
  <div class="tabla-wrap"><table class="ciudades">
    <thead><tr><th>Ciudad</th><th>Índice de concentración de la sombra</th><th class="num">Sombra, quintil más pobre</th><th class="num">Sombra, quintil más rico</th><th class="num">Calor de más en el quintil más pobre</th><th class="num">Cubierta arbórea urbana __TCD__</th></tr></thead>
    <tbody id="filas"></tbody>
  </table></div>
</section>

<section class="bloque" id="detalle">
  <div class="controles">
    <label>Ciudad <select id="f-ciudad"></select></label>
    <label>Mostrar <select id="f-modo"><option value="sombra">Sombra</option><option value="calor">Calor</option><option value="renta">Renta</option></select></label>
  </div>
</section>
<main>
  <div>
    <div class="mapa"><svg id="mapa" viewBox="0 0 800 600" role="img" aria-label="Mapa de secciones censales">
      <defs><pattern id="rayas" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5" stroke="var(--line)" stroke-width="2"/></pattern></defs>
      <g id="secciones"></g></svg></div>
    <div class="leyenda" id="leyenda" aria-label="Leyenda"></div>
  </div>
  <div class="panel card" id="panel" aria-live="polite"></div>
</main>

<section class="bloque" id="por-que">
  <h2>Por qué importa</h2>
  <div class="dos">
    <div>
      <p>En Baltimore, Nueva York y otras ciudades de Estados Unidos, la cubierta de árboles sigue a la renta: Schwarz y otros lo resumieron en 2015 con un título que se ha hecho famoso, «Trees grow on money» (<a href="https://doi.org/10.1371/journal.pone.0122051">PLoS ONE 10: e0122051</a>). Donde hay menos árboles el suelo se calienta más, y las olas de calor matan sobre todo a personas mayores, enfermas o que viven en casas que no pueden refrescar.</p>
      <p>Esta página hace la misma pregunta en España con datos abiertos y la misma regla para todas las ciudades: ¿tienen los barrios pobres menos sombra y más calor?</p>
    </div>
    <div>
      <p>El Reglamento europeo de Restauración de la Naturaleza (<a href="https://eur-lex.europa.eu/eli/reg/2024/1991/oj">Reglamento (UE) 2024/1991</a>, artículo 8) obliga a que, en 2030, la cubierta arbórea urbana no haya bajado respecto a 2024, y a que crezca después. La última columna de la tabla es esa cifra para cada ciudad, medida con la capa que la Comisión recomienda: la base de 2024 contra la que habrá que medir.</p>
      <p class="aviso">Son indicios, no veredictos. Una sección con poca sombra puede tener otras razones (un casco antiguo de calles estrechas, un polígono) y la temperatura del suelo no es la del aire que se respira.</p>
    </div>
  </div>
</section>

<section class="method" id="metodo">
  <div>
    <h2>Cómo se calcula</h2>
    <ol>
      <li>Se toman las secciones censales de cada municipio y su renta media por unidad de consumo del Atlas de Distribución de Renta de los Hogares del INE, que reparte los ingresos declarados a Hacienda según dónde vive cada persona. La unidad de consumo corrige el tamaño del hogar.</li>
      <li>La sombra de cada sección es la parte de su superficie cubierta por copas de árbol según la Street Tree Layer del Urban Atlas de Copernicus, a la que se suma el bosque urbano que esa capa deja fuera. Como contraste se calcula también la densidad de cubierta arbórea de la capa Tree Cover Density, a 10 metros.</li>
      <li>El calor es la temperatura del suelo que mide la banda térmica de Landsat 8 y 9 en julio y agosto. Se descartan los píxeles con nubes, sombras o agua y se toma, para cada punto, la mediana de todos los días despejados de tres veranos. Después se promedia en cada sección.</li>
      <li>Solo entran en las comparaciones las secciones urbanas con suficientes vecinos. Se ordenan por renta y se reparten en cinco grupos con la misma población: del quintil más pobre al más rico.</li>
      <li>El índice de concentración resume en un número cómo se reparte la sombra a lo largo de esa ordenación: 0 si todos tienen la misma, positivo si se acumula en los barrios ricos, negativo si en los pobres.</li>
    </ol>
    <h3>Parámetros</h3>
    __PARAMETROS__
  </div>
  <div>
    <h3>Contraste</h3>
    <p>Las dos capas de árboles miden cosas distintas: la Street Tree Layer dibuja manchas de 500 m² o más, y la Tree Cover Density estima la densidad de copa en cada píxel de 10 metros. Si ordenan las secciones de forma parecida, la conclusión no depende de la capa elegida.</p>
    __VALIDACION__
    <h3>Lo que hay que saber antes de citarlo</h3>
    <p class="aviso">La Street Tree Layer no ve los árboles de alineación sueltos ni las copas pequeñas, que en los barrios densos son casi toda la sombra de la calle. Por eso los barrios de calles estrechas pueden salir con menos sombra de la que se siente a pie.</p>
    <p class="aviso">Landsat pasa hacia las once de la mañana, hora solar. Mide el calor del suelo a esa hora, no el de la tarde ni el del aire, y los tejados cuentan tanto como la calle.</p>
    <p>La renta es de __ANIO__ y las capas de árboles, de 2020–2021 (Street Tree Layer) y __TCD__ (Tree Cover Density). Los árboles cambian despacio, pero una plantación o una tala grande de esos años puede mover alguna sección. Las capas de 2018 y 2021 de la Street Tree Layer se hicieron con métodos distintos y no se comparan entre sí.</p>
    <h3>Datos abiertos</h3>
    <p><a href="secciones.csv">secciones.csv</a> con cada sección · <a href="ciudades.csv">ciudades.csv</a> con el resumen · <a href="indicators.json">indicators.json</a> con la cubierta arbórea urbana · <a href="__REPO__">código</a>.</p>
  </div>
</section>

<footer class="site-footer">
  <p class="principle">Datos públicos, reglas a la vista y cada cifra enlazada a su fuente. Indicios, no veredictos.</p>
  <p>Street Tree Layer, Urban Atlas y Tree Cover Density: Copernicus Land Monitoring Service, © Unión Europea, Agencia Europea de Medio Ambiente · Landsat 8 y 9: USGS, vía Microsoft Planetary Computer · Renta, población y secciones censales: Instituto Nacional de Estadística.</p>
  <nav aria-label="Proyectos hermanos"><ul class="siblings">
    <li><a href="https://asensio94.github.io/observatorio-alegaciones/">Observatorio de alegaciones</a></li>
    <li><a href="https://asensio94.github.io/vigia-incendios/">Vigía de incendios</a></li>
    <li><a href="https://asensio94.github.io/centinela-natura/">Centinela Natura</a></li>
    <li><a href="https://asensio94.github.io/vigilancia-humedales/">Vigilancia de humedales</a></li>
    <li><a href="https://asensio94.github.io/sub-nocte/">Sub Nocte</a></li>
    <li><a href="https://asensio94.github.io/riesgo-tendidos-aves/">Riesgo de tendidos para aves</a></li>
    <li><a href="https://asensio94.github.io/grafo-promotores/">Grafo de promotores</a></li>
    <li><a href="https://asensio94.github.io/cartera-cotizadas/">Cartera de las cotizadas</a></li>
    <li><a href="https://asensio94.github.io/cuaderno-campo/">Cuaderno de campo</a></li>
    <li><a href="https://asensio94.github.io/caudal-ecologico/">Caudal ecológico</a></li>
    <li><a href="https://asensio94.github.io/estado-iba/">Estado de las IBA</a></li>
    <li><a href="https://asensio94.github.io/acuiferos-francia/">Acuíferos de Francia</a></li>
    <li aria-current="page"><a href="https://asensio94.github.io/quien-tiene-sombra/">¿Quién tiene sombra?</a></li>
  </ul></nav>
</footer>
<script>
const C = __DATOS__;
const num = (x,d=0) => x==null ? "—" : x.toLocaleString("es-ES",{minimumFractionDigits:d,maximumFractionDigits:d});
const sig = (x,d=1) => x==null ? "—" : (x>0?"+":x<0?"−":"") + num(Math.abs(x),d);
const selC = document.getElementById("f-ciudad"), selM = document.getElementById("f-modo");
const cache = {};
let cur = null, data = null, sel = null;
for (const c of C) selC.add(new Option(c.name, c.slug));

document.getElementById("filas").innerHTML = [...C].sort((a,b) => (b.ci_canopy??-9) - (a.ci_canopy??-9)).map(c => {
  const v = c.ci_canopy ?? 0, w = Math.min(Math.abs(v), .5) / .5 * 50;
  const bar = `<div class="barra" title="${num(c.ci_canopy,3)}"><i class="${v<0?"neg":""}" style="left:${v<0?50-w:50}%;width:${w}%"></i></div>`;
  return `<tr data-c="${c.slug}" tabindex="0"><td>${c.name}</td><td><span style="display:flex;gap:8px;align-items:center">${bar}<span class="data">${sig(c.ci_canopy,2)}</span></span></td>
    <td class="num">${num(c.quintiles["1"].canopy,1)} %</td><td class="num">${num(c.quintiles["5"].canopy,1)} %</td>
    <td class="num">${sig(c.lst_gap,1)} °C</td><td class="num">${num(c.canopy_urban_tcd_pct,1)} %</td></tr>`;
}).join("");
document.getElementById("filas").addEventListener("click", e => { const r = e.target.closest("tr"); if (r) { elegir(r.dataset.c); document.getElementById("detalle").scrollIntoView({behavior:"smooth"}); } });
document.getElementById("filas").addEventListener("keydown", e => { const r = e.target.closest("tr"); if (r && e.key === "Enter") elegir(r.dataset.c); });

// Rows: [cusec, path, population, income, canopy STL %, canopy TCD %, LST °C, ranked]
function wmean(rows, i){ let s=0, w=0; for (const r of rows) if (r[7] && r[i]!=null && r[2]) { s += r[i]*r[2]; w += r[2]; } return w ? s/w : null; }
function cortes(vals){ const v = vals.filter(x => x!=null).sort((a,b)=>a-b); return [.2,.4,.6,.8].map(q => v[Math.floor(q*(v.length-1))]); }
function cuartiles(vals){ const v = vals.slice().sort((a,b)=>a-b); return [.25,.5,.75].map(q => v[Math.floor(q*(v.length-1))]); }
const ESC = {sombra:"s", calor:"h", renta:"r"};
function clase(v, br){ if (v==null) return null; let i = br.findIndex(t => v < t); return i < 0 ? 4 : i; }
function pintar(){
  if (!data) return;
  const modo = selM.value, rk = data.s.filter(r => r[7]);
  const lstMedia = wmean(data.s, 6);
  const val = r => modo === "sombra" ? r[4] : modo === "renta" ? r[3] : (r[6]==null ? null : r[6] - lstMedia);
  // Many sections have no tree patch at all: in shade mode they get their own class and the rest
  // are split into quartiles.
  const sinCopa = modo === "sombra";
  const br = modo === "calor" ? [-3,-1,1,3]
    : sinCopa ? [1e-9, ...cuartiles(rk.map(val).filter(v => v > 0))] : cortes(rk.map(val));
  const g = document.getElementById("secciones");
  for (const el of g.children) {
    const r = data.byId[el.dataset.c], v = val(r), k = r[7] ? clase(v, br) : null;
    el.classList.toggle("nd", k == null); el.style.fill = k == null ? "" : `var(--${ESC[modo]}${k})`;
    el.classList.toggle("sel", el.dataset.c === sel);
    el.firstChild.textContent = `Sección ${r[0]} · ${num(r[2])} residentes · ${num(r[3])} € por unidad de consumo · sombra ${num(r[4],1)} % · suelo ${num(r[6],1)} °C` + (r[7] ? "" : " · no entra en la comparación");
  }
  const fmt = modo === "sombra" ? (x => num(x,1)+" %") : modo === "renta" ? (x => num(Math.round(x/100)*100)+" €") : (x => sig(x,0)+" °C");
  const lab = modo === "calor" ? ["3 °C o más por debajo","1 a 3 °C por debajo","±1 °C","1 a 3 °C por encima","3 °C o más por encima"]
    : sinCopa ? ["sin manchas de árboles", "hasta "+fmt(br[1]), fmt(br[1])+" – "+fmt(br[2]), fmt(br[2])+" – "+fmt(br[3]), "≥ "+fmt(br[3])]
    : ["< "+fmt(br[0]), fmt(br[0])+" – "+fmt(br[1]), fmt(br[1])+" – "+fmt(br[2]), fmt(br[2])+" – "+fmt(br[3]), "≥ "+fmt(br[3])];
  const pre = modo === "sombra" ? "Parte de la sección con copa de árbol: " : modo === "renta" ? "Renta por unidad de consumo: " : `Temperatura del suelo frente a la media de la ciudad (${num(lstMedia,1)} °C): `;
  document.getElementById("leyenda").innerHTML = pre + lab.map((t,i) => `<span><i style="background:var(--${ESC[modo]}${i})"></i>${t}</span>`).join("")
    + `<span><i style="background:url(#rayas);border:1px solid var(--line)"></i>sin datos o no urbana</span>`;
}
function dispersion(){
  const rk = data.s.filter(r => r[7] && r[3]!=null && r[4]!=null);
  const W = 360, H = 230, L = 40, R = 8, T = 14, B = 30;
  const xs = rk.map(r => r[3]), ys = rk.map(r => r[4]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y1 = Math.max(5, ...ys) * 1.05;
  const x = v => L + (v - x0) / (x1 - x0) * (W - L - R), y = v => T + (1 - v / y1) * (H - T - B);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Renta y sombra de cada sección">`;
  for (const t of [0, .5, 1]) { const v = y1/1.05*t; s += `<line class="eje" x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L-4}" y="${y(v)+4}" text-anchor="end">${num(v,0)} %</text>`; }
  for (const t of [0, .5, 1]) { const v = x0 + (x1-x0)*t; s += `<text x="${x(v)}" y="${H-14}" text-anchor="middle">${num(Math.round(v/1000))} mil €</text>`; }
  s += `<text x="${W-R}" y="${H-1}" text-anchor="end">renta por unidad de consumo →</text>`;
  s += rk.map(r => `<circle class="pt${r[0]===sel?" sel":""}" data-c="${r[0]}" cx="${x(r[3]).toFixed(1)}" cy="${y(r[4]).toFixed(1)}" r="${Math.max(1.2, Math.sqrt(r[2])/18).toFixed(1)}"><title>Sección ${r[0]}: ${num(r[3])} €, sombra ${num(r[4],1)} %</title></circle>`).join("");
  return s + "</svg>";
}
function quintiles(c){
  // Two bands so labels never collide: ground temperature (points) on top, shade (bars) below.
  const W = 360, H = 200, L = 8, R = 8, T = 22, B = 22, bw = (W - L - R) / 5;
  const HT = 22, HB = 32;  // temperature band: label row + point range
  const top = T + HT + HB + 14, sub = T + HT + HB + 4;
  const q = [1,2,3,4,5].map(k => c.quintiles[k]);
  const ms = Math.max(...q.map(v => v.canopy || 0)) || 1;
  const ls = q.map(v => v.lst).filter(v => v!=null), lmin = Math.min(...ls), lmax = Math.max(...ls);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Sombra y calor por quintil de renta"><text class="tit" x="${L}" y="12">Suelo en verano (puntos) y sombra (barras) por quintil de renta</text>`;
  s += `<line class="eje" x1="${L}" x2="${W-R}" y1="${sub}" y2="${sub}"/>`;
  q.forEach((v,i) => {
    const h = (v.canopy||0)/ms*(H-top-B-14), cx = L + bw*i + bw/2;
    s += `<rect class="q" x="${L+bw*i+8}" y="${H-B-h}" width="${bw-16}" height="${h}"><title>Quintil ${i+1}: ${num(v.canopy,1)} % de sombra</title></rect>`;
    s += `<text x="${cx}" y="${H-B-h-4}" text-anchor="middle">${num(v.canopy,1)} %</text>`;
    if (v.lst!=null) { const yy = T + HT + (lmax - v.lst) / ((lmax - lmin) || 1) * HB; s += `<circle class="qh" cx="${cx}" cy="${yy}" r="4"><title>Quintil ${i+1}: ${num(v.lst,1)} °C</title></circle><text x="${cx}" y="${T + 12}" text-anchor="middle">${num(v.lst,1)} °C</text>`; }
    s += `<text x="${cx}" y="${H-6}" text-anchor="middle">${i===0?"más pobre":i===4?"más rico":"Q"+(i+1)}</text>`;
  });
  return s + "</svg>";
}
function panel(){
  const c = cur, p = document.getElementById("panel");
  let extra = "";
  if (sel && data.byId[sel]) { const r = data.byId[sel];
    extra = `<div class="card"><b>Sección ${r[0]}</b><dl class="cifras"><div><dt>Residentes</dt><dd>${num(r[2])}</dd></div><div><dt>Renta por u. de consumo</dt><dd>${num(r[3])} €</dd></div><div><dt>Sombra (STL)</dt><dd>${num(r[4],1)} %</dd></div><div><dt>Densidad de copa (TCD)</dt><dd>${num(r[5],1)} %</dd></div><div><dt>Suelo en verano</dt><dd>${num(r[6],1)} °C</dd></div></dl></div>`; }
  p.innerHTML = `<div><h2 id="${c.slug}">${c.name}</h2><p class="sub">${num(c.ranked)} de ${num(c.sections)} secciones entran en la comparación · ${num(c.population_ranked)} residentes</p></div>
    <dl class="cifras">
      <div><dt>Índice de concentración</dt><dd>${sig(c.ci_canopy,2)}</dd></div>
      <div><dt>Sombra media</dt><dd>${num(c.canopy_pct,1)} %</dd></div>
      <div><dt>Sombra, más pobre / más rico</dt><dd>${num(c.quintiles["1"].canopy,1)} / ${num(c.quintiles["5"].canopy,1)} %</dd></div>
      <div><dt>Suelo, más pobre − más rico</dt><dd>${sig(c.lst_gap,1)} °C</dd></div>
      <div><dt>Cubierta arbórea urbana __TCD__</dt><dd>${num(c.canopy_urban_tcd_pct,1)} %</dd></div>
    </dl>
    <figure class="graf" style="margin:0">${quintiles(c)}</figure>
    <figure class="graf" style="margin:0">${dispersion()}<figcaption class="note">Cada punto es una sección; su tamaño, los residentes. Pulse un punto o una sección del mapa.</figcaption></figure>
    ${extra}`;
}
async function elegir(slug, keepSel){
  cur = C.find(c => c.slug === slug); selC.value = slug; if (!keepSel) sel = null;
  for (const tr of document.querySelectorAll("#filas tr")) tr.classList.toggle("sel", tr.dataset.c === slug);
  data = cache[slug] || (cache[slug] = await fetch(`data/${slug}.json`).then(r => r.json()));
  data.byId = data.byId || Object.fromEntries(data.s.map(r => [r[0], r]));
  const svg = document.getElementById("mapa"); svg.setAttribute("viewBox", `0 0 ${data.w} ${data.h}`);
  document.getElementById("secciones").innerHTML = data.s.map(r => `<path data-c="${r[0]}" d="${r[1]}"><title></title></path>`).join("");
  history.replaceState(null, "", "#" + slug);
  pintar(); panel();
}
function marcar(c){ sel = c; pintar(); panel(); }
document.getElementById("secciones").addEventListener("click", e => { const t = e.target.closest("path"); if (t) marcar(t.dataset.c); });
document.getElementById("panel").addEventListener("click", e => { const t = e.target.closest("circle.pt"); if (t) marcar(t.dataset.c); });
selC.addEventListener("change", () => elegir(selC.value));
selM.addEventListener("change", pintar);
const h = location.hash.slice(1);
if (C.length) elegir(C.some(c => c.slug === h) ? h : C[0].slug);
</script>
</body>
</html>
"""


def build() -> Path:
    sums = summaries()
    if not sums:
        raise SystemExit("no cities yet; run `python -m shade run` first")
    config.DOCS_DIR.mkdir(exist_ok=True)
    (config.DOCS_DIR / "data").mkdir(exist_ok=True)
    for s in sums:
        (config.DOCS_DIR / "data" / f"{s['slug']}.json").write_text(
            json.dumps(city_json(s), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    open_csv(sums)
    generated = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    (config.DOCS_DIR / "indicators.json").write_text(
        json.dumps(indicators(sums, generated), ensure_ascii=False, indent=1), encoding="utf-8")

    ci = [s["ci_canopy"] for s in sums if s.get("ci_canopy") is not None]
    gaps = sorted(s["lst_gap"] for s in sums if s.get("lst_gap") is not None)
    brecha = gaps[len(gaps) // 2] if gaps else None
    years = sorted({s["income_year"] for s in sums})
    html = (PLANTILLA
            .replace("__LOGO__", LOGO_SVG)
            .replace("__FAVICON__", favicon_link(ACCENT, ACCENT_DARK))
            .replace("__COMMON_CSS__", COMMON_CSS)
            .replace("__ACCENT__", ACCENT).replace("__ACCENT_DARK__", ACCENT_DARK)
            .replace("__NCIU__", str(len(sums)))
            .replace("__ANIO__", "/".join(map(str, years)))
            .replace("__TCD__", str(config.TCD_YEAR))
            .replace("__NRICA__", f"{sum(c > 0 for c in ci)} de {len(ci)}")
            .replace("__BRECHA__", f"{_es(brecha, 1, signo=True)} °C")
            .replace("__NSEC__", _es(sum(s["sections"] for s in sums)))
            .replace("__POB__", _es(sum(s["population"] for s in sums)))
            .replace("__PARAMETROS__", _parametros(sums))
            .replace("__VALIDACION__", _validacion(sums))
            .replace("__REPO__", config.REPO_URL)
            .replace("__DATOS__", json.dumps(
                [{k: s[k] for k in ("slug", "name", "sections", "ranked", "population_ranked", "ci_canopy",
                                    "canopy_pct", "quintiles", "lst_gap", "canopy_urban_tcd_pct")} for s in sums],
                ensure_ascii=False, separators=(",", ":"))))
    out = config.DOCS_DIR / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
