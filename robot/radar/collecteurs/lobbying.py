"""Lobbying à Washington (LDA.gov) des compagnies des listes du score : dépenses du dernier trimestre et sujets.

Sans compte : 15 requêtes par minute (robots.txt : 4 secondes entre deux requêtes ; le client en attend 4,5).
Une recherche par compagnie (au plus 4 pages de 25 rapports), une fois par jour de semaine ; chaque compagnie est
relue après 7 jours. Seuls les rapports au nom EXACT de la compagnie comptent (mêmes mots, sans « Inc », « Corp »…) :
pas les filiales, ni les noms mal écrits (rien plutôt que faux).
Règle officielle (guide du LDA, révisé le 28 février 2025) : une compagnie qui a ses propres lobbyistes déclare des
dépenses qui incluent ce qu'elle paie aux firmes de lobbying. Le total retenu est donc ses propres dépenses ; sinon,
la somme des revenus déclarés par les firmes qu'elle paie. Les montants sont arrondis aux 10 000 $ par les déposants.
Conditions de l'API : citer la date de lecture et la phrase AVERTISSEMENT (affichées dans l'app).
0 point dans le score : l'étude (Chen, Parsley et Yang, 2015) mesure un effet sur 3 ans, selon le lobbying par rapport à
la taille de la compagnie, que Radar ne mesure pas.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

VERSION = "lobbying-1"
API = "https://lda.gov/api/v1/filings/"
AVERTISSEMENT = ("Senate Office of Public Records cannot vouch for the data or analyses derived from these data after "
                 "the data have been retrieved from LDA.gov.")
PERIODES = {1: "first_quarter", 2: "second_quarter", 3: "third_quarter", 4: "fourth_quarter"}
MAX_PAGES = 4
MAX_REQUETES = 40  # par passage : 3 minutes au plus à 15 requêtes par minute
RELIRE_JOURS = 7
SUFFIXES = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LLC", "LP", "LLP", "PLC",
            "SA", "NV", "AG", "SE", "THE"}
# Mots trop courants pour une recherche (le filtre au nom exact vient ensuite)
COMMUNS = {"FIRST", "CAPITAL", "GROUP", "HOLDING", "HOLDINGS", "BANCORP", "BANCSHARES", "FINANCIAL", "INTERNATIONAL",
           "AMERICAN", "NATIONAL", "TECHNOLOGIES", "TECHNOLOGY", "THERAPEUTICS", "PHARMACEUTICALS", "ENERGY", "SYSTEMS",
           "SERVICES", "INDUSTRIES", "PARTNERS", "TRUST", "BANK", "GLOBAL", "RESOURCES", "SOLUTIONS", "MANAGEMENT",
           "ASSET", "INVESTMENT", "DATA", "HEALTH", "MEDICAL", "BIOSCIENCES", "SCIENCES"}
# Les 79 sujets officiels (constants/filing/lobbyingactivityissues), en français
SUJETS_FR = {
    "ACC": "Comptabilité", "ADV": "Publicité", "AER": "Aérospatiale", "AGR": "Agriculture",
    "ALC": "Alcool et drogues", "ANI": "Animaux", "APP": "Vêtements et textiles", "ART": "Arts et divertissement",
    "AUT": "Industrie automobile", "AVI": "Aviation, compagnies aériennes et aéroports", "BAN": "Banques",
    "BNK": "Faillites", "BEV": "Industrie des boissons", "BUD": "Budget et crédits",
    "CIV": "Droits et libertés civils", "CHM": "Produits chimiques", "CAW": "Qualité de l'air et de l'eau",
    "CDT": "Matières premières", "COM": "Communications, radio et télévision", "CPI": "Industrie informatique",
    "CON": "Constitution", "CSP": "Consommateurs et sécurité des produits",
    "CPT": "Droits d'auteur, brevets et marques", "DEF": "Défense", "DIS": "Catastrophes et urgences",
    "DOC": "District de Columbia", "ECN": "Économie et développement économique", "EDU": "Éducation",
    "ENG": "Énergie et nucléaire", "ENV": "Environnement (dont Superfund)", "FAM": "Famille, avortement et adoption",
    "FIN": "Institutions financières, placements et valeurs mobilières", "FIR": "Armes à feu et munitions",
    "FOO": "Industrie alimentaire (salubrité, étiquetage…)", "FOR": "Relations étrangères",
    "FUE": "Carburants, gaz et pétrole", "GAM": "Jeux de hasard et casinos", "GOV": "Affaires gouvernementales",
    "HCR": "Santé", "HOM": "Sécurité intérieure", "HOU": "Logement", "IMM": "Immigration",
    "IND": "Affaires autochtones", "INS": "Assurances", "INT": "Renseignement",
    "LBR": "Travail, concurrence et milieu de travail", "LAW": "Police, criminalité et justice pénale",
    "MAN": "Fabrication", "MAR": "Maritime, navigation et pêches", "MIA": "Médias et édition",
    "MED": "Recherche médicale et laboratoires", "MMM": "Medicare et Medicaid", "MON": "Monnaie",
    "NAT": "Ressources naturelles", "PHA": "Pharmacie", "POS": "Poste", "RRR": "Chemins de fer",
    "RES": "Immobilier, aménagement du territoire et conservation", "REL": "Religion", "RET": "Retraite",
    "ROD": "Routes et autoroutes", "SCI": "Science et technologie", "SMB": "Petites entreprises", "SPO": "Sports",
    "TAR": "Tarifs douaniers (projets de loi divers)", "TAX": "Fiscalité (impôts)", "TEC": "Télécommunications",
    "TOB": "Tabac", "TOR": "Responsabilité civile", "TRD": "Commerce (intérieur et extérieur)", "TRA": "Transports",
    "TOU": "Voyages et tourisme", "TRU": "Camionnage et expédition", "URB": "Développement urbain et municipalités",
    "UNM": "Chômage", "UTI": "Services publics (électricité, eau, gaz)", "VET": "Anciens combattants",
    "WAS": "Déchets (dangereux, solides, nucléaires…)", "WEL": "Aide sociale",
}


def dernier_trimestre_complet(jour: date) -> tuple[int, int]:
    """(année, trimestre) : le dernier trimestre dont la date limite de dépôt (le 20 du mois suivant) est passée."""
    annee, t = jour.year, (jour.month - 1) // 3 + 1
    while True:
        t -= 1
        if t == 0:
            annee, t = annee - 1, 4
        mois = t * 3 + 1  # le mois qui suit la fin du trimestre
        if jour > date(annee + (mois > 12), (mois - 1) % 12 + 1, 20):
            return annee, t


def libelle_trimestre(annee: int, t: int) -> str:
    return f"{'1er' if t == 1 else f'{t}e'} trimestre {annee}"


def mots_nom(nom: str) -> list[str]:
    """Mots significatifs d'un nom de compagnie (sans accents, apostrophes, « Inc », « Corp »… à la fin)."""
    n = unicodedata.normalize("NFKD", nom or "").encode("ascii", "ignore").decode().upper()
    m = re.findall(r"[A-Z0-9]+", n.replace("&", " AND ").replace("'", ""))
    while m and m[-1] in SUFFIXES:
        m.pop()
    while m and m[0] == "THE":
        m.pop(0)
    return m


def meme_nom(a: str, b: str) -> bool:
    """Mêmes mots, dans n'importe quel ordre (la SEC écrit « FULLER H B CO », le LDA « H.B. FULLER COMPANY »)."""
    ma, mb = mots_nom(a), mots_nom(b)
    return bool(ma) and sorted(ma) == sorted(mb)


def mot_de_recherche(mots: list[str]) -> str:
    candidats = [x for x in mots if len(x) >= 4 and x not in COMMUNS] or [x for x in mots if len(x) >= 4] or mots
    return max(candidats, key=len)


def types_du_trimestre(t: int) -> set[str]:
    """Rapports trimestriels, modifications et fins de mandat du trimestre (pas les inscriptions)."""
    return {f"Q{t}", f"Q{t}Y", f"{t}T", f"{t}TY", f"{t}A", f"{t}AY", f"{t}@", f"{t}@Y"}


def resume(f: dict) -> dict:
    sans_activite = f["filing_type"].endswith("Y")
    montant = f.get("expenses") if f.get("expenses") is not None else f.get("income")
    soi_meme = f["client"].get("client_self_select") is True or meme_nom(f["registrant"]["name"], f["client"]["name"])
    return {
        "uuid": f["filing_uuid"], "type": f["filing_type"], "registrant": " ".join(f["registrant"]["name"].split()),
        "registrant_id": f["registrant"]["id"], "client": " ".join(f["client"]["name"].split()),
        "client_id": f["client"]["id"], "soi_meme": soi_meme, "sans_activite": sans_activite,
        "montant": None if montant is None else float(montant), "poste": (f.get("dt_posted") or "")[:10],
        "url": f["filing_document_url"],
        "sujets": sorted({a["general_issue_code"] for a in f.get("lobbying_activities") or []}),
        "sujets_officiels": {a["general_issue_code"]: a.get("general_issue_code_display")
                             for a in f.get("lobbying_activities") or []},
    }


def bilan(nom: str, rapports: list[dict], t: int) -> dict:
    """Le dernier rapport de chaque paire (déposant, client) ; le total selon la règle officielle."""
    derniers: dict = {}
    for r in sorted((r for r in rapports if r["type"] in types_du_trimestre(t)), key=lambda r: (r["poste"], r["uuid"])):
        derniers[(r["registrant_id"], r["client_id"])] = r  # une modification remplace le rapport précédent
    gardes = sorted(derniers.values(), key=lambda r: (-(r["montant"] or 0), r["registrant"]))
    actifs = [r for r in gardes if not r["sans_activite"]]
    maison = [r for r in actifs if r["soi_meme"]]
    firmes = [r for r in actifs if not r["soi_meme"]]
    if maison:
        base, total = "compagnie", sum(r["montant"] or 0 for r in maison)
    else:
        base, total = "firmes", sum(r["montant"] or 0 for r in firmes)
    compte = Counter(c for r in actifs for c in r["sujets"])
    noms_officiels = {c: n for r in actifs for c, n in r["sujets_officiels"].items()}
    return {
        "rapports": [{k: v for k, v in r.items() if k not in ("registrant_id", "client_id", "sujets_officiels")}
                     for r in gardes],
        "base": base if actifs else None, "total": total if actifs else None,
        "firmes": len({r["registrant"] for r in firmes}),
        "revenus_firmes": sum(r["montant"] or 0 for r in firmes) if firmes else None,
        "moins_de_5000": sum(1 for r in actifs if r["montant"] is None),
        "sujets": [{"code": c, "nom": SUJETS_FR.get(c) or noms_officiels.get(c) or c}
                   for c, _ in sorted(compte.items(), key=lambda kv: (-kv[1], kv[0]))],
    }


def chemin_cache(donnees, annee: int, t: int) -> Path:
    return Path(donnees) / "lobbying" / f"{annee}-T{t}.json"


def compagnies_des_listes(donnees) -> list[tuple[str, str]]:
    p = Path(donnees) / "app" / "aujourdhui.json"
    if not p.exists():
        return []
    s = json.loads(p.read_text(encoding="utf-8"))
    return [(x["symbole"], x["nom"]) for liste in ("hausse", "baisse") for x in s.get(liste, [])]


def collecter(ctx) -> list:
    """Met à jour data/lobbying/AAAA-Tn.json pour les compagnies des listes. Aucune info dans le fil."""
    annee, t = dernier_trimestre_complet(ctx.maintenant.date())
    chemin = chemin_cache(ctx.donnees, annee, t)
    cache = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    limite = (ctx.maintenant - timedelta(days=RELIRE_JOURS)).isoformat()
    requetes = 0
    for symbole, nom in compagnies_des_listes(ctx.donnees):
        if symbole in cache and cache[symbole]["lu"] >= limite and cache[symbole]["nom"] == nom:
            continue
        mots = mots_nom(nom)
        if not mots or requetes >= MAX_REQUETES:
            continue
        mot = mot_de_recherche(mots)
        url = (f"{API}?filing_year={annee}&filing_period={PERIODES[t]}&page_size=25&client_name={quote(mot)}")
        trouves, pages, complet = [], 0, True
        while url:
            if pages == MAX_PAGES:
                complet = False  # trop de résultats pour ce mot : pas vérifié (jamais un « 0 » faux)
                break
            d = json.loads(ctx.client.get(url).contenu)
            requetes += 1
            pages += 1
            trouves += [resume(f) for f in d.get("results", []) if meme_nom(f["client"]["name"], nom)]
            url = d.get("next")
        cache[symbole] = {"nom": nom, "recherche": mot, "pages": pages, "complet": complet,
                          "lu": ctx.maintenant.isoformat(), **bilan(nom, trouves, t)}
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(cache, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return []


def pour_app(donnees, symboles: list[str], maintenant: datetime) -> dict:
    """Le fichier de l'app (data/app/lobbying.json) : seulement les compagnies des listes, lues ce trimestre."""
    annee, t = dernier_trimestre_complet(maintenant.date())
    p = chemin_cache(donnees, annee, t)
    cache = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return {"trimestre": {"annee": annee, "numero": t, "libelle": libelle_trimestre(annee, t)},
            "avertissement": AVERTISSEMENT, "source": "https://lda.gov/",
            "par_symbole": {s: cache[s] for s in symboles if s in cache}}
