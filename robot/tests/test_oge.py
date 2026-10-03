"""Rapports 278-T de l'OGE sur les VRAIES réponses de l'adresse de données publique et les vrais PDF (3 octobre 2026).

Les 2 rapports du président (11 Mo et 27 Mo, images numérisées) ne sont pas gardés dans les tests : un PDF de
remplacement est servi à leur place (le robot ne lit pas le contenu, seulement « %PDF- » et l'empreinte).
"""

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from radar.collecteurs import oge
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import Contexte, executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "oge"
MAINTENANT = datetime(2026, 10, 3, 11, 7, tzinfo=timezone.utc)
PDFS = json.loads((F / "pdfs.json").read_text(encoding="utf-8"))
REMPLACEMENT = b"%PDF-1.6 (remplacement pour les tests : le vrai rapport numerise fait 11 Mo ou 27 Mo)"
# Les 2 adresses exactes utilisées au labo (le 3 octobre 2026) : le robot doit envoyer les mêmes
ADRESSE_LABO = ("https://extapps2.oge.gov/201/Presiden.nsf/API.xsp/v3/rest?draw=1&order%5B0%5D%5Bcolumn%5D=0"
                "&order%5B0%5D%5Bdir%5D=desc" + "".join(
                    f"&columns%5B{i}%5D%5Bdata%5D={c}&columns%5B{i}%5D%5Bsearchable%5D=true"
                    f"&columns%5B{i}%5D%5Borderable%5D=true"
                    for i, c in enumerate(("docDate", "title", "type", "name", "agency", "level")))
                + "&search%5Bvalue%5D=&columns%5B2%5D%5Bsearch%5D%5Bvalue%5D=Transaction")


def lu(nom):
    return gzip.decompress((F / nom).read_bytes())


class FauxInternet:
    def __init__(self, pdf_casse=None):
        self.appels, self.pdf_casse = [], pdf_casse

    def get(self, url):
        self.appels.append(url)
        if url == oge.adresse(oge.FILTRES[0]):
            c = lu("oge_niveaux.json.gz")
        elif url == oge.adresse(oge.FILTRES[1]):
            c = lu("oge_president.json.gz")
        elif url == self.pdf_casse:
            c = b"<html>Unable to Process Request</html>"
        elif url in PDFS["gardes"]:
            c = lu(PDFS["gardes"][url])
        elif url.rsplit("/", 1)[1] in PDFS["trop_gros"]:
            c = REMPLACEMENT
        else:
            raise AssertionError(f"page inattendue : {url}")
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()


def lignes(nom):
    return json.loads(lu(nom))["data"]


def test_meme_adresse_que_la_page_officielle():
    assert oge.adresse(oge.FILTRES[0]) == ADRESSE_LABO + "&columns%5B5%5D%5Bsearch%5D%5Bvalue%5D=Level&start=0&length=100"
    assert oge.adresse(oge.FILTRES[1]) == ADRESSE_LABO + "&columns%5B1%5D%5Bsearch%5D%5Bvalue%5D=President&start=0&length=100"


def test_jamais_un_rapport_qui_exige_le_formulaire_201():
    niveaux, president = lignes("oge_niveaux.json.gz"), lignes("oge_president.json.gz")
    gardes_n = [x for x in map(oge.lire_ligne, niveaux) if x]
    gardes_p = [x for x in map(oge.lire_ligne, president) if x]
    assert len(gardes_n) == 100 and {x["niveau"] for x in gardes_n} == {"Level I", "Level II"}
    assert len(gardes_p) == 19 and {x["titre"] for x in gardes_p} == {"President"}
    exige_201 = [r for r in president if "Request this Document" in r["type"]]
    assert len(exige_201) == 81 and all(oge.lire_ligne(r) is None for r in exige_201)  # conseillers, etc. : écartés


def test_noms_et_postes_en_clair():
    assert oge.nom_affiche("Kupor, Scott A") == "Scott A Kupor"
    warsh = next(x for x in map(oge.lire_ligne, lignes("oge_niveaux.json.gz")) if x and x["nom"] == "Warsh, Kevin")
    assert oge.poste_fr(warsh) == "Governor & Chairman, Federal Reserve System Board of Governors, niveau I"


def test_rapports_des_90_derniers_jours(tmp_path):
    ctx = Contexte(client=FauxInternet(), maintenant=MAINTENANT, donnees=tmp_path)
    evs = oge.collecter(ctx)
    assert len(evs) == 21 and len({e.official_id for e in evs}) == 21  # 19 niveaux I et II + 2 du président
    assert min(e.published_on for e in evs) >= "2026-07-05"
    titres = {e.title for e in evs}
    assert "Donald J Trump (président des États-Unis) : nouveau rapport de transactions (278-T)" in titres
    assert ("Kevin Warsh (Governor & Chairman, Federal Reserve System Board of Governors, niveau I) : nouveau rapport "
            "de transactions (278-T)") in titres
    for e in evs:
        v = valider(e, MAINTENANT.date())
        assert v.badge == "officiel", (e.title, [k for k, ok in v.checks.items() if not ok])
        assert e.tickers == [] and "ne lit pas le contenu" in e.notes[0]


def test_deja_lus_pas_relus(tmp_path):
    executer(tmp_path, collecteurs={"oge_278t": oge.collecter}, client=FauxInternet(), maintenant=MAINTENANT)
    internet = FauxInternet()
    executer(tmp_path, collecteurs={"oge_278t": oge.collecter}, client=internet, maintenant=MAINTENANT)
    assert internet.appels == [oge.adresse(f) for f in oge.FILTRES]  # aucun PDF retéléchargé


def test_pdf_illisible_reste_a_verifier(tmp_path):
    casse = next(iter(PDFS["gardes"]))
    evs = oge.collecter(Contexte(client=FauxInternet(pdf_casse=casse), maintenant=MAINTENANT, donnees=tmp_path))
    e = next(e for e in evs if e.official_url == casse)
    v = valider(e, MAINTENANT.date())
    assert v.badge == "a_verifier" and v.checks["document_pdf"] is False


def test_un_pdf_qui_ne_repond_pas_n_empeche_pas_les_autres(tmp_path):
    absent = next(iter(PDFS["gardes"]))

    class UnPdfEnPanne(FauxInternet):
        def get(self, url):
            if url == absent:
                raise ErreurSource(f"{url} : HTTP 404")
            return super().get(url)

    lecteurs = {"oge_278t": oge.collecter}
    executer(tmp_path, collecteurs=lecteurs, client=UnPdfEnPanne(), maintenant=MAINTENANT)
    etat = json.loads((tmp_path / "etat_sources.json").read_text(encoding="utf-8"))["oge_278t"]
    assert etat["derniere_erreur"] is None and etat["compte"]["recus"] == 20  # 21 rapports, 1 PDF en panne
    internet = FauxInternet()
    executer(tmp_path, collecteurs=lecteurs, client=internet, maintenant=MAINTENANT)
    assert internet.appels[2:] == [absent]  # au passage suivant : seulement le PDF manquant


def test_reponse_inattendue_la_source_tombe_en_panne(tmp_path):
    class Vide:
        def get(self, url):
            return type("T", (), {"contenu": b'{"error": "maintenance"}', "sha256": "0" * 64})()

    with pytest.raises(ErreurSource):
        oge.collecter(Contexte(client=Vide(), maintenant=MAINTENANT, donnees=tmp_path))
