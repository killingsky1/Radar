"""Tests des transactions des élus sur de VRAIS rapports (Sénat et Chambre, septembre-octobre 2026)."""

import gzip
import io
import json
import re
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from radar.collecteurs import elus, sec
from radar.collecteurs.elus import lire_index_chambre, lire_page_senat, lire_pdf_chambre, nom_coherent, rapport_chambre
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import executer
from radar.validate import valider

FX = Path(__file__).parent / "fixtures"
JOUR = date(2026, 10, 2)
WHITEHOUSE = "6bf3b6f7-9e1b-499a-bd5a-990292ce2e72"
JUSTICE = "0a93a20c-2a0f-4979-80ca-cc2f61297527"
BOOKER = "e5144197-e49c-4f74-bec4-19f1f3124668"


@pytest.fixture(scope="module")
def syms():
    return sec.Symboles(json.loads(gzip.decompress((FX / "sec" / "company_tickers_exchange_complet.json.gz").read_bytes())))


def info_chambre(doc):
    m = (FX / "chambre" / f"{doc}.membre.xml").read_text(encoding="utf-8")
    return {k: (re.search(rf"<{k}>(.*?)</{k}>", m, re.S) or [None, ""])[1].strip()
            for k in ("Prefix", "Last", "First", "Suffix", "FilingType", "StateDst", "Year", "FilingDate", "DocID")}


def pdf(doc):
    return (FX / "chambre" / f"{doc}.pdf").read_bytes()


# ---------- Chambre : PDF lu colonne par colonne ----------


def test_pdf_franklin_proprietaires_et_montants():
    entete, tx, complet = lire_pdf_chambre(pdf("20035450"))
    assert entete == {"numero": "20035450", "nom": "Hon. Scott Scott Franklin", "circonscription": "FL18"}
    assert complet and len(tx) == 12
    assert (tx[0]["proprietaire"], tx[0]["actif"], tx[0]["type"], tx[0]["date"], tx[0]["avis"], tx[0]["montant"]) == (
        "", "Accenture plc Class A Ordinary Shares (ACN) [ST]", "P", "08/26/2026", "09/02/2026", "$1,001 - $15,000")
    assert tx[1]["proprietaire"] == "SP" and tx[2]["type"] == "S (partial)"
    assert tx[0]["etiquettes"] == {"FS": "New", "SO": "Fidelity Roth IRA"}


def test_pdf_hern_transaction_coupee_par_un_changement_de_page():
    _, tx, complet = lire_pdf_chambre(pdf("20035491"))
    assert complet and len(tx) == 99
    devon = [t for t in tx if "(DVN)" in t["actif"] and t["date"] == "09/02/2026"]
    # « …$100,001 - » au bas de la page 3, « Stock (DVN) [ST] $250,000 » en haut de la page 4
    assert [t["montant"] for t in devon] == ["$100,001 - $250,000"]
    assert devon[0]["actif"] == "Devon Energy Corporation Common Stock (DVN) [ST]"


def test_pdf_numerise_est_laisse_de_cote():
    assert rapport_chambre(info_chambre("9116342"), pdf("9116342"), "https://x") is None


def test_index_officiel_de_la_chambre():
    rapports = lire_index_chambre((FX / "chambre" / "2026FD.zip").read_bytes(), 2026)
    assert len(rapports) == 407
    [franklin] = [r for r in rapports if r["DocID"] == "20035450"]
    assert (franklin["Last"], franklin["StateDst"], franklin["FilingDate"]) == ("Franklin", "FL18", "9/17/2026")


def test_infos_de_la_chambre(syms):
    r = rapport_chambre(info_chambre("20035450"), pdf("20035450"),
                        "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/2026/20035450.pdf")
    evs = [valider(e, JOUR) for e in elus.evenements(r, syms)]
    assert all(e.badge == "officiel" for e in evs), [e.checks for e in evs if e.badge != "officiel"]
    par_symbole = {(e.tickers[0], e.direction): e for e in evs}
    acn = par_symbole[("ACN", 1)]
    assert acn.title == "Scott Scott Franklin (Chambre, FL18) achète ACN (2 transactions) : 2 002 $ à 30 000 $ — conjoint·e, l'élu·e"
    assert (acn.amount_min, acn.amount_max, acn.occurred_on, acn.published_on) == (2002.0, 30000.0, "2026-08-26", "2026-09-17")
    assert ("LSYIX", 1) not in par_symbole  # fonds d'obligations : pas une action
    assert par_symbole[("GOOG", -1)].kind == "vente_elu"


# ---------- Sénat : tableaux web ----------


def page_senat(numero):
    return (FX / "senat" / f"{numero}.html").read_text(encoding="utf-8")


def test_page_senat_whitehouse(syms):
    r = lire_page_senat(page_senat(WHITEHOUSE), WHITEHOUSE, f"https://efdsearch.senate.gov/search/view/ptr/{WHITEHOUSE}/",
                        "a" * 64, "2026-10-01")
    assert r.nom == "Sheldon Whitehouse" and r.depose == "2026-10-01" and r.complet and len(r.transactions) == 5
    evs = {e.tickers[0]: valider(e, JOUR) for e in elus.evenements(r, syms)}
    assert set(evs) == {"JPM", "ADI", "V"}
    jpm = evs["JPM"]
    assert jpm.badge == "officiel", jpm.checks
    assert jpm.title == "Sheldon Whitehouse (Sénat) vend JPM (2 transactions) : 30 002 $ à 100 000 $ — conjoint·e, l'élu·e"
    assert jpm.direction == -1 and jpm.occurred_on == "2026-09-04"


def test_page_senat_nom_avec_mr():
    r = lire_page_senat(page_senat(JUSTICE), JUSTICE, "https://efdsearch.senate.gov/x", "a" * 64, "2026-09-28")
    assert r.nom == "James Conley Justice II" and r.verifs == {"date_de_depot": True, "nom_lu": True}


@pytest.mark.parametrize("actif,nom_sec,attendu", [
    ("JP Morgan Chase & Co. Common Stock", "JPMORGAN CHASE & CO", True),
    ("Danaher Corporation Common Stock (DHR) [ST]", "DANAHER CORP /DE/", True),
    ("McDonald's Corporation Common Stock (MCD) [ST]", "MCDONALDS CORP", True),
    ("General Motors Company", "GENERAL MILLS INC", False),  # erreur de symbole
    ("Paramount Global - Class B Common Stock", "Banzai International, Inc.", False),  # symbole réutilisé
])
def test_nom_coherent_avec_le_symbole(actif, nom_sec, attendu):
    assert nom_coherent(actif, nom_sec) is attendu


# ---------- Les lecteurs au complet, avec un faux Internet qui sert les vrais documents ----------


class FauxInternet:
    def __init__(self, pages):
        self.pages, self.appels, self.envois = pages, [], []

    def _rep(self, url):
        if url not in self.pages:
            raise ErreurSource(f"{url} : HTTP 404")
        c = self.pages[url]
        return type("T", (), {"contenu": c, "sha256": empreinte(c)})()

    def get(self, url):
        self.appels.append(url)
        return self._rep(url)

    def post(self, url, donnees, entetes=None):
        self.envois.append((url, donnees))
        return self._rep(url)

    def cookie(self, nom):
        return "jeton-de-test" if nom == "csrftoken" else None

    def ajouter_sec(self):
        self.pages["https://www.sec.gov/files/company_tickers_exchange.json"] = gzip.decompress(
            (FX / "sec" / "company_tickers_exchange_complet.json.gz").read_bytes())
        return self


def internet_senat():
    S = "https://efdsearch.senate.gov"
    recherche = json.loads((FX / "senat" / "recherche.json").read_text(encoding="utf-8"))
    gardes = [l for l in recherche["data"] if any(n in l[3] for n in (WHITEHOUSE, JUSTICE, BOOKER))]
    gardes += [l for l in recherche["data"] if "Amendment" in l[3]][:1] + [l for l in recherche["data"] if "/paper/" in l[3]][:1]
    accueil = b'<form method="post"><input type="hidden" name="csrfmiddlewaretoken" value="abc123">' \
              b'<input type="checkbox" name="prohibition_agreement" value="1"></form>'
    pages = {f"{S}/search/home/": accueil,
             f"{S}/search/report/data/": json.dumps(dict(recherche, data=gardes)).encode()}
    for n in (WHITEHOUSE, JUSTICE, BOOKER):
        pages[f"{S}/search/view/ptr/{n}/"] = page_senat(n).encode()
    return FauxInternet(pages).ajouter_sec()


def test_lecteur_senat_au_complet(tmp_path):
    internet = internet_senat()
    maintenant = datetime(2026, 10, 2, 22, 17, tzinfo=timezone.utc)
    rapport = executer(tmp_path, client=internet, maintenant=maintenant, collecteurs={"senat_ptr": elus.collecter_senat})
    assert rapport["senat_ptr"]["ok"], rapport
    # Les conditions du site sont acceptées avant la recherche, avec le jeton du formulaire
    assert internet.envois[0] == ("https://efdsearch.senate.gov/search/home/",
                                  {"prohibition_agreement": "1", "csrfmiddlewaretoken": "abc123"})
    pages_lues = [u for u in internet.appels if "/view/" in u]
    assert len(pages_lues) == 3  # ni l'amendement ni le rapport papier
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    assert {e["data"]["elu"] for e in fil} == {"Sheldon Whitehouse", "Cory A Booker"}  # Justice : pas d'action cotée
    assert all(e["category"] == "politiciens" for e in fil)

    avant = len(internet.appels)
    executer(tmp_path, client=internet, maintenant=maintenant.replace(hour=23), collecteurs={"senat_ptr": elus.collecter_senat})
    assert not [u for u in internet.appels[avant:] if "/view/" in u]  # rapports déjà lus : pas relus


def internet_chambre(docs):
    C = "https://disclosures-clerk.house.gov/public_disc"
    with zipfile.ZipFile(FX / "chambre" / "2026FD.zip") as z:
        x = z.read("2026FD.xml").decode("utf-8")
    membres = [m for m in re.findall(r"<Member>.*?</Member>", x, re.S) if any(f"<DocID>{d}</DocID>" in m for d in docs)]
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w") as z:
        z.writestr("2026FD.xml", "<FinancialDisclosure>" + "".join(membres) + "</FinancialDisclosure>")
    pages = {f"{C}/financial-pdfs/2026FD.zip": tampon.getvalue()}
    for d in docs:
        pages[f"{C}/ptr-pdfs/2026/{d}.pdf"] = pdf(d)
    return FauxInternet(pages).ajouter_sec()


def test_lecteur_chambre_au_complet(tmp_path):
    internet = internet_chambre(["20035450", "20035491", "9116342"])
    maintenant = datetime(2026, 10, 2, 22, 17, tzinfo=timezone.utc)
    rapport = executer(tmp_path, client=internet, maintenant=maintenant, collecteurs={"chambre_ptr": elus.collecter_chambre})
    assert rapport["chambre_ptr"]["ok"], rapport
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    assert {e["data"]["elu"] for e in fil} == {"Scott Scott Franklin", "Kevin Hern"}  # nom officiel, tel quel dans l index et le PDF
    lus = json.loads((tmp_path / "elus" / "rapports_lus.json").read_text())
    assert set(lus["chambre"]) == {"20035450", "20035491", "9116342"}  # le rapport numérisé aussi : pas relu
    avant = len(internet.appels)
    executer(tmp_path, client=internet, maintenant=maintenant.replace(hour=23), collecteurs={"chambre_ptr": elus.collecter_chambre})
    assert not [u for u in internet.appels[avant:] if u.endswith(".pdf")]


def test_pdf_illisibles_ne_sont_pas_notes_comme_lus(tmp_path):
    internet = internet_chambre(["20035450", "20035491", "9116342"])
    for u in internet.pages:
        if u.endswith(".pdf"):
            internet.pages[u] = b"%PDF-1.4 pas un vrai pdf"
    internet.pages = {k: v for k, v in internet.pages.items()}
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 22, tzinfo=timezone.utc),
                       collecteurs={"chambre_ptr": elus.collecter_chambre})
    # 3 PDF illisibles sur 3 : pas assez pour la panne (seuil : plus de 3), mais aucun n'est noté comme lu
    assert rapport["chambre_ptr"]["ok"]
    assert not (tmp_path / "elus" / "rapports_lus.json").exists() or \
        not json.loads((tmp_path / "elus" / "rapports_lus.json").read_text()).get("chambre")


def test_sans_liste_sec_la_source_attend(tmp_path):
    internet = internet_chambre(["20035450"])
    del internet.pages["https://www.sec.gov/files/company_tickers_exchange.json"]
    rapport = executer(tmp_path, client=internet, maintenant=datetime(2026, 10, 2, 22, tzinfo=timezone.utc),
                       collecteurs={"chambre_ptr": elus.collecter_chambre})
    assert rapport["chambre_ptr"]["ok"] is False and "symboles" in rapport["chambre_ptr"]["erreur"]
