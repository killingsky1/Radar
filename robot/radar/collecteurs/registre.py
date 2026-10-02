"""Registre fédéral américain (federalregister.gov) : l'API officielle, gratuite, sans compte.

On garde seulement ce qui peut bouger l'argent (le reste est du bruit administratif) :
- Gouvernement : documents présidentiels (décrets, proclamations, mémorandums, déterminations),
  sanctions du Trésor (OFAC), contrôles d'exportation (BIS), commerce extérieur et tarifs (USTR).
- Militaire : avis de ventes d'armes à l'étranger (texte officiel des avis envoyés au Congrès).

« La veille » : l'inspection publique montre les documents AVANT leur parution officielle.
Un document déjà lu n'est pas relu (la 1re lecture gagne), sauf s'il est retiré avant sa parution.
L'empreinte SHA-256 est celle du texte officiel (sans la mise en page web, qui change à chaque visite).

Formats vérifiés sur de vrais documents des 22 septembre au 2 octobre 2026.
"""

from __future__ import annotations

import html
import json
import re
from datetime import date, timedelta

from ..models import Evenement, empreinte
from ..store import Depot
from ..validate import controle_source

VERSION = "registre-3"
API = "https://www.federalregister.gov/api/v1"
CHAMPS = ("title", "type", "subtype", "document_number", "html_url", "pdf_url", "publication_date", "signing_date",
          "agencies", "executive_order_number", "raw_text_url", "abstract")
JOURS_EN_ARRIERE = 5  # rattrapage si des passages ont été manqués
JOURS_ARMES = 45  # les avis de ventes d'armes arrivent par paquets
MAX_PAGES = 5

AGENCES = {  # slug officiel -> (nom court, libellé, sorte)
    "foreign-assets-control-office": ("OFAC", "Sanctions (Trésor, OFAC)", "sanctions"),
    "industry-and-security-bureau": ("BIS", "Exportations (Commerce, BIS)", "exportations"),
    "trade-representative-office-of-united-states": ("USTR", "Commerce extérieur (USTR)", "commerce_exterieur"),
}
PRESIDENTIELS = {  # sous-type officiel -> libellé
    "Executive Order": "Décret présidentiel",
    "Proclamation": "Proclamation présidentielle",
    "Memorandum": "Mémorandum présidentiel",
    "Determination": "Détermination présidentielle",
    "Notice": "Avis présidentiel",
}
# Bruit : formulaires, réunions, licences web de routine, cas individuels.
BRUIT = re.compile(
    r"^(agency information collection|information collection|proposed information collection|submission for omb"
    r"|privacy act of 1974|sunshine act|meetings?\b|notice of (federal )?advisory committee|request for nominations)"
    r"|advisory committee|web general licen[cs]e|denial of export privileges|order denying export privileges",
    re.I,
)
# L'inspection publique ne donne pas le sous-type : on le lit dans le titre officiel quand il y est écrit.
TITRES_PRESIDENTIELS = (
    ("Executive Order", re.compile(r"\bExecutive Order\b")),
    ("Determination", re.compile(r"\bPresidential Determination\b")),
    ("Memorandum", re.compile(r"\bMemorandum\b")),
    ("Proclamation", re.compile(r"\bProclamation\b")),
)
COMMEMORATIF = re.compile(r"\b(day|week|month)\b", re.I)
ANNEE = re.compile(r"\b(19|20)\d\d\b")
HOMMAGE = re.compile(r"\b(anniversary|honoring the memory)\b", re.I)


def commemoratif(titre: str) -> bool:
    """Proclamation de célébration (« Labor Day, 2026 », « Patriot Day 2026, the 25th Anniversary… »,
    drapeaux en berne) : sans effet sur l'argent."""
    return bool(HOMMAGE.search(titre) or (COMMEMORATIF.search(titre) and ANNEE.search(titre)))
CONTINUATION = re.compile(r"^continuation of the national emergency", re.I)
MONTANT_ARMES = re.compile(r"TOTAL\s*\.*\s*\$\s*([\d.,]+)\s*(million|billion)", re.I)


# ---------- Lecture des listes ----------


def _liste(ctx, requete: str) -> list[dict]:
    url = f"{API}/documents.json?per_page=100&order=newest&" + "&".join(f"fields[]={c}" for c in CHAMPS) + requete
    resultats = []
    for _ in range(MAX_PAGES):
        page = json.loads(ctx.client.get(url).contenu)
        resultats.extend(page.get("results") or [])
        url = page.get("next_page_url")
        if not url:
            break
    return resultats


def slugs(doc: dict) -> list[str]:
    return [a["slug"] for a in doc.get("agencies") or [] if a.get("slug")]


def choisir(doc: dict) -> tuple[str, str, str] | None:
    """(sorte, libellé, catégorie) si le document compte, sinon None."""
    titre = " ".join((doc.get("title") or "").split())
    if not titre or BRUIT.search(titre):
        return None
    if doc.get("type") == "Presidential Document":
        if CONTINUATION.search(titre):
            return None
        sous_type = doc.get("subtype") or next((s for s, m in TITRES_PRESIDENTIELS if m.search(titre)), "")
        if sous_type in ("Proclamation", "") and commemoratif(titre):  # "" : inspection publique, sorte inconnue
            return None
        return ("presidentiel", PRESIDENTIELS.get(sous_type, "Document présidentiel"), "gouvernement")
    if titre.startswith("Arms Sales Notification") and "defense-department" in slugs(doc):
        return ("vente_armes", "Vente d'armes à l'étranger", "militaire")
    for s in slugs(doc):
        if s in AGENCES:
            _, libelle, sorte = AGENCES[s]
            return (sorte, libelle, "gouvernement")
    return None


# ---------- Texte officiel ----------


def texte_officiel(brut: bytes) -> str:
    """Le texte du document sans la mise en page web (balises, liens de courriels masqués…)."""
    t = brut.decode("utf-8", "replace")
    t = re.sub(r"<[^>]+>", " ", t)
    return " ".join(html.unescape(t).split())


def montant(texte: str) -> float | None:
    m = MONTANT_ARMES.search(texte)
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    return n * (1e9 if m.group(2).lower() == "billion" else 1e6)


def lire_vente_armes(texte: str) -> dict:
    """Champs officiels d'un avis de vente d'armes (articles numérotés (i), (ii)… de la loi AECA)."""
    d: dict = {}
    m = re.search(r"Transmittal No\.\s*([A-Z]*\s?[\w-]+)", texte)
    d["transmission"] = m.group(1).strip() if m else None
    # « (i) Prospective Purchaser: … » ou, dans les rapports d'ajout, « (i) (U) Purchaser: … » ((U) = non classifié)
    m = re.search(r"\(i\) (?:\(U\) )?(?:Prospective )?Purchaser:\s*(.+?)\s*\(ii\)", texte)
    d["acheteur"] = m.group(1).strip() if m else None
    d["total"] = montant(texte)
    m = re.search(r"principal (?:U\.S\. )?contractors? (?:will be|is|are)\s+(.+?)\.\s+(?:At this time|There are no|The purchaser)",
                  texte)
    d["fournisseurs_texte"] = m.group(1).strip() if m else None
    d["fournisseurs"] = [x.split(", located")[0].strip() for x in re.split(r";\s*(?:and\s+)?", d["fournisseurs_texte"])] \
        if d["fournisseurs_texte"] else []
    m = re.search(r"Date Report Delivered to Congress:\s*([A-Z][a-z]+ \d{1,2}, \d{4})", texte)
    d["date_congres"] = m.group(1) if m else None
    d["ajout_a_une_vente"] = bool(re.search(r"Sec\. 36\(b\)\(1\), AECA Transmittal No\.", texte))
    return d


MOIS = {m: i for i, m in enumerate(("January", "February", "March", "April", "May", "June", "July", "August",
                                    "September", "October", "November", "December"), 1)}


MOIS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre")


def date_fr(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{'1er' if d.day == 1 else d.day} {MOIS_FR[d.month - 1]} {d.year}"


def date_en(texte: str | None) -> str | None:
    m = re.fullmatch(r"([A-Z][a-z]+) (\d{1,2}), (\d{4})", texte or "")
    if not m or m.group(1) not in MOIS:
        return None
    return date(int(m.group(3)), MOIS[m.group(1)], int(m.group(2))).isoformat()


PAYS_FR = {  # nom officiel (après « Government of ») -> nom français ; inconnu : le nom officiel tel quel
    "Canada": "Canada", "Qatar": "Qatar", "State of Qatar": "Qatar", "Bahrain": "Bahreïn", "Kingdom of Bahrain": "Bahreïn",
    "Kuwait": "Koweït", "State of Kuwait": "Koweït", "Norway": "Norvège", "Sweden": "Suède", "France": "France",
    "Pakistan": "Pakistan", "Singapore": "Singapour", "Republic of Singapore": "Singapour", "Japan": "Japon",
    "Poland": "Pologne", "Republic of Poland": "Pologne", "Germany": "Allemagne",
    "Federal Republic of Germany": "Allemagne", "Saudi Arabia": "Arabie saoudite", "Kingdom of Saudi Arabia": "Arabie saoudite",
    "United Arab Emirates": "Émirats arabes unis", "Israel": "Israël", "Egypt": "Égypte", "Arab Republic of Egypt": "Égypte",
    "India": "Inde", "Australia": "Australie", "Commonwealth of Australia": "Australie", "United Kingdom": "Royaume-Uni",
    "Netherlands": "Pays-Bas", "the Netherlands": "Pays-Bas", "Kingdom of the Netherlands": "Pays-Bas",
    "Denmark": "Danemark", "Kingdom of Denmark": "Danemark", "Finland": "Finlande", "Romania": "Roumanie",
    "Philippines": "Philippines", "Republic of the Philippines": "Philippines", "Republic of Korea": "Corée du Sud",
    "Korea": "Corée du Sud", "Italy": "Italie", "Spain": "Espagne", "Greece": "Grèce", "Hellenic Republic": "Grèce",
    "Turkey": "Turquie", "Türkiye": "Turquie", "Republic of Türkiye": "Turquie", "Lebanon": "Liban", "Jordan": "Jordanie",
    "Hashemite Kingdom of Jordan": "Jordanie", "Morocco": "Maroc", "Kingdom of Morocco": "Maroc", "Oman": "Oman",
    "Sultanate of Oman": "Oman", "Brazil": "Brésil", "Mexico": "Mexique", "Chile": "Chili", "Colombia": "Colombie",
    "Peru": "Pérou", "Argentina": "Argentine", "Czech Republic": "Tchéquie", "Slovakia": "Slovaquie",
    "Hungary": "Hongrie", "Bulgaria": "Bulgarie", "Republic of Bulgaria": "Bulgarie", "Croatia": "Croatie",
    "Lithuania": "Lituanie", "Republic of Lithuania": "Lituanie", "Latvia": "Lettonie", "Estonia": "Estonie",
    "Belgium": "Belgique", "Switzerland": "Suisse", "Austria": "Autriche", "Portugal": "Portugal", "Ukraine": "Ukraine",
    "New Zealand": "Nouvelle-Zélande", "Indonesia": "Indonésie", "Thailand": "Thaïlande", "Vietnam": "Vietnam",
    "Malaysia": "Malaisie", "Iraq": "Irak", "Tunisia": "Tunisie", "Nigeria": "Nigeria", "Ecuador": "Équateur",
    "Georgia": "Géorgie (pays)", "Taipei Economic and Cultural Representative Office in the United States": "Taïwan (TECRO)",
}


def nom_pays(acheteur: str | None) -> str | None:
    """« Government of Qatar » -> « Qatar ». Un nom absent de la table reste en anglais officiel (rien d'inventé)."""
    if not acheteur:
        return None
    sans = re.sub(r"^(the )?government of (the )?", "", acheteur.strip(), flags=re.I).strip()
    if sans in PAYS_FR:
        return PAYS_FR[sans]
    if "north atlantic treaty organization" in sans.lower():
        return "OTAN (" + sans + ")"
    return sans or acheteur


# ---------- Symboles des fournisseurs (liste officielle SEC, nom exact seulement) ----------

SUFFIXES = re.compile(r"\b(THE|INCORPORATED|INC|CORPORATION|CORP|COMPANY|CO|LLC|LTD|PLC|LP|HOLDINGS?)\b")


def nom_normalise(nom: str) -> str:
    n = re.sub(r"/[A-Z]{2}/?", " ", nom.upper())  # « /DE/ » : État d'incorporation dans les noms SEC
    n = re.sub(r"[^A-Z0-9& ]", " ", n)
    return " ".join(SUFFIXES.sub(" ", n).split())


def symboles_par_nom(syms) -> dict[str, str]:
    """Nom normalisé -> symbole, seulement si un seul symbole coté porte ce nom (sinon : ambigu, ignoré)."""
    trouves: dict[str, set[str]] = {}
    for cik in syms.par_cik:
        cote = syms.cote(cik)
        if cote:
            trouves.setdefault(nom_normalise(cote["name"]), set()).add(cote["ticker"])
    return {nom: next(iter(t)) for nom, t in trouves.items() if len(t) == 1 and nom}


# ---------- Événements ----------


def evenement(doc: dict, choix: tuple[str, str, str], texte: str, etape: str, publie: str, syms_noms: dict) -> Evenement:
    sorte, libelle, categorie = choix
    titre = " ".join(doc["title"].split())
    occ = doc.get("signing_date") if doc.get("signing_date") and doc["signing_date"] <= publie else publie
    data = {
        "numero": doc["document_number"], "type": doc.get("type"), "sous_type": doc.get("subtype"),
        "agences": [a.get("name") or a.get("raw_name") for a in doc.get("agencies") or []],
        "titre_officiel": titre, "etape": etape, "sorte": sorte,
        "numero_dans_le_texte": doc["document_number"] in texte,  # le texte lu est bien celui de ce document
    }
    if doc.get("executive_order_number"):
        data["numero_decret"] = doc["executive_order_number"]
    if doc.get("publication_date"):
        data["parution_prevue" if etape == "inspection_publique" else "parution"] = doc["publication_date"]
    tickers, entites, montant_total, notes = [], [], None, []
    if sorte == "vente_armes":
        v = lire_vente_armes(texte)
        data["vente"] = v
        pays = nom_pays(v["acheteur"]) or "pays non lu"
        montant_total = v["total"]
        titre_fr = f"{libelle} : {pays}"
        if v["fournisseurs"]:
            titre_fr += f" — fournisseur{'s' if len(v['fournisseurs']) > 1 else ''} : " + ", ".join(v["fournisseurs"])
        entites = [x for x in [v["acheteur"]] + v["fournisseurs"] if x]
        for f in v["fournisseurs"]:
            t = syms_noms.get(nom_normalise(f))
            if t and t not in tickers:
                tickers.append(t)
        if tickers:
            data["symboles_trouves_par"] = "nom exact dans la liste officielle de la SEC"
        if v["date_congres"] and date_en(v["date_congres"]):
            occ = date_en(v["date_congres"])
            notes.append(f"Avis envoyé au Congrès le {date_fr(occ)} ; publié au Registre plus tard.")
        if v["ajout_a_une_vente"]:
            notes.append("Ajout ou mise à niveau d'une vente déjà annoncée.")
    else:
        titre_fr = f"{libelle} : {titre}"
        entites = data["agences"]
    if doc.get("retire"):
        notes.append("Retiré par l'agence avant sa parution (avis officiel du Registre).")
        data["retire"] = True
    return Evenement(
        source="ventes_armes" if sorte == "vente_armes" else "registre_federal",
        official_id=doc["document_number"], category=categorie, kind=sorte, title=titre_fr,
        occurred_on=min(occ, publie), published_on=publie, official_url=doc["html_url"],
        sha256=empreinte(texte.encode("utf-8")), parser_version=VERSION,
        tickers=tickers, entities=entites, amount_min=montant_total, amount_max=montant_total, notes=notes, data=data,
    )


def _controles_communs(ev: Evenement) -> dict[str, bool]:
    return {
        "numero_officiel": bool(re.fullmatch(r"\d{4}-\d{5}", ev.official_id)),
        "lien_du_meme_document": ev.official_id in ev.official_url,
        "texte_du_meme_document": bool(ev.data.get("numero_dans_le_texte")),
        "non_retire": not ev.data.get("retire"),
    }


@controle_source("registre_federal")
def controles_registre(ev: Evenement) -> dict[str, bool]:
    return _controles_communs(ev)


@controle_source("ventes_armes")
def controles_armes(ev: Evenement) -> dict[str, bool]:
    v = ev.data.get("vente") or {}
    return {
        **_controles_communs(ev),
        "acheteur_lu": bool(v.get("acheteur")),
        # Un montant lu doit être plausible : entre 1 M$ et 100 G$ pour une seule vente.
        "montant_plausible": ev.amount_min is None or 1e6 <= ev.amount_min <= 1e11,
    }


def deja_lus(ctx) -> dict[str, tuple[str, str]]:
    """Numéro -> (version du lecteur, étape) des documents déjà enregistrés."""
    depot = Depot(ctx.donnees)
    return {d["official_id"]: (d["parser_version"], d.get("data", {}).get("etape", ""))
            for dossier in ("evenements", "a_verifier") for d in depot.lire(dossier)
            if d["source"] in ("registre_federal", "ventes_armes")}


def _symboles_noms(ctx) -> dict:
    """Pour relier un fournisseur à son symbole. Si la SEC ne répond pas : pas de symbole (jamais un faux)."""
    if "registre_noms" not in ctx.cache:
        try:
            from .sec import symboles

            ctx.cache["registre_noms"] = symboles_par_nom(symboles(ctx))
        except Exception:  # noqa: BLE001
            ctx.cache["registre_noms"] = {}
    return ctx.cache["registre_noms"]


def collecter(ctx, sorte_voulue: str) -> list[Evenement]:
    """sorte_voulue : « gouvernement » (registre_federal) ou « militaire » (ventes_armes)."""
    aujourd_hui = ctx.maintenant.date()
    candidats: dict[str, tuple[dict, str, str]] = {}  # numéro -> (document, étape, date de 1re publicité)

    if sorte_voulue == "gouvernement":
        depuis = (aujourd_hui - timedelta(days=JOURS_EN_ARRIERE)).isoformat()
        requetes = [f"&conditions[publication_date][gte]={depuis}&conditions[type][]=PRESDOCU",
                    f"&conditions[publication_date][gte]={depuis}"
                    + "".join(f"&conditions[agencies][]={s}" for s in AGENCES)]
        # Inspection publique (la veille) : documents déposés, pas encore parus.
        courant = json.loads(ctx.client.get(f"{API}/public-inspection-documents/current.json").contenu)
        for doc in courant.get("results") or []:
            if not doc.get("document_number") or not doc.get("html_url"):
                continue
            depose = (doc.get("filed_at") or doc.get("last_public_inspection_issue") or "")[:10]
            if not re.fullmatch(r"\d{4}-\d\d-\d\d", depose):
                continue
            doc = dict(doc, retire=bool(re.search(r"withdraw", doc.get("editorial_note") or "", re.I)))
            candidats[doc["document_number"]] = (doc, "inspection_publique", depose)
    else:
        depuis = (aujourd_hui - timedelta(days=JOURS_ARMES)).isoformat()
        requetes = [f"&conditions[publication_date][gte]={depuis}&conditions[agencies][]=defense-department"
                    "&conditions[term]=%22Arms+Sales+Notification%22"]
    for r in requetes:
        for doc in _liste(ctx, r):
            if doc.get("document_number") and doc.get("publication_date") and doc.get("html_url"):
                candidats.setdefault(doc["document_number"], (doc, "parution", doc["publication_date"]))

    lus = deja_lus(ctx)
    evenements = []
    for numero, (doc, etape, publie) in sorted(candidats.items()):
        choix = choisir(doc)
        if choix is None or choix[2] != sorte_voulue:
            continue
        if numero in lus and not doc.get("retire"):
            version, etape_lue = lus[numero]
            # La 1re lecture gagne. Exception : un document déjà PARU est relu quand le lecteur s'améliore
            # (même texte, même date de parution : seule la lecture change).
            if version == VERSION or etape_lue != "parution" or etape != "parution":
                continue
        if not doc.get("raw_text_url"):
            continue
        texte = texte_officiel(ctx.client.get(doc["raw_text_url"]).contenu)
        evenements.append(evenement(doc, choix, texte, etape, publie, _symboles_noms(ctx) if choix[0] == "vente_armes" else {}))
    return evenements


def collecter_registre(ctx) -> list[Evenement]:
    return collecter(ctx, "gouvernement")


def collecter_ventes_armes(ctx) -> list[Evenement]:
    return collecter(ctx, "militaire")
