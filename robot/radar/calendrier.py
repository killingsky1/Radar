"""Calendrier de l'app : les fins prévues de blocage après une entrée en bourse (lot F, source sec_blocage).

Un blocage dure souvent 180 jours : plus que les 3 mois du fil. Les infos sont donc lues dans tous les mois gardés,
pour cette source seulement. Seulement les infos validées (« Officiel » ou « Confirmé ») ; rien n'est estimé : la date
de fin = date du prospectus + la durée écrite dans le prospectus. Les fins des 7 derniers jours restent, marquées
« passée ».
"""

from __future__ import annotations

from datetime import date, timedelta

from .store import Depot

MOIS_LUS = 15  # rattrapage depuis avril 2026 + blocages jusqu'à un an
JOURS_PASSES = 7


def preparer(depot: Depot, jour: date) -> dict:
    depuis = (jour - timedelta(days=JOURS_PASSES)).isoformat()
    evenements = {e["id"]: e for e in depot.lire("evenements", MOIS_LUS)
                  if e["source"] == "sec_blocage" and e["kind"] == "fin_blocage" and e.get("badge") in ("officiel", "confirme")
                  and (e.get("data") or {}).get("fin_blocage", "") >= depuis}
    lignes = sorted(({"id": e["id"], "symbole": (e.get("tickers") or [None])[0], "compagnie": (e.get("entities") or [""])[0],
                      "bourse": e["data"].get("bourse"), "fin": e["data"]["fin_blocage"], "duree": e["data"]["duree_jours"],
                      "prospectus": e["data"]["date_prospectus"], "depose": e["published_on"],
                      "passee": e["data"]["fin_blocage"] < jour.isoformat()}
                     for e in evenements.values()), key=lambda l: (l["fin"], l["compagnie"]))
    return {"jour": jour.isoformat(), "lignes": lignes, "evenements": evenements,
            "explication": "Après une entrée en bourse, les dirigeants et les anciens actionnaires s'engagent à ne pas "
                           "vendre pendant une période écrite dans le prospectus (souvent 180 jours). Dates prévues : les "
                           "banques qui ont mené l'entrée en bourse peuvent lever le blocage plus tôt. Information "
                           "seulement : 0 point dans la note."}
