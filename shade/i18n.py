"""Interface strings and number formats, one dictionary per language.

Each country's page is written in that country's language: the Spanish one in Spanish, the
French one in French. Data files (CSV, JSON) stay in canonical, language-independent values;
only what a reader sees goes through here. Same pattern as humedales/i18n.py in
vigilancia-humedales.

French strings are written with ordinary spaces and `_fr_typography` puts the narrow no-break
space where French typography wants it: before « % ; : ? ! » and units, inside the guillemets
and between groups of thousands.
"""
from __future__ import annotations

import re

LANG_BY_COUNTRY = {"ES": "es", "FR": "fr"}
LOCALE = {"es": "es-ES", "fr": "fr-FR"}
NNBSP = " "  # narrow no-break space


def lang_of(country: str) -> str:
    return LANG_BY_COUNTRY.get(country, "es")


def space(lang: str) -> str:
    """The space before a unit (%, °C, €): ordinary in Spanish, narrow no-break in French."""
    return " " if lang == "es" else NNBSP


def num(x: float | None, lang: str = "es", decimals: int = 0, sign: bool = False) -> str:
    """1.500 and 0,15 in Spanish, 1 500 and 0,15 in French; «—» if missing."""
    if x is None or x != x:
        return "—"
    s = f"{abs(x) if sign else x:,.{decimals}f}".replace(",", "_").replace(".", ",")
    s = s.replace("_", "." if lang == "es" else NNBSP)
    return (("+" if x > 0 else "−" if x < 0 else "") + s) if sign else s.replace("-", "−")


def _fr_typography(s: str) -> str:
    s = re.sub(r"(\d) (?=\d{3}\b)", r"\1" + NNBSP, s)       # 2 000
    s = re.sub(r" (?=[%;:?!»€]|°C|k€|m²)", NNBSP, s)       # 50 %, 3 °C, ombre ?
    return s.replace("« ", "«" + NNBSP)


def t(lang: str, key: str, **kw) -> str:
    """The string `key` in `lang`, formatted with `kw`. Falls back to Spanish."""
    s = UI.get(lang, UI["es"]).get(key) or UI["es"][key]
    return s.format(**kw) if kw else s


def js(lang: str) -> dict[str, str]:
    """The strings the page script needs, for `const T = …`."""
    return {k[3:]: t(lang, k) for k in UI["es"] if k.startswith("js_")}


UI: dict[str, dict[str, str]] = {
    "es": {
        "title": "¿Quién tiene sombra?",
        "h1": "¿Quién tiene <span>sombra</span>?",
        "description": ("Cubierta arbórea y temperatura de superficie en verano por sección censal frente a "
                        "la renta de los hogares, en las grandes ciudades españolas."),
        "countries": "Países",
        "country_ES": "España",
        "country_FR": "Francia",
        "label": "{n} ciudades · sección censal · renta {year}",
        "lede": ("Árboles y calor de verano, barrio a barrio, frente a la renta de los hogares. Con datos "
                 "abiertos de Copernicus, Landsat y el INE se mide cuánta sombra tiene cada sección censal "
                 "de las grandes ciudades y cuánto se calienta su suelo en julio y agosto, y se ordena por "
                 "lo que ganan sus vecinos."),
        "fig_rich": "ciudades donde la sombra se concentra en los barrios de más renta",
        "fig_heat": "más de calor en el suelo de los barrios más pobres (mediana de las ciudades)",
        "fig_units": "secciones censales",
        "fig_people": "residentes",
        "of": "{a} de {b}",
        "of_people": "{p} % de los residentes",
        "by_city": "Ciudad a ciudad",
        "by_city_note": ("El quintil más pobre y el más rico agrupan cada uno a la quinta parte de los "
                         "residentes. Pulse una ciudad para ver su mapa."),
        "th_city": "Ciudad",
        "th_ci": "Índice de concentración de la sombra",
        "th_q1": "Sombra, quintil más pobre",
        "th_q5": "Sombra, quintil más rico",
        "th_heat": "Calor de más en el quintil más pobre",
        "th_canopy": "Cubierta arbórea urbana {year}",
        "ctl_city": "Ciudad",
        "ctl_show": "Mostrar",
        "mode_shade": "Sombra",
        "mode_heat": "Calor",
        "mode_income": "Renta",
        "map_label": "Mapa de secciones censales",
        "legend": "Leyenda",
        "why": "Por qué importa",
        "why_1": ("En Baltimore, Nueva York y otras ciudades de Estados Unidos, la cubierta de árboles sigue a "
                  "la renta: Schwarz y otros lo resumieron en 2015 con un título que se ha hecho famoso, «Trees "
                  "grow on money» (<a href=\"https://doi.org/10.1371/journal.pone.0122051\">PLoS ONE 10: "
                  "e0122051</a>). Donde hay menos árboles el suelo se calienta más, y las olas de calor matan "
                  "sobre todo a personas mayores, enfermas o que viven en casas que no pueden refrescar."),
        "why_2": ("Esta página hace la misma pregunta en España con datos abiertos y la misma regla para todas "
                  "las ciudades: ¿tienen los barrios pobres menos sombra y más calor?"),
        "why_3": ("El Reglamento europeo de Restauración de la Naturaleza (<a href=\"https://eur-lex.europa.eu/"
                  "eli/reg/2024/1991/oj\">Reglamento (UE) 2024/1991</a>, artículo 8) obliga a que, en 2030, la "
                  "cubierta arbórea urbana no haya bajado respecto a 2024, y a que crezca después. La última "
                  "columna de la tabla es esa cifra para cada ciudad, medida con la capa que la Comisión "
                  "recomienda: la base de 2024 contra la que habrá que medir."),
        "why_4": ("Son indicios, no veredictos. Una sección con poca sombra puede tener otras razones (un casco "
                  "antiguo de calles estrechas, un polígono) y la temperatura del suelo no es la del aire que se "
                  "respira."),
        "method": "Cómo se calcula",
        "step_1": ("Se toman las secciones censales de cada municipio y su renta media por unidad de consumo del "
                   "Atlas de Distribución de Renta de los Hogares del INE, que reparte los ingresos declarados a "
                   "Hacienda según dónde vive cada persona. La unidad de consumo corrige el tamaño del hogar."),
        "step_2": ("La sombra de cada sección es la parte de su superficie cubierta por copas de árbol según la "
                   "Street Tree Layer del Urban Atlas de Copernicus, a la que se suma el bosque urbano que esa "
                   "capa deja fuera. Como contraste se calcula también la densidad de cubierta arbórea de la "
                   "capa Tree Cover Density, a 10 metros."),
        "step_3": ("El calor es la temperatura del suelo que mide la banda térmica de Landsat 8 y 9 en julio y "
                   "agosto. Se descartan los píxeles con nubes, sombras o agua y se toma, para cada punto, la "
                   "mediana de todos los días despejados de tres veranos. Después se promedia en cada sección."),
        "step_4": ("Solo entran en las comparaciones las secciones urbanas con suficientes vecinos. Se ordenan "
                   "por renta y se reparten en cinco grupos con la misma población: del quintil más pobre al "
                   "más rico."),
        "step_5": ("El índice de concentración resume en un número cómo se reparte la sombra a lo largo de esa "
                   "ordenación: 0 si todos tienen la misma, positivo si se acumula en los barrios ricos, "
                   "negativo si en los pobres."),
        "params": "Parámetros",
        "p_income": "Renta",
        "p_income_v": ("renta media por unidad de consumo, Atlas de Distribución de Renta de los Hogares del INE "
                       "({year}), por sección censal"),
        "p_units": "Secciones",
        "p_units_v": "las del INE a 1 de enero del año siguiente al de la renta, que son las que usa el Atlas",
        "p_shade": "Sombra",
        "p_shade_v": ("Street Tree Layer 2021 del Urban Atlas (manchas de árboles de 500 m² o más) y bosque urbano "
                      "(clase 31000 del Urban Atlas 2021), en % de la superficie de la sección"),
        "p_shade2": "Sombra, contraste",
        "p_shade2_v": "densidad de cubierta arbórea HRL Tree Cover Density {year}, 10 m",
        "p_heat": "Calor",
        "p_heat_v": ("temperatura de superficie de Landsat 8 y 9 (Collection 2 nivel 2, banda térmica), julio y "
                     "agosto de {summers}; mediana de las pasadas despejadas, al menos {clear} por píxel de {res} m"),
        "p_heat_default": "los tres últimos veranos",
        "p_ranked": "Secciones que cuentan",
        "p_ranked_v": ("al menos {pop} residentes y {urban} % de superficie artificial según el Urban Atlas; las "
                       "demás se ven en el mapa rayadas"),
        "p_quintiles": "Quintiles",
        "p_quintiles_v": "cinco grupos de secciones ordenadas por renta, con la misma población cada uno",
        "p_ci": "Índice de concentración",
        "p_ci_v": ("de −1 a 1, ponderado por población; positivo si la sombra se acumula en las secciones de "
                   "más renta"),
        "p_art8": "Cubierta arbórea urbana (art. 8)",
        "p_art8_v": ("media de la Tree Cover Density {year} sobre el suelo artificial del Urban Atlas 2021 dentro "
                     "del municipio"),
        "contrast": "Contraste",
        "contrast_p": ("Las dos capas de árboles miden cosas distintas: la Street Tree Layer dibuja manchas de "
                       "500 m² o más, y la Tree Cover Density estima la densidad de copa en cada píxel de 10 "
                       "metros. Si ordenan las secciones de forma parecida, la conclusión no depende de la capa "
                       "elegida."),
        "v_th_rho": "Correlación de rangos entre STL y Tree Cover Density por sección",
        "inv_title": "Inventarios municipales de arbolado",
        "inv_trees": "Árboles",
        "inv_rho_stl": "Correl. STL",
        "inv_rho_tcd": "Correl. TCD",
        "inv_ci_shade": "Índice sombra",
        "inv_ci_trees": "Índice árboles/ha",
        "inv_ci_res": "Índice árboles/vecino",
        "inv_note": "Sin palmeras. Fuentes: {sources}. Se guardan solo los recuentos por sección.",
        "inv_pending": ("Pendiente: comparar la sombra de cada sección con los inventarios municipales de "
                        "arbolado de Madrid y Barcelona (árboles por hectárea)."),
        "caveats": "Lo que hay que saber antes de citarlo",
        "cav_stl": ("La Street Tree Layer no ve los árboles de alineación sueltos ni las copas pequeñas, que en "
                    "los barrios densos son casi toda la sombra de la calle. Por eso los barrios de calles "
                    "estrechas pueden salir con menos sombra de la que se siente a pie."),
        "cav_landsat": ("Landsat pasa hacia las once de la mañana, hora solar. Mide el calor del suelo a esa hora, "
                        "no el de la tarde ni el del aire, y los tejados cuentan tanto como la calle."),
        "cav_years": ("La renta es de {year} y las capas de árboles, de 2020–2021 (Street Tree Layer) y {tcd} "
                      "(Tree Cover Density). Los árboles cambian despacio, pero una plantación o una tala grande "
                      "de esos años puede mover alguna sección. Las capas de 2018 y 2021 de la Street Tree Layer se "
                      "hicieron con métodos distintos y no se comparan entre sí."),
        "cav_other_country": ("Francia tiene su <a href=\"france.html\">propia página</a>, con el mismo método "
                              "por IRIS. Los índices de concentración y los quintiles se comparan entre países, "
                              "porque solo dependen del orden dentro de cada ciudad; los euros, no: allí se usa "
                              "la mediana de la renta disponible (después de impuestos y prestaciones) y aquí la "
                              "media de la renta neta."),
        "open_data": "Datos abiertos",
        "open_data_p": ("<a href=\"secciones.csv\">secciones.csv</a> con cada sección · <a href=\"ciudades.csv\">"
                        "ciudades.csv</a> con el resumen · <a href=\"indicators.json\">indicators.json</a> con la "
                        "cubierta arbórea urbana · <a href=\"{repo}\">código</a>."),
        "principle": ("Datos públicos, reglas a la vista y cada cifra enlazada a su fuente. Indicios, no "
                      "veredictos."),
        "sources": ("Street Tree Layer, Urban Atlas y Tree Cover Density: Copernicus Land Monitoring Service, © "
                    "Unión Europea, Agencia Europea de Medio Ambiente · Landsat 8 y 9: USGS, vía Microsoft "
                    "Planetary Computer · Renta, población y secciones censales: Instituto Nacional de "
                    "Estadística."),
        "inv_findings": ("Los árboles municipales por hectárea de cada sección ordenan las secciones de forma "
                         "parecida a las dos capas de satélite (correlaciones de rangos en torno a 0,4), así que "
                         "las capas miden algo real en la calle.{trunk} Pero esos árboles no se concentran en las "
                         "secciones de más renta: por hectárea están repartidos casi por igual. La sombra de más "
                         "que ve el satélite en los barrios ricos sale sobre todo de lo que no está en el "
                         "inventario: jardines privados, patios de manzana y suelo de otras administraciones. Por "
                         "vecino, en Madrid sí hay más árboles en los barrios ricos, porque están menos poblados."),
        "inv_trunk": (" En Madrid, que mide el perímetro de cada tronco, la sección del tronco por hectárea sigue "
                      "mejor a la Street Tree Layer (correlación de {rho}) y tampoco cambia con la renta (índice "
                      "{ci}): los árboles municipales de los barrios ricos no son más grandes."),
        "cav_lst_gaps": ("Landsat no tiene pasadas despejadas suficientes (al menos {clear} por píxel) sobre parte "
                         "de algunas ciudades: {cities} secciones urbanas se quedan sin temperatura y fuera de la "
                         "comparación. La regla no se cambia para ellas."),
        "ind_title": "Cubierta arbórea urbana de {name} en {year}",
        "legal_basis": "Reglamento (UE) 2024/1991, art. 8",
        "siblings": "Proyectos hermanos",
        # Strings used by the page script.
        "js_unit": "Sección",
        "js_tip": ("Sección {id} · {pop} residentes · {inc} por unidad de consumo · sombra {shade} · suelo "
                   "{lst}"),
        "js_out": " · no entra en la comparación",
        "js_heat_bins": "3 °C o más por debajo|1 a 3 °C por debajo|±1 °C|1 a 3 °C por encima|3 °C o más por encima",
        "js_no_patch": "sin manchas de árboles",
        "js_upto": "hasta ",
        "js_pre_shade": "Parte de la sección con copa de árbol: ",
        "js_pre_income": "Renta por unidad de consumo: ",
        "js_pre_heat": "Temperatura del suelo frente a la media de la ciudad ({t}): ",
        "js_nodata": "sin datos o no urbana",
        "js_scatter_label": "Renta y sombra de cada sección",
        "js_thousand": "{n} mil €",
        "js_x_axis": "renta por unidad de consumo →",
        "js_pt": "Sección {id}: {inc}, sombra {shade}",
        "js_q_label": "Sombra y calor por quintil de renta",
        "js_q_title": "Suelo en verano (puntos) y sombra (barras) por quintil de renta",
        "js_q_shade": "Quintil {k}: {v} de sombra",
        "js_q_heat": "Quintil {k}: {v}",
        "js_poorest": "más pobre",
        "js_richest": "más rico",
        "js_residents": "Residentes",
        "js_income_uc": "Renta por u. de consumo",
        "js_shade_stl": "Sombra (STL)",
        "js_shade_tcd": "Densidad de copa (TCD)",
        "js_ground": "Suelo en verano",
        "js_ranked": "{a} de {b} secciones entran en la comparación · {pop} residentes",
        "js_ci": "Índice de concentración",
        "js_mean_shade": "Sombra media",
        "js_shade_q": "Sombra, más pobre / más rico",
        "js_ground_q": "Suelo, más pobre − más rico",
        "js_canopy": "Cubierta arbórea urbana",
        "js_scatter_note": "Cada punto es una sección; su tamaño, los residentes. Pulse un punto o una sección del mapa.",
    },
    "fr": {
        "title": "Qui a de l'ombre ?",
        "h1": "Qui a de l'<span>ombre</span> ?",
        "description": ("Couvert arboré et température de surface en été par IRIS face au revenu des ménages, "
                        "dans les grandes villes françaises."),
        "countries": "Pays",
        "country_ES": "Espagne",
        "country_FR": "France",
        "label": "{n} villes · IRIS · revenus {year}",
        "lede": ("Les arbres et la chaleur de l'été, quartier par quartier, face au revenu des ménages. Avec les "
                 "données ouvertes de Copernicus, de Landsat et de l'Insee, on mesure l'ombre de chaque IRIS des "
                 "grandes villes françaises et combien son sol chauffe en juillet et en août, puis on les classe "
                 "selon le revenu de leurs habitants."),
        "fig_rich": "villes où l'ombre se concentre dans les quartiers les plus aisés",
        "fig_heat": "de chaleur en plus au sol des quartiers les plus pauvres (médiane des villes)",
        "fig_units": "IRIS",
        "fig_people": "habitants",
        "of": "{a} sur {b}",
        "of_people": "{p} % des habitants",
        "by_city": "Ville par ville",
        "by_city_note": ("Le quintile le plus pauvre et le plus aisé regroupent chacun un cinquième des habitants. "
                         "Cliquez sur une ville pour voir sa carte."),
        "th_city": "Ville",
        "th_ci": "Indice de concentration de l'ombre",
        "th_q1": "Ombre, quintile le plus pauvre",
        "th_q5": "Ombre, quintile le plus aisé",
        "th_heat": "Chaleur en plus dans le quintile le plus pauvre",
        "th_canopy": "Couvert arboré urbain {year}",
        "ctl_city": "Ville",
        "ctl_show": "Afficher",
        "mode_shade": "Ombre",
        "mode_heat": "Chaleur",
        "mode_income": "Revenu",
        "map_label": "Carte des IRIS",
        "legend": "Légende",
        "why": "Pourquoi c'est important",
        "why_1": ("À Baltimore, New York et dans d'autres villes des États-Unis, le couvert arboré suit le revenu : "
                  "Schwarz et ses coauteurs l'ont résumé en 2015 par un titre devenu célèbre, « Trees grow on "
                  "money » (<a href=\"https://doi.org/10.1371/journal.pone.0122051\">PLoS ONE 10 : e0122051</a>). "
                  "Là où il y a moins d'arbres, le sol chauffe davantage, et les canicules tuent surtout les "
                  "personnes âgées, malades ou qui vivent dans des logements impossibles à rafraîchir."),
        "why_2": ("Cette page pose la même question en France, avec des données ouvertes et la même règle pour "
                  "toutes les villes : les quartiers pauvres ont-ils moins d'ombre et plus de chaleur ? Elle "
                  "reprend la méthode de la <a href=\"index.html\">page espagnole</a>, IRIS par IRIS."),
        "why_3": ("Le règlement européen sur la restauration de la nature (<a href=\"https://eur-lex.europa.eu/"
                  "eli/reg/2024/1991/oj\">règlement (UE) 2024/1991</a>, article 8) impose qu'en 2030 le couvert "
                  "arboré urbain n'ait pas baissé par rapport à 2024, puis qu'il augmente. La dernière colonne du "
                  "tableau donne ce chiffre pour chaque ville, mesuré avec la couche que recommande la "
                  "Commission : le niveau de 2024 auquel il faudra se comparer."),
        "why_4": ("Ce sont des indices, pas des verdicts. Un IRIS avec peu d'ombre peut avoir d'autres raisons (un "
                  "centre ancien aux rues étroites, une zone d'activités) et la température du sol n'est pas "
                  "celle de l'air que l'on respire."),
        "method": "Comment c'est calculé",
        "step_1": ("On prend les IRIS de chaque commune, les petits quartiers d'environ 2 000 habitants que "
                   "l'Insee découpe pour le recensement, avec leur revenu disponible médian par unité de "
                   "consommation (dispositif Filosofi de l'Insee) et leurs habitants (recensement). Le revenu "
                   "disponible est ce qui reste après impôts et prestations sociales ; l'unité de consommation "
                   "corrige la taille du ménage."),
        "step_2": ("L'ombre de chaque IRIS est la part de sa surface couverte par des houppiers selon la Street "
                   "Tree Layer de l'Urban Atlas de Copernicus, à laquelle on ajoute la forêt urbaine que cette "
                   "couche laisse de côté. Pour comparer, on calcule aussi la densité du couvert arboré de la "
                   "couche Tree Cover Density, à 10 mètres."),
        "step_3": ("La chaleur est la température du sol que mesure la bande thermique de Landsat 8 et 9 en juillet "
                   "et en août. On écarte les pixels avec nuages, ombres ou eau et on garde, pour chaque point, la "
                   "médiane de tous les jours dégagés de trois étés. On en fait ensuite la moyenne dans chaque "
                   "IRIS."),
        "step_4": ("Seuls les IRIS urbains assez peuplés et dont l'Insee publie le revenu entrent dans les "
                   "comparaisons. On les classe par revenu et on les répartit en cinq groupes de même population : "
                   "du quintile le plus pauvre au plus aisé."),
        "step_5": ("L'indice de concentration résume en un nombre la façon dont l'ombre se répartit le long de ce "
                   "classement : 0 si tout le monde a la même, positif si elle s'accumule dans les quartiers "
                   "aisés, négatif si c'est dans les quartiers pauvres."),
        "params": "Paramètres",
        "p_income": "Revenu",
        "p_income_v": ("revenu disponible médian par unité de consommation, Filosofi {year} (Insee), par IRIS ; "
                       "c'est le dernier millésime"),
        "p_units": "IRIS",
        "p_units_v": ("contours IRIS de l'IGN et de l'Insee ; dans les six villes, les codes sont les mêmes dans "
                      "Filosofi (géographie au 1er janvier 2022), le recensement et les contours"),
        "p_people": "Habitants",
        "p_people_v": "population municipale du recensement {year}, par IRIS",
        "p_shade": "Ombre",
        "p_shade_v": ("Street Tree Layer 2021 de l'Urban Atlas (taches d'arbres de 500 m² ou plus) et forêt urbaine "
                      "(classe 31000 de l'Urban Atlas 2021), en % de la surface de l'IRIS"),
        "p_shade2": "Ombre, contrôle",
        "p_shade2_v": "densité du couvert arboré HRL Tree Cover Density {year}, 10 m",
        "p_heat": "Chaleur",
        "p_heat_v": ("température de surface de Landsat 8 et 9 (Collection 2 niveau 2, bande thermique), juillet "
                     "et août {summers} ; médiane des passages dégagés, au moins {clear} par pixel de {res} m"),
        "p_heat_default": "des trois derniers étés",
        "p_ranked": "IRIS retenus",
        "p_ranked_v": ("au moins {pop} habitants, un revenu publié par l'Insee et {urban} % de surface artificielle "
                       "selon l'Urban Atlas ; les autres apparaissent hachurés sur la carte"),
        "p_quintiles": "Quintiles",
        "p_quintiles_v": "cinq groupes d'IRIS classés par revenu, chacun avec la même population",
        "p_ci": "Indice de concentration",
        "p_ci_v": ("de −1 à 1, pondéré par la population ; positif si l'ombre s'accumule dans les IRIS les plus "
                   "aisés"),
        "p_art8": "Couvert arboré urbain (art. 8)",
        "p_art8_v": ("moyenne de la Tree Cover Density {year} sur les surfaces artificielles de l'Urban Atlas 2021 "
                     "dans la commune"),
        "contrast": "Contrôles",
        "contrast_p": ("Les deux couches d'arbres ne mesurent pas la même chose : la Street Tree Layer dessine des "
                       "taches de 500 m² ou plus, la Tree Cover Density estime la densité du houppier dans chaque "
                       "pixel de 10 mètres. Si elles classent les IRIS de façon proche, la conclusion ne dépend "
                       "pas de la couche choisie."),
        "v_th_rho": "Corrélation de rangs entre STL et Tree Cover Density par IRIS",
        "inv_title": "Inventaires municipaux des arbres",
        "inv_trees": "Arbres",
        "inv_rho_stl": "Corrél. STL",
        "inv_rho_tcd": "Corrél. TCD",
        "inv_ci_shade": "Indice ombre",
        "inv_ci_trees": "Indice arbres/ha",
        "inv_ci_res": "Indice arbres/habitant",
        "inv_note": "Sans palmiers. Sources : {sources}. Seuls les comptages par IRIS sont conservés.",
        "inv_pending": ("À venir : comparer l'ombre de chaque IRIS avec les inventaires d'arbres de Paris et de "
                        "Lyon (arbres par hectare)."),
        "caveats": "Ce qu'il faut savoir avant de le citer",
        "cav_stl": ("La Street Tree Layer ne voit pas les arbres d'alignement isolés ni les petits houppiers, qui "
                    "dans les quartiers denses font presque toute l'ombre de la rue. Les quartiers aux rues "
                    "étroites peuvent donc sortir avec moins d'ombre qu'on n'en sent à pied."),
        "cav_landsat": ("Landsat passe vers onze heures du matin, heure solaire. Il mesure la chaleur du sol à "
                        "cette heure-là, pas celle de l'après-midi ni celle de l'air, et les toits comptent autant "
                        "que la rue."),
        "cav_years": ("Le revenu est celui de {year} et les habitants ceux du recensement {census} ; les couches "
                      "d'arbres datent de 2020–2021 (Street Tree Layer) et de {tcd} (Tree Cover Density). Les "
                      "arbres changent lentement, mais une grande plantation ou un abattage de ces années-là peut "
                      "déplacer un IRIS."),
        "cav_filosofi": ("Filosofi {year} est le dernier millésime : l'Insee a renoncé à produire 2022, car la "
                         "suppression de la taxe d'habitation sur les résidences principales empêche de relier "
                         "les foyers fiscaux à leur logement avec la qualité voulue. Tant que la série ne reprend "
                         "pas, cette page ne peut pas suivre l'évolution des écarts de revenu."),
        "cav_other_country": ("Les indices de concentration et les quintiles se comparent avec la <a "
                              "href=\"index.html\">page espagnole</a>, car ils ne dépendent que du classement à "
                              "l'intérieur de chaque ville ; les euros, non : ici on utilise la médiane du "
                              "revenu disponible (après impôts et prestations), en Espagne la moyenne du revenu "
                              "net."),
        "open_data": "Données ouvertes",
        "open_data_p": ("<a href=\"iris.csv\">iris.csv</a> avec chaque IRIS · <a href=\"ciudades.csv\">"
                        "ciudades.csv</a> avec le résumé des villes des deux pays · <a href=\"indicators.json\">"
                        "indicators.json</a> avec le couvert arboré urbain · <a href=\"{repo}\">code</a>."),
        "principle": ("Données publiques, règles visibles et chaque chiffre relié à sa source. Des indices, pas "
                      "des verdicts."),
        "sources": ("Street Tree Layer, Urban Atlas et Tree Cover Density : Copernicus Land Monitoring Service, © "
                    "Union européenne, Agence européenne pour l'environnement · Landsat 8 et 9 : USGS, via "
                    "Microsoft Planetary Computer · Revenus (Filosofi) et population par IRIS : Insee · Contours "
                    "IRIS : IGN et Insee."),
        "inv_findings": ("À Paris, l'inventaire couvre les arbres gérés par la Ville (alignements, parcs et jardins, "
                         "cimetières, écoles), sans les bois de Boulogne et de Vincennes. Ses arbres par hectare "
                         "classent les IRIS dans un ordre proche de celui des deux couches satellite (corrélations "
                         "de rangs de {paris_stl} et {paris_tcd}), et leur indice de concentration selon le revenu "
                         "({paris_ci_trees}) va dans le même sens que celui de l'ombre ({paris_ci_shade}). À Lyon, "
                         "l'inventaire ne compte que les arbres d'alignement de la Métropole, et la corrélation "
                         "s'inverse ({lyon_stl} et {lyon_tcd}) : les IRIS les plus ombragés sont les collines "
                         "boisées des 5e et 9e arrondissements, qui ont peu d'arbres de rue, alors que les "
                         "alignements se concentrent dans les quartiers denses. Les deux couches satellite, elles, "
                         "s'accordent à Lyon comme ailleurs. L'inventaire lyonnais ne valide donc pas la couche "
                         "d'ombre ; il mesure autre chose, les arbres de rue, dont l'indice selon le revenu est de "
                         "{lyon_ci_trees}. Aucun inventaire ne compte les arbres des jardins privés ni des cours "
                         "d'immeubles, que le satellite voit."),
        "cav_secret": ("L'Insee ne diffuse pas le revenu d'un IRIS quand il compte trop peu de ménages fiscaux "
                       "(secret statistique) ou quand l'estimation n'est pas fiable. IRIS sans revenu : {cities}. "
                       "Ils restent sur la carte, hachurés, mais n'entrent pas dans les quintiles. S'ils étaient en "
                       "moyenne plus pauvres ou plus riches que les autres, les écarts mesurés en seraient un peu "
                       "déformés."),
        "cav_scope": ("On s'en tient à la commune centre : Villeurbanne, Saint-Denis ou Mérignac n'y sont pas, même "
                      "si elles font partie de la même agglomération. Les IRIS d'activité ou « divers » (bois, "
                      "ports, aéroports, grands équipements) ont peu d'habitants et restent en dehors des "
                      "comparaisons."),
        "cav_lst_gaps": ("Landsat n'a pas assez de passages dégagés (au moins {clear} par pixel) sur une partie de "
                         "certaines villes : {cities} IRIS urbains restent sans température et hors comparaison. "
                         "On ne change pas la règle pour eux."),
        "ind_title": "Couvert arboré urbain de {name} en {year}",
        "legal_basis": "Règlement (UE) 2024/1991, art. 8",
        "siblings": "Projets frères",
        "js_unit": "IRIS",
        "js_tip": ("IRIS {id} · {pop} habitants · {inc} par unité de consommation · ombre {shade} · sol {lst}"),
        "js_out": " · hors comparaison",
        "js_heat_bins": ("3 °C ou plus en dessous|1 à 3 °C en dessous|±1 °C|1 à 3 °C au-dessus|"
                         "3 °C ou plus au-dessus"),
        "js_no_patch": "pas de tache d'arbres",
        "js_upto": "jusqu'à ",
        "js_pre_shade": "Part de l'IRIS sous houppier : ",
        "js_pre_income": "Revenu disponible médian par unité de consommation : ",
        "js_pre_heat": "Température du sol par rapport à la moyenne de la ville ({t}) : ",
        "js_nodata": "sans données ou non urbain",
        "js_scatter_label": "Revenu et ombre de chaque IRIS",
        "js_thousand": "{n} k€",
        "js_x_axis": "revenu par unité de consommation →",
        "js_pt": "IRIS {id} : {inc}, ombre {shade}",
        "js_q_label": "Ombre et chaleur par quintile de revenu",
        "js_q_title": "Sol en été (points) et ombre (barres) par quintile de revenu",
        "js_q_shade": "Quintile {k} : {v} d'ombre",
        "js_q_heat": "Quintile {k} : {v}",
        "js_poorest": "plus pauvre",
        "js_richest": "plus aisé",
        "js_residents": "Habitants",
        "js_income_uc": "Revenu par u. de conso.",
        "js_shade_stl": "Ombre (STL)",
        "js_shade_tcd": "Densité du houppier (TCD)",
        "js_ground": "Sol en été",
        "js_ranked": "{a} IRIS sur {b} entrent dans la comparaison · {pop} habitants",
        "js_ci": "Indice de concentration",
        "js_mean_shade": "Ombre moyenne",
        "js_shade_q": "Ombre, plus pauvre / plus aisé",
        "js_ground_q": "Sol, plus pauvre − plus aisé",
        "js_canopy": "Couvert arboré urbain",
        "js_scatter_note": "Chaque point est un IRIS ; sa taille, ses habitants. Cliquez sur un point ou un IRIS de la carte.",
    },
}
UI["fr"] = {k: _fr_typography(v) for k, v in UI["fr"].items()}
