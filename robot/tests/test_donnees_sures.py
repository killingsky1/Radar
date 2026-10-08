"""Étape 1, données sûres (0.27.1) : fichiers « _0 » de la SEC et taille en bourse de la même époque que les actions.

Un regroupement d'actions (ex. 1 pour 10) donne un nouveau CUSIP et divise le nombre d'actions, mais le nombre déclaré à
la SEC reste l'ancien jusqu'au rapport suivant : ancien nombre × nouveau prix = valeur 10 fois trop haute. Mesuré au labo
le 8 octobre 2026 : 294 achats de dirigeants sur 25 173 (1,17 %) avec un CUSIP vu pour la 1re fois après la date des
actions, dont 107 qui passaient à tort la règle des 100 M$ (ex. EVLO : 395 M$ calculés au lieu d'environ 31 M$).

Vraies lignes : MSTU dans les extraits du lot G (CUSIP 26923N173 jusqu'au 24 août 2026 à 2,73 $, puis 26923Y708 dès le
25 août à 28,86 $ : regroupement 1 pour 10).
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import date
from pathlib import Path

import pytest

from radar import score as sc
from radar.collecteurs import prix_sec
from radar.collecteurs import taille as ta

G = Path(__file__).parent / "fixtures" / "lotG"
SEUILS = {"mois": "202608", "p30": 2236.27, "p70": 13366.01}
FICHE = {"cik": 1, "rapports": ["10-K", "10-Q"]}
JOUR = date(2026, 9, 20)


def zip_de(cle: str) -> bytes:
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr(f"cnsfails{cle}.txt", (G / f"cnsfails{cle}.txt").read_bytes())
    return tampon.getvalue()


@pytest.fixture(scope="module")
def mstu():
    """L'historique de MSTU construit par le robot avec les vrais extraits du lot G (avril à septembre 2026)."""
    symboles = {}
    for cle in ("202604a", "202607b", "202608a", "202608b", "202609a"):
        ta.ajouter_lignes(symboles, ta.lire_lignes(zip_de(cle)))
    return symboles["MSTU"]


def taille(actions, prix, h, debut="20250901"):
    t = {"seuils": SEUILS, "actions": {"1": actions}, "prix": {"XYZ": prix}}
    return ta.classer(FICHE, t, "XYZ", JOUR, {"debut": debut, "symboles": {"XYZ": h}})


def test_historique_des_vrais_fichiers(mstu):
    # [1er jour vu, dernier jour vu, jour du dernier prix, dernier prix, jour du 1er prix, 1er prix]
    assert mstu == {"26923N173": ["20260402", "20260824", "20260824", 2.73, "20260402", 4.1],
                    "26923Y708": ["20260825", "20260914", "20260914", 30.41, "20260825", 28.86]}
    assert ta.lire_prix(zip_de("202608b"))["MSTU"] == ["20260831", 30.05, "26923Y708"]  # le plus récent du fichier


def test_lignes_sans_prix_comptent_comme_vues():
    contenu = io.BytesIO()
    with zipfile.ZipFile(contenu, "w") as z:
        z.writestr("x.txt", "\n".join([prix_sec.ENTETE, "20260901|A1|XYZ|10|X|1.50", "20260903|A1|XYZ|10|X|.",
                                       "20260902|B2|XYZ|10|X|.", "20260902|A1|XYZ|10|X|1.70", "20260902|A1|XYZ|10|X|9.99",
                                       "Trailer total quantity of shares 40"]) + "\n")
    lignes = ta.lire_lignes(contenu.getvalue())
    assert len(lignes) == 5 and lignes[1] == ("20260903", "A1", "XYZ", None)
    h = {}
    ta.ajouter_lignes(h, lignes)
    # A1 : vu du 1er au 3 ; dernier prix le 2 (la 1re ligne du jour gagne, comme lire_prix) ; B2 : vu, jamais de prix
    assert h == {"XYZ": {"A1": ["20260901", "20260903", "20260902", 1.7, "20260901", 1.5],
                         "B2": ["20260902", "20260902", None, None, None, None]}}
    assert ta.lire_prix(contenu.getvalue()) == {"XYZ": ["20260902", 1.7, "A1"]}


def test_epoque_avec_le_vrai_regroupement_de_mstu(mstu):
    assert ta.epoque(mstu, "26923Y708", "20260825") == {"cas": "meme"}  # actions déclarées après le changement
    assert ta.epoque(mstu, "26923Y708", "20260901") == {"cas": "meme"}
    # actions déclarées le 15 août : l'ancien CUSIP est encore vu le 24 → le changement est venu après les actions
    assert ta.epoque(mstu, "26923Y708", "20260815") == {"cas": "ancien", "ancien": "26923N173",
                                                        "dernier_ancien": "20260824", "premier": "20260825"}
    assert ta.epoque(mstu, "26923N173", "20260815") == {"cas": "meme"}  # le prix de l'ancien CUSIP : même époque


def test_taille_avec_le_prix_de_l_ancien_cusip(mstu):
    # 10 millions d'actions déclarées le 15 août, prix le plus récent 28,86 $ (nouveau CUSIP, 25 août)
    sans = ta.classer(FICHE, {"seuils": SEUILS, "actions": {"1": [10_000_000, "2026-08-15"]},
                              "prix": {"XYZ": ["20260825", 28.86, "26923Y708"]}}, "XYZ", JOUR)
    assert sans["valeur_m"] == 288.6  # 0.27.0 : ancien nombre × nouveau prix, 10 fois trop
    t = taille([10_000_000, "2026-08-15"], ["20260825", 28.86, "26923Y708"], mstu)
    assert (t["taille"], t["valeur_m"], t["prix"]) == ("petite", 27.3, ["20260824", 2.73])
    assert t["note"].startswith("Prix de l'ancien code du titre (CUSIP 26923N173), vu jusqu'au 24 août 2026 : le "
                                "nouveau code, vu dès le 25 août 2026, est arrivé après les actions déclarées au 15 "
                                "août 2026")
    assert sc.trop_petite({"taille": t})  # 27,3 M$ : hors de la liste « hausse » (0.27.0 la gardait à 288,6 M$)
    # actions déclarées après le changement : le nouveau prix, comme avant
    apres = taille([1_000_000, "2026-08-28"], ["20260825", 28.86, "26923Y708"], mstu)
    assert (apres["valeur_m"], apres["prix"]) == (28.9, ["20260825", 28.86]) and "note" not in apres


def test_ancien_prix_trop_vieux_regroupement_un_maximum_sur(mstu):
    """Le 24 octobre, le nouveau prix (14 septembre) a 40 jours, l'ancien (24 août) en a 61 : pas de valeur exacte. Mais
    le prix a été multiplié par 10,6 au changement (2,73 $ → 28,86 $) : regroupement d'actions probable, donc ancien nombre
    d'actions × nouveau prix est un MAXIMUM. Mesuré au labo (8 octobre 2026) : sans ce maximum, une taille inconnue
    n'est jamais écartée et des compagnies de quelques M$ restaient dans la liste « hausse »."""
    def le_24_octobre(n):
        return ta.classer(FICHE, {"seuils": SEUILS, "actions": {"1": [n, "2026-08-15"]},
                                  "prix": {"XYZ": ["20260914", 30.41, "26923Y708"]}}, "XYZ", date(2026, 10, 24),
                          {"debut": "20250901", "symboles": {"XYZ": mstu}})
    t = le_24_octobre(10_000_000)  # au plus 304,1 M$ : petite à coup sûr (bonus), mais 100 M$ pas sûr (gardée)
    assert (t["taille"], t["valeur_m"], t["valeur_max"], t["prix"]) == ("petite", 304.1, True, ["20260914", 30.41])
    assert t["note"] == ("Nouveau code du titre (CUSIP) vu dès le 25 août 2026, après les actions déclarées au 15 août "
                         "2026, avec un prix 10,6 fois plus haut : regroupement d'actions probable. Leur nombre est "
                         "peut-être d'avant le regroupement : la valeur est au plus 304,1 M$, petite compagnie dans tous "
                         "les cas.")
    assert not sc.trop_petite({"taille": t})
    assert sc.trop_petite({"taille": le_24_octobre(1_000_000)})  # au plus 30,4 M$ : sous 100 M$ à coup sûr, écartée
    gros = le_24_octobre(100_000_000)  # au plus 3,0 G$ : au-dessus du 30e centile, on ne sait pas
    assert gros["taille"] is None and gros["raison"] == (
        "nouveau code du titre (CUSIP) vu dès le 25 août 2026, après les actions déclarées au 15 août 2026 "
        "(regroupement ou fractionnement d'actions possible), et pas de prix de l'ancien code depuis 60 jours")
    assert not sc.trop_petite({"taille": gros})


def test_ancien_prix_trop_vieux_sans_saut_de_prix_taille_inconnue():
    """Changement de CUSIP sans saut de prix (nom, fusion…) ou 1er prix du nouveau CUSIP inconnu : pas de maximum sûr."""
    for neuf in (["20260825", "20260914", "20260914", 3.1, "20260825", 2.9],  # 2,73 $ → 2,90 $ : pas un regroupement
                 ["20260825", "20260914", "20260914", 3.1, None, None]):
        h = {"O1": ["20260402", "20260824", "20260824", 2.73, "20260402", 4.1], "N1": neuf}
        t = ta.classer(FICHE, {"seuils": SEUILS, "actions": {"1": [10_000_000, "2026-08-15"]},
                               "prix": {"XYZ": ["20260914", 3.1, "N1"]}}, "XYZ", date(2026, 10, 24),
                       {"debut": "20250901", "symboles": {"XYZ": h}})
        assert t["taille"] is None and t["raison"].endswith("pas de prix de l'ancien code depuis 60 jours"), t


H_DEUX = {"O1": ["20260301", "20260803", "20260803", 2.0], "N1": ["20260818", "20260910", "20260910", 20.0]}


def test_deux_valeurs_possibles_meme_taille():
    # ancien CUSIP vu la dernière fois le 3 août, nouveau la 1re fois le 18 : actions du 10 août, côté inconnu
    t = taille([3_000_000, "2026-08-10"], ["20260910", 20.0, "N1"], H_DEUX)
    assert (t["taille"], t["valeur_m"], t["valeur_min_m"], t["prix"]) == ("petite", 60.0, 6.0, ["20260910", 20.0])
    assert t["note"] == ("Code du titre (CUSIP) changé entre le 3 août 2026 et le 18 août 2026, autour des actions "
                         "déclarées au 10 août 2026 : 6,0 M$ ou 60,0 M$ selon le côté du changement (regroupement ou "
                         "fractionnement d'actions possible) : petite compagnie dans les deux cas ; la règle des 100 M$ "
                         "prend la plus grande valeur.")
    assert sc.trop_petite({"taille": t})  # sous 100 M$ des deux côtés : écartée
    t2 = taille([30_000_000, "2026-08-10"], ["20260910", 20.0, "N1"], H_DEUX)  # 60 M$ ou 600 M$ : petite les deux
    assert (t2["taille"], t2["valeur_m"], t2["valeur_min_m"]) == ("petite", 600.0, 60.0)
    assert not sc.trop_petite({"taille": t2})  # 100 M$ pas sûr : gardée (comme une taille inconnue)


def test_deux_valeurs_possibles_tailles_differentes():
    t = taille([300_000_000, "2026-08-10"], ["20260910", 20.0, "N1"], H_DEUX)  # 600 M$ ou 6 G$
    assert t["taille"] is None and "valeur_m" not in t
    assert t["raison"] == ("code du titre (CUSIP) changé entre le 3 août 2026 et le 18 août 2026, autour des actions "
                           "déclarées au 10 août 2026 : 600,0 M$ ou 6,0 G$ selon le côté du changement (regroupement ou "
                           "fractionnement d'actions possible)")


@pytest.mark.parametrize("h, cusip, fin, attendu", [
    ({"N1": ["20260818", "20260910", "20260910", 20.0]}, "N1", "20260810", {"cas": "meme"}),  # aucun autre CUSIP
    ({"O1": ["20260301", "20260820", "20260820", 2.0], "N1": ["20260818", "20260910", "20260910", 20.0]}, "N1",
     "20260810", {"cas": "inconnue", "pourquoi": "chevauchement", "premier": "20260818"}),
    ({"O1": ["20260301", "20260601", "20260601", 1.0], "M1": ["20260815", "20260816", "20260816", 2.0],
      "N1": ["20260818", "20260910", "20260910", 20.0]}, "N1", "20260810",
     {"cas": "inconnue", "pourquoi": "plusieurs", "premier": "20260818"}),
    ({"O1": ["20260301", "20260803", "20260803", 2.0]}, "N1", "20260810", {"cas": "inconnue", "pourquoi": "absent"}),
])
def test_cas_ou_on_ne_sait_pas(h, cusip, fin, attendu):
    assert ta.epoque(h, cusip, fin) == attendu


def test_raisons_des_cas_inconnus():
    prix = ["20260910", 20.0, "N1"]
    chev = taille([3_000_000, "2026-08-10"], prix, {"O1": ["20260301", "20260820", "20260820", 2.0], "N1": H_DEUX["N1"]})
    assert chev["raison"] == ("nouveau code du titre (CUSIP) vu dès le 18 août 2026, après les actions déclarées au 10 "
                              "août 2026, et l'ancien encore vu après : impossible de savoir si leur nombre est d'avant "
                              "ou d'après un regroupement ou un fractionnement d'actions")
    plus = taille([3_000_000, "2026-08-10"], prix, {"O1": ["20260301", "20260601", "20260601", 1.0],
                                                    "M1": ["20260815", "20260816", "20260816", 2.0], "N1": H_DEUX["N1"]})
    assert plus["raison"] == "plusieurs changements du code du titre (CUSIP) depuis les actions déclarées au 10 août 2026"
    for t in (chev, plus):
        assert t["taille"] is None and not sc.trop_petite({"taille": t})  # inconnue : jamais écartée (lot M)


def test_pas_verifiable_le_calcul_d_avant_dit_tel_quel():
    """Juste après la mise en ligne, l'historique n'est pas encore lu (la taille est lue au passage du matin) : le calcul de
    la 0.27.0, avec la note, plutôt que des tailles inconnues qui remettraient les écartées dans la liste « hausse »."""
    prix = ["20260910", 20.0, "N1"]
    cas = {"jamais lu": ta.classer(FICHE, {"seuils": SEUILS, "actions": {"1": [3_000_000, "2026-08-10"]},
                                           "prix": {"XYZ": prix}}, "XYZ", JOUR, {}),
           "trop court": taille([3_000_000, "2026-08-10"], prix, H_DEUX, debut="20260815"),
           "prix d'avant l'étape 1": taille([3_000_000, "2026-08-10"], prix[:2], H_DEUX),
           "CUSIP absent": taille([3_000_000, "2026-08-10"], prix, {})}
    for nom, t in cas.items():
        assert (t["taille"], t["valeur_m"], t["prix"], t["note"]) == ("petite", 600.0 / 10, ["20260910", 20.0],
                                                                      ta.NON_VERIFIE), nom
        assert sc.trop_petite({"taille": t}), nom  # 60 M$ : écartée, comme avant
    assert ta.NON_VERIFIE == ("Changement du code du titre (CUSIP) pas encore vérifié : l'historique des fichiers de la "
                              "SEC n'est pas encore lu jusqu'à la date des actions.")


def test_sans_historique_comme_avant():
    """Les anciens rejeux du labo appellent classer sans historique : aucune vérification, comme la 0.27.0."""
    t = ta.classer(FICHE, {"seuils": SEUILS, "actions": {"1": [3_000_000, "2026-08-10"]},
                           "prix": {"XYZ": ["20260910", 20.0]}}, "XYZ", JOUR)
    assert (t["taille"], t["valeur_m"], t["prix"]) == ("petite", 60.0, ["20260910", 20.0]) and "note" not in t


def test_nouveau_fichier_ajoute_a_l_historique_sans_relire_les_anciens(tmp_path):
    """Le robot lit l'historique une fois (400 jours), puis seulement chaque nouveau fichier publié par la SEC."""
    from datetime import datetime, timezone

    from radar.http import ErreurSource
    from radar.models import empreinte
    from radar.run import Contexte

    cles = ["202607b", "202608a", "202608b"]

    class Internet:
        def __init__(self):
            self.appels = []

        def get(self, url, entetes=None):
            self.appels.append(url)
            if url == ta.SEUILS:
                c = (Path(__file__).parent / "fixtures" / "lotL" / "ME_Breakpoints_CSV.zip").read_bytes()
            elif url.startswith("https://data.sec.gov/api/xbrl/frames/"):
                c = json.dumps({"data": [{"cik": 1, "end": "2026-08-15", "val": 10_000_000}]}).encode()
            elif url == prix_sec.PAGE:
                c = "".join(f'<a href="/files/data/fails-deliver-data/cnsfails{k}.zip">{k}</a>' for k in cles).encode()
            elif "cnsfails" in url and url.rsplit("cnsfails", 1)[1][:7] in cles:
                c = zip_de(url.rsplit("cnsfails", 1)[1][:7])
            else:
                raise ErreurSource(f"{url} : HTTP 404")
            return type("T", (), {"contenu": c, "sha256": empreinte(c)})()

    i1 = Internet()
    ta.collecter(Contexte(client=i1, maintenant=datetime(2026, 9, 10, 11, 7, tzinfo=timezone.utc), donnees=tmp_path))
    assert sorted(u.rsplit("cnsfails", 1)[1] for u in i1.appels if "cnsfails" in u) == [f"{k}.zip" for k in cles]
    h1 = ta.charger_cusips(tmp_path)
    assert h1["fichiers"] == cles and h1["debut"] == "20260715" and h1["symboles"]["MSTU"]["26923Y708"][0] == "20260825"
    cles.append("202609a")  # la SEC publie la 1re moitié de septembre
    i2 = Internet()
    ta.collecter(Contexte(client=i2, maintenant=datetime(2026, 9, 30, 11, 7, tzinfo=timezone.utc), donnees=tmp_path))
    lus = [u.rsplit("cnsfails", 1)[1] for u in i2.appels if "cnsfails" in u]
    assert lus == ["202608b.zip", "202609a.zip"]  # les 2 derniers pour les prix ; l'historique : 202609a seulement
    h2 = ta.charger_cusips(tmp_path)
    assert h2["fichiers"] == cles and h2["symboles"]["MSTU"]["26923Y708"][1] == "20260914"
    assert h2["symboles"]["MSTU"]["26923N173"] == h1["symboles"]["MSTU"]["26923N173"]
    # MSTU : 10 millions d'actions au 15 août × le dernier prix de l'ancien CUSIP (24 août, 2,73 $)
    t = ta.pour_score(tmp_path, {"MSTU": {"cik": 1, "rapports": ["10-K", "10-Q"]}}, date(2026, 9, 30))["MSTU"]
    assert (t["valeur_m"], t["prix"]) == (27.3, ["20260824", 2.73]), t
