"""Lot G, résultats de Radar, sur de VRAIS extraits des fichiers d'échecs de livraison de la SEC (tests/fixtures/lotG :
juillet à septembre 2026, lignes de SPY, IVV, VOO, AAPL, GME, MSTU, CRE… et une vraie ligne par date de règlement pour
garder le calendrier complet) et la vraie page officielle. Les entrées dans les listes sont des exemples (TEST) placées
en juillet et en août 2026 pour mesurer sur ces vrais prix ; les résultats attendus sont calculés à la main."""

import gzip
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from radar import resultats as rs
from radar.collecteurs import prix_sec as ps
from radar.http import ErreurSource
from radar.models import empreinte
from radar.publish import publier
from radar.registry import SOURCES
from radar.run import Contexte

F = Path(__file__).parent / "fixtures" / "lotG"
PAGE = gzip.decompress((F / "page_ftd.html.gz").read_bytes())
MAINTENANT = datetime(2026, 10, 4, 22, 0, tzinfo=timezone.utc)


def zip_de(cle):
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr(f"cnsfails{cle}.txt", (F / f"cnsfails{cle}.txt").read_bytes())
    return tampon.getvalue()


class FauxInternet:
    def __init__(self):
        self.appels = []

    def get(self, url, entetes=None):
        self.appels.append(url)
        c = PAGE if url == ps.PAGE else None
        for cle in ("202607b", "202608a", "202608b", "202609a"):
            if url.endswith(f"cnsfails{cle}.zip"):
                c = zip_de(cle)
        if c is None:
            raise ErreurSource(f"{url} : HTTP 404")
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def entree(symbole, sens, quand, note=8.0):
    return {"symbole": symbole, "nom": f"TEST {symbole}", "sens": sens, "entree": quand, "vue": quand[:10], "note10": note,
            "methode": "score-7"}


ENTREES = [
    entree("AAPL", "hausse", "2026-07-20T14:00:00+00:00"),   # lundi 10 h (Toronto)
    entree("MSTU", "hausse", "2026-08-14T21:00:00+00:00"),   # vendredi 17 h : après la clôture
    entree("CRE", "baisse", "2026-08-17T12:00:00+00:00", 2.0),
    entree("LESL", "baisse", "2026-07-20T14:00:00+00:00", 1.1),
    entree("XMPL", "hausse", "2026-07-20T14:00:00+00:00"),  # symbole fictif : aucune ligne à la SEC
    entree("GME", "hausse", "2026-09-11T15:00:00+00:00", 9.3),
]


def prepare(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "PREMIER_FICHIER", "202607b")  # en vrai : octobre 2026 (début de la méthode actuelle)
    (tmp_path / "resultats").mkdir()
    (tmp_path / "resultats" / "suggestions.json").write_text(json.dumps({"entrees": ENTREES}), encoding="utf-8")
    internet = FauxInternet()
    assert ps.collecter(Contexte(client=internet, maintenant=MAINTENANT, donnees=tmp_path)) == []
    return internet


def test_page_officielle_fichiers_et_moities_du_mois():
    liens = ps.fichiers_de_la_page(PAGE.decode("utf-8", "replace"))
    assert len(liens) == 411 and max(liens) == "202609a"
    assert liens["202609a"] == "https://www.sec.gov/files/data/fails-deliver-data/cnsfails202609a.zip"
    assert ps.periode("202609a") == ("20260901", "20260914") and ps.periode("202607b") == ("20260715", "20260731")
    # La SEC : 1re moitié publiée à la fin du mois, 2e moitié vers le 15 du mois suivant
    assert str(ps.mise_en_ligne_prevue("20261006")) == "2026-10-31"
    assert str(ps.mise_en_ligne_prevue("20261015")) == "2026-11-15"
    assert str(ps.mise_en_ligne_prevue("20261215")) == "2027-01-15"


def test_lecture_des_vrais_fichiers_calendrier_complet_et_prix(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    e = ps.lire_etat(tmp_path)
    assert sorted(e["fichiers"]) == ["202607b", "202608a", "202608b", "202609a"]
    jours = ps.calendrier(e)
    assert len(jours) == 43 and jours[0] == "20260715" and jours[-1] == "20260914"
    assert "20260907" not in jours  # fête du Travail : pas de règlement
    assert e["prix"]["SPY"]["20260715"] == [751.83, "78462F103"]
    assert e["prix"]["MSTU"]["20260825"][1] != e["prix"]["MSTU"]["20260824"][1]  # nouveau CUSIP
    assert set(e["prix"]) <= {"SPY", "IVV", "VOO", "AAPL", "MSTU", "CRE", "LESL", "GME"}  # seulement les suivis
    assert ps.couvert_jusqu_au(e) == "20260914"


def test_relance_ne_relit_rien_puis_nouvelle_compagnie_relue(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    internet = FauxInternet()
    ps.collecter(Contexte(client=internet, maintenant=MAINTENANT, donnees=tmp_path))
    assert internet.appels == [ps.PAGE]  # rien de nouveau : seulement la page
    h = json.loads((tmp_path / "resultats" / "suggestions.json").read_text())
    h["entrees"].append(entree("NVDA", "hausse", "2026-08-31T14:00:00+00:00"))
    (tmp_path / "resultats" / "suggestions.json").write_text(json.dumps(h))
    internet = FauxInternet()
    ps.collecter(Contexte(client=internet, maintenant=MAINTENANT, donnees=tmp_path))
    # NVDA entre le 31 août : relue seulement dans les fichiers qui couvrent cette date
    assert [u.rsplit("/", 1)[1] for u in internet.appels[1:]] == ["cnsfails202608b.zip", "cnsfails202609a.zip"]


def test_aapl_depart_apres_la_suggestion_semaine_et_mois(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    r = rs.calculer(tmp_path, MAINTENANT)
    aapl = next(l for l in r["lignes"] if l["symbole"] == "AAPL")
    # Suggestion le lundi 20 juillet : 2e date de règlement après = 22 juillet (pas de prix), puis le 23 : 325,89 $
    assert aapl["depart"] == {"statut": "ok", "date": "20260723", "prix": 325.89, "cusip": "037833100"}
    s = aapl["horizons"]["7"]  # 30 juillet : 338,19 $ ; marché : IVV (SPY n'a pas de prix le 30)
    assert (s["statut"], s["date"], s["prix"], s["variation"]) == ("mesure", "20260730", 338.19, 0.0377)
    assert s["marche"] == {"fonds": "IVV", "variation": -0.0237} and s["battu"] is True and s["ecart"] == 0.0614
    m = aapl["horizons"]["30"]  # 22 août (samedi) → 24 août : 309,35 $ ; SPY 747,41 → 765,72
    assert (m["date"], m["variation"], m["marche"], m["battu"]) == ("20260824", -0.0508, {"fonds": "SPY", "variation": 0.0245},
                                                                     False)


def test_nouveau_cusip_pas_comparable_et_saut_anormal_a_verifier(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    r = {l["symbole"]: l for l in rs.calculer(tmp_path, MAINTENANT)["lignes"]}
    # MSTU : suggérée vendredi 14 août après la clôture → départ le 18 (1,88 $) ; le 25, nouveau CUSIP (28,86 $)
    assert r["MSTU"]["depart"]["date"] == "20260818"
    assert r["MSTU"]["horizons"]["7"]["statut"] == "pas_comparable" and "CUSIP" in r["MSTU"]["horizons"]["7"]["pourquoi"]
    # CRE : 2,50 $ puis 6,81 $ (×2,72) : à vérifier, hors du taux
    assert r["CRE"]["depart"]["date"] == "20260819" and r["CRE"]["horizons"]["7"]["statut"] == "a_verifier"


def test_pas_de_prix_et_en_attente_des_prochains_fichiers(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    res = rs.calculer(tmp_path, MAINTENANT)
    r = {l["symbole"]: l for l in res["lignes"]}
    assert r["XMPL"]["depart"] == {"statut": "pas_de_prix"}  # aucune ligne à la SEC
    # LESL (vrais prix) : départ le 23 juillet (2,41 $) ; aucun prix du 30 juillet au 2 août → pas de prix à 1 semaine ;
    # 24 août : 0,60 $ (−75 %, et 2,41 → 1,33 $ en un jour) → à vérifier, hors du taux
    assert r["LESL"]["depart"]["prix"] == 2.41 and r["LESL"]["horizons"]["7"] == {"statut": "pas_de_prix"}
    assert r["LESL"]["horizons"]["30"]["statut"] == "a_verifier" and r["LESL"]["horizons"]["30"]["variation"] == -0.751
    # GME suggérée le 11 septembre : la SEC n'a publié que jusqu'au 14 → en attente du fichier du 15 au 30 (vers le 15 oct.)
    assert r["GME"]["horizons"]["7"] == {"statut": "en_attente", "attendu_vers": "2026-10-15"}
    assert res["prix_jusqu_au"] == "2026-09-14" and res["prochains_prix_vers"] == "2026-10-15"
    # AAPL 1 mois mesuré ; hors du taux : MSTU (pas comparable), CRE (à vérifier), LESL (pas de prix)
    # Hausse à 1 semaine : AAPL mesurée (battu) ; MSTU pas comparable ; XMPL sans prix ; GME en attente
    assert res["resume"]["hausse_7"] == {"mesurees": 1, "battu": 1, "ecart_moyen": 0.0614, "en_attente": 1}
    assert res["resume"]["baisse_7"]["mesurees"] == 0


def test_marche_deux_fonds_qui_ne_concordent_pas_pas_de_verdict(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    e = ps.lire_etat(tmp_path)
    e["prix"]["SPY"]["20260730"] = [700.0, "78462F103"]  # faux prix : SPY −6 % pendant qu'IVV fait −2,4 %
    ps.chemin_etat(tmp_path).write_text(json.dumps(e))
    s = next(l for l in rs.calculer(tmp_path, MAINTENANT)["lignes"] if l["symbole"] == "AAPL")["horizons"]["7"]
    assert s["statut"] == "mesure" and s["battu"] is None and "ne concordent pas" in s["pourquoi"]


def test_entrees_une_fois_tant_qu_elle_reste_dans_la_liste():
    h = {"entrees": []}
    gme = {"symbole": "GME", "nom": "GameStop Corp.", "note10": 9.3, "depuis": None}
    lesl = {"symbole": "LESL", "nom": "Leslie's", "note10": 1.1, "depuis": "2026-10-03T21:55:32+00:00"}
    score = {"version": "score-7", "hausse": [gme], "baisse": [lesl]}
    nouvelles = rs.noter_entrees(h, score, MAINTENANT)
    assert [(e["symbole"], e["sens"], e["entree"], e["vue"]) for e in nouvelles] == [
        ("GME", "hausse", MAINTENANT.isoformat(), "2026-10-04"), ("LESL", "baisse", "2026-10-03T21:55:32+00:00", "2026-10-04")]
    # Toujours dans la liste, jour après jour (même 2 mois) : jamais une 2e entrée
    for jour in ("2026-10-20", "2026-11-10", "2026-12-05"):
        assert rs.noter_entrees(h, score, datetime.fromisoformat(f"{jour}T15:00:00+00:00")) == []
    assert [e["vue"] for e in h["entrees"]] == ["2026-12-05", "2026-12-05"]
    # GME sort de la liste le 6 décembre et y revient le 10 janvier (plus de 30 jours) : nouvelle entrée
    for jour in ("2026-12-06", "2026-12-20", "2027-01-03"):  # le robot tourne : LESL reste vue, GME n'y est plus
        rs.noter_entrees(h, {"version": "score-7", "hausse": [], "baisse": [lesl]},
                         datetime.fromisoformat(f"{jour}T15:00:00+00:00"))
    revient = datetime(2027, 1, 10, 15, 0, tzinfo=timezone.utc)
    assert [(e["symbole"], e["entree"]) for e in rs.noter_entrees(h, score, revient)] == [("GME", revient.isoformat())]
    # Elle était sortie seulement 10 jours : pas une nouvelle entrée
    h2 = {"entrees": [dict(nouvelles[0], vue="2026-12-01")]}
    assert rs.noter_entrees(h2, {"version": "score-7", "hausse": [gme], "baisse": []},
                            datetime(2026, 12, 11, 15, tzinfo=timezone.utc)) == []


def test_publication_resultats_et_historique(tmp_path, monkeypatch):
    prepare(tmp_path, monkeypatch)
    publier(tmp_path, {}, set(), MAINTENANT)
    r = json.loads((tmp_path / "app" / "resultats.json").read_text(encoding="utf-8"))
    assert len(r["lignes"]) == 6 and r["horizons"] == {"7": "1 semaine", "30": "1 mois"}
    assert any("clôture de la veille" in m for m in r["methode"]) and any("jamais une clôture" in m for m in r["methode"])


def test_la_source_sert_seulement_a_calculer():
    s = SOURCES["sec_ftd"]
    assert s.ecartee is None and s.officielle is False and s.passages == ("soir",)
    assert "seulement pour mesurer" in s.nom


def test_en_tete_inattendu_refuse():
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr("x.txt", "DATE|SYMBOL|PRICE\n20260901|SPY|700\n")
    with pytest.raises(ValueError, match="en-tête inattendu"):
        ps.lire_fichier(tampon.getvalue(), {"SPY"})
