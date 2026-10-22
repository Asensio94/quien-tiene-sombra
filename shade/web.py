"""docs/: one page per country, one JSON per city with its units, the open CSVs and indicators.json.

The Spanish page (index.html) is in Spanish and shows the Spanish cities by census section; the
French page (france.html) is in French and shows the French cities by IRIS. Both come from the
same template, filled from i18n.UI; the data files are shared and language-independent.
"""
from __future__ import annotations

import datetime as dt
import json
import re
from html import escape
from pathlib import Path

import pandas as pd

from . import city as city_mod
from . import config, i18n
from .logo import LOGO_SVG, favicon_link

COMMON_CSS = Path(__file__).with_name("common.css").read_text(encoding="utf-8").strip()
ACCENT, ACCENT_DARK = "#3f7d20", "#94d06c"
MAP_WIDTH = 800
SIMPLIFY_M = 6
UNIT_CSV = {"ES": "secciones.csv", "FR": "iris.csv"}
LST_GAP_SHARE = 0.02  # cities with more units than this left without summer temperature get a note


def _es(x: float | None, decimales: int = 0, signo: bool = False) -> str:
    """Número a la española: 1.500 y 0,15; «—» si falta."""
    return i18n.num(None if x is None or pd.isna(x) else x, "es", decimales, signo)


def country_of(s: dict) -> str:
    """Country of a city summary or validation result (older Spanish files carry none)."""
    return s.get("country") or config.CITY[s["slug"]].country


# Common footer of the Terra Aperta projects, in the hub's menu order: (Spanish name, page, French name,
# French page). This project is not one of the twelve, so none is marked as the current page.
_SITE = "https://asensio94.github.io/"
FOOTER_PROJECTS = [
    ("Sub Nocte", "sub-nocte/", "Sub Nocte", "sub-nocte/"),
    ("Vigía de incendios", "vigia-incendios/", "Vigie des incendies", "vigia-incendios/fr/"),
    ("Centinela Natura", "centinela-natura/", "Centinela Natura", "centinela-natura/fr/"),
    ("Estado de las IBA", "estado-iba/", "État des IBA", "estado-iba/fr/"),
    ("Riesgo de tendidos para aves", "riesgo-tendidos-aves/",
     "Risque des lignes pour les oiseaux", "riesgo-tendidos-aves/regions.fr.html"),
    ("Observatorio de alegaciones", "observatorio-alegaciones/",
     "Observatoire des consultations", "observatorio-alegaciones/"),
    ("Grafo de promotores", "grafo-promotores/", "Graphe des porteurs de projet", "grafo-promotores/"),
    ("Vigilancia de humedales", "vigilancia-humedales/",
     "Veille des zones humides", "vigilancia-humedales/france.html"),
    ("Caudal ecológico", "caudal-ecologico/", "Débit écologique", "caudal-ecologico/"),
    ("Acuíferos de Francia", "acuiferos-francia/", "Nappes de France", "acuiferos-francia/fr/"),
    ("Depuración y baño", "depuracion-y-bano/", "Épuration et baignade", "depuracion-y-bano/fr/"),
    ("Construir en zona inundable", "zona-inundable/", "Construire en zone inondable", "zona-inundable/"),
]
FOOTER_HUB = {"es": ("← Terra Aperta: todos los proyectos", "terra-aperta/"),
              "fr": ("← Terra Aperta : tous les projets", "terra-aperta/fr/")}


def footer_nav(lang: str) -> str:
    """The hub link and the twelve sibling projects, labels and pages in the page's language."""
    hub, hub_page = FOOTER_HUB[lang]
    items = "\n".join(f'    <li><a href="{_SITE}{fr_page if lang == "fr" else page}">'
                      f'{escape(fr if lang == "fr" else es)}</a></li>'
                      for es, page, fr, fr_page in FOOTER_PROJECTS)
    return (f'  <p class="hub"><a href="{_SITE}{hub_page}">{escape(hub)}</a></p>\n'
            f'  <nav aria-label="{i18n.t(lang, "siblings")}"><ul class="siblings">\n{items}\n  </ul></nav>')


# --- Data ----------------------------------------------------------------------------------

def summaries(country: str | None = None) -> list[dict]:
    out = []
    for c in config.cities(country):
        p = config.SECTIONS_DIR / f"{c.slug}.json"
        if p.exists():
            out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def _read_units(s: dict) -> pd.DataFrame:
    unit = config.CITY[s["slug"]].unit
    return pd.read_csv(config.SECTIONS_DIR / f"{s['slug']}.csv", dtype={unit: str, "district": str})


def _path(geom, tf) -> str:
    out = []
    for p in getattr(geom, "geoms", [geom]):
        for ring in [p.exterior, *p.interiors]:
            pts = [tf(x, y) for x, y in ring.coords]
            out.append("M" + "L".join(f"{a},{b}" for a, b in pts) + "Z")
    return "".join(out)


def city_json(s: dict) -> dict:
    """Units of one city (census sections or IRIS) with their SVG outline, for the map and the
    scatter plot."""
    city = config.CITY[s["slug"]]
    df = _read_units(s)
    secs = city_mod.units(city, s["income_year"])
    x0, y0, x1, y1 = secs.total_bounds
    k = MAP_WIDTH / (x1 - x0)

    def tf(x, y):
        return round((x - x0) * k, 1), round((y1 - y) * k, 1)

    geoms = secs.geometry.simplify(SIMPLIFY_M)
    rows = []
    for r in df.itertuples():
        code = getattr(r, city.unit)
        g = geoms.get(code)
        if g is None or g.is_empty:
            continue
        rows.append([code, _path(g, tf), None if pd.isna(r.population) else int(r.population),
                     None if pd.isna(r.income) else int(r.income),
                     None if pd.isna(r.canopy_stl_pct) else round(r.canopy_stl_pct, 1),
                     None if pd.isna(r.canopy_tcd_pct) else round(r.canopy_tcd_pct, 1),
                     None if pd.isna(r.lst_c) else round(r.lst_c, 1), int(bool(r.ranked))])
    return {"w": MAP_WIDTH, "h": round((y1 - y0) * k), "s": rows}


def open_csv(sums: list[dict]) -> None:
    """secciones.csv (Spain) and iris.csv (France), one row per unit; ciudades.csv, both."""
    for country, name in UNIT_CSV.items():
        unit = config.UNIT[country]
        frames = [_read_units(s).assign(country=country, city=s["name"])
                  for s in sums if country_of(s) == country]
        if frames:
            cols = ["country", "city", unit, "population", "income", "area_ha", "urban_share",
                    "canopy_stl_pct", "canopy_tcd_pct", "lst_c", "ranked"]
            pd.concat(frames)[cols].to_csv(config.DOCS_DIR / name, index=False)
    keep = ["name", "country", "municipality", "income_year", "sections", "ranked", "population_ranked",
            "ci_canopy", "ci_canopy_tcd", "rho_canopy", "rho_lst", "canopy_pct", "canopy_gap", "lst_gap",
            "canopy_urban_tcd_pct", "canopy_municipality_tcd_pct", "sections_without_income"]
    rows = [{**{k: s.get(k) for k in keep}, "country": country_of(s)} for s in sums]
    pd.DataFrame(rows, columns=keep).to_csv(config.DOCS_DIR / "ciudades.csv", index=False)


def page_url(country: str, slug: str = "") -> str:
    page = "" if country == "ES" else config.PAGES[country]
    return config.SITE_URL + page + (f"#{slug}" if slug else "")


def indicators(sums: list[dict], generated: str) -> dict:
    """Urban tree canopy per city, the quantity Article 8 of the Nature Restoration Regulation
    says must not fall below its 2024 level. Version 2 adds `country` to each indicator: the
    municipality code is the INE code in Spain and the INSEE commune code in France, and the
    two can coincide, so the id carries the country too. Proposed format; estado-iba does not
    read it yet."""
    countries = sorted({country_of(s) for s in sums})
    names = {"ES": "España", "FR": "Francia"}
    out = []
    for s in sums:
        if s.get("canopy_urban_tcd_pct") is None:
            continue
        country = country_of(s)
        lang = i18n.lang_of(country)
        out.append({
            "id": f"urban_tree_canopy:{country}:{s['municipality']}:{config.TCD_YEAR}",
            "kind": "urban_tree_canopy",
            "country": country,
            "date": f"{config.TCD_YEAR}-12-31",
            "title": i18n.t(lang, "ind_title", name=s["name"], year=config.TCD_YEAR),
            "url": page_url(country, s["slug"]),
            "municipalities": [s["municipality"]],
            "value": {"amount": s["canopy_urban_tcd_pct"], "unit": "%"},
            "baseline": config.TCD_YEAR == 2024,
            "details": {"legal_basis": i18n.t(lang, "legal_basis"),
                        "area_ha": s.get("urban_area_ha"),
                        "whole_municipality_pct": s.get("canopy_municipality_tcd_pct")},
        })
    return {
        "source": "quien-tiene-sombra", "version": 2, "generated": generated,
        "coverage": {"label": f"{len(out)} ciudades de " + " y ".join(names[c] for c in countries),
                     "countries": countries,
                     "note": "Cubierta arbórea media (HRL Tree Cover Density 2024, 10 m) sobre el suelo "
                             "artificial del Urban Atlas 2021 dentro del término municipal (commune en "
                             "Francia)."},
        "indicators": out,
    }


# --- Page ----------------------------------------------------------------------------------

def _summers(sums: list[dict], lang: str) -> str:
    lst = sums[0]["lst"] if sums else {}
    years = lst.get("summers") or []
    return "–".join(str(y) for y in years[::max(1, len(years) - 1)]) or i18n.t(lang, "p_heat_default")


def _parameters(sums: list[dict], lang: str, country: str) -> str:
    income_year = sums[0]["income_year"] if sums else config.INCOME_YEAR
    rows = [("p_income", {"year": income_year}), ("p_units", {})]
    if country == "FR":
        rows.append(("p_people", {"year": config.CENSUS_YEAR}))
    rows += [("p_shade", {}), ("p_shade2", {"year": config.TCD_YEAR}),
             ("p_heat", {"summers": _summers(sums, lang), "clear": config.LST_MIN_CLEAR,
                         "res": config.LST_RESOLUTION_M}),
             ("p_ranked", {"pop": config.MIN_POPULATION, "urban": int(config.MIN_URBAN_SHARE * 100)}),
             ("p_quintiles", {}), ("p_ci", {}), ("p_art8", {"year": config.TCD_YEAR})]
    if lang == "fr":  # the numbers that went into the strings need French spacing too
        fix = i18n._fr_typography
    else:
        fix = str
    return '<table class="params">' + "".join(
        f"<tr><th>{escape(i18n.t(lang, k))}</th><td>{escape(fix(i18n.t(lang, k + '_v', **kw)))}</td></tr>"
        for k, kw in rows) + "</table>"


def _list(pairs: list[tuple[str, str]], lang: str) -> str:
    """«Paris 0,52, Lyon 0,48» / «Paris 0,52 y Lyon 0,48»."""
    items = [f"{escape(a)} {b}" for a, b in pairs]
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + (" y " if lang == "es" else " et ") + items[-1]


def _validation(sums: list[dict], lang: str, country: str) -> str:
    n = lambda x, d=0, sign=False: i18n.num(None if x is None or pd.isna(x) else x, lang, d, sign)  # noqa: E731
    rows = "".join(f"<tr><td>{escape(s['name'])}</td><td class='num'>{n(s.get('rho_stl_tcd'), 2)}</td></tr>"
                   for s in sums if s.get("rho_stl_tcd") is not None)
    table = (f'<table class="params valid"><tr><th>{i18n.t(lang, "th_city")}</th><th class="num">'
             f'{i18n.t(lang, "v_th_rho")}</th></tr>' + rows + "</table>") if rows else ""
    v = config.VALIDATION_DIR / "inventories.json"
    res = []
    if v.exists():
        res = [x for x in json.loads(v.read_text(encoding="utf-8")).get("results", [])
               if country_of(x) == country]
    if not res:
        return table + f'<p class="note">{i18n.t(lang, "inv_pending")}</p>'
    rows = "".join(
        f"<tr><td>{escape(x['name'])}</td><td class='num'>{n(x['trees'])}</td>"
        f"<td class='num'>{n(x['rho_stl'], 2)}</td><td class='num'>{n(x['rho_tcd'], 2)}</td>"
        f"<td class='num'>{n(x['ci_canopy'], 2, True)}</td>"
        f"<td class='num'>{n(x['ci_trees'], 2, True)}</td>"
        f"<td class='num'>{n(x['ci_trees_per_resident'], 2, True)}</td></tr>" for x in res)
    sources = "; ".join(f"{escape(x['source'])}, {escape(x['edition'])}" for x in res)
    head = "".join(f'<th class="num">{i18n.t(lang, k)}</th>' for k in
                   ("inv_trees", "inv_rho_stl", "inv_rho_tcd", "inv_ci_shade", "inv_ci_trees", "inv_ci_res"))
    if country == "ES":
        mad = next((x for x in res if x["slug"] == "madrid" and "ci_basal" in x), None)
        trunk = i18n.t(lang, "inv_trunk", rho=n(mad["rho_basal_stl"], 2),
                       ci=n(mad["ci_basal"], 2, True)) if mad else ""
        findings = i18n.t(lang, "inv_findings", trunk=trunk)
    else:
        by = {x["slug"]: x for x in res}
        findings = ""
        if {"paris", "lyon"} <= set(by):
            findings = i18n.t(lang, "inv_findings", **{
                f"{c}_{k}": n(by[c][f], 2, k.startswith("ci"))
                for c in ("paris", "lyon")
                for k, f in (("stl", "rho_stl"), ("tcd", "rho_tcd"),
                             ("ci_trees", "ci_trees"), ("ci_shade", "ci_canopy"))})
    return (table + f"<h3>{i18n.t(lang, 'inv_title')}</h3>"
            f'<table class="params valid"><tr><th>{i18n.t(lang, "th_city")}</th>{head}</tr>' + rows + "</table>"
            + (f"<p>{findings}</p>" if findings else "") +
            f'<p class="note">{i18n.t(lang, "inv_note", sources=sources)}</p>')


def _caveats(sums: list[dict], lang: str, country: str) -> str:
    """The paragraphs under «what to know before quoting it» that depend on the data."""
    n = lambda x: i18n.num(x, lang)  # noqa: E731
    years = "/".join(map(str, sorted({s["income_year"] for s in sums})))
    out = [i18n.t(lang, "cav_years", year=years, tcd=config.TCD_YEAR, census=config.CENSUS_YEAR)]
    if country == "FR":
        out.append(i18n.t(lang, "cav_filosofi", year=config.FILOSOFI_YEAR))
        secret = []
        for s in sums:
            if s.get("sections_without_income"):
                df = _read_units(s)
                share = df.population[df.income.isna()].sum() / df.population.sum()
                secret.append((s["name"], i18n.t(lang, "of", a=n(s["sections_without_income"]), b=n(s["sections"]))
                               + " (" + i18n.t(lang, "of_people", p=i18n.num(100 * share, lang, 0)) + ")"))
        if secret:
            out.append(i18n.t(lang, "cav_secret", cities=_list(secret, lang)))
        out.append(i18n.t(lang, "cav_scope"))
    gaps = []
    for s in sums:
        df = _read_units(s)
        urban = df[(df.population >= config.MIN_POPULATION) & (df.urban_share >= config.MIN_URBAN_SHARE)]
        share = urban.lst_c.isna().mean() if len(urban) else 0
        if share > LST_GAP_SHARE:
            gaps.append((s["name"], i18n.t(lang, "of", a=n(int(urban.lst_c.isna().sum())), b=n(len(urban)))))
    if gaps:
        out.append(i18n.t(lang, "cav_lst_gaps", cities=_list(gaps, lang), clear=config.LST_MIN_CLEAR))
    out.append(i18n.t(lang, "cav_other_country"))
    if lang == "fr":
        out = [i18n._fr_typography(p) for p in out]
    return "".join(f"<p>{p}</p>" for p in out)


def _countries(lang: str, country: str) -> str:
    links = "".join(
        f' <a href="{page}"' + (' aria-current="page"' if c == country else "") + f">{i18n.t(lang, 'country_' + c)}</a>"
        + (" ·" if i < len(config.PAGES) - 1 else "")
        for i, (c, page) in enumerate(config.PAGES.items()))
    return f'<nav class="paises label" aria-label="{i18n.t(lang, "countries")}">{links.strip()}</nav>'


def page(sums: list[dict], country: str) -> str:
    lang = i18n.lang_of(country)
    sp = i18n.space(lang)
    ci = [s["ci_canopy"] for s in sums if s.get("ci_canopy") is not None]
    gaps = sorted(s["lst_gap"] for s in sums if s.get("lst_gap") is not None)
    gap = gaps[len(gaps) // 2] if gaps else None
    years = "/".join(map(str, sorted({s["income_year"] for s in sums})))
    kw = {"n": len(sums), "year": years, "tcd": config.TCD_YEAR, "repo": config.REPO_URL}
    kw_th = {**kw, "year": config.TCD_YEAR}
    html = re.sub(r"\[\[(\w+)\]\]",
                  lambda m: i18n.t(lang, m[1], **(kw_th if m[1] == "th_canopy" else kw)), TEMPLATE)
    js = {**i18n.js(lang), "sp": sp}
    return (html
            .replace("__LANG__", lang)
            .replace("__LOGO__", LOGO_SVG)
            .replace("__FAVICON__", favicon_link(ACCENT, ACCENT_DARK))
            .replace("__COMMON_CSS__", COMMON_CSS)
            .replace("__ACCENT__", ACCENT).replace("__ACCENT_DARK__", ACCENT_DARK)
            .replace("__PAISES__", _countries(lang, country))
            .replace("__FOOTER_NAV__", footer_nav(lang))
            .replace("__TCD__", str(config.TCD_YEAR))
            .replace("__NRICA__", i18n.t(lang, "of", a=sum(c > 0 for c in ci), b=len(ci)))
            .replace("__BRECHA__", f"{i18n.num(gap, lang, 1, True)}{sp}°C")
            .replace("__NSEC__", i18n.num(sum(s["sections"] for s in sums), lang))
            .replace("__POB__", i18n.num(sum(s["population"] for s in sums), lang))
            .replace("__PARAMETROS__", _parameters(sums, lang, country))
            .replace("__VALIDACION__", _validation(sums, lang, country))
            .replace("__AVISOS__", _caveats(sums, lang, country))
            .replace("__LOCALE__", i18n.LOCALE[lang])
            .replace("__T__", json.dumps(js, ensure_ascii=False))
            .replace("__DATOS__", json.dumps(
                [{k: s[k] for k in ("slug", "name", "sections", "ranked", "population_ranked", "ci_canopy",
                                    "canopy_pct", "quintiles", "lst_gap", "canopy_urban_tcd_pct")} for s in sums],
                ensure_ascii=False, separators=(",", ":"))))


TEMPLATE = r"""<!doctype html>
<html lang="__LANG__">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
__FAVICON__
<title>[[title]]</title>
<meta name="description" content="[[description]]">
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
.paises{margin:0;font-size:14px;color:var(--muted)} .paises a[aria-current]{color:var(--ink);text-decoration:none}
@media (max-width:900px){main,.method,.dos{grid-template-columns:1fr}}
</style>
</head>
<body>
<header class="site-header">
  <div class="marca">
    <h1>__LOGO__[[h1]]</h1>
    <span class="label">[[label]]</span>
    __PAISES__
  </div>
  <p class="lede">[[lede]]</p>
  <div class="figures">
    <div><b>__NRICA__</b><span>[[fig_rich]]</span></div>
    <div><b>__BRECHA__</b><span>[[fig_heat]]</span></div>
    <div><b>__NSEC__</b><span>[[fig_units]]</span></div>
    <div><b>__POB__</b><span>[[fig_people]]</span></div>
  </div>
</header>

<section class="bloque" id="ciudades">
  <h2>[[by_city]]</h2>
  <p class="note">[[by_city_note]]</p>
  <div class="tabla-wrap"><table class="ciudades">
    <thead><tr><th>[[th_city]]</th><th>[[th_ci]]</th><th class="num">[[th_q1]]</th><th class="num">[[th_q5]]</th><th class="num">[[th_heat]]</th><th class="num">[[th_canopy]]</th></tr></thead>
    <tbody id="filas"></tbody>
  </table></div>
</section>

<section class="bloque" id="detalle">
  <div class="controles">
    <label>[[ctl_city]] <select id="f-ciudad"></select></label>
    <label>[[ctl_show]] <select id="f-modo"><option value="sombra">[[mode_shade]]</option><option value="calor">[[mode_heat]]</option><option value="renta">[[mode_income]]</option></select></label>
  </div>
</section>
<main>
  <div>
    <div class="mapa"><svg id="mapa" viewBox="0 0 800 600" role="img" aria-label="[[map_label]]">
      <defs><pattern id="rayas" width="5" height="5" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="5" stroke="var(--line)" stroke-width="2"/></pattern></defs>
      <g id="secciones"></g></svg></div>
    <div class="leyenda" id="leyenda" aria-label="[[legend]]"></div>
  </div>
  <div class="panel card" id="panel" aria-live="polite"></div>
</main>

<section class="bloque" id="por-que">
  <h2>[[why]]</h2>
  <div class="dos">
    <div>
      <p>[[why_1]]</p>
      <p>[[why_2]]</p>
    </div>
    <div>
      <p>[[why_3]]</p>
      <p class="aviso">[[why_4]]</p>
    </div>
  </div>
</section>

<section class="method" id="metodo">
  <div>
    <h2>[[method]]</h2>
    <ol>
      <li>[[step_1]]</li>
      <li>[[step_2]]</li>
      <li>[[step_3]]</li>
      <li>[[step_4]]</li>
      <li>[[step_5]]</li>
    </ol>
    <h3>[[params]]</h3>
    __PARAMETROS__
  </div>
  <div>
    <h3>[[contrast]]</h3>
    <p>[[contrast_p]]</p>
    __VALIDACION__
    <h3>[[caveats]]</h3>
    <p class="aviso">[[cav_stl]]</p>
    <p class="aviso">[[cav_landsat]]</p>
    __AVISOS__
    <h3>[[open_data]]</h3>
    <p>[[open_data_p]]</p>
  </div>
</section>

<footer class="site-footer">
  <p class="principle">[[principle]]</p>
  <p>[[sources]]</p>
__FOOTER_NAV__
</footer>
<script>
const C = __DATOS__, T = __T__, LOC = "__LOCALE__", SP = T.sp;
const num = (x,d=0) => x==null ? "—" : x.toLocaleString(LOC,{minimumFractionDigits:d,maximumFractionDigits:d});
const sig = (x,d=1) => x==null ? "—" : (x>0?"+":x<0?"−":"") + num(Math.abs(x),d);
const pct = (x,d=1) => num(x,d) + SP + "%", deg = (x,d=1) => num(x,d) + SP + "°C", eur = x => num(x) + SP + "€";
const fill = (s,o) => s.replace(/\{(\w+)\}/g, (_,k) => o[k]);
const selC = document.getElementById("f-ciudad"), selM = document.getElementById("f-modo");
const cache = {};
let cur = null, data = null, sel = null;
for (const c of C) selC.add(new Option(c.name, c.slug));

document.getElementById("filas").innerHTML = [...C].sort((a,b) => (b.ci_canopy??-9) - (a.ci_canopy??-9)).map(c => {
  const v = c.ci_canopy ?? 0, w = Math.min(Math.abs(v), .5) / .5 * 50;
  const bar = `<div class="barra" title="${num(c.ci_canopy,3)}"><i class="${v<0?"neg":""}" style="left:${v<0?50-w:50}%;width:${w}%"></i></div>`;
  return `<tr data-c="${c.slug}" tabindex="0"><td>${c.name}</td><td><span style="display:flex;gap:8px;align-items:center">${bar}<span class="data">${sig(c.ci_canopy,2)}</span></span></td>
    <td class="num">${pct(c.quintiles["1"].canopy)}</td><td class="num">${pct(c.quintiles["5"].canopy)}</td>
    <td class="num">${sig(c.lst_gap,1)}${SP}°C</td><td class="num">${pct(c.canopy_urban_tcd_pct)}</td></tr>`;
}).join("");
document.getElementById("filas").addEventListener("click", e => { const r = e.target.closest("tr"); if (r) { elegir(r.dataset.c); document.getElementById("detalle").scrollIntoView({behavior:"smooth"}); } });
document.getElementById("filas").addEventListener("keydown", e => { const r = e.target.closest("tr"); if (r && e.key === "Enter") elegir(r.dataset.c); });

// Rows: [unit code, path, population, income, canopy STL %, canopy TCD %, LST °C, ranked]
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
  // Many units have no tree patch at all: in shade mode they get their own class and the rest
  // are split into quartiles.
  const sinCopa = modo === "sombra";
  const br = modo === "calor" ? [-3,-1,1,3]
    : sinCopa ? [1e-9, ...cuartiles(rk.map(val).filter(v => v > 0))] : cortes(rk.map(val));
  const g = document.getElementById("secciones");
  for (const el of g.children) {
    const r = data.byId[el.dataset.c], v = val(r), k = r[7] ? clase(v, br) : null;
    el.classList.toggle("nd", k == null); el.style.fill = k == null ? "" : `var(--${ESC[modo]}${k})`;
    el.classList.toggle("sel", el.dataset.c === sel);
    el.firstChild.textContent = fill(T.tip, {id: r[0], pop: num(r[2]), inc: eur(r[3]), shade: pct(r[4]), lst: deg(r[6])}) + (r[7] ? "" : T.out);
  }
  const fmt = modo === "sombra" ? (x => pct(x)) : modo === "renta" ? (x => eur(Math.round(x/100)*100)) : (x => sig(x,0)+SP+"°C");
  const lab = modo === "calor" ? T.heat_bins.split("|")
    : sinCopa ? [T.no_patch, T.upto+fmt(br[1]), fmt(br[1])+" – "+fmt(br[2]), fmt(br[2])+" – "+fmt(br[3]), "≥ "+fmt(br[3])]
    : ["< "+fmt(br[0]), fmt(br[0])+" – "+fmt(br[1]), fmt(br[1])+" – "+fmt(br[2]), fmt(br[2])+" – "+fmt(br[3]), "≥ "+fmt(br[3])];
  const pre = modo === "sombra" ? T.pre_shade : modo === "renta" ? T.pre_income : fill(T.pre_heat, {t: deg(lstMedia)});
  document.getElementById("leyenda").innerHTML = pre + lab.map((t,i) => `<span><i style="background:var(--${ESC[modo]}${i})"></i>${t}</span>`).join("")
    + `<span><i style="background:url(#rayas);border:1px solid var(--line)"></i>${T.nodata}</span>`;
}
function dispersion(){
  const rk = data.s.filter(r => r[7] && r[3]!=null && r[4]!=null);
  const W = 360, H = 230, L = 40, R = 8, T0 = 14, B = 30;
  const xs = rk.map(r => r[3]), ys = rk.map(r => r[4]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y1 = Math.max(5, ...ys) * 1.05;
  const x = v => L + (v - x0) / (x1 - x0) * (W - L - R), y = v => T0 + (1 - v / y1) * (H - T0 - B);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${T.scatter_label}">`;
  for (const t of [0, .5, 1]) { const v = y1/1.05*t; s += `<line class="eje" x1="${L}" x2="${W-R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L-4}" y="${y(v)+4}" text-anchor="end">${pct(v,0)}</text>`; }
  for (const t of [0, .5, 1]) { const v = x0 + (x1-x0)*t; s += `<text x="${x(v)}" y="${H-14}" text-anchor="middle">${fill(T.thousand, {n: num(Math.round(v/1000))})}</text>`; }
  s += `<text x="${W-R}" y="${H-1}" text-anchor="end">${T.x_axis}</text>`;
  s += rk.map(r => `<circle class="pt${r[0]===sel?" sel":""}" data-c="${r[0]}" cx="${x(r[3]).toFixed(1)}" cy="${y(r[4]).toFixed(1)}" r="${Math.max(1.2, Math.sqrt(r[2])/18).toFixed(1)}"><title>${fill(T.pt, {id: r[0], inc: eur(r[3]), shade: pct(r[4])})}</title></circle>`).join("");
  return s + "</svg>";
}
function quintiles(c){
  // Two bands so labels never collide: ground temperature (points) on top, shade (bars) below.
  const W = 360, H = 200, L = 8, R = 8, T0 = 22, B = 22, bw = (W - L - R) / 5;
  const HT = 22, HB = 32;  // temperature band: label row + point range
  const top = T0 + HT + HB + 14, sub = T0 + HT + HB + 4;
  const q = [1,2,3,4,5].map(k => c.quintiles[k]);
  const ms = Math.max(...q.map(v => v.canopy || 0)) || 1;
  const ls = q.map(v => v.lst).filter(v => v!=null), lmin = Math.min(...ls), lmax = Math.max(...ls);
  let s = `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${T.q_label}"><text class="tit" x="${L}" y="12">${T.q_title}</text>`;
  s += `<line class="eje" x1="${L}" x2="${W-R}" y1="${sub}" y2="${sub}"/>`;
  q.forEach((v,i) => {
    const h = (v.canopy||0)/ms*(H-top-B-14), cx = L + bw*i + bw/2;
    s += `<rect class="q" x="${L+bw*i+8}" y="${H-B-h}" width="${bw-16}" height="${h}"><title>${fill(T.q_shade, {k: i+1, v: pct(v.canopy)})}</title></rect>`;
    s += `<text x="${cx}" y="${H-B-h-4}" text-anchor="middle">${pct(v.canopy)}</text>`;
    if (v.lst!=null) { const yy = T0 + HT + (lmax - v.lst) / ((lmax - lmin) || 1) * HB; s += `<circle class="qh" cx="${cx}" cy="${yy}" r="4"><title>${fill(T.q_heat, {k: i+1, v: deg(v.lst)})}</title></circle><text x="${cx}" y="${T0 + 12}" text-anchor="middle">${deg(v.lst)}</text>`; }
    s += `<text x="${cx}" y="${H-6}" text-anchor="middle">${i===0?T.poorest:i===4?T.richest:"Q"+(i+1)}</text>`;
  });
  return s + "</svg>";
}
function panel(){
  const c = cur, p = document.getElementById("panel");
  let extra = "";
  if (sel && data.byId[sel]) { const r = data.byId[sel];
    extra = `<div class="card"><b>${T.unit} ${r[0]}</b><dl class="cifras"><div><dt>${T.residents}</dt><dd>${num(r[2])}</dd></div><div><dt>${T.income_uc}</dt><dd>${eur(r[3])}</dd></div><div><dt>${T.shade_stl}</dt><dd>${pct(r[4])}</dd></div><div><dt>${T.shade_tcd}</dt><dd>${pct(r[5])}</dd></div><div><dt>${T.ground}</dt><dd>${deg(r[6])}</dd></div></dl></div>`; }
  p.innerHTML = `<div><h2 id="${c.slug}">${c.name}</h2><p class="sub">${fill(T.ranked, {a: num(c.ranked), b: num(c.sections), pop: num(c.population_ranked)})}</p></div>
    <dl class="cifras">
      <div><dt>${T.ci}</dt><dd>${sig(c.ci_canopy,2)}</dd></div>
      <div><dt>${T.mean_shade}</dt><dd>${pct(c.canopy_pct)}</dd></div>
      <div><dt>${T.shade_q}</dt><dd>${num(c.quintiles["1"].canopy,1)} / ${pct(c.quintiles["5"].canopy)}</dd></div>
      <div><dt>${T.ground_q}</dt><dd>${sig(c.lst_gap,1)}${SP}°C</dd></div>
      <div><dt>${T.canopy} __TCD__</dt><dd>${pct(c.canopy_urban_tcd_pct)}</dd></div>
    </dl>
    <figure class="graf" style="margin:0">${quintiles(c)}</figure>
    <figure class="graf" style="margin:0">${dispersion()}<figcaption class="note">${T.scatter_note}</figcaption></figure>
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


def build() -> list[Path]:
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
    out = []
    for country, name in config.PAGES.items():
        mine = [s for s in sums if country_of(s) == country]
        if mine:
            path = config.DOCS_DIR / name
            path.write_text(page(mine, country), encoding="utf-8")
            out.append(path)
    return out
