"""Lot H : détecteur STRICT des annonces de rachat d'actions dans un 8-K, pour le labo (même règle que le robot,
tenue à jour à la main ; aucun import du robot). Une annonce : une phrase avec une formule d'autorisation, le conseil,
rien d'un ancien programme avant la formule, aucune autre sorte de titre, rien de conditionnel, aucune date de plus de
60 jours. Sortes : nouveau programme, hausse (montant ajouté), total (nouveau plafond total, gardé seulement si le
dépôt n'annonce pas aussi un nouveau programme ou une hausse).
"""
import re
from datetime import date

MONTANT_MIN = 10_000_000
JOURS_MAX = 60  # une date plus vieille dans la phrase : un ancien programme décrit de nouveau
PHRASE_MAX = 1500  # au-delà, c'est un tableau aplati, pas une phrase
MOIS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
        "December")

DOLLARS = (r"(?<![A-Za-z])(?:US)?\$\s?(?P<n>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
           r"(?:\s*(?P<u>million|billion|thousand|bn\b|mm\b|[MB]\b))?")
ACTIONS = (r"(?P<a>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?\s*million)\s+(?:(?:of\s+)?(?:its|our|the\s+Company['’]s)\s+)?"
           r"(?:outstanding\s+)?(?:ordinary\s+|common\s+|Class\s+[A-C]\s+(?:common\s+)?)?(?:shares|stock)")
V = f"(?:{DOLLARS}|{ACTIONS})"
VERBE = r"(?:approved|authorized|authorised|adopted)"
OBJET = r"(?:share\s+|stock\s+|equity\s+)?(?:repurchase|buy-?back)"
PROGRAMME = OBJET + r"\s+(?:program|programme|plan|authori[sz]ation)"
TROU = r"(?:(?!dividend|\bnotes?\b|debt)[^.$;]){0,80}?"  # « … program under which the Company may repurchase up to $X »
AGREGAT = r"(?:an?\s+(?:aggregate|total)\s+(?:amount\s+)?(?:of\s+)?)?"
PLUS = r"(?:additional|incremental)"
SA = r"(?:its|the|our|the\s+Company['’]s)"
FORMULES = {
    "hausse": [
        VERBE + r"\s+an?\s+" + PLUS + r"\s+(?:share\s+|stock\s+)?(?:repurchase\s+)?authori(?:[sz]ation|ty)\s+to\s+"
        r"(?:re)?purchase\s+(?:up\s+to\s+)?" + V,
        VERBE + r"\s+an?\s+" + PLUS + r"\s+" + V + r"\s+(?:for|of|in|to|under)\s+(?:" + SA + r"\s+)?(?:existing\s+)?"
        + OBJET + r"s?",
        VERBE + r"\s+an?\s+" + PLUS + r"\s+" + V + r"\s+" + OBJET,
        V + r"\s+(?:in\s+)?" + PLUS + r"\s+" + OBJET + r"\s+authori(?:ty|[sz]ation)\s+(?:was\s+|has\s+been\s+)?"
        r"(?:approved|authorized|authorised)",
        r"(?:increased|expanded|upsized)\s+" + SA + r"\s+(?:existing\s+)?" + PROGRAMME + r"\s+by\s+(?:an\s+additional\s+)?"
        + V,
        VERBE + r"\s+an?\s+" + V + r"\s+(?:increase|expansion|addition)\s+(?:to|in|of)\s+" + SA + r"\s+(?:existing\s+)?"
        + PROGRAMME,
        VERBE + r"\s+an?\s+(?:increase|expansion)\s+(?:of|in\s+the\s+amount\s+of)\s+" + V + r"\s+(?:to|in)\s+" + SA
        + r"\s+(?:existing\s+)?" + PROGRAMME,
        # « approved the upsizing of its existing share repurchase program (…) which the Company may repurchase by $1.5
        # billion (the “Additional Authorization”) » (Talen Energy, 29 sept. 2026)
        VERBE + r"\s+(?:the|an?)\s+(?:upsizing|upsize|increase|expansion)\s+(?:of|to|in)\s+" + SA + r"\s+(?:existing\s+)?"
        + PROGRAMME + r"[^;]{0,250}?\bby\s+(?:an\s+additional\s+)?" + V,
    ],
    "nouveau": [
        VERBE + r"\s+(?:a|an|the)\s+(?:new\s+)?" + PROGRAMME + TROU + r"\b(?:up\s+to|of|for|totaling|totalling|"
        r"in\s+the\s+amount\s+of)\s+" + AGREGAT + r"(?:up\s+to\s+)?" + V,
        VERBE + r"\s+(?:a|an)\s+(?:new\s+)?" + V + r"\s+" + OBJET + r"(?:\s+(?:program|programme|plan|"
        r"authori[sz]ation))?",
        VERBE + r"\s+(?:the\s+)?(?:re)?purchase\s+of\s+" + AGREGAT + r"up\s+to\s+" + V,
        VERBE + r"\s+an?\s+(?:new\s+)?(?:program|programme|plan)\s+to\s+(?:re)?purchase\s+(?:up\s+to\s+)?" + V,
        VERBE + r"\s+(?:the\s+Company|us|it|management)\s+to\s+(?:re)?purchase\s+" + AGREGAT + r"up\s+to\s+" + V,
        V + r"\s+(?:new\s+)?" + PROGRAMME + r"\s+(?:was\s+|has\s+been\s+)?(?:approved|authorized|authorised)\s+by",
    ],
    # Le nouveau plafond TOTAL (le montant ajouté n'est pas écrit) : « approved an increase to the Company's share
    # repurchase authorization to $1.5 billion » (Lear), « has increased our share buyback authorization back to $250
    # million » (Jefferies). Gardé seulement si le dépôt n'annonce pas aussi un nouveau programme ou une hausse.
    "total": [
        VERBE + r"\s+an?\s+(?:increase|expansion)\s+(?:to|in|of)\s+" + SA + r"\s+(?:existing\s+)?" + PROGRAMME
        + r"\s+(?:back\s+)?to\s+(?:a\s+total\s+of\s+)?" + V,
        r"(?:increased|expanded|upsized|replenished|raised)\s+" + SA + r"\s+(?:existing\s+)?" + PROGRAMME
        + r"\s+(?:back\s+)?to\s+(?:a\s+total\s+of\s+)?" + V,
    ],
}
FORMULES = {sorte: [re.compile(m, re.I) for m in motifs] for sorte, motifs in FORMULES.items()}
RACHAT = re.compile(r"repurchas|buy-?backs?|buy\s+back", re.I)
CONSEIL = re.compile(r"\bboard\b|\bdirectors\b", re.I)
AUTRE_TITRE = re.compile(r"\bnotes?\b|debentures?|\bbonds?\b|\bsenior\b|convertible|preferred|warrants?|trust\s+account"
                         r"|redemption|repurchase\s+agreement|tender\s+offer|\bunits?\b(?!\s+of\s+(?:the\s+)?partnership)",
                         re.I)
ANCIEN = re.compile(r"previously\s+(?:announced|reported|disclosed|authorized|authorised|approved|adopted)|\bprior\b"
                    r"|\bprevious\b|\bremain(?:ing|s|ed)?\b|available\s+under|\bas\s+of\b|\bhad\s+(?:previously\s+)?"
                    r"(?:approved|authorized|authorised)|since\s+(?:its\s+|the\s+)?inception|cumulative", re.I)
# Une autorisation qui dépend d'autre chose (ex. Inogen : « Subject to the closing of the transaction ») : pas encore réelle
CONDITION = re.compile(r"subject\s+to\s+(?:the\s+)?(?:closing|completion|consummation|approval)|upon\s+(?:the\s+)?"
                       r"(?:closing|completion|consummation)|contingent\s+(?:on|upon)|conditioned\s+(?:on|upon)", re.I)
DATE = re.compile(r"\b(" + "|".join(MOIS) + r")(?:\s+(\d{1,2}),?)?\s+(\d{4})\b")
ANNEE = re.compile(r"\b(20\d\d)\b")
# Pas de coupure de phrase après ces abréviations (« Accenture plc », « Inc. », « U.S. »)
ABREVIATIONS = {"Inc", "Corp", "Co", "Ltd", "Mr", "Ms", "Mrs", "Dr", "Jr", "Sr", "St", "No", "Nos", "U.S", "N.V", "S.A",
                "L.P", "L.L.C", "LLC", "plc", "approx", "vs", "e.g", "i.e", "U.K", "Bros", "Mfg", "Intl", "Hldgs", "Cos",
                "Ph.D", "Corps", "Assn", "Natl", "Svcs", "Grp", "Tech", "Ltda", "Pty", "Ave", "Blvd"}
FIN_DE_PHRASE = re.compile(
    r"[.!?][”\"’)]*\s+|\s+(?=[•●▪])"
    # Ligne de date d'un communiqué : « COLUMBIA, Mo., October 1, 2026 – American Outdoor Brands… », « /PRNewswire/ -- »
    r"|(?<=\d{4})\s*(?:/\s*[A-Za-z][A-Za-z .]*/)?\s*(?:–|—|--)\s*(?=[A-Z])|(?<=\d{4})\s+-\s+(?=[A-Z])|\((?:BUSINESS|GLOBE)\s+(?:WIRE|NEWSWIRE)\)\s*(?:--|–|—)?\s*"
    # Titre d'un point du 8-K sans ponctuation : « Item 8.01.Other Events On September 30, 2026, … »
    r"|\bItem\s+\d\.\d\d\.?\s*(?:Other\s+Events|Regulation\s+FD\s+Disclosure|Results\s+of\s+Operations\s+and\s+"
    r"Financial\s+Condition)\.?\s*")
SORTES = {"nouveau": "Nouveau programme", "hausse": "Programme augmenté", "total": "Plafond total porté à ce montant"}
LIBELLES_PLAFOND = {"nouveau": "Plafond autorisé", "hausse": "Ajouté au plafond", "total": "Nouveau plafond total"}


def phrases(texte: str) -> list[str]:
    """Les phrases d'un texte, sans couper après une abréviation (« Inc. », « U.S. ») ni avant une minuscule ou un
    chiffre ; une puce (•) commence une nouvelle phrase."""
    out, debut = [], 0
    for m in FIN_DE_PHRASE.finditer(texte):
        if texte[m.start()] == ".":
            mot = re.search(r"([A-Za-z.]+)$", texte[debut:m.start()])
            mot = mot.group(1) if mot else ""
            suite = texte[m.end():m.end() + 1]
            if mot in ABREVIATIONS or re.fullmatch(r"[A-Z]", mot) or (suite and (suite.islower() or suite.isdigit())):
                continue
        p = texte[debut:m.end()].strip()
        if p:
            out.append(p)
        debut = m.end()
    if texte[debut:].strip():
        out.append(texte[debut:].strip())
    return out


def valeur(m: re.Match) -> tuple[float | None, float | None]:
    """(dollars, actions) d'une formule trouvée."""
    if m.group("n"):
        n = float(m.group("n").replace(",", ""))
        unite = (m.group("u") or "").lower()
        return n * {"million": 1e6, "m": 1e6, "mm": 1e6, "billion": 1e9, "bn": 1e9, "b": 1e9, "thousand": 1e3}.get(unite, 1), None
    a = m.group("a")
    return None, float(a.replace(",", "").replace("million", "").strip()) * (1e6 if "million" in a else 1)


def vieille_date(phrase: str, depose: date) -> str | None:
    """Une date de plus de 60 jours avant le dépôt, ou une année passée écrite seule."""
    for mois, jour, annee in DATE.findall(phrase):
        d = date(int(annee), MOIS.index(mois) + 1, min(int(jour), 28) if jour else 28)
        if (depose - d).days > JOURS_MAX:
            return f"{mois} {jour + ', ' if jour else ''}{annee}"
    for annee in ANNEE.findall(DATE.sub(" ", phrase)):
        if int(annee) < depose.year:
            return annee
    return None


def dates_completes(texte: str) -> set[date]:
    """Les dates écrites au complet (« October 1, 2026 »)."""
    out = set()
    for mois, jour, annee in DATE.findall(texte):
        if jour:
            try:
                out.add(date(int(annee), MOIS.index(mois) + 1, int(jour)))
            except ValueError:
                pass
    return out


def analyser(phrase: str, depose: date) -> dict:
    """{'sorte', 'dollars', 'actions', 'formule'} si la phrase annonce un rachat selon la règle stricte, sinon
    {'rejet': raison}."""
    if not RACHAT.search(phrase):
        return {"rejet": "pas un rachat"}
    if len(phrase) > PHRASE_MAX:
        return {"rejet": "trop longue (tableau)"}
    trouve = next(((sorte, m) for sorte, motifs in FORMULES.items() for motif in motifs
                   if (m := motif.search(phrase))), None)
    if trouve is None:
        return {"rejet": "aucune formule d'autorisation"}
    sorte, m = trouve
    if not CONSEIL.search(phrase):
        return {"rejet": "conseil pas nommé"}
    if t := AUTRE_TITRE.search(phrase):
        return {"rejet": f"autre titre : {t.group(0)}"}
    if c := CONDITION.search(phrase):
        return {"rejet": f"conditionnel : {c.group(0)}"}
    if a := ANCIEN.search(phrase[:m.end()]):
        return {"rejet": f"ancien programme : {a.group(0)}"}
    if v := vieille_date(phrase, depose):
        return {"rejet": f"ancienne date : {v}"}
    dollars, actions = valeur(m)
    if dollars is not None and dollars < 1_000_000:
        return {"rejet": "montant illisible"}
    return {"sorte": sorte, "dollars": dollars, "actions": actions, "formule": m.group(0)}




def decision(trouves: list[dict]) -> dict:
    """Une annonce par dépôt : un nouveau programme ou une hausse l'emporte sur un total ; ensuite, toutes les phrases
    retenues doivent dire la même chose (sorte et montant)."""
    if any(t["sorte"] != "total" for t in trouves):
        trouves = [t for t in trouves if t["sorte"] != "total"]
    if not trouves:
        return {"statut": "rien"}
    cles = {(t["sorte"], t["dollars"], t["actions"]) for t in trouves}
    if len(cles) > 1:
        return {"statut": "contradictoire", "cles": sorted(map(str, cles))}
    sorte, dollars, actions = cles.pop()
    return {"statut": "annonce", "sorte": sorte, "dollars": dollars, "actions": actions}


CANDIDAT = RACHAT
