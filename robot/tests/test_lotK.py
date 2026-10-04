"""Lot K : santé financière (9 critères de Piotroski, 2000), sur de VRAIES données officielles lues le 4 octobre 2026
(tests/fixtures/lotK) : les 44 fichiers « frames » de l'API XBRL de la SEC, réduits à 8 compagnies. Les critères
attendus viennent de la recherche du labo (labo/reconnaissance26.py, son propre code) : le robot doit les retrouver."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from radar.collecteurs import COLLECTEURS
from radar.collecteurs import sante as sa
from radar.http import ErreurSource
from radar.models import empreinte
from radar.registry import SOURCES
from radar.run import Contexte

F = Path(__file__).parent / "fixtures" / "lotK"
EXTRAITS = json.loads((F / "frames_extraits.json").read_text(encoding="utf-8"))
ATTENDUS = json.loads((F / "attendus.json").read_text(encoding="utf-8"))
MAINTENANT = datetime(2026, 10, 5, 11, 7, tzinfo=timezone.utc)
CIKS = {"GME": 1326380, "FUL": 39368, "GPUS": 896493, "LESL": 1821806, "XENE": 1582313, "PRHI": 1502292,
        "AAPL": 320193, "AMD": 2488}


class FauxInternet:
    """Sert les vrais extraits ; une étiquette que la SEC n'a pas (pas dans les extraits) répond 404, comme la SEC."""

    def __init__(self, remplace=None):
        self.appels = []
        self.remplace = remplace or {}

    def get(self, url, entetes=None):
        self.appels.append(url)
        tag, _, periode = url.removeprefix("https://data.sec.gov/api/xbrl/frames/us-gaap/").removesuffix(".json").split("/")
        cle = f"{tag}|{periode}"
        if cle in self.remplace:
            c = json.dumps(self.remplace[cle]).encode()
        elif cle in EXTRAITS:
            c = json.dumps(EXTRAITS[cle]).encode()
        else:
            raise ErreurSource(f"{url} : HTTP 404")
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def contexte(tmp_path, internet=None):
    (tmp_path / "sec").mkdir(exist_ok=True)
    (tmp_path / "sec" / "emetteurs.json").write_text(json.dumps(
        {s: {"cik": c, "type": "compagnie"} for s, c in CIKS.items()}), encoding="utf-8")
    return Contexte(client=internet or FauxInternet(), maintenant=MAINTENANT, donnees=tmp_path)


def test_source_branchee_le_matin_sans_aucune_info_ni_point(tmp_path):
    assert COLLECTEURS["sec_sante"] is sa.collecter and SOURCES["sec_sante"].passages == ("matin",)
    internet = FauxInternet()
    assert sa.collecter(contexte(tmp_path, internet)) == []  # aucune info : rien n'entre dans la note
    # 13 étiquettes de durée × 2 exercices + 6 étiquettes de bilan × 3 fins d'exercice = 44 fichiers, chacun lu une fois
    assert len(internet.appels) == 44 == len(set(internet.appels))
    assert sa.FRAMES.format(tag="Assets", periode="CY2023Q4I") in internet.appels


@pytest.mark.parametrize("symbole", sorted(CIKS))
def test_les_9_criteres_comme_la_recherche_du_labo(tmp_path, symbole):
    sa.collecter(contexte(tmp_path))
    x = json.loads(sa.chemin(tmp_path).read_text(encoding="utf-8"))
    assert x["cadre"] == "CY2025" and x["version"] == "sante-1"
    r = sa.criteres(x["par_cik"][str(CIKS[symbole])])
    attendu = ATTENDUS[symbole]
    if attendu["f_score"] is None:  # XENE (biotech : pas de marge brute), PRHI : pas de score plutôt qu'un faux
        assert r is None
    else:
        assert r["criteres"] == attendu["signaux"] and sum(r["criteres"].values()) == attendu["f_score"]


def test_gme_les_chiffres_derriere_ses_7_sur_9(tmp_path):
    sa.collecter(contexte(tmp_path))
    v = json.loads(sa.chemin(tmp_path).read_text(encoding="utf-8"))["par_cik"]["1326380"]
    assert v["accn"] and v["debut"] < v["fin"]  # le rapport annuel de l'exercice étudié (dates de la SEC)
    r = sa.criteres(v)
    c = r["chiffres"]
    assert c["roa"] > 0 and c["cfo"] > c["roa"] and c["roa"] > c["roa_avant"]  # ROA, ACCRUAL, ΔROA : 1
    assert c["levier"] >= c["levier_avant"]  # ΔLEVER : 0 (la dette n'a pas baissé)
    assert c["rotation"] <= c["rotation_avant"]  # ΔTURN : 0
    assert c["emission"] <= 0 and c["liquidite"] > c["liquidite_avant"] and c["marge"] > c["marge_avant"]


def test_fichier_pas_reecrit_s_il_ne_change_pas(tmp_path):
    sa.collecter(contexte(tmp_path))
    sa.chemin(tmp_path).write_text(sa.chemin(tmp_path).read_text() + " ")  # marque
    sa.collecter(contexte(tmp_path))
    assert sa.chemin(tmp_path).read_text().endswith("\n ")  # même contenu : fichier pas réécrit


def test_format_inattendu_met_la_source_en_panne(tmp_path):
    autre = dict(EXTRAITS["Assets|CY2025Q4I"], uom="EUR")
    with pytest.raises(RuntimeError, match="réponse inattendue"):
        sa.collecter(contexte(tmp_path, FauxInternet({"Assets|CY2025Q4I": autre})))


def test_une_autre_erreur_que_404_met_la_source_en_panne(tmp_path):
    class Refus(FauxInternet):
        def get(self, url, entetes=None):
            raise ErreurSource(f"{url} : HTTP 403")
    with pytest.raises(ErreurSource, match="HTTP 403"):
        sa.collecter(contexte(tmp_path, Refus()))


def test_rien_plutot_que_faux_et_regle_de_la_dette_et_des_emissions():
    complet = {"t": {"actif": 1000, "benefice": 90, "flux": 120, "ventes": 2000, "marge_brute": 800, "actif_court": 400,
                     "passif_court": 200, "dette_lt": 100},
               "t1": {"actif": 900, "benefice": 60, "ventes": 1700, "marge_brute": 650, "actif_court": 350,
                      "passif_court": 200, "dette_lt": 150},
               "t2": {"actif": 800}}
    r = sa.criteres(complet)
    assert r["criteres"] == {k: 1 for k in sa.CRITERES}  # calculé à la main : les 9 bons signes
    sans_marge = json.loads(json.dumps(complet))
    del sans_marge["t"]["marge_brute"]
    assert sa.criteres(sans_marge) is None  # pas de marge brute ni de coût des ventes : pas de score
    avec_cout = json.loads(json.dumps(sans_marge))
    avec_cout["t"]["cout_ventes"] = 1200  # marge brute = ventes − coût des ventes = 800
    assert sa.criteres(avec_cout)["criteres"]["ΔMARGIN"] == 1
    sans_dette = json.loads(json.dumps(complet))
    del sans_dette["t"]["dette_lt"], sans_dette["t1"]["dette_lt"]
    assert sa.criteres(sans_dette)["criteres"]["ΔLEVER"] == 0  # 0 et 0 : la dette n'a pas baissé
    emise = json.loads(json.dumps(complet))
    emise["t"]["emission"] = 5_000_000
    assert sa.criteres(emise)["criteres"]["EQ_OFFER"] == 0  # actions émises : mauvais signe


def test_pour_l_app_seulement_les_scores_complets_des_listes(tmp_path):
    sa.collecter(contexte(tmp_path))
    app = sa.pour_app(tmp_path, ["GME", "FUL", "GPUS", "LESL", "XENE", "PRHI", "AAPL", "NOPE"])
    assert app["cadre"] == "CY2025" and app["etude"] == sa.ETUDE and app["version"] == "sante-1"
    assert set(app["par_symbole"]) == {"GME", "FUL", "GPUS", "LESL", "AAPL"}  # XENE, PRHI, NOPE : rien plutôt que faux
    g = app["par_symbole"]["GME"]
    assert g["f_score"] == 7 and g["cik"] == 1326380 and list(g["criteres"]) == sa.CRITERES
    assert g["lien"] == (f"https://www.sec.gov/Archives/edgar/data/1326380/{g['accn'].replace('-', '')}/"
                         f"{g['accn']}-index.htm")
    assert {s: x["f_score"] for s, x in app["par_symbole"].items()} == {
        "GME": 7, "FUL": 7, "GPUS": 5, "LESL": 3, "AAPL": 8}
    assert sa.pour_app(tmp_path / "vide", ["GME"]) == {}  # pas encore lu : pas de fichier pour l'app
