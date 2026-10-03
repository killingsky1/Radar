"""Gouvernement américain actionnaire : un 8-K (SEC) où une compagnie cotée écrit que le gouvernement américain
(ministère du Commerce, de la Défense ou Guerre, de l'Énergie ; « U.S. Government ») reçoit, détient ou revend des
actions, des actions privilégiées ou des bons de souscription de la compagnie.

Lecture : les 8-K du jour qui ont un point 1.01 (accord important), 3.02 (vente d'actions non inscrites) ou 8.01
(autres événements) : le document principal et les communiqués joints (EX-99). On montre l'extrait exact du dépôt,
sans résumé ; le titre dit seulement de quel ministère il s'agit.

Mesuré le 3 octobre 2026 : les 8 cas réels de 2025-2026 (Intel, MP Materials, D-Wave, Lithium Americas, Trilogy Metals,
USA Rare Earth, L3Harris, Rigetti) sont trouvés ; sur 200 8-K pris au hasard (1er et 2 octobre 2026), 1 vrai cas
(financement du Department of War en actions privilégiées et bons de souscription) et 0 fausse alerte avec les règles
ci-dessous :
- le ministère (ou une abréviation définie juste après lui, d'une liste fermée : DOE, DoW, « Department »…), le titre
  (actions, bons de souscription…) et le verbe (émettre, vendre, revendre, investir…) à moins de 250 caractères ;
- pas « U.S. government securities, treasury, programs… » (placements, politiques) ni « United States of America »
  (formules comptables : « principles generally accepted in the United States of America »).
La recherche plein texte de la SEC (efts.sec.gov) n'est pas utilisée : son robots.txt répond 403 (interdit).
"""

from __future__ import annotations

import html
import re

from ..models import Evenement
from ..validate import controle_source
from .gazette import details
from .regulateurs import canonique
from .sec import ARCHIVES, empreinte_entete, lire_8k, lire_journees, symboles

VERSION = "participations-1"
POINTS_LUS = {"1.01", "3.02", "8.01"}
# Descriptions officielles EDGAR (« ITEM INFORMATION » de l'en-tête) : le lecteur des 8-K ne garde pas 3.02 ni 8.01
POINTS_EDGAR = {"entry into a material definitive agreement": "1.01", "unregistered sales of equity securities": "3.02",
                "other events": "8.01"}
PROCHE = 250  # caractères entre le ministère, le titre et le verbe
MINISTERE = (r"(?:U\.S\.|United\s+States)\s+(?:Department|Dept\.)\s+of\s+(?:Commerce|War|Defense|Energy)"
             r"|Department\s+of\s+(?:Commerce|War|Defense|Energy)"
             r"|(?:U\.S\.|United\s+States)\s+[Gg]overnment(?!\s*(?:’s?|'s?)?\s*(?:securities|treasury|treasuries|obligations|"
             r"bonds|bills|notes|debt|agenc|polic|program|contract|spending|fund|shutdown|regulat|budget|grant))")
# Abréviations admises si elles sont définies juste après le ministère : « U.S. Department of Energy (“DOE”) »
ALIAS_PERMIS = {"DOC", "DOE", "DoE", "DoD", "DOD", "DoW", "DOW", "USG", "U.S. Government", "US Government", "Government",
                "United States", "Department", "Purchaser", "Investor", "Holder", "Lender", "Commerce"}
DEFINITION = re.compile(r"(?:" + MINISTERE + r")[^().;]{0,120}?\(\s*(?:the\s+)?[“\"‘']\s*([A-Za-z][A-Za-z.\- ]{1,24}?)\s*"
                        r"[”\"’']\s*\)")
TITRE = re.compile(r"\bwarrants?\b|preferred\s+stock|common\s+stock|common\s+shares|\bshares\b|equity\s+(?:stake|interest|"
                   r"investment)|ownership\s+interest", re.I)
VERBE = re.compile(r"\b(?:issue[sd]?|issuance|issuing|sell|sold|sale|resale|resell|purchase[sd]?|purchasing|acquire[sd]?|"
                   r"acquisition|grant(?:ed)?|receive[sd]?|hold(?:s|ing)?|own(?:s|ed)?|subscri(?:be|bed|ption)|"
                   r"invest(?:s|ed|ment)?|convert(?:ible|s|ed)?)\b", re.I)
BOILERPLATE = re.compile(r"forward[- ]looking|These risks include|risk factors", re.I)
NOMS = {"Commerce": "ministère du Commerce", "War": "ministère de la Guerre (Défense)",
        "Defense": "ministère de la Défense", "Energy": "ministère de l'Énergie"}


def texte_doc(contenu: bytes) -> str:
    """Texte d'un document : un espace entre les blocs, rien pour une balise dans une ligne."""
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>|<!--.*?-->", " ", contenu.decode("utf-8", "replace"))
    t = re.sub(r"(?i)<\s*/?\s*(?:br|p|div|li|tr|td|th|table|h\d)\b[^>]*>", " ", t)
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", t)).replace("\xa0", " ").split())


def gouvernement(texte: str) -> re.Pattern:
    alias = {a.strip() for a in DEFINITION.findall(texte)} & ALIAS_PERMIS
    return re.compile(MINISTERE + "".join(r"|\b" + re.escape(a) + r"\b" for a in sorted(alias, key=len, reverse=True)))


def passages(texte: str) -> list[dict]:
    """Les extraits où le gouvernement, un titre de propriété et un verbe sont proches (au plus 3, sans doublon)."""
    motif, trouves = gouvernement(texte), []
    for m in motif.finditer(texte):
        debut, fin = max(0, m.start() - PROCHE), min(len(texte), m.end() + PROCHE)
        zone = texte[debut:fin]
        if not (TITRE.search(zone) and VERBE.search(zone)) or BOILERPLATE.search(zone):
            continue
        if any(debut < t["fin"] for t in trouves):  # chevauche l'extrait précédent
            continue
        # L'extrait commence au début de la phrase ou de la puce (pas au milieu d'un mot ou d'une diapositive)
        coupe = max(texte.rfind(". ", debut, m.start()), texte.rfind("• ", debut, m.start()))
        if coupe > debut:
            debut = coupe + 2
            zone = texte[debut:fin]
        ministere = re.search(r"Department\s+of\s+(Commerce|War|Defense|Energy)", m.group(0))
        trouves.append({"debut": debut, "fin": fin, "cite": m.group(0), "ministere": ministere.group(1) if ministere else None,
                        "extrait": ("… " if debut else "") + zone.strip() + (" …" if fin < len(texte) else "")})
        if len(trouves) == 3:
            break
    return trouves


def ministere_principal(trouves: list[dict]) -> str | None:
    for t in trouves:
        if t["ministere"]:
            return t["ministere"]
    return None


def evenement(depot, cik: str, cote: dict, documents: list[tuple[str, str, list[dict]]], items: list[dict],
              sha: str) -> Evenement:
    tous = [t for _, _, ts in documents for t in ts]
    m = ministere_principal(tous)
    qui = f"le gouvernement américain ({NOMS[m]})" if m else "le gouvernement américain"
    premier_doc = next(url for url, _, ts in documents if ts)
    d = {"cik": cik, "points": [i["item"] for i in items], "ministere": m,
         "documents": [{"url": url, "type": sorte, "extraits": [t["extrait"] for t in ts]} for url, sorte, ts in documents if ts],
         "details": details(("Compagnie", cote["name"]), ("Ministère", NOMS.get(m, "") if m else ""),
                            ("Points du 8-K", ", ".join(i["item"] for i in items)),
                            *[(f"Extrait ({sorte})", t["extrait"]) for _, sorte, ts in documents for t in ts[:2]])}
    return Evenement(
        source="participations_gouv", official_id=depot.acc, category="gouvernement", kind="participation_gouv",
        title=f"{cote['name']} : un 8-K dit que {qui} reçoit, détient ou revend des titres de la compagnie",
        occurred_on=depot.depose, published_on=depot.depose, official_url=depot.page_officielle(cik), sha256=sha,
        parser_version=VERSION, tickers=[cote["ticker"]], entities=[cote["name"], "Gouvernement américain"], data=d,
        notes=["Lisez l'extrait officiel : le titre résume seulement qu'il est question de titres de la compagnie et du "
               "gouvernement américain (achat, détention, bons de souscription ou revente)."])


@controle_source("participations_gouv")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    extraits = [x for doc in d.get("documents") or [] for x in doc["extraits"]]
    return {
        "extrait_officiel": bool(extraits),
        "gouvernement_nomme": any(re.search(MINISTERE, x) for x in extraits) or bool(d.get("ministere")),
        "titre_de_propriete": all(TITRE.search(x) for x in extraits),
        "point_8k_retenu": bool(set(d.get("points") or []) & POINTS_LUS),
        "compagnie_cotee": bool(ev.tickers),
    }


def points(entete: str) -> list[dict]:
    """Les points 1.01, 3.02 et 8.01 écrits dans l'en-tête officiel du dépôt (« ITEM INFORMATION »)."""
    vus = []
    for desc in re.findall(r"ITEM INFORMATION:\s*([^\n<]+)", html.unescape(entete)):
        item = POINTS_EDGAR.get(desc.strip().lower())
        if item and item not in [v["item"] for v in vus]:
            vus.append({"item": item, "officiel": desc.strip()})
    return vus


def documents_du_depot(page_index: str) -> list[tuple[str, str]]:
    """Le document principal et les communiqués joints (EX-99) d'après la page d'index officielle du dépôt."""
    docs = []
    for ligne in re.findall(r"<tr[^>]*>(.*?)</tr>", page_index, re.S):
        lien = re.search(r'href="(?:/ix\?doc=)?(/Archives/edgar/data/[^"]+\.htm)"', ligne)
        cellules = re.findall(r"<td[^>]*>([^<]*)</td>", ligne)
        if lien and len(cellules) >= 2:
            sorte = cellules[-2].strip()
            if sorte in ("8-K", "8-K/A") or sorte.startswith("EX-99"):
                docs.append((ARCHIVES.rsplit("/Archives", 1)[0] + lien.group(1), sorte))
    return docs[:4]


def lire_un(ctx, depot) -> list[Evenement]:
    cik = depot.filers[0][0]
    entete = ctx.cache.get("entetes_8k", {}).get(depot.acc)  # déjà lue par le lecteur des 8-K, sinon on la lit
    if entete is None:
        entete = ctx.client.get(f"{depot.dossier(cik)}/{depot.acc}-index-headers.html").contenu.decode("utf-8", "replace")
    f = lire_8k(entete)  # pour les déposants
    items = points(entete)
    if not items:
        return []
    syms = symboles(ctx)
    cik_cote, cote = next(((c, syms.cote(c)) for c, _ in f["filers"] if syms.cote(c)), (None, None))
    if cote is None:
        return []  # comme le lecteur des 8-K : seulement les compagnies cotées
    page = ctx.client.get(depot.page_officielle(cik)).contenu.decode("utf-8", "replace")
    documents = []
    for url, sorte in documents_du_depot(page):
        documents.append((url, sorte, passages(texte_doc(ctx.client.get(url).contenu))))
    if not any(ts for _, _, ts in documents):
        return []
    return [evenement(depot, cik_cote, cote, documents, items,
                      canonique({"entete": empreinte_entete(entete), "extraits": [t["extrait"] for _, _, ts in documents
                                                                                 for t in ts]}))]


def collecter(ctx) -> list[Evenement]:
    return lire_journees(ctx, "participations_gouv", {"8-K"}, lire_un)
