"""python -m shade {run,web,income-year}"""
from __future__ import annotations

import argparse
import logging
import sys
import traceback

from . import config


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="shade")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="compute sections and summary for some or all cities")
    r.add_argument("--city", action="extend", nargs="+", choices=sorted(config.CITY),
                   help="one or more slugs; default all")
    r.add_argument("--income-year", type=int, default=None,
                   help="ADRH year (default: the latest the INE publishes)")
    sub.add_parser("web", help="rebuild docs/ from data/sections")
    sub.add_parser("income-year", help="print the latest ADRH year")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    # GDAL warns once per Landsat tile that QA fill (1) was nudged to 0; the fill pixels are
    # dropped anyway because their thermal band is 0.
    logging.getLogger("rasterio").setLevel(logging.ERROR)

    if a.cmd == "income-year":
        from . import ine
        print(ine.latest_income_year())
        return 0
    if a.cmd == "web":
        from . import web
        print(web.build())
        return 0

    from . import city as city_mod, ine
    year = a.income_year or ine.latest_income_year()
    failed = []
    for slug in a.city or [c.slug for c in config.CITIES]:
        c = config.CITY[slug]
        try:
            df, summary = city_mod.process(c, year)
            city_mod.save(c, df, summary)
            logging.info("%s: C=%s, canopy gap %s pt, heat gap %s °C", c.name, summary["ci_canopy"],
                         summary["canopy_gap"], summary["lst_gap"])
        except Exception:  # one city failing must not lose the others
            traceback.print_exc()
            failed.append(slug)
    if failed:
        print(f"failed: {', '.join(failed)}", file=sys.stderr)
    return 1 if failed and len(failed) == len(a.city or config.CITIES) else 0


if __name__ == "__main__":
    raise SystemExit(main())
