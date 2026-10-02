"""CFTC : positions des gros spéculateurs (« non commerciaux ») sur les contrats à terme, chaque semaine.

Données officielles de la CFTC (rapport « Commitments of Traders », version « Legacy, futures only »),
par l'API publique publicreporting.cftc.gov, gratuite, sans compte. Positions du mardi, publiées le vendredi.
On suit 8 marchés qui touchent les placements (codes officiels vérifiés sur le rapport du 29 sept. 2026).
"""

from __future__ import annotations

import json
from datetime import timedelta
from zoneinfo import ZoneInfo

from ..models import Evenement, empreinte
from ..store import Depot
from ..validate import controle_source

VERSION = "cftc-1"
API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
MARCHES = {  # code officiel -> (nom en français, mot qui doit être dans le nom officiel)
    "13874A": ("S&P 500 (E-mini)", "E-MINI S&P 500"),
    "209742": ("Nasdaq-100 (E-mini)", "NASDAQ MINI"),
    "088691": ("Or", "GOLD"),
    "067651": ("Pétrole WTI", "WTI"),
    "085692": ("Cuivre", "COPPER"),
    "043602": ("Obligations américaines 10 ans", "UST 10Y NOTE"),
    "090741": ("Dollar canadien", "CANADIAN DOLLAR"),
    "133741": ("Bitcoin (CME)", "BITCOIN"),
}


def entier(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def nombre_fr(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def evenement(r: dict, publie: str) -> Evenement | None:
    code = (r.get("cftc_contract_market_code") or "").strip()
    if code not in MARCHES or not r.get("id") or not r.get("report_date_as_yyyy_mm_dd"):
        return None
    nom, _ = MARCHES[code]
    long_, short = entier(r.get("noncomm_positions_long_all")), entier(r.get("noncomm_positions_short_all"))
    dl, ds = entier(r.get("change_in_noncomm_long_all")), entier(r.get("change_in_noncomm_short_all"))
    if None in (long_, short, dl, ds):
        return None
    net, variation = long_ - short, dl - ds
    sens = "acheteurs" if net >= 0 else "vendeurs"
    var = f"{'+' if variation >= 0 else '−'}{nombre_fr(abs(variation))}"
    rapport = r["report_date_as_yyyy_mm_dd"][:10]
    return Evenement(
        source="cftc_cot", official_id=r["id"], category="baleines", kind="positions_speculateurs",
        title=f"{nom} : les gros spéculateurs sont {sens} nets de {nombre_fr(abs(net))} contrats ({var} en une semaine)",
        occurred_on=rapport, published_on=max(publie, rapport), official_url=f"{API}?id={r['id']}",
        sha256=empreinte(json.dumps(r, sort_keys=True).encode("utf-8")), parser_version=VERSION,
        entities=[r.get("market_and_exchange_names", "")], direction=(variation > 0) - (variation < 0),
        data={"marche": nom, "code": code, "nom_officiel": r.get("market_and_exchange_names"), "net": net,
              "variation": variation, "long": long_, "short": short, "open_interest": entier(r.get("open_interest_all")),
              "date_rapport": rapport},
    )


@controle_source("cftc_cot")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    oi = d.get("open_interest") or 0
    attendu = MARCHES.get(d.get("code"), (None, "\0"))[1]
    return {
        "marche_attendu": attendu in (d.get("nom_officiel") or "").upper(),
        "positions_coherentes": 0 <= d.get("long", -1) <= oi and 0 <= d.get("short", -1) <= oi,
        "variation_coherente": abs(d.get("variation", oi + 1)) <= oi,
    }


def collecter(ctx) -> list[Evenement]:
    codes = ",".join(f"'{c}'" for c in MARCHES)
    url = (f"{API}?$where=cftc_contract_market_code%20in({codes})"
           f"&$order=report_date_as_yyyy_mm_dd%20DESC&$limit={2 * len(MARCHES)}")
    rangees = json.loads(ctx.client.get(url).contenu)
    if not rangees:
        raise RuntimeError("aucune donnée de la CFTC")
    derniere = max(r["report_date_as_yyyy_mm_dd"] for r in rangees)
    if derniere[:10] < (ctx.maintenant.date() - timedelta(days=21)).isoformat():
        raise RuntimeError(f"rapport CFTC trop vieux : {derniere[:10]}")  # la source ne publie plus : à signaler
    # Date de publication : le jour où le robot voit le rapport (publié le vendredi après-midi).
    publie = ctx.maintenant.astimezone(ZoneInfo("America/Toronto")).date().isoformat()
    deja = Depot(ctx.donnees).ids_enregistres({"cftc_cot"})
    evs = []
    for r in rangees:
        if r["report_date_as_yyyy_mm_dd"] == derniere and r.get("id") not in deja:
            ev = evenement(r, publie)
            if ev:
                evs.append(ev)
    return evs
