"""Lobbying (LDA.gov) sur de VRAIES réponses de l'API lues le 3 octobre 2026 (tests/fixtures/lobbying)."""

import gzip
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from radar.collecteurs import lobbying as lb
from radar.http import ClientPoli
from radar.models import empreinte
from radar.run import Contexte, executer

F = Path(__file__).parent / "fixtures" / "lobbying"
MAINTENANT = datetime(2026, 10, 3, 11, 7, tzinfo=timezone.utc)
RECHERCHE = "https://lda.gov/api/v1/filings/?filing_year=2026&filing_period=second_quarter&page_size=25&client_name="


def lu(nom):
    return gzip.decompress((F / nom).read_bytes())


PAGES = {RECHERCHE + "LOCKHEED": "lda_lockheed.json.gz", RECHERCHE + "GAMESTOP": "lda_gamestop.json.gz",
         RECHERCHE + "EAGLE": "lda_eagle.json.gz", RECHERCHE + "SOUTHWEST": "lda_southwest_1.json.gz",
         json.loads((F / "pages.json").read_text())["southwest_page_2"]: "lda_southwest_2.json.gz"}


class FauxInternet:
    def __init__(self):
        self.appels = []

    def get(self, url):
        self.appels.append(url)
        if url not in PAGES:
            raise AssertionError(f"page inattendue : {url}")
        c = lu(PAGES[url])
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def avec_listes(tmp_path, compagnies):
    (tmp_path / "app").mkdir(parents=True, exist_ok=True)
    (tmp_path / "app" / "aujourdhui.json").write_text(json.dumps(
        {"hausse": [{"symbole": s, "nom": n} for s, n in compagnies], "baisse": []}), encoding="utf-8")


def contexte(tmp_path, quand=MAINTENANT):
    return Contexte(client=FauxInternet(), maintenant=quand, donnees=tmp_path)


@pytest.mark.parametrize("jour, attendu", [
    (date(2026, 10, 3), (2026, 2)), (date(2026, 10, 20), (2026, 2)), (date(2026, 10, 21), (2026, 3)),
    (date(2027, 1, 10), (2026, 3)), (date(2027, 1, 21), (2026, 4)), (date(2026, 4, 21), (2026, 1)),
])
def test_dernier_trimestre_dont_la_date_limite_est_passee(jour, attendu):
    assert lb.dernier_trimestre_complet(jour) == attendu  # date limite : le 20 du mois qui suit le trimestre


def test_meme_nom_seulement_avec_les_memes_mots():
    assert lb.meme_nom("FULLER H B CO", "H.B. FULLER COMPANY")  # la SEC inverse parfois les mots
    assert lb.meme_nom("DICK'S SPORTING GOODS, INC.", "DICKS SPORTING GOODS INC")
    assert not lb.meme_nom("LOCKHEED MARTIN CORP", "LOCKHEED MARTIN CORPORORATION")  # faute de frappe : pas compté
    assert not lb.meme_nom("LOCKHEED MARTIN CORP", "LOCKHEED MARTIN AERONAUTIC SECTOR")  # filiale : pas comptée
    assert not lb.meme_nom("EAGLE BANCORP INC", "EAGLE BANCORP MONTANA, INC.")
    assert lb.mot_de_recherche(lb.mots_nom("CAPITAL SOUTHWEST CORP")) == "SOUTHWEST"


def test_tous_les_sujets_officiels_ont_un_nom_en_francais():
    officiels = {s["value"] for s in json.loads(lu("lda_sujets.json.gz"))}
    assert len(officiels) == 79 and officiels == set(lb.SUJETS_FR)


def test_lockheed_ses_propres_depenses_incluent_les_firmes():
    """Guide du LDA : les dépenses d'une compagnie qui a ses propres lobbyistes incluent ce qu'elle paie aux firmes."""
    resultats = json.loads(lu("lda_lockheed.json.gz"))["results"]
    trouves = [lb.resume(f) for f in resultats if lb.meme_nom(f["client"]["name"], "LOCKHEED MARTIN CORP")]
    assert len(resultats) == 17 and len(trouves) == 15  # filiale et faute de frappe écartées
    b = lb.bilan("LOCKHEED MARTIN CORP", trouves, 2)
    assert (b["base"], b["total"], b["firmes"], b["revenus_firmes"]) == ("compagnie", 4_180_000.0, 12, 500_000.0)
    assert len(b["rapports"]) == 14 and b["rapports"][0]["registrant"] == "LOCKHEED MARTIN CORPORATION"  # pas l'inscription
    assert [s["code"] for s in b["sujets"][:4]] == ["DEF", "BUD", "TAX", "INT"]
    assert b["sujets"][0]["nom"] == "Défense" and b["moins_de_5000"] == 0
    assert any(r["sans_activite"] for r in b["rapports"])  # Venable : rapport « sans activité » gardé, pas compté


def test_sans_ses_propres_lobbyistes_le_total_est_celui_des_firmes():
    resultats = json.loads(lu("lda_lockheed.json.gz"))["results"]
    firmes = [lb.resume(f) for f in resultats if lb.meme_nom(f["client"]["name"], "LOCKHEED MARTIN CORP")
              and f["registrant"]["name"] != "LOCKHEED MARTIN CORPORATION"]
    b = lb.bilan("LOCKHEED MARTIN CORP", firmes, 2)
    assert (b["base"], b["total"], b["firmes"]) == ("firmes", 500_000.0, 12)


def test_une_modification_remplace_le_rapport_precedent():
    f = json.loads(lu("lda_lockheed.json.gz"))["results"][-1]  # le rapport de Lockheed Martin elle-même
    original = lb.resume(f)
    modifie = {**original, "uuid": "modif", "type": "2A", "montant": 4_200_000.0, "poste": "2026-08-01"}
    assert lb.bilan("LOCKHEED MARTIN CORP", [original, modifie], 2)["total"] == 4_200_000.0


def test_collecte_des_compagnies_des_listes(tmp_path):
    avec_listes(tmp_path, [("LMT", "LOCKHEED MARTIN CORP"), ("GME", "GameStop Corp."), ("CSWC", "CAPITAL SOUTHWEST CORP"),
                           ("EGBN", "EAGLE BANCORP INC")])
    ctx = contexte(tmp_path)
    assert lb.collecter(ctx) == []  # pas d'infos dans le fil
    assert len(ctx.client.appels) == 5  # Southwest : 2 pages
    cache = json.loads(lb.chemin_cache(tmp_path, 2026, 2).read_text(encoding="utf-8"))
    assert cache["LMT"]["total"] == 4_180_000.0 and cache["LMT"]["complet"]
    for s in ("GME", "CSWC", "EGBN"):  # aucune de ces compagnies n'a de rapport à son nom exact
        assert cache[s]["rapports"] == [] and cache[s]["total"] is None and cache[s]["complet"], s
    assert cache["CSWC"]["pages"] == 2
    # Relu après 7 jours seulement
    ctx2 = contexte(tmp_path, MAINTENANT + timedelta(days=6))
    lb.collecter(ctx2)
    assert ctx2.client.appels == []
    ctx3 = contexte(tmp_path, MAINTENANT + timedelta(days=8))
    lb.collecter(ctx3)
    assert len(ctx3.client.appels) == 5


def test_trop_de_pages_pas_de_zero_faux(tmp_path, monkeypatch):
    monkeypatch.setattr(lb, "MAX_PAGES", 1)
    avec_listes(tmp_path, [("CSWC", "CAPITAL SOUTHWEST CORP")])
    lb.collecter(contexte(tmp_path))
    c = json.loads(lb.chemin_cache(tmp_path, 2026, 2).read_text(encoding="utf-8"))["CSWC"]
    assert c["complet"] is False and c["pages"] == 1  # l'app dira « pas vérifié », jamais « aucun lobbying »


def test_fichier_de_l_app(tmp_path):
    avec_listes(tmp_path, [("LMT", "LOCKHEED MARTIN CORP"), ("GME", "GameStop Corp.")])
    lb.collecter(contexte(tmp_path))
    app = lb.pour_app(tmp_path, ["LMT", "XENE"], MAINTENANT)  # XENE : pas encore lue
    assert app["trimestre"] == {"annee": 2026, "numero": 2, "libelle": "2e trimestre 2026"}
    assert app["avertissement"] == ("Senate Office of Public Records cannot vouch for the data or analyses derived "
                                    "from these data after the data have been retrieved from LDA.gov.")
    assert list(app["par_symbole"]) == ["LMT"] and app["par_symbole"]["LMT"]["lu"] == MAINTENANT.isoformat()


def test_publication_ecrit_le_lobbying_des_listes(tmp_path):
    (tmp_path / "evenements").mkdir()
    (tmp_path / "evenements" / "2026-10.jsonl").write_bytes(gzip.decompress(
        (Path(__file__).parent / "fixtures" / "score" / "evenements_20261003.jsonl.gz").read_bytes()))
    executer(tmp_path, collecteurs={}, maintenant=datetime(2026, 10, 3, 3, 17, tzinfo=timezone.utc))
    app = json.loads((tmp_path / "app" / "lobbying.json").read_text(encoding="utf-8"))
    assert app["par_symbole"] == {} and app["trimestre"]["libelle"] == "2e trimestre 2026"  # rien lu : liste vide


def test_le_client_attend_4_secondes_et_demie_entre_deux_requetes_au_lda():
    attentes, temps = [], [100.0]

    class Session:
        def get(self, url, headers, timeout):
            return type("R", (), {"status_code": 200, "content": b"{}", "headers": {}})()

    c = ClientPoli("x@y.z", session=Session(), dormir=attentes.append, horloge=lambda: temps[0])
    c.get("https://lda.gov/api/v1/filings/?a=1")
    c.get("https://lda.gov/api/v1/filings/?a=2")
    assert attentes == [pytest.approx(4.5)]
