"""Tests de la CFTC sur les VRAIES données des rapports du 22 et du 29 septembre 2026."""

import json
from datetime import date, datetime, timezone
from pathlib import Path

from radar.collecteurs import cftc
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "cftc" / "semaines.json"


def rangees():
    return json.loads(F.read_text(encoding="utf-8"))


def test_or_calcul_a_la_main():
    [r] = [r for r in rangees() if r["id"] == "260929088691F"]
    ev = valider(cftc.evenement(r, "2026-10-02"), date(2026, 10, 2))
    # 249 736 contrats acheteurs - 31 104 vendeurs = 218 632 nets ; variation -4 246 - (+2 975) = -7 221
    assert ev.title == "Or : les gros spéculateurs sont acheteurs nets de 218 632 contrats (−7 221 en une semaine)"
    assert (ev.data["net"], ev.data["variation"], ev.direction, ev.badge) == (218632, -7221, -1, "officiel")
    assert ev.occurred_on == "2026-09-29" and ev.official_url.endswith("?id=260929088691F")


def test_vendeurs_nets():
    [r] = [r for r in rangees() if r["id"].startswith("260929") and r["cftc_contract_market_code"] == "13874A"]
    ev = valider(cftc.evenement(r, "2026-10-02"), date(2026, 10, 2))
    assert ev.title.startswith("S&P 500 (E-mini) : les gros spéculateurs sont vendeurs nets de")


def test_marche_inattendu_va_dans_a_verifier():
    [r] = [r for r in rangees() if r["id"] == "260929088691F"]
    r = dict(r, market_and_exchange_names="SILVER - COMMODITY EXCHANGE INC.")  # le code ne correspond plus au nom
    ev = valider(cftc.evenement(r, "2026-10-02"), date(2026, 10, 2))
    assert ev.badge == "a_verifier" and ev.checks["marche_attendu"] is False


class FauxInternet:
    def __init__(self, donnees):
        self.donnees, self.appels = donnees, []

    def get(self, url):
        self.appels.append(url)
        if not url.startswith(cftc.API):
            raise ErreurSource(f"{url} : HTTP 404")
        c = json.dumps(self.donnees).encode()
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def test_seulement_la_derniere_semaine_et_une_seule_fois(tmp_path):
    internet = FauxInternet(sorted(rangees(), key=lambda r: r["report_date_as_yyyy_mm_dd"], reverse=True))
    lecteur = {"cftc_cot": cftc.collecter}
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 22, 17, tzinfo=timezone.utc),
                       collecteurs=lecteur)
    assert rapport["cftc_cot"] == {"ok": True, "nouveaux": 8, "modifies": 0, "inchanges": 0}
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    assert {e["occurred_on"] for e in fil} == {"2026-09-29"} and {e["published_on"] for e in fil} == {"2026-10-02"}
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 3, 12, tzinfo=timezone.utc),
                       collecteurs=lecteur)
    assert rapport["cftc_cot"]["nouveaux"] == 0


def test_rapport_trop_vieux_met_la_source_en_panne(tmp_path):
    internet = FauxInternet(rangees())
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 11, 20, 22, tzinfo=timezone.utc),
                       collecteurs={"cftc_cot": cftc.collecter})
    assert rapport["cftc_cot"]["ok"] is False and "trop vieux" in rapport["cftc_cot"]["erreur"]
