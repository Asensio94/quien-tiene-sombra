# ¿Quién tiene sombra?

Cubierta arbórea y temperatura de superficie en verano por sección censal, frente a la renta de los hogares, en las veinte ciudades españolas de más de 200.000 habitantes; y por IRIS en seis ciudades francesas (París, Marsella, Lyon, Toulouse, Burdeos y Lille). Datos de Copernicus (Urban Atlas, Street Tree Layer, Tree Cover Density), Landsat 8 y 9, el INE y el Insee. Web: <https://asensio94.github.io/quien-tiene-sombra/> (España, en español) y <https://asensio94.github.io/quien-tiene-sombra/france.html> (Francia, en francés).

La pregunta es la de Schwarz y otros (2015, [«Trees grow on money»](https://doi.org/10.1371/journal.pone.0122051), PLoS ONE): ¿tienen los barrios pobres menos sombra y más calor? Además, la página publica la cubierta arbórea urbana de cada ciudad en 2024, la base contra la que el Reglamento europeo de Restauración (art. 8) exige que no baje.

> **Estado: mantenimiento.** Sigue funcionando y se corrigen sus fallos, pero por ahora no se le añaden funciones.

## Cómo funciona

1. **Secciones y renta.** Secciones censales del INE y renta media por unidad de consumo del Atlas de Distribución de Renta de los Hogares (ADRH). La renta del año N va con las secciones a 1 de enero de N+1: los códigos del ADRH 2023 casan uno a uno con el seccionado de 2024.
2. **Sombra.** Parte de cada sección cubierta por la Street Tree Layer 2021 (manchas de árboles de 500 m² o más sobre suelo artificial) más el bosque urbano del Urban Atlas 2021 (clase 31000). Como contraste, la densidad media de la Tree Cover Density 2024 a 10 m.
3. **Calor.** Temperatura de superficie de Landsat 8 y 9 (Collection 2, nivel 2, banda ST_B10) de julio y agosto de los tres últimos veranos. Se enmascaran nubes, sombras, nieve y agua con `QA_PIXEL`; cada píxel de 30 m se queda con la mediana de sus días despejados (al menos cuatro), y cada sección con la media de sus píxeles.
4. **Comparación.** Entran las secciones con 300 residentes o más y al menos la mitad de suelo artificial según el Urban Atlas. Se reparten en quintiles de renta con la misma población y se calcula el índice de concentración de la sombra (de −1 a 1, ponderado por población; positivo si se acumula en las secciones de más renta).
5. **Indicador del art. 8.** Media de la Tree Cover Density 2024 sobre el suelo artificial del Urban Atlas dentro del término municipal: la capa que las notas explicativas de la Comisión (julio de 2026) indican para aplicar el Reglamento.

## Francia

Francia es una dimensión más del mismo proyecto (`country = "FR"`), con el mismo método y la misma regla; solo cambian la unidad y la fuente de la renta.

- **Unidad: IRIS.** Los barrios de unos 2.000 habitantes que el Insee dibuja para el censo, con los contornos del IGN (servicio WFS `STATISTICALUNITS.IRIS:contours_iris` de data.geopf.fr). París, Lyon y Marsella publican sus IRIS bajo los códigos de sus distritos (751xx, 6938x, 132xx), que el código reagrupa en el municipio (75056, 69123, 13055).
- **Renta: Filosofi 2021.** Mediana de la renta disponible por unidad de consumo (`DISP_MED21`), después de impuestos y prestaciones. Es el último año: el Insee no publicará 2022 porque, sin la taxe d'habitation, ya no puede ligar los hogares fiscales a su vivienda con la calidad necesaria. No es la misma magnitud que la media de renta neta del ADRH: **los euros no se comparan entre países**; los índices de concentración y los quintiles sí, porque solo dependen del orden dentro de cada ciudad.
- **Población: censo 2022** (`P22_POP`, IRIS). Los códigos de Filosofi (geografía de 2022), del censo y de los contornos casan uno a uno en las seis ciudades.
- **Secreto estadístico.** El Insee deja en blanco («ns», «nd») la renta de los IRIS con pocos hogares fiscales o con estimación poco fiable. Esos IRIS se ven en el mapa, rayados, pero no entran en los quintiles. Pesa sobre todo en Marsella.
- **Inventarios de arbolado.** París (Ville de Paris, *Les arbres*: alineación, parques, cementerios y escuelas, sin los bosques de Boulogne y Vincennes) y Lyon (Métropole de Lyon: solo árboles de alineación). Solo se guardan recuentos por IRIS. En París confirman la capa de sombra (correlación de rangos de 0,56 con el STL y 0,42 con el TCD). En Lyon la correlación es negativa (−0,38 y −0,29): los IRIS con más copa son las colinas arboladas de los distritos 5.º y 9.º, con pocos árboles de calle, y los de alineación se concentran en el centro denso. El inventario de Lyon mide otra cosa y no sirve para validar; la web francesa lo explica.
- **Página en francés.** `docs/france.html`, generada con la misma plantilla que la española a partir de `shade/i18n.py` (un diccionario por idioma, tipografía francesa con espacio fino ante «%», «:» y como separador de miles). Los datos (CSV, JSON) no dependen del idioma.

## Contraste

- **Dos capas de árboles.** Para cada ciudad se publica la correlación de rangos entre la sombra de la Street Tree Layer y la de la Tree Cover Density por sección. Si ordenan igual, el resultado no depende de la capa.
- **Inventarios municipales.** Árboles por hectárea de los inventarios de arbolado de Madrid (798.391 árboles) y Barcelona (213.441), sin palmeras, frente a la sombra de cada sección. Ordenan las secciones de forma parecida a las capas de satélite (correlación de rangos de 0,40 a 0,46; en Madrid, con la sección de los troncos, 0,58). Pero no se concentran en las secciones de más renta: por hectárea están repartidos casi por igual (índice de +0,01 en Madrid y −0,03 en Barcelona), y en Madrid tampoco son más grandes. La sombra de más que ve el satélite en los barrios ricos sale de lo que no está en el inventario: jardines privados, patios de manzana y suelo de otras administraciones. Es solo validación; no entra en las cifras.

## Límites

- La Street Tree Layer no ve los árboles de alineación sueltos ni las copas de menos de 500 m². En barrios densos de calles estrechas eso es casi toda la sombra de la calle.
- Landsat pasa hacia las 10:50 hora solar: mide el suelo a media mañana, no el pico de la tarde ni la temperatura del aire, y los tejados cuentan igual que la calle.
- Las capas no son del mismo año: renta de 2023, Street Tree Layer de 2020–2021, Tree Cover Density de 2024, Landsat de los tres últimos veranos.
- La Street Tree Layer 2021 aún figura como «no validada» y cambia de método respecto a la de 2018; las dos ediciones no se comparan entre sí.
- En secciones pequeñas el INE asigna parte de la renta por imputación para proteger el secreto estadístico. Además, los extremos aparecen recortados: la misma renta mínima (8.797 €) y máxima (58.752 €) se repite en muchas ciudades, así que dentro del quintil más rico no se distingue lo muy rico de lo rico.
- La unidad es el municipio núcleo, no el área urbana funcional: L'Hospitalet va aparte de Barcelona, y Villeurbanne o Saint-Denis quedan fuera en Francia.
- En Francia los años casan peor: renta de 2021, población de 2022, Tree Cover Density de 2024. Filosofi no tiene relevo, así que no se puede seguir la evolución de la brecha de renta.
- Donde Landsat no tiene cuatro pasadas despejadas por píxel en tres veranos, la sección o el IRIS se queda sin temperatura y fuera de la comparación. No se cambia la regla para ninguna ciudad; la página dice cuántas unidades se pierden.

## Pendiente

- Ampliar a las 81 áreas urbanas funcionales con Street Tree Layer 2021.
- Proponer a Estado de las IBA el formato de `indicators.json` (la cubierta arbórea no es un hecho con fecha y no encaja en `signals.json`). La versión 2 añade `country` a cada indicador y lo incluye en el `id` (`urban_tree_canopy:FR:75056:2024`), porque un código INE y uno INSEE pueden coincidir.

## Uso

```bash
pip install -r requirements.txt
export CDSE_USER=… CDSE_PASSWORD=…   # cuenta gratuita de Copernicus Data Space
python -m shade income-year            # último año de renta publicado por el INE
python -m shade run --city madrid      # una ciudad; sin --city, todas
python -m shade run --country FR       # solo las ciudades francesas
python -m shade validate               # contraste con los inventarios de Madrid, Barcelona, París y Lyon
python -m shade web                    # docs/ a partir de data/sections y data/validation
python -m pytest
```

El bot (`.github/workflows/anual.yml`) pasa cada 10 de noviembre, después de que el INE publique el ADRH, y se puede lanzar a mano para una ciudad o solo para rehacer la página. Necesita los secretos `CDSE_USER` y `CDSE_PASSWORD`.

## Datos que se guardan

| Fichero | Contenido |
|---|---|
| `data/sections/<ciudad>.csv` | Cada sección (columna `CUSEC`) o IRIS (columna `IRIS`): población, renta, superficie, parte urbana, sombra STL y TCD, temperatura del suelo y si entra en la comparación |
| `data/sections/<ciudad>.json` | Resumen de la ciudad: índice de concentración, quintiles, brechas, cubierta arbórea urbana y escenas usadas |
| `docs/secciones.csv`, `docs/iris.csv`, `docs/ciudades.csv` | Lo mismo, junto, para descargar, con una columna `country` |
| `docs/data/<ciudad>.json` | Secciones o IRIS simplificados para el mapa |
| `docs/index.html`, `docs/france.html` | Página de España (en español) y de Francia (en francés) |
| `data/validation/<ciudad>.csv`, `inventories.json` | Árboles de los inventarios municipales por sección (y sección de tronco por hectárea en Madrid) y su comparación con las capas |
| `docs/indicators.json` | Cubierta arbórea urbana por ciudad (propuesta de formato para los proyectos hermanos) |
| `data/cache/` | Descargas; no se guarda en el repositorio |

## Fuentes y licencias

- Street Tree Layer 2021, Urban Atlas 2021 y HRL Tree Cover Density 2024: Copernicus Land Monitoring Service, © Unión Europea, Agencia Europea de Medio Ambiente. Acceso libre y gratuito según el Reglamento Delegado (UE) 1159/2013.
- Landsat 8 y 9 Collection 2 Level-2: USGS, dominio público; vía Microsoft Planetary Computer.
- Inventarios de arbolado: Ayuntamiento de Madrid (datos.madrid.es) y Ajuntament de Barcelona (Open Data BCN), CC BY 4.0. Solo se publican recuentos por sección.
- Atlas de Distribución de Renta de los Hogares y secciones censales: Instituto Nacional de Estadística, con mención de la fuente.
- Filosofi 2021 y censo 2022 por IRIS: Insee, licencia abierta Etalab 2.0. Contornos IRIS: IGN e Insee, licencia abierta Etalab 2.0.
- Inventarios de arbolado de Francia: Ville de Paris (opendata.paris.fr, ODbL) y Métropole de Lyon (data.grandlyon.com, con la licencia que indica la ficha del conjunto). Solo se publican recuentos por IRIS.

Código con licencia MIT; datos propios con licencia CC BY 4.0.

Forma parte de un conjunto de proyectos hermanos: [Observatorio de alegaciones](https://asensio94.github.io/observatorio-alegaciones/), [Vigía de incendios](https://asensio94.github.io/vigia-incendios/), [Centinela Natura](https://asensio94.github.io/centinela-natura/), [Vigilancia de humedales](https://asensio94.github.io/vigilancia-humedales/), [Sub Nocte](https://asensio94.github.io/sub-nocte/), [Riesgo de tendidos para aves](https://asensio94.github.io/riesgo-tendidos-aves/), [Grafo de promotores](https://asensio94.github.io/grafo-promotores/), [Cartera de las cotizadas](https://asensio94.github.io/cartera-cotizadas/), [Cuaderno de campo](https://asensio94.github.io/cuaderno-campo/), [Caudal ecológico](https://asensio94.github.io/caudal-ecologico/) y [Estado de las IBA](https://asensio94.github.io/estado-iba/).
