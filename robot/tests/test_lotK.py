"""Lot K : santé financière (9 critères de Piotroski, 2000), tirée du DERNIER RAPPORT ANNUEL de chaque compagnie, aux
dates de son exercice, sur de VRAIES données officielles lues le 4 octobre 2026 (tests/fixtures/lotK) : les dossiers
« companyfacts » de la SEC de 9 compagnies (chiffres depuis 2021, étiquettes utiles). Les attendus viennent du labo
(labo/fixtures_lotK2.py), qui a refait le calcul SANS companyfacts : en lisant le fichier XBRL (instance) des rapports
annuels eux-mêmes, avec son propre code. Les pièges sont réels : la circulaire de GME (DEF 14A) répète son bénéfice,
arrondi, après le 10-K ; les rapports trimestriels de LESL donnent des bilans plus proches de la fin de l'année civile."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from radar.collecteurs import COLLECTEURS
from radar.collecteurs import sante as sa
from radar.http import ErreurSource
from radar.models import empreinte
from radar.registry import PASSAGES, SOURCES
from radar.run import Contexte

F = Path(__file__).parent / "fixtures" / "lotK"
ATTENDUS = json.loads((F / "attendus.json").read_text(encoding="utf-8"))
CIKS = {s: a["cik"] for s, a in ATTENDUS.items()}
MAINTENANT = datetime(2026, 10, 5, 11, 7, tzinfo=timezone.utc)
# Noms du labo → noms du robot
NOMS = {"brute": "marge_brute", "cout": "cout_ventes", "ac": "actif_court", "pc": "passif_court", "dette": "dette_lt"}


def dossier(cik):
    return json.loads((F / "companyfacts" / f"{cik}.json").read_text(encoding="utf-8"))


class FauxInternet:
    """Sert les vrais dossiers ; une compagnie sans dossier répond 404, comme la SEC."""

    def __init__(self, remplace=None):
        self.appels = []
        self.remplace = remplace or {}

    def get(self, url, entetes=None):
        self.appels.append(url)
        cik = int(url.removeprefix("https://data.sec.gov/api/xbrl/companyfacts/CIK").removesuffix(".json"))
        if cik in self.remplace:
            c = json.dumps(self.remplace[cik]).encode()
        elif (F / "companyfacts" / f"{cik}.json").exists():
            c = (F / "companyfacts" / f"{cik}.json").read_bytes()
        else:
            raise ErreurSource(f"{url} : HTTP 404")
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def contexte(tmp_path, listes=("GME", "LESL", "XENE"), internet=None, maintenant=MAINTENANT):
    """Les listes du passage précédent : toutes à la hausse, sauf la dernière compagnie (à la baisse)."""
    (tmp_path / "sec").mkdir(exist_ok=True)
    (tmp_path / "app").mkdir(exist_ok=True)
    emet = {s: {"cik": c, "type": "compagnie"} for s, c in CIKS.items()}
    emet["NOPE"] = {"cik": 999999, "type": "compagnie"}
    (tmp_path / "sec" / "emetteurs.json").write_text(json.dumps(emet), encoding="utf-8")
    (tmp_path / "app" / "aujourdhui.json").write_text(json.dumps(
        {"hausse": [{"symbole": s} for s in listes[:-1]], "baisse": [{"symbole": listes[-1]}]}), encoding="utf-8")
    return Contexte(client=internet or FauxInternet(), maintenant=maintenant, donnees=tmp_path)


def test_source_branchee_a_chaque_passage_pour_les_compagnies_des_listes(tmp_path):
    assert COLLECTEURS["sec_sante"] is sa.collecter and SOURCES["sec_sante"].passages == PASSAGES
    internet = FauxInternet()
    assert sa.collecter(contexte(tmp_path, internet=internet)) == []  # aucune info : rien n'entre dans la note
    assert internet.appels == [sa.DOSSIER.format(cik=CIKS[s]) for s in ("GME", "LESL", "XENE")]  # un dossier chacune


@pytest.mark.parametrize("symbole", sorted(ATTENDUS))
def test_chaque_compagnie_comme_le_labo_qui_a_lu_les_rapports_annuels(symbole):
    a = ATTENDUS[symbole]
    v = sa.extraire(dossier(a["cik"]))
    assert (v["rapport"]["accn"], v["rapport"]["forme"], v["rapport"]["depose"]) == (a["accn"], a["forme"], a["depose"])
    assert (v["debut"], v["fin"], v["debut1"], v["fin1"], v["fin2"], v["source_t2"]) == (
        a["debut"], a["fin"], a["debut1"], a["fin1"], a["fin2"], a["source_t2"])
    assert v["etiquettes"] == {NOMS.get(k, k): x for k, x in a["etiquettes"].items()}
    for periode in ("t", "t1", "t2"):  # chaque chiffre, pas seulement les critères
        assert v[periode] == {NOMS.get(k, k): x for k, x in a["valeurs"][periode].items()}
    r = sa.criteres(v)
    if a["f_score"] is None:  # XENE (pas de coût des ventes), PRHI (pas d'actif à court terme) : rien plutôt que faux
        assert r is None
    else:
        assert r["criteres"] == a["criteres"] and sum(r["criteres"].values()) == a["f_score"]


def test_gme_le_rapport_annuel_pas_la_circulaire_qui_repete_le_benefice_arrondi():
    d = dossier(CIKS["GME"])
    exercice = [f for f in d["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"]
                if (f.get("start"), f["end"]) == ("2025-02-02", "2026-01-31")]
    circulaire = [f for f in exercice if f["form"] == "DEF 14A"]
    rapport = [f for f in exercice if f["form"] == "10-K"]
    assert circulaire[0]["filed"] > rapport[0]["filed"] and circulaire[0]["val"] != rapport[0]["val"]  # 418,0 M$ ≠ 418,4 M$
    v = sa.extraire(d)
    assert v["rapport"] == {"accn": rapport[0]["accn"], "forme": "10-K", "depose": rapport[0]["filed"]}
    assert v["t"]["benefice"] == rapport[0]["val"] == 418_400_000


def test_lesl_bilans_de_fin_d_exercice_jamais_ceux_d_un_rapport_trimestriel():
    d = dossier(CIKS["LESL"])
    actifs = d["facts"]["us-gaap"]["Assets"]["units"]["USD"]
    assert any(f["form"] == "10-Q" and f["end"] == "2026-01-03" for f in actifs)  # le piège : plus près du 31 décembre
    v = sa.extraire(d)
    assert (v["fin"], v["fin1"], v["fin2"]) == ("2025-10-04", "2024-09-28", "2023-09-30")
    du_10k = {f["end"]: f["val"] for f in actifs if f["accn"] == v["rapport"]["accn"]}
    assert (v["t"]["actif"], v["t1"]["actif"]) == (du_10k["2025-10-04"], du_10k["2024-09-28"])
    assert v["source_t2"] != v["rapport"]["accn"]  # le bilan de fin t-2 vient du rapport annuel précédent


def test_msft_exercice_qui_finit_en_juin():
    v = sa.extraire(dossier(CIKS["MSFT"]))
    assert (v["debut"], v["fin"], v["fin2"]) == ("2025-07-01", "2026-06-30", "2024-06-30")
    assert sum(sa.criteres(v)["criteres"].values()) == 5


def test_un_rapport_annuel_modifie_remplace_l_original():
    d = dossier(CIKS["GME"])
    original = "0001326380-26-000013"
    for x in d["facts"]["us-gaap"].values():
        copies = [dict(f, accn="0001326380-26-099999", form="10-K/A", filed="2026-09-01")
                  for f in x["units"]["USD"] if f["accn"] == original]
        x["units"]["USD"] += copies
    for f in d["facts"]["us-gaap"]["NetIncomeLoss"]["units"]["USD"]:
        if f["accn"] == "0001326380-26-099999" and f["end"] == "2026-01-31":
            f["val"] = 400_000_000  # bénéfice corrigé
    v = sa.extraire(d)
    assert v["rapport"] == {"accn": "0001326380-26-099999", "forme": "10-K/A", "depose": "2026-09-01"}
    assert v["t"]["benefice"] == 400_000_000 and v["fin"] == "2026-01-31"


def test_une_fois_par_jour_et_une_nouvelle_compagnie_au_passage_suivant(tmp_path):
    internet = FauxInternet()
    sa.collecter(contexte(tmp_path, ("GME", "LESL"), internet))
    sa.collecter(contexte(tmp_path, ("GME", "LESL", "FUL"), internet, MAINTENANT.replace(hour=16)))
    assert internet.appels[2:] == [sa.DOSSIER.format(cik=CIKS["FUL"])]  # même jour : seule FUL (nouvelle) est lue
    sa.collecter(contexte(tmp_path, ("GME", "FUL"), internet, MAINTENANT + timedelta(days=1)))
    assert len(internet.appels) == 5  # le lendemain : relues
    x = json.loads(sa.chemin(tmp_path).read_text(encoding="utf-8"))
    assert set(x["par_cik"]) == {str(CIKS["GME"]), str(CIKS["FUL"])}  # LESL a quitté les listes : retirée du fichier
    assert x["version"] == sa.VERSION and x["par_cik"][str(CIKS["GME"])]["lu"] == "2026-10-06"


def test_fichier_pas_reecrit_s_il_ne_change_pas(tmp_path):
    sa.collecter(contexte(tmp_path))
    sa.chemin(tmp_path).write_text(sa.chemin(tmp_path).read_text() + " ")  # marque
    sa.collecter(contexte(tmp_path, maintenant=MAINTENANT.replace(hour=20)))
    assert sa.chemin(tmp_path).read_text().endswith("\n ")  # même contenu : fichier pas réécrit


def test_compagnie_sans_dossier_xbrl_et_sans_listes(tmp_path):
    sa.collecter(contexte(tmp_path, ("NOPE", "GME")))  # la SEC répond 404 pour NOPE
    x = json.loads(sa.chemin(tmp_path).read_text(encoding="utf-8"))
    assert x["par_cik"]["999999"] == {"lu": "2026-10-05", "rien": "aucune donnée XBRL à la SEC"}
    vide = tmp_path / "vide"
    (vide / "sec").mkdir(parents=True)
    internet = FauxInternet()
    sa.collecter(Contexte(client=internet, maintenant=MAINTENANT, donnees=vide))  # pas encore de listes : rien à lire
    assert internet.appels == [] and json.loads(sa.chemin(vide).read_text()) == {"version": sa.VERSION, "par_cik": {}}


def test_une_autre_erreur_que_404_met_la_source_en_panne(tmp_path):
    class Refus(FauxInternet):
        def get(self, url, entetes=None):
            raise ErreurSource(f"{url} : HTTP 403")
    with pytest.raises(ErreurSource, match="HTTP 403"):
        sa.collecter(contexte(tmp_path, internet=Refus()))


def test_format_inattendu_met_la_source_en_panne(tmp_path):
    with pytest.raises(RuntimeError, match="réponse inattendue"):
        sa.collecter(contexte(tmp_path, internet=FauxInternet({CIKS["GME"]: {"cik": 1, "facts": {}}})))


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
    listes = ("GME", "FUL", "GPUS", "XENE", "PRHI", "NOPE", "LESL")
    sa.collecter(contexte(tmp_path, listes))
    app = sa.pour_app(tmp_path, list(listes) + ["AAPL"])  # AAPL : pas dans les listes lues, donc pas encore lue
    assert app["etude"] == sa.ETUDE and app["version"] == sa.VERSION
    assert {s: x["f_score"] for s, x in app["par_symbole"].items()} == {"GME": 7, "FUL": 7, "GPUS": 4, "LESL": 3}
    g = app["par_symbole"]["GME"]
    assert (g["cik"], g["forme"], g["fin"], list(g["criteres"])) == (1326380, "10-K", "2026-01-31", sa.CRITERES)
    assert g["lien"] == "https://www.sec.gov/Archives/edgar/data/1326380/000132638026000013/0001326380-26-000013-index.htm"
    sa.chemin(tmp_path).write_text(json.dumps({"version": "sante-1", "cadre": "CY2025", "par_cik": {}}))
    assert sa.pour_app(tmp_path, ["GME"]) == {}  # ancien calcul (fichiers « frames ») : rien
    assert sa.pour_app(tmp_path / "vide", ["GME"]) == {}  # pas encore lu : pas de fichier pour l'app
