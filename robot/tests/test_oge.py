"""Rapports 278-T de l'OGE sur les VRAIES réponses de l'adresse de données publique et 19 vrais rapports du cabinet
(3 octobre 2026). Les 2 rapports du président (11 Mo et 27 Mo, images numérisées) ne sont pas gardés dans les tests :
un PDF de remplacement est servi à leur place (le robot ne lit jamais leur contenu)."""

import copy
import gzip
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from radar import score as sc
from radar.collecteurs import oge
from radar.collecteurs.sec import Symboles
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import Contexte, executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "oge"
SEC = Path(__file__).parent / "fixtures" / "sec" / "company_tickers_exchange_complet.json.gz"
LISTE_SEC = "https://www.sec.gov/files/company_tickers_exchange.json"
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
        elif url == LISTE_SEC:
            c = gzip.decompress(SEC.read_bytes())
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


_LUS: dict = {}
_LIRE_RAPPORT = oge.lire_rapport


def lire_une_fois(pdf):
    """Tests seulement : un même PDF n'est lu qu'une fois (environ 4 s pour les 19) ; copie fraîche à chaque fois."""
    cle = empreinte(pdf)
    if cle not in _LUS:
        _LUS[cle] = _LIRE_RAPPORT(pdf)
    return copy.deepcopy(_LUS[cle])


@pytest.fixture(autouse=True)
def lecture_une_seule_fois(monkeypatch):
    monkeypatch.setattr(oge, "lire_rapport", lire_une_fois)


def rapport(fichier):
    return lire_une_fois(lu(f"pdf_{fichier}.pdf.gz"))


def collecte(tmp_path, **k):
    return oge.collecter(Contexte(client=FauxInternet(**k), maintenant=MAINTENANT, donnees=tmp_path))


@pytest.fixture(scope="module")
def evs(tmp_path_factory):
    return collecte(tmp_path_factory.mktemp("oge"))


# ---------- L'index officiel ----------

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


# ---------- Les lignes des rapports du cabinet ----------

def test_les_243_lignes_des_19_rapports_du_cabinet():
    total = 0
    for f in sorted(F.glob("pdf_*.pdf.gz")):
        r = rapport(f.name[4:-7])
        assert r and r["lecture_complete"], f.name  # lignes numérotées de 1 à N, sans trou
        assert all(l["type"] in oge.TYPES_278T and len(l["date"]) == 10 and "Page" not in l["montant"] + l["avis"]
                   for l in r["lignes"]), f.name  # le pied de page « … - Page 2 » ne se colle jamais à une ligne
        total += len(r["lignes"])
    assert total == 243


def test_une_ligne_sur_deux_pages_de_texte():
    r = rapport("Markwayne-Mullin-06.24.2026-278T")
    assert (r["declarant"], r["poste_declare"], r["signe_le"]) == (
        "Mullin, Markwayne", "Secretary, Department of Homeland Security", "2026-06-24")
    assert len(r["lignes"]) == 68 and r["prolongation"]
    assert {k: r["lignes"][1][k] for k in ("description", "type", "date", "avis", "montant")} == {
        "description": "Alphabet Inc CL A (GOOGL)", "type": "Sale", "date": "2026-06-10", "avis": "Yes",
        "montant": "$250,001 - $500,000"}  # le montant tient sur 2 lignes dans le PDF
    assert r["lignes"][0]["description"] == "ALAMOGORDO N MEX MUN SCH DIST NO 001 GO BDS"  # description sur 2 lignes
    u = rapport("Eric-M-Ueland-08.06.2026-278T")["lignes"][14]  # dernière ligne d'une page
    assert (u["description"], u["montant"]) == ("Vanguard Small-Cap Value Index Fund ETF Class Shares (VBR)",
                                                "$1,001 - $15,000")


def test_notes_de_fin_rattachees_a_leur_ligne():
    w = rapport("Kevin-Warsh-06.25.2026-278T")["lignes"]
    assert w[41]["note"] == "Sold stock that resulted from exercising vested stock options."
    assert w[41]["description"] == "Aven"  # « See Endnote » enlevé
    assert [l["note"] for l in rapport("Scott-A-Kupor-06.22.2026-278T")["lignes"]] == ["Call Option Exercise"] * 2
    k1 = rapport("Scott-A-Kupor-06.22.2026-278T1")["lignes"]  # notes sur 2 pages : jamais « PART # ENDNOTE »
    assert [l["note"] for l in k1] == ["Call option exercise"] + ["Call Option Exercise"] * 8
    b = rapport("Douglas-J-Burgum-05.12.2026-278T")["lignes"][2]
    assert b["description"] == "Arthur Ventures Growth IV, LP - Nucleus Security, Inc."


def test_un_document_qui_n_est_pas_un_rapport_en_texte():
    assert _LIRE_RAPPORT(REMPLACEMENT) is None  # PDF illisible ou numérisé : aucune ligne inventée
    assert _LIRE_RAPPORT(b"%PDF-1.4 pas un vrai document") is None


# ---------- Les infos ----------

def test_rapports_et_compagnies_des_90_derniers_jours(evs):
    rapports = [e for e in evs if e.kind == "rapport_278t"]
    compagnies = [e for e in evs if e.kind != "rapport_278t"]
    assert len(rapports) == 21 and min(e.published_on for e in rapports) >= "2026-07-05"
    assert len(compagnies) == 74 and {e.kind for e in compagnies} == {"achat_cabinet", "vente_cabinet"}
    badges = {e.official_id: valider(e, MAINTENANT.date()).badge for e in evs}
    assert all(badges[e.official_id] == "officiel" for e in rapports)
    a_verifier = sorted(e.tickers[0] for e in compagnies if badges[e.official_id] == "a_verifier")
    assert a_verifier == ["COST", "EMR", "LLY", "LRCX", "OMDA", "PG", "PM", "TJX"]  # nom abrégé ou mal écrit
    for e in compagnies:
        if badges[e.official_id] == "a_verifier":
            assert [k for k, ok in valider(e, MAINTENANT.date()).checks.items() if not ok] == ["nom_coherent_avec_symbole"]
    assert not any("AAPL" in e.tickers or "APPL" in e.tickers for e in compagnies)  # « Apple Inc. (APPL) » : pas relié


def test_info_d_une_compagnie(evs):
    g = next(e for e in evs if e.tickers == ["GOOGL"])
    assert g.title == "Markwayne Mullin (Secretary, Department of Homeland Security, niveau I) vend GOOGL"
    assert (g.amount_min, g.amount_max, g.direction, g.occurred_on, g.published_on) == (
        250_001.0, 500_000.0, -1, "2026-06-10", "2026-07-25")
    assert g.notes == ["Le déclarant a reçu l'avis de cette transaction plus de 30 jours après qu'elle a eu lieu."]
    assert g.entities == ["Markwayne Mullin", "Alphabet Inc."] and g.official_url.endswith("Markwayne-Mullin-06.24.2026-278T.pdf")
    okta = [e for e in evs if e.tickers == ["OKTA"]]
    assert any(e.title.endswith("vend OKTA (4 transactions)") for e in okta)  # 4 lignes d'un même rapport : 1 info
    assert any("Note du déclarant (ligne 1) : « Call option exercise »" in e.notes for e in okta)


def test_rapport_du_cabinet_avec_ses_lignes_et_du_president_en_liste(evs):
    t = [e for e in evs if e.kind == "rapport_278t" and e.title.startswith("Donald J Trump")]
    assert len(t) == 2 and all(e.title.endswith("image numérisée") and "transactions" not in e.data for e in t)
    m = next(e for e in evs if e.kind == "rapport_278t" and e.official_url.endswith("Markwayne-Mullin-06.24.2026-278T.pdf"))
    assert m.title.endswith("rapport de transactions (278-T), 68 transactions") and len(m.data["transactions"]) == 68
    assert m.notes[0].startswith("68 lignes lues : 48 reliées à une action cotée à la SEC")
    assert "Rapport déposé avec une prolongation de 45 jours (selon le document)." in m.notes
    w = next(e for e in evs if e.kind == "rapport_278t" and e.official_url.endswith("Kevin-Warsh-08.06.2026-278T.pdf"))
    assert w.notes[0].startswith("5 lignes lues : aucune action cotée à la SEC")


def test_le_score_ne_donne_aucun_point(evs):
    g = next(e for e in evs if e.tickers == ["GOOGL"])
    d = json.loads(json.dumps(g.to_dict()))
    d["badge"] = "officiel"
    (a,) = sc.evaluer(d)
    assert a.regle is None and a.pourquoi == sc.SANS_POINTS["cabinet"]


# ---------- Relire une fois, puis jamais ----------

def test_deja_lus_pas_relus(tmp_path):
    executer(tmp_path, collecteurs={"oge_278t": oge.collecter}, client=FauxInternet(), maintenant=MAINTENANT)
    internet = FauxInternet()
    executer(tmp_path, collecteurs={"oge_278t": oge.collecter}, client=internet, maintenant=MAINTENANT)
    assert internet.appels == [oge.adresse(f) for f in oge.FILTRES]  # aucun PDF retéléchargé


def test_rapports_lus_par_l_ancien_lecteur_relus_une_fois(tmp_path, monkeypatch):
    lecteurs = {"oge_278t": oge.collecter}
    monkeypatch.setattr(oge, "VERSION", "oge-1")
    executer(tmp_path, collecteurs=lecteurs, client=FauxInternet(), maintenant=MAINTENANT)
    (tmp_path / "oge" / "lus.json").unlink()  # comme avant : l'ancien lecteur ne gardait pas cette liste
    monkeypatch.setattr(oge, "VERSION", "oge-2")
    internet = FauxInternet()
    executer(tmp_path, collecteurs=lecteurs, client=internet, maintenant=MAINTENANT)
    assert sum(1 for u in internet.appels if u.endswith(".pdf")) == 21  # les 21 rapports relus une fois
    internet = FauxInternet()
    executer(tmp_path, collecteurs=lecteurs, client=internet, maintenant=MAINTENANT)
    assert not any(u.endswith(".pdf") for u in internet.appels)  # puis plus jamais


def test_pdf_illisible_reste_a_verifier(tmp_path):
    casse = next(iter(PDFS["gardes"]))
    e = next(e for e in collecte(tmp_path, pdf_casse=casse) if e.official_url == casse)
    v = valider(e, MAINTENANT.date())
    assert v.badge == "a_verifier" and v.checks["document_pdf"] is False and e.title.endswith("document illisible")


def test_un_pdf_qui_ne_repond_pas_n_empeche_pas_les_autres(tmp_path):
    absent = next(iter(PDFS["gardes"]))
    attendus = 95 - len([e for e in collecte(tmp_path / "tous") if e.official_url == absent])

    class UnPdfEnPanne(FauxInternet):
        def get(self, url):
            if url == absent:
                raise ErreurSource(f"{url} : HTTP 404")
            return super().get(url)

    lecteurs = {"oge_278t": oge.collecter}
    executer(tmp_path, collecteurs=lecteurs, client=UnPdfEnPanne(), maintenant=MAINTENANT)
    etat = json.loads((tmp_path / "etat_sources.json").read_text(encoding="utf-8"))["oge_278t"]
    assert etat["derniere_erreur"] is None and etat["compte"]["recus"] == attendus
    internet = FauxInternet()
    executer(tmp_path, collecteurs=lecteurs, client=internet, maintenant=MAINTENANT)
    assert [u for u in internet.appels if u.endswith(".pdf")] == [absent]  # au passage suivant : seulement celui-là


def test_sans_la_liste_de_la_sec_la_source_attend(tmp_path):
    class SansSec(FauxInternet):
        def get(self, url):
            if url == LISTE_SEC:
                raise ErreurSource("HTTP 503")
            return super().get(url)

    with pytest.raises(RuntimeError, match="liste officielle des symboles"):
        oge.collecter(Contexte(client=SansSec(), maintenant=MAINTENANT, donnees=tmp_path))
    assert not (tmp_path / "oge" / "lus.json").exists()  # rien n'est marqué lu : nouvel essai au prochain passage


def test_reponse_inattendue_la_source_tombe_en_panne(tmp_path):
    class Vide:
        def get(self, url):
            return type("T", (), {"contenu": b'{"error": "maintenance"}', "sha256": "0" * 64})()

    with pytest.raises(ErreurSource):
        oge.collecter(Contexte(client=Vide(), maintenant=MAINTENANT, donnees=tmp_path))
