"""Étape 2 : le prix du formulaire 4 quand la SEC n'a pas de prix depuis 60 jours.

Un titre a un prix de la SEC seulement les jours où il a des échecs de livraison : mesuré au labo le 9 octobre 2026,
3 068 achats de dirigeants sur 26 651 (11,5 %, 2023-2026) n'avaient aucun prix de la SEC de 60 jours ou moins (taille
inconnue). Le prix que les dirigeants ont payé ou reçu en bourse (formulaire 4, actions ordinaires seulement) donne la
même taille que la clôture de la SEC d'après dans 99,6 % des cas comparés.

Vrais documents : formulaires 4 du 1er octobre 2026 (tests/fixtures/sec) : GameStop (achat, « Class A Common Stock »),
Samsara (12 ventes, « Class A Common Stock »), Simon Property (« Common Stock »), BBASX (« Class S units », un fonds).
Vraies lignes : MSTU dans les extraits du lot G (regroupement 1 pour 10, nouveau CUSIP dès le 25 août 2026).
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

from radar.collecteurs import sec
from radar.collecteurs import taille as ta
from radar.collecteurs.sec import Symboles, evenements_form4, lire_form4, lire_index
from radar.models import empreinte
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "sec"
G = Path(__file__).parent / "fixtures" / "lotG"
SEUILS = {"mois": "202608", "p30": 2236.27, "p70": 13366.01}
FICHE = {"cik": 1, "rapports": ["10-K", "10-Q"]}
GME, IOT, SPG, BBASX = ("0001822293-26-000002", "0001895111-26-000019", "0002109729-26-000010",
                        "0001193125-26-410415")


def lire(nom: str) -> str:
    return (F / nom).read_text(encoding="utf-8", errors="replace")


@pytest.fixture(scope="module")
def syms():
    return Symboles(json.loads(lire("company_tickers_exchange.json")))


@pytest.fixture(scope="module")
def index():
    return lire_index((F / "master.20261001.idx").read_text(encoding="latin-1"))


def form4(acc, index, syms):
    """Les infos du robot (comme dans le dépôt : des dictionnaires), validées le 2 octobre 2026."""
    t = lire(f"{acc}.txt")
    return [json.loads(json.dumps(valider(e, date(2026, 10, 2)).to_dict()))
            for e in evenements_form4(t, empreinte(t.encode()), index[acc], syms)]


@pytest.fixture(scope="module")
def mstu():
    symboles = {}
    for cle in ("202604a", "202607b", "202608a", "202608b", "202609a"):
        tampon = io.BytesIO()
        with zipfile.ZipFile(tampon, "w") as z:
            z.writestr(f"cnsfails{cle}.txt", (G / f"cnsfails{cle}.txt").read_bytes())
        ta.ajouter_lignes(symboles, ta.lire_lignes(tampon.getvalue()))
    return symboles["MSTU"]


# ---------- Le lecteur garde le nom du titre de chaque transaction ----------


def test_le_lecteur_garde_le_nom_du_titre():
    assert sec.VERSION == "sec-8"  # lecteur changé : les formulaires lus avant n'ont pas le nom du titre
    titres = {acc: [t["titre_valeur"] for t in lire_form4(lire(f"{acc}.txt"))["transactions"]]
              for acc in (GME, IOT, SPG, BBASX)}
    assert titres == {GME: ["Class A Common Stock"], IOT: ["Class A Common Stock"] * 12, SPG: ["Common Stock"],
                      BBASX: ["Class S units of beneficial interest"]}


@pytest.mark.parametrize("titre,oui", [
    ("Common Stock", True), ("Class A Common Stock", True), ("Ordinary Shares", True),
    ("Common Stock, par value $0.001", True), ("COMMON SHARES", True),
    ("Series B Preferred Stock", False),  # ADTX au labo : 20 000 $ quand l'ordinaire valait 0,18 $
    ("Class S units of beneficial interest", False), ("Common Units", False), ("American Depositary Shares", False),
    ("Warrants to purchase Common Stock", False), ("Convertible Notes", False), ("Rights", False),
    ("Stock Option (right to buy)", False), ("", False), (None, False),
])
def test_actions_ordinaires_seulement(titre, oui):
    assert ta.commune(titre) is oui


# ---------- Le prix des formulaires 4 ----------


def test_prix_de_l_achat_de_gamestop(index, syms):
    [ev] = form4(GME, index, syms)
    assert ev["badge"] == "officiel"
    assert ta.prix_formulaires_4([ev], date(2026, 10, 2)) == {"GME": ["20261001", 24.33]}


def test_ventes_de_samsara_prix_moyen_pondere(index, syms):
    [ev] = form4(IOT, index, syms)
    # 12 ventes sur 3 jours (29 septembre : 6, 30 septembre : 4, 1er octobre : 2) : le prix est celui du jour le plus
    # récent seulement (21 129 actions pour 820 041,42 $), pas la moyenne des 3 jours (38,03 $) datée du 1er octobre
    assert ta.prix_formulaires_4([ev], date(2026, 10, 2)) == {"IOT": ["20261001", 38.8112]}
    assert round(820041.42 / 21129, 4) == 38.8112
    assert ta.prix_formulaires_4([ev], date(2026, 9, 30)) == {}  # déposé le 1er octobre : pas encore connu le 30


def test_ce_qui_ne_donne_pas_de_prix(index, syms):
    [ev] = form4(GME, index, syms)
    jour = date(2026, 10, 2)

    def sans(modif):
        e = json.loads(json.dumps(ev))
        modif(e)
        return ta.prix_formulaires_4([e], jour)

    def ligne(**champs):
        return lambda e: e["data"]["transactions"][0].update(champs)

    assert sans(ligne(titre_valeur="Series A Preferred Stock")) == {}
    assert sans(lambda e: e["data"]["transactions"][0].pop("titre_valeur")) == {}  # lu avant sec-8
    assert sans(lambda e: e.update(badge="a_verifier")) == {}  # ex. prix de plus de 2 000 $
    assert sans(lambda e: e["data"].update(hors_bourse="initial public offering")) == {}
    assert sans(lambda e: e["data"].update(automatique="dividend reinvestment")) == {}
    assert sans(lambda e: e.update(published_on="2026-10-03")) == {}  # déposé après le jour du calcul
    assert sans(ligne(date="2026-08-02")) == {}  # 61 jours avant
    assert sans(ligne(date="2026-08-03")) == {"GME": ["20260803", 24.33]}  # 60 jours : encore bon
    assert sans(ligne(prix=0.0)) == {}
    # un autre initié a acheté la même action le même jour au même prix lors d'une émission
    assert ta.prix_formulaires_4([ev], jour, frozenset({("GME", "2026-10-01", 24.33)})) == {}
    assert ta.prix_formulaires_4([ev], jour, frozenset({("GME", "2026-10-01", 24.0)})) == {"GME": ["20261001", 24.33]}
    autre = json.loads(json.dumps(ev))
    autre.update(source="sec_form144")
    assert ta.prix_formulaires_4([autre], jour) == {}


def test_le_jour_le_plus_recent_gagne_et_le_meme_jour_fait_la_moyenne(index, syms):
    [ev] = form4(GME, index, syms)
    jour = date(2026, 10, 2)

    def copie(date_, prix, actions):
        e = json.loads(json.dumps(ev))
        e["data"]["transactions"][0].update(date=date_, prix=prix, actions=actions)
        return e

    vieux, recent = copie("2026-09-20", 30.0, 1000), copie("2026-09-25", 20.0, 1000)
    assert ta.prix_formulaires_4([recent, vieux], jour) == {"GME": ["20260925", 20.0]}
    meme_jour = copie("2026-09-25", 26.0, 3000)  # (1 000 × 20 + 3 000 × 26) ÷ 4 000 = 24,50
    assert ta.prix_formulaires_4([vieux, recent, meme_jour], jour) == {"GME": ["20260925", 24.5]}


# ---------- La taille avec le prix du formulaire 4 ----------


def classer(actions, prix_sec, prix_f4, h=None, debut="20250901", jour=date(2026, 11, 20)):
    t = {"seuils": SEUILS, "actions": {"1": actions}, "prix": {"XYZ": prix_sec} if prix_sec else {}}
    cusips = {"debut": debut, "symboles": {"XYZ": h}} if h is not None else {"debut": debut, "symboles": {}}
    return ta.classer(FICHE, t, "XYZ", jour, cusips, prix_f4)


def test_prix_de_la_sec_trop_vieux_le_formulaire_4_donne_la_taille(mstu):
    # actions déclarées après le regroupement (1er septembre) ; dernier prix de la SEC : 14 septembre (67 jours)
    r = classer([20_000_000, "2026-09-01"], ["20260914", 30.41, "26923Y708"], {"XYZ": ["20261110", 25.0]}, mstu)
    assert r == {"taille": "petite", "seuils": SEUILS, "source_actions": "frames", "valeur_m": 500.0,
                 "actions": [20_000_000, "2026-09-01"], "prix": ["20261110", 25.0], "source_prix": "formulaire 4"}


def test_prix_de_la_sec_recent_le_formulaire_4_ne_sert_pas(mstu):
    r = classer([20_000_000, "2026-09-01"], ["20260914", 30.41, "26923Y708"], {"XYZ": ["20261001", 25.0]}, mstu,
                jour=date(2026, 10, 2))
    assert r["prix"] == ["20260914", 30.41] and "source_prix" not in r


def test_regroupement_entre_les_actions_et_le_formulaire_4_taille_inconnue(mstu):
    # actions déclarées le 15 août, AVANT le nouveau CUSIP (25 août) : le prix du formulaire 4 de novembre est d'après
    # le regroupement 1 pour 10, le nombre d'actions d'avant : valeur 10 fois trop haute
    r = classer([20_000_000, "2026-08-15"], ["20260914", 30.41, "26923Y708"], {"XYZ": ["20261110", 25.0]}, mstu)
    assert r["taille"] is None and "valeur_m" not in r
    assert r["raison"] == ("pas de prix de la SEC depuis 60 jours, et le prix du formulaire 4 du 10 novembre 2026 est "
                           "peut-être d'une autre époque que les actions déclarées au 15 août 2026 : nouveau code du "
                           "titre (CUSIP) vu dès le 25 août 2026 (regroupement ou fractionnement d'actions possible)")


def test_formulaire_4_avant_le_regroupement_et_actions_apres_taille_inconnue(mstu):
    # l'inverse : prix d'avant le regroupement (20 août), actions d'après (1er septembre) : valeur 10 fois trop basse
    r = classer([20_000_000, "2026-09-01"], None, {"XYZ": ["20260820", 2.6]}, mstu, jour=date(2026, 10, 16))
    assert r["taille"] is None and "valeur_m" not in r
    assert r["raison"].startswith("pas de prix de la SEC depuis 60 jours, et le prix du formulaire 4 du 20 août 2026 ")
    assert r["raison"].endswith("nouveau code du titre (CUSIP) vu dès le 25 août 2026 (regroupement ou fractionnement "
                                "d'actions possible)")


def test_historique_pas_lu_le_calcul_avec_une_note():
    r = classer([20_000_000, "2026-09-01"], None, {"XYZ": ["20261110", 25.0]}, debut=None)
    assert r["taille"] == "petite" and r["source_prix"] == "formulaire 4" and r["note"] == ta.NON_VERIFIE


def test_aucun_prix_la_raison_le_dit():
    assert classer([20_000_000, "2026-09-01"], None, {})["raison"] == (
        "pas de prix de la SEC ni de formulaire 4 depuis 60 jours")
    t = {"seuils": SEUILS, "actions": {"1": [20_000_000, "2026-09-01"]}, "prix": {}}
    assert ta.classer(FICHE, t, "XYZ", date(2026, 11, 20), {"debut": "20250901", "symboles": {}})["raison"] == (
        "pas de prix de la SEC depuis 60 jours")  # sans prix de secours (anciens rejeux du labo) : comme avant
