"""Tests du Registre fédéral sur de VRAIS documents (22 septembre au 2 octobre 2026, tests/fixtures/registre)."""

import gzip
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from radar.collecteurs import registre, sec
from radar.collecteurs.registre import choisir, lire_vente_armes, texte_officiel
from radar.http import ErreurSource
from radar.models import empreinte
from radar.run import executer
from radar.validate import valider

F = Path(__file__).parent / "fixtures" / "registre"
FS = Path(__file__).parent / "fixtures" / "sec"
JOUR = date(2026, 10, 2)


def docs(nom):
    return json.loads((F / nom).read_text(encoding="utf-8"))["results"]


def texte(numero):
    return texte_officiel((F / f"{numero}.txt").read_bytes())


@pytest.fixture(scope="module")
def noms_sec():
    syms = sec.Symboles(json.loads(gzip.decompress((FS / "company_tickers_exchange_complet.json.gz").read_bytes())))
    return registre.symboles_par_nom(syms)


# ---------- Ce qu'on garde et ce qu'on laisse de côté ----------


def test_documents_presidentiels():
    par_titre = {d["title"]: choisir(d) for d in docs("presidentiels.json")}
    assert par_titre["Inaugurating the Era of Super Intelligence"] == ("presidentiel", "Décret présidentiel", "gouvernement")
    assert par_titre["Presidential Determination on Refugee Admissions for Fiscal Year 2027"][1] == "Détermination présidentielle"
    assert par_titre["Gold Star Mother's and Family's Day, 2026"] is None  # journée commémorative
    assert par_titre["Continuation of the National Emergency With Respect to the Situation in and in Relation to Syria"] is None


def test_agences_sans_le_bruit():
    choix = {d["title"]: choisir(d) for d in docs("agences.json")}
    assert choix["Notice of OFAC Sanctions Action"] == ("sanctions", "Sanctions (Trésor, OFAC)", "gouvernement")
    assert choix["Cuba Sanctions Regulations"][0] == "sanctions"
    bruit = [t for t, c in choix.items() if c is None]
    assert any(t.startswith("Agency Information Collection") for t in bruit)
    assert any("Web General License" in t for t in bruit)
    assert all("Web General License" not in t for t, c in choix.items() if c)


def test_inspection_publique_la_veille():
    choix = {d["document_number"]: choisir(d) for d in docs("veille.json")}
    assert choix["2026-20439"][1] == "Détermination présidentielle"  # déposée le 2 oct., parution prévue le 5
    assert choix["2026-20341"][2] == "gouvernement"  # USTR : accord Canada-États-Unis-Mexique
    assert choix["2026-20295"] is None  # réunion de la SEC : bruit


# ---------- Ventes d'armes : texte officiel des avis au Congrès ----------


def test_vente_armes_qatar_quatre_fournisseurs():
    v = lire_vente_armes(texte("2026-19323"))
    assert v["acheteur"] == "Government of Qatar"
    assert v["total"] == 4.50e9
    assert v["fournisseurs"] == ["The Boeing Corporation", "Pratt & Whitney Military Engines", "RTX Corporation",
                                 "Northrop Grumman Corporation"]
    assert v["date_congres"] == "August 18, 2026" and v["ajout_a_une_vente"] is False


def test_vente_armes_coree_millions():
    v = lire_vente_armes(texte("2026-19322"))
    assert (v["acheteur"], v["total"], v["fournisseurs"]) == ("Republic of Korea", 125e6, ["RTX Corporation"])


def test_ajout_a_une_vente_sans_montant_total():
    v = lire_vente_armes(texte("2026-19316"))  # Bahreïn : rapport d'ajout (36(b)(5)(C)), montants en texte libre
    assert v["acheteur"] == "Government of Bahrain" and v["ajout_a_une_vente"] is True
    assert v["total"] is None  # rien plutôt que faux : on ne devine pas dans le texte libre


def test_rapport_d_ajout_avec_mention_de_classification():
    v = lire_vente_armes(texte("2026-17559"))  # « (i) (U) Purchaser: Government of Georgia »
    assert v["acheteur"] == "Government of Georgia" and v["ajout_a_une_vente"] is True and v["total"] is None
    assert registre.nom_pays(v["acheteur"]) == "Géorgie (pays)"  # un gouvernement acheteur : le pays, pas l'État américain


def test_symboles_des_fournisseurs_par_nom_exact(noms_sec):
    trouves = {f: noms_sec.get(registre.nom_normalise(f)) for f in
               ["The Boeing Corporation", "RTX Corporation", "Northrop Grumman Corporation", "Pratt & Whitney Military Engines",
                "Lockheed Martin Company", "Lockheed Martin, Sikorsky", "BAE Systems"]}
    assert trouves == {"The Boeing Corporation": "BA", "RTX Corporation": "RTX", "Northrop Grumman Corporation": "NOC",
                       "Pratt & Whitney Military Engines": None, "Lockheed Martin Company": "LMT",
                       "Lockheed Martin, Sikorsky": None, "BAE Systems": None}


def test_evenement_vente_armes_complet(noms_sec):
    [doc] = [d for d in docs("armes_liste.json") if d["document_number"] == "2026-19323"]
    doc = {**doc, "agencies": [{"slug": "defense-department", "name": "Defense Department"}], "type": "Notice"}
    ev = valider(registre.evenement(doc, choisir(doc), texte("2026-19323"), "parution", "2026-09-22", noms_sec), JOUR)
    assert ev.badge == "officiel", ev.checks
    assert ev.source == "ventes_armes" and ev.category == "militaire"
    assert ev.title.startswith("Vente d'armes à l'étranger : Qatar — fournisseurs : The Boeing Corporation, Pratt")
    assert registre.nom_pays("Republic of Korea") == "Corée du Sud" and registre.nom_pays("Government of Kuwait") == "Koweït"
    assert registre.nom_pays("Government of Atlantis") == "Atlantis"  # inconnu : le nom officiel, rien d'inventé
    assert ev.tickers == ["BA", "RTX", "NOC"] and ev.amount_min == 4.5e9
    assert ev.occurred_on == "2026-08-18" and ev.published_on == "2026-09-22"
    assert "Avis envoyé au Congrès le 18 août 2026" in ev.notes[0]


def test_texte_officiel_sans_mise_en_page():
    brut = (F / "2026-19316.txt").read_bytes()
    t = texte_officiel(brut)
    assert "<" not in t and "cdn-cgi" not in t and "[FR Doc No: 2026-19316]" in t
    # Les liens de courriels masqués changent à chaque visite : l'empreinte ne doit pas en dépendre.
    variante = brut.replace(b"5025223f3f3a7e2a", b"9a9b9c9d9e9f0a0b")
    assert empreinte(texte_officiel(variante).encode()) == empreinte(t.encode())


# ---------- Le lecteur au complet ----------


class FauxInternet:
    def __init__(self, pages):
        self.pages, self.appels = pages, []

    def get(self, url):
        self.appels.append(url)
        for debut, contenu in self.pages.items():
            if url.startswith(debut):
                return type("T", (), {"contenu": contenu, "sha256": empreinte(contenu)})()
        raise ErreurSource(f"{url} : HTTP 404")


def internet_du_2_octobre(veille=None):
    pres = (F / "presidentiels.json").read_bytes()
    texte_generique = b"<html><pre>[FR Doc No: %s] texte officiel</pre></html>"
    pages = {
        "https://www.federalregister.gov/api/v1/public-inspection-documents/current.json":
            json.dumps(veille).encode() if veille else (F / "veille.json").read_bytes(),
        "https://www.federalregister.gov/api/v1/documents.json?per_page=100&order=newest&fields[]=title"
        "&fields[]=type&fields[]=subtype&fields[]=document_number&fields[]=html_url&fields[]=pdf_url"
        "&fields[]=publication_date&fields[]=signing_date&fields[]=agencies&fields[]=executive_order_number"
        "&fields[]=raw_text_url&fields[]=abstract&conditions[publication_date][gte]=2026-09-27&conditions[type][]=PRESDOCU": pres,
        "https://www.federalregister.gov/api/v1/documents.json?per_page=100&order=newest&fields[]=title"
        "&fields[]=type&fields[]=subtype&fields[]=document_number&fields[]=html_url&fields[]=pdf_url"
        "&fields[]=publication_date&fields[]=signing_date&fields[]=agencies&fields[]=executive_order_number"
        "&fields[]=raw_text_url&fields[]=abstract&conditions[publication_date][gte]=2026-09-27&conditions[agencies]":
            (F / "agences.json").read_bytes(),
    }
    for d in docs("presidentiels.json") + docs("agences.json") + docs("veille.json"):
        url = d.get("raw_text_url") or f"https://www.federalregister.gov/texte/{d['document_number']}.txt"
        pages[url] = texte_generique % d["document_number"].encode()
    return pages


def ajouter_textes(docs_json: bytes) -> bytes:
    """Les listes de test n'ont pas toutes le champ raw_text_url : on l'ajoute (même forme que l'API)."""
    d = json.loads(docs_json)
    for x in d["results"]:
        x.setdefault("raw_text_url", f"https://www.federalregister.gov/texte/{x['document_number']}.txt")
    return json.dumps(d).encode()


def test_lecteur_gouvernement_au_complet(tmp_path):
    pages = internet_du_2_octobre()
    for k in list(pages):
        if "documents.json" in k:
            pages[k] = ajouter_textes(pages[k])
    internet = FauxInternet(pages)
    maintenant = datetime(2026, 10, 2, 22, 17, tzinfo=timezone.utc)
    rapport = executer(tmp_path, client=internet, maintenant=maintenant,
                       collecteurs={"registre_federal": registre.collecter_registre})
    assert rapport["registre_federal"]["ok"], rapport
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    titres = {e["official_id"]: e["title"] for e in fil}
    assert titres["2026-20321"] == "Décret présidentiel : Inaugurating the Era of Super Intelligence"
    assert titres["2026-20439"].startswith("Détermination présidentielle : Lebanon")  # la veille de sa parution
    assert "2026-20093" not in titres  # journée commémorative
    assert all(e["badge"] == "officiel" for e in fil), [e["checks"] for e in fil if e["badge"] != "officiel"]
    [lebanon] = [e for e in fil if e["official_id"] == "2026-20439"]
    assert lebanon["published_on"] == "2026-10-02" and lebanon["data"]["etape"] == "inspection_publique"

    # 2e passage : la 1re lecture gagne, aucun texte n'est retéléchargé
    avant = len(internet.appels)
    executer(tmp_path, client=internet, maintenant=maintenant.replace(hour=23),
             collecteurs={"registre_federal": registre.collecter_registre})
    assert not [u for u in internet.appels[avant:] if "/texte/" in u or "/raw_text/" in u]


def test_document_retire_avant_parution_va_dans_a_verifier(tmp_path):
    veille = json.loads((F / "veille.json").read_text(encoding="utf-8"))
    pages = internet_du_2_octobre()
    for k in list(pages):
        if "documents.json" in k:
            pages[k] = ajouter_textes(pages[k])
    collecteurs = {"registre_federal": registre.collecter_registre}
    maintenant = datetime(2026, 10, 2, 22, 17, tzinfo=timezone.utc)
    executer(tmp_path, client=FauxInternet(pages), maintenant=maintenant, collecteurs=collecteurs)

    # Plus tard, l'agence demande le retrait (avis officiel dans « editorial_note ») : l'info ne reste pas « officielle ».
    for d in veille["results"]:
        if d["document_number"] == "2026-20439":
            d["editorial_note"] = "An agency letter requesting withdrawal of this document was received after placement on public inspection."
    pages["https://www.federalregister.gov/api/v1/public-inspection-documents/current.json"] = json.dumps(veille).encode()
    executer(tmp_path, client=FauxInternet(pages), maintenant=maintenant.replace(hour=23), collecteurs=collecteurs)
    a_verifier = json.loads((tmp_path / "app" / "a_verifier.json").read_text(encoding="utf-8"))
    [ev] = [e for e in a_verifier if e["official_id"] == "2026-20439"]
    assert ev["checks"]["non_retire"] is False and any("Retiré" in n for n in ev["notes"])
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    assert not any(e["official_id"] == "2026-20439" for e in fil)


def test_un_lecteur_ameliore_relit_les_documents_deja_parus(tmp_path, monkeypatch):
    pages = internet_du_2_octobre()
    for k in list(pages):
        if "documents.json" in k:
            pages[k] = ajouter_textes(pages[k])
    collecteurs = {"registre_federal": registre.collecter_registre}
    maintenant = datetime(2026, 10, 2, 22, 17, tzinfo=timezone.utc)
    executer(tmp_path, client=FauxInternet(pages), maintenant=maintenant, collecteurs=collecteurs)
    monkeypatch.setattr(registre, "VERSION", "registre-test-nouveau")
    internet = FauxInternet(pages)
    executer(tmp_path, client=internet, maintenant=maintenant.replace(hour=23), collecteurs=collecteurs)
    relus = [u for u in internet.appels if "/texte/" in u or "/raw_text/" in u]
    assert any("2026-20321" in u for u in relus)  # décret paru : relu avec le nouveau lecteur
    assert not any("/raw_text/" in u for u in relus)  # inspection publique : la 1re lecture gagne
    fil = json.loads((tmp_path / "app" / "fil.json").read_text(encoding="utf-8"))
    [decret] = [e for e in fil if e["official_id"] == "2026-20321"]
    assert decret["parser_version"] == "registre-test-nouveau" and decret["published_on"] == "2026-10-02"
    assert not any("modifié" in n for n in decret["notes"])
