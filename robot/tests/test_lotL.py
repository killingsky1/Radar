"""Lot L : initiés « routiniers » (0 point) et petites compagnies (×1,5), sur de VRAIES données officielles lues le
5 octobre 2026 (tests/fixtures/lotL, labo/fixtures_lotL.py) :
- les jeux de données de la SEC sur les formulaires 3, 4 et 5 de 2023 à 2025 (12 fichiers trimestriels), réduits aux
  dépôts de 12 initiés (Milton C. Ault III et Ault & Company chez GPUS, Daniel L. Florness chez FUL, Ryan Cohen chez
  GME, puis des routiniers, des inhabituels et des initiés sans historique choisis par le labo) ;
- les seuils du NYSE de Kenneth French (fichier complet), les fichiers « frames » des actions en circulation et les
  2 derniers fichiers d'échecs de livraison de la SEC (réduits à 19 compagnies), les fiches SEC de ces compagnies ;
- 19 vrais formulaires 4 lus par le robot (GPUS, FUL, FLNA, PAM, GME, PRHI).
Les attendus viennent du labo, qui a classé chaque initié et calculé chaque taille sur les fichiers COMPLETS, avec son
propre code."""
import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from radar import emetteurs as em
from radar import score as sc
from radar.collecteurs import COLLECTEURS
from radar.collecteurs import inities as ini
from radar.collecteurs import prix_sec
from radar.collecteurs import taille as ta
from radar.collecteurs.sec import Symboles
from radar.http import ErreurSource
from radar.models import empreinte
from radar.registry import SOURCES
from radar.run import Contexte

F = Path(__file__).parent / "fixtures" / "lotL"
A_INI = json.loads((F / "attendus_inities.json").read_text(encoding="utf-8"))
A_TAILLE = json.loads((F / "attendus_taille.json").read_text(encoding="utf-8"))
EVENEMENTS = json.loads((F / "evenements_form4.json").read_text(encoding="utf-8"))
MAINTENANT = datetime(2026, 10, 5, 11, 7, tzinfo=timezone.utc)
CIKS = {s: x["cik"] for s, x in A_TAILLE["compagnies"].items()}
TRIMESTRES = [f"{a}q{q}" for a in (2023, 2024, 2025) for q in (1, 2, 3, 4)]


def telechargement(c: bytes):
    return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


class FauxInternet:
    """Sert les vrais fichiers réduits, aux vraies adresses de la SEC et de Kenneth French ; le reste : 404."""

    def __init__(self, page_jeux=None, remplace=None):
        self.appels = []
        self.page_jeux = page_jeux
        self.remplace = remplace or {}

    def get(self, url, entetes=None):
        self.appels.append(url)
        if url in self.remplace:
            return telechargement(self.remplace[url])
        nom = url.rsplit("/", 1)[-1]
        if url == ini.PAGE:
            return telechargement(self.page_jeux or (F / "page_jeux_de_donnees.html").read_bytes())
        if url.startswith("https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/"):
            return telechargement((F / "jeux" / nom).read_bytes())
        if url == ta.SEUILS:
            return telechargement((F / "ME_Breakpoints_CSV.zip").read_bytes())
        if url.startswith("https://data.sec.gov/api/xbrl/frames/dei/EntityCommonStockSharesOutstanding/shares/") and \
                (F / f"frames_{nom}").exists():
            return telechargement((F / f"frames_{nom}").read_bytes())
        if url == prix_sec.PAGE:
            return telechargement((F / "page_echecs.html").read_bytes())
        if url.startswith("https://www.sec.gov/files/data/fails-deliver-data/") and (F / nom).exists():
            return telechargement((F / nom).read_bytes())
        raise ErreurSource(f"{url} : HTTP 404")


def contexte(tmp_path, maintenant=MAINTENANT, internet=None):
    return Contexte(client=internet or FauxInternet(), maintenant=maintenant, donnees=tmp_path)


def fiches():
    """{symbole : fiche comme emetteurs.json la garde} d'après les vraies fiches de la SEC."""
    sortie = {}
    for s, cik in CIKS.items():
        f = json.loads((F / "fiches" / f"CIK{cik:010d}.json").read_text(encoding="utf-8"))
        sortie[s] = {"cik": cik, "type": em.classer(f)[0], "rapports": em.rapports(f)}
    return sortie


@pytest.fixture(scope="module")
def classement():
    lignes = [l for t in TRIMESTRES for l in ini.transactions((F / "jeux" / f"{t}_form345.zip").read_bytes(),
                                                              {2023, 2024, 2025})]
    return ini.classer(lignes, [2023, 2024, 2025])


# ---------- Sources ----------


def test_deux_sources_de_calcul_lues_le_matin():
    assert COLLECTEURS["sec_historique_inities"] is ini.collecter and COLLECTEURS["taille_bourse"] is ta.collecter
    for sid in ("sec_historique_inities", "taille_bourse"):
        assert SOURCES[sid].passages == ("matin",) and SOURCES[sid].officielle is False  # jamais un signal seul
    assert SOURCES["taille_bourse"].domaines == ("sec.gov", "dartmouth.edu")


# ---------- Initiés routiniers ----------


def test_les_12_fichiers_trouves_sur_la_page_de_la_sec():
    liens = ini.fichiers_de_la_page((F / "page_jeux_de_donnees.html").read_text(encoding="utf-8"))
    assert sorted(liens) == TRIMESTRES
    assert liens["2025q4"] == ("https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/"
                               "2025q4_form345.zip")


@pytest.mark.parametrize("cle", sorted(A_INI["par_cik"]))
def test_chaque_initie_classe_comme_le_labo_par_cik(classement, cle):
    o, e = cle.split(":")
    a = A_INI["par_cik"][cle]
    trouve = classement["cik"].get(e, {}).get(o)
    assert trouve == (a["mois_communs"] if a["classe"] == "routinier" else None), a


@pytest.mark.parametrize("cle", sorted(A_INI["par_nom"]))
def test_chaque_initie_classe_comme_le_labo_par_nom(classement, cle):
    e, nom = cle.split("|")
    a = A_INI["par_nom"][cle]
    assert ini.nom_normal(nom) == nom
    trouve = classement["noms"].get(e, {}).get(nom)
    assert trouve == (a["mois_communs"] if a["classe"] == "routinier" else None), a


def test_ault_routinier_chez_gpus_mais_pas_ault_and_company(classement):
    assert classement["cik"]["896493"]["1212502"] == [6, 11]  # juin et novembre, chacune des 3 années
    assert "1734770" not in classement["cik"]["896493"]  # Ault & Company : seulement en 2025
    assert classement["noms"]["896493"]["AULT MILTON C III"] == [6, 11]
    assert ini.nom_normal("Ault Milton C. III") == "AULT MILTON C III"


def test_collecte_une_fois_pour_l_annee_puis_rien(tmp_path):
    internet = FauxInternet()
    assert ini.collecter(contexte(tmp_path, internet=internet)) == []  # aucune info : rien n'entre dans la note
    assert internet.appels == [ini.PAGE] + [ini.fichiers_de_la_page(
        (F / "page_jeux_de_donnees.html").read_text(encoding="utf-8"))[t] for t in TRIMESTRES]
    e = ini.charger(tmp_path)
    assert list(e["annees"]) == ["2026"] and e["annees"]["2026"]["depuis"] == [2023, 2024, 2025]
    assert e["annees"]["2026"]["cik"]["896493"]["1212502"] == [6, 11]
    internet2 = FauxInternet()
    ini.collecter(contexte(tmp_path, internet=internet2))
    assert internet2.appels == [ini.PAGE]  # déjà classé : seulement la page
    # Janvier 2027 : le 4e trimestre 2026 n'est pas publié → pas de classement 2027, celui de 2026 reste
    internet3 = FauxInternet()
    ini.collecter(contexte(tmp_path, datetime(2027, 1, 10, tzinfo=timezone.utc), internet3))
    assert internet3.appels == [ini.PAGE] and list(ini.charger(tmp_path)["annees"]) == ["2026"]
    # 2028 : le classement de 2026 ne sert plus (les infos de 2026 ont plus de 90 jours)
    ini.collecter(contexte(tmp_path, datetime(2028, 3, 1, tzinfo=timezone.utc), FauxInternet()))
    assert ini.charger(tmp_path)["annees"] == {}


def test_pas_de_classement_si_un_trimestre_manque(tmp_path):
    page = (F / "page_jeux_de_donnees.html").read_text(encoding="utf-8").replace("2025q4_form345.zip", "x.zip")
    internet = FauxInternet(page_jeux=page.encode())
    ini.collecter(contexte(tmp_path, internet=internet))
    assert internet.appels == [ini.PAGE] and not ini.chemin(tmp_path).exists()


def test_page_changee_ou_fichier_illisible_est_une_panne(tmp_path):
    with pytest.raises(RuntimeError, match="aucun fichier"):
        ini.collecter(contexte(tmp_path, internet=FauxInternet(page_jeux=b"<html>rien</html>")))
    import io
    import zipfile
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("SUBMISSION.tsv", "ACCESSION_NUMBER\tAUTRE\n")
    url = ini.fichiers_de_la_page((F / "page_jeux_de_donnees.html").read_text(encoding="utf-8"))["2023q1"]
    with pytest.raises(ValueError, match="colonnes absentes de SUBMISSION"):
        ini.collecter(contexte(tmp_path, internet=FauxInternet(remplace={url: b.getvalue()})))
    assert not ini.chemin(tmp_path).exists()  # rien d'écrit : l'ancien classement reste


def evenement(id_):
    return json.loads(json.dumps(next(e for e in EVENEMENTS if e["id"] == id_)))


def test_le_vrai_achat_de_gpus_est_routinier_par_nom_puis_par_cik(classement):
    routiniers = {"version": ini.VERSION, "annees": {"2026": classement}}
    ev = evenement("sec_form4:0001214659-26-012383:P")  # lu avant le lot L : pas de CIK des déclarants
    assert "proprietaires_cik" not in ev["data"]
    assert ini.routinier(routiniers, ev) == {"mois": [6, 11], "annees": [2023, 2024, 2025]}  # par le nom
    ev["data"]["proprietaires_cik"] = ["1734770", "1212502"]
    ev["entities"] = ["X", "Y", "Hyperscale Data, Inc."]
    assert ini.routinier(routiniers, ev)["mois"] == [6, 11]  # par le CIK
    assert ini.en_mots(ini.routinier(routiniers, ev)) == "juin et novembre (2023, 2024 et 2025)"
    ev["occurred_on"] = "2025-12-30"  # pas de classement pour 2025 : rien ne change
    assert ini.routinier(routiniers, ev) is None
    assert ini.routinier(None, evenement("sec_form4:0001214659-26-012383:P")) is None
    florness = evenement("sec_form4:0001225208-26-008015:P")  # sans historique chez FUL
    assert ini.routinier(routiniers, florness) is None


def test_le_formulaire_4_garde_le_cik_des_declarants():
    from radar.collecteurs.sec import evenements_form4, lire_index
    S = Path(__file__).parent / "fixtures" / "sec"
    syms = Symboles(json.loads((S / "company_tickers_exchange.json").read_text(encoding="utf-8")))
    index = lire_index((S / "master.20261001.idx").read_text(encoding="latin-1"))
    t = (S / "0001822293-26-000002.txt").read_text(encoding="utf-8", errors="replace")
    [ev] = evenements_form4(t, "a" * 64, index["0001822293-26-000002"], syms)
    assert ev.entities[:-1] == ["Turner Nat"] and ev.data["proprietaires_cik"] == ["1822293"]


def test_en_mots():
    assert ini.en_mots({"mois": [3], "annees": [2023, 2024, 2025]}) == "mars (2023, 2024 et 2025)"
    assert ini.en_mots({"mois": list(range(1, 13)), "annees": [2023, 2024, 2025]}) == "chaque mois (2023, 2024 et 2025)"
    assert ini.en_mots({"mois": [2, 8, 12], "annees": [2023, 2024, 2025]}) == "février, août et décembre (2023, 2024 et 2025)"


# ---------- Taille en bourse ----------


def test_seuils_du_nyse_comme_le_labo():
    s = ta.lire_seuils((F / "ME_Breakpoints_CSV.zip").read_bytes())
    assert s == {"mois": "202608", "compagnies_nyse": 1071, "p30": 2236.27, "p70": 13366.01}
    assert {k: s[k] for k in ("mois", "p30", "p70")} == A_TAILLE["seuils"]


def test_periodes():
    assert ta.periodes(date(2026, 10, 5)) == ["CY2026Q4I", "CY2026Q3I", "CY2026Q2I", "CY2026Q1I", "CY2025Q4I"]
    assert ta.periodes(date(2027, 2, 1)) == ["CY2027Q1I", "CY2026Q4I", "CY2026Q3I", "CY2026Q2I", "CY2026Q1I"]


def collecter_taille(tmp_path, internet=None):
    internet = internet or FauxInternet()
    assert ta.collecter(contexte(tmp_path, internet=internet)) == []
    return internet


@pytest.mark.parametrize("symbole", sorted(A_TAILLE["compagnies"]))
def test_chaque_taille_comme_le_labo(tmp_path, symbole):
    collecter_taille(tmp_path)
    t = ta.pour_score(tmp_path, fiches(), MAINTENANT.date())[symbole]
    a = A_TAILLE["compagnies"][symbole]
    assert t["taille"] == a["taille"], (t, a)
    if a["taille"]:
        assert abs(t["valeur_m"] - a["valeur_m"]) <= 0.06 and t["actions"] == a["actions"][:2] and t["prix"] == a["prix"]
        assert t["seuils"] == A_TAILLE["seuils"]
    else:
        assert t["raison"]


def test_raisons_des_tailles_inconnues(tmp_path):
    collecter_taille(tmp_path)
    t = ta.pour_score(tmp_path, fiches(), MAINTENANT.date())
    assert t["PAM"]["raison"].startswith("compagnie étrangère")  # 20-F : certificats (ADS) de 25 actions
    assert t["HELP"]["raison"].startswith("compagnie étrangère")  # 40-F
    assert t["GPUS"]["raison"].startswith("pas d'actions en circulation")
    assert t["CPHC"]["raison"].startswith("pas de prix de la SEC")
    plus_tard = ta.pour_score(tmp_path, fiches(), date(2026, 12, 1))  # prix du 14 septembre : plus de 60 jours
    assert plus_tard["FLNA"]["taille"] is None and plus_tard["FLNA"]["raison"].startswith("pas de prix")
    assert ta.pour_score(tmp_path, {"FLNA": {"cik": CIKS["FLNA"]}}, MAINTENANT.date())["FLNA"]["raison"] == \
        "fiche de la SEC pas encore lue"  # fiche d'avant le lot L : sans la liste des rapports
    assert ta.pour_score(tmp_path / "vide", fiches(), MAINTENANT.date())["FLNA"]["raison"] == \
        "seuils du NYSE pas encore lus"


def test_prix_relus_seulement_quand_la_sec_publie_un_nouveau_fichier(tmp_path):
    internet = collecter_taille(tmp_path)
    ftd = [u for u in internet.appels if "cnsfails" in u]
    assert ftd == ["https://www.sec.gov/files/data/fails-deliver-data/cnsfails202608b.zip",
                   "https://www.sec.gov/files/data/fails-deliver-data/cnsfails202609a.zip"]
    contenu = ta.chemin(tmp_path).read_text(encoding="utf-8")
    internet2 = collecter_taille(tmp_path)
    assert not [u for u in internet2.appels if "cnsfails" in u]
    assert ta.chemin(tmp_path).read_text(encoding="utf-8") == contenu  # rien de changé : fichier pas réécrit
    e = ta.charger(tmp_path)
    assert e["frames"]["CY2026Q4I"] == {"statut": 404}  # trimestre en cours : pas encore de fichier, normal
    assert e["fichiers_prix"] == ["202608b", "202609a"] and e["prix"]["FLNA"] == ["20260914", 0.77]


def test_autre_erreur_que_404_est_une_panne(tmp_path):
    class Panne(FauxInternet):
        def get(self, url, entetes=None):
            if "CY2026Q2I" in url:
                raise ErreurSource(f"{url} : HTTP 503")
            return super().get(url, entetes)
    with pytest.raises(ErreurSource, match="503"):
        ta.collecter(contexte(tmp_path, internet=Panne()))
    assert not ta.chemin(tmp_path).exists()


def test_rapports_des_fiches():
    f = fiches()
    assert f["GPUS"]["rapports"] == ["10-K", "10-Q"] and f["PAM"]["rapports"] == ["20-F", "6-K"]
    assert f["HELP"]["rapports"] == ["40-F", "6-K"]


def test_fiches_d_avant_le_lot_l_relues_une_fois(tmp_path):
    class Fiches:
        def __init__(self):
            self.appels = []

        def get(self, url, entetes=None):
            self.appels.append(url)
            cik = int(url.rsplit("CIK", 1)[1][:10])
            return telechargement((F / "fiches" / f"CIK{cik:010d}.json").read_bytes())
    (tmp_path / "sec").mkdir()
    (tmp_path / "sec" / "emetteurs.json").write_text(json.dumps({"GME": {
        "cik": 1326380, "nom": "GameStop Corp.", "type": "compagnie", "formulaires_fonds": [], "lu": "2026-10-04"}}),
        encoding="utf-8")
    ctx = Contexte(client=Fiches(), maintenant=MAINTENANT, donnees=tmp_path)
    ctx.cache["sec_symboles"] = Symboles(json.loads(gzip.decompress(
        (Path(__file__).parent / "fixtures" / "sec" / "company_tickers_exchange_complet.json.gz").read_bytes())))
    assert em.rafraichir(ctx, {"GME"}) == {"lues": 1, "erreurs": 0}
    assert em.charger(tmp_path)["GME"]["rapports"] == ["10-K", "10-Q"]
    assert em.rafraichir(ctx, {"GME"}) == {"lues": 0, "erreurs": 0}  # une seule fois


# ---------- Le score avec les deux règles ----------


@pytest.fixture(scope="module")
def regles(classement, tmp_path_factory):
    d = tmp_path_factory.mktemp("taille")
    ta.collecter(contexte(d))
    return {"version": ini.VERSION, "annees": {"2026": classement}}, ta.pour_score(d, fiches(), MAINTENANT.date())


def lignes(score):
    return {r["symbole"]: r for liste in ("hausse", "baisse") for r in score[liste]}


def facteurs(r):
    return {tuple(f) for g in r["groupes"] for i in g["infos"] for f in i["facteurs"]}


def test_score_avant_et_apres(regles):
    routiniers, tailles = regles
    avant = lignes(sc.calculer(EVENEMENTS, MAINTENANT))
    apres = sc.calculer(EVENEMENTS, MAINTENANT, routiniers=routiniers, tailles=tailles)
    assert apres["version"] == "score-8"
    l = lignes(apres)
    # GPUS : son seul achat vient d'un initié routinier → 0 point, hors des listes
    assert "GPUS" in avant and "GPUS" not in l
    # FLNA (37 M$) et PRHI (33 M$) : petites → ×1,5 sur les achats du dirigeant
    assert ("Petite compagnie", 1.5) in facteurs(l["FLNA"]) and ("Petite compagnie", 1.5) in facteurs(l["PRHI"])
    assert l["FLNA"]["score"] == pytest.approx(avant["FLNA"]["score"] * 1.5, abs=0.02)  # scores publiés arrondis
    assert l["FLNA"]["taille"]["taille"] == "petite" and l["FLNA"]["taille"]["valeur_m"] == pytest.approx(37.2, abs=0.1)
    # FUL et GME (moyennes), PAM (étrangère, taille inconnue) : aucun bonus
    for s in ("FUL", "GME"):
        assert ("Petite compagnie", 1.5) not in facteurs(l[s]) and l[s]["score"] == avant[s]["score"]
    assert ("Petite compagnie", 1.5) not in facteurs(l.get("PAM") or {"groupes": []})


def test_routinier_garde_la_raison_en_contexte(regles):
    routiniers, tailles = regles
    gpus = evenement("sec_form4:0001214659-26-012383:P")
    [a] = sc.evaluer(gpus, routiniers=routiniers)
    assert a.regle is None and a.pourquoi == sc.SANS_POINTS["routinier"] + \
        " Mois : juin et novembre (2023, 2024 et 2025)."
    vente = {**gpus, "kind": "vente_initie", "direction": -1}  # une vente routinière : 0 point aussi
    assert sc.evaluer(vente, routiniers=routiniers)[0].regle is None
    gpus["data"]["plan_10b5_1"] = True  # plan 10b5-1 : la raison la plus précise d'abord
    assert sc.evaluer(gpus, routiniers=routiniers)[0].pourquoi == sc.SANS_POINTS["plan"]


def test_vente_jamais_multipliee_par_la_taille(regles):
    _, tailles = regles
    ev = evenement("sec_form4:0001437749-26-031597:P")  # FLNA, petite
    vente = {**ev, "id": ev["id"] + "V", "kind": "vente_initie", "direction": -1, "amount_min": 2e6, "amount_max": 2e6}
    r = sc.calculer([vente], MAINTENANT, tailles=tailles)
    assert not any(("Petite compagnie", 1.5) in facteurs(x) for x in r["hausse"] + r["baisse"])


def test_methode_explique_les_deux_regles():
    m = sc.METHODE
    assert sc.SANS_POINTS["routinier"] in m["sans_points"] and "30e centile" in m["taille"]
    achat = next(r for r in m["regles"] if r["code"] == "achat_dirigeant")
    assert any(d.startswith("×1,5 si c'est une petite compagnie") for d in achat["details"])
    assert any("routinier" in d for d in achat["details"])


# ---------- Résultats : les raisons de chaque entrée, puis le résumé par signal ----------


def test_chaque_nouvelle_entree_garde_ses_raisons(regles):
    from radar import resultats as rs
    routiniers, tailles = regles
    score = sc.calculer(EVENEMENTS, MAINTENANT, routiniers=routiniers, tailles=tailles)
    h = {"entrees": []}
    nouvelles = {e["symbole"]: e for e in rs.noter_entrees(h, score, MAINTENANT)}
    flna = nouvelles["FLNA"]
    assert flna["signaux"] == [{"famille": "inities", "sens": 1, "regle": "achat_dirigeant",
                                "facteurs": ["PDG, directeur financier ou président du conseil", "Petite compagnie"]}]
    assert flna["taille"] == "petite" and flna["note10_sans_taille"] == 7.3 and flna["grace_a_la_taille"] is False
    assert flna["note10_sans_bonus"] == flna["note10"] and flna["grace_au_bonus"] is False  # une seule famille
    assert nouvelles["FUL"]["taille"] == "moyenne" and "Groupe d'achats" in nouvelles["FUL"]["signaux"][0]["facteurs"]
    assert nouvelles["PAM"]["taille"] is None and nouvelles["PAM"]["note10_sans_taille"] == nouvelles["PAM"]["note10"]
    assert list(nouvelles) == ["PRHI", "GME", "FLNA", "PAM", "FUL"]  # GPUS (routinier) n'entre pas
    # Un administrateur seul de PRHI (petite) : 7,3/10 avec le bonus de taille, 6,5 sans → entré grâce à lui
    smith = evenement("sec_form4:0001193125-26-410905:P")
    seul = rs.noter_entrees({"entrees": []}, sc.calculer([smith], MAINTENANT, routiniers=routiniers, tailles=tailles),
                            MAINTENANT)
    assert [(e["symbole"], e["note10"], e["note10_sans_taille"], e["grace_a_la_taille"]) for e in seul] == [
        ("PRHI", 7.3, 6.5, True)]
    assert sc.calculer([smith], MAINTENANT)["hausse"] == []  # sans la règle de taille : pas dans la liste


def test_resume_par_signal_sur_de_vrais_prix(tmp_path, monkeypatch):
    """Les entrées (exemples) et les vrais prix de la SEC du lot G : chaque signal additionne ses entrées mesurées."""
    from radar import resultats as rs
    from test_lotG import ENTREES, prepare
    raisons = {
        "AAPL": {"signaux": [{"famille": "inities", "sens": 1, "regle": "achat_dirigeant", "facteurs": ["Groupe d'achats"]}],
                 "taille": "grande", "note10_sans_bonus": 8.0, "grace_au_bonus": False},
        "GME": {"signaux": [{"famille": "inities", "sens": 1, "regle": "achat_dirigeant", "facteurs": []},
                            {"famille": "activistes", "sens": 1, "regle": "activiste_13d", "facteurs": []}],
                "taille": "moyenne", "note10_sans_bonus": 6.9, "grace_au_bonus": True},
        "MSTU": {"signaux": [{"famille": "inities", "sens": 1, "regle": "achat_dirigeant", "facteurs": ["Petite compagnie"]}],
                 "taille": "petite", "note10_sans_taille": 6.7, "grace_a_la_taille": True},
        "CRE": {"signaux": [{"famille": "sec", "sens": -1, "regle": "sec_procedure", "facteurs": []}], "taille": None},
    }
    entrees = [{**e, **raisons.get(e["symbole"], {})} for e in ENTREES]  # LESL et XMPL : d'avant le lot L
    monkeypatch.setattr("test_lotG.ENTREES", entrees)
    prepare(tmp_path, monkeypatch)
    r = rs.calculer(tmp_path, datetime(2026, 10, 4, 22, 0, tzinfo=timezone.utc))
    p = r["par_signal"]
    assert p["sans_raisons"] == 2
    lignes_ = {l["symbole"]: l for l in r["lignes"]}
    for sens, signal, symboles in (
            ("hausse", "regle:achat_dirigeant", ["AAPL", "GME", "MSTU"]), ("hausse", "regle:activiste_13d", ["GME"]),
            ("hausse", "facteur:Groupe d'achats", ["AAPL"]), ("hausse", "plusieurs_familles", ["GME"]),
            ("hausse", "grace_au_bonus", ["GME"]), ("hausse", "grace_a_la_taille", ["MSTU"]),
            ("hausse", "taille:petite", ["MSTU"]), ("hausse", "taille:grande", ["AAPL"]),
            ("baisse", "regle:sec_procedure", ["CRE"]), ("baisse", "taille:inconnue", ["CRE"])):
        x = p[sens][signal]
        assert x["entrees"] == len(symboles), signal
        for hz in ("7", "30"):  # refait ici à partir des lignes mesurées
            m = [lignes_[s]["horizons"][hz] for s in symboles if lignes_[s]["horizons"][hz]["statut"] == "mesure"
                 and lignes_[s]["horizons"][hz]["battu"] is not None]
            assert x[hz]["mesurees"] == len(m) and x[hz]["battu"] == sum(v["battu"] for v in m), (signal, hz)
            assert x[hz]["ecart_moyen"] == (round(sum(v["ecart"] for v in m) / len(m), 4) if m else None)
    assert "facteur:Petite compagnie" not in p["hausse"]  # déjà dans « taille:petite »
    assert p["hausse"]["regle:achat_dirigeant"]["libelle"] == "Achat d'actions par un dirigeant ou un administrateur"
    assert p["hausse"]["regle:achat_dirigeant"]["7"]["mesurees"] >= 1  # au moins une vraie mesure (AAPL, juillet)
