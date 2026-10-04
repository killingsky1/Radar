"""Lot H : détecteur STRICT des annonces de rachat d'actions dans un 8-K, pour le labo : même règle que le robot (copiée
à la main de robot/radar/collecteurs/rachats.py, version 2), aucun import du robot. Voir la règle dans ce fichier-là.
"""
import re
from datetime import date

MONTANT_MIN = 10_000_000
JOURS_MAX = 30  # une date plus vieille dans la phrase : un ancien programme décrit de nouveau
JOURS_AVANCE = 400  # une date à venir (ex. « beginning August 10, 2026 ») montre aussi que l'annonce est récente
JOURS_MEME_ANNONCE = 30  # même compagnie, même sorte, même montant dans un autre 8-K : la même annonce
PHRASE_MAX = 1500  # au-delà, c'est un tableau aplati, pas une phrase
MOIS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
        "December")
MOIS_COURTS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "Jun": 6, "Jul": 7, "Aug": 8, "Sep": 9, "Sept": 9, "Oct": 10,
               "Nov": 11, "Dec": 12}

DOLLARS = (r"(?<![A-Za-z])(?:US)?\$\s?(?P<n>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
           r"(?:\s*(?P<u>million|billion|thousand|bn\b|mm\b|[MB]\b))?")
ACTIONS = (r"(?P<a>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?\s*million)\s+(?:(?:of\s+)?(?:its|our|the\s+Company['’]s)\s+)?"
           r"(?:outstanding\s+)?(?:ordinary\s+|common\s+|Class\s+[A-C]\s+(?:common\s+)?)?(?:shares|stock)")
V = f"(?:{DOLLARS}|{ACTIONS})"
VERBE = r"(?:approved|authorized|authorised|adopted)"
OBJET = r"(?:(?:common\s+)?(?:share|stock|equity)\s+)?(?:repurchase|buy-?back)"
PROGRAMME = OBJET + r"\s+(?:program|programme|plan|authori[sz]ation)"
# « its », « our », « the Company's », ou le nom de la compagnie au possessif (« Evertec's », « Diamondback's »)
SA = r"(?:its|the|our|the\s+Company['’]s|[A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,3}['’]s)"
QUALIF = r"(?:existing\s+|aggregate\s+|total\s+|current\s+)?"
PAREN = r"(?:\s*\([^()]{0,80}\))?"  # « (the “SRP”) », « (exclusive of fees and commissions) »
ADJ = r"(?:(?:new|expanded|enhanced|amended|renewed|refreshed|additional)\s+)?"
# Entre le programme et le montant : pas un autre sujet (dividende, dette), ni une hausse (alors c'est une « hausse »)
TROU = r"(?:(?!dividend|\bnotes?\b|debt|increase|additional|incremental|expan)[^.$;]){0,120}?"
AGREGAT = r"(?:an?\s+(?:aggregate|total)\s+(?:amount\s+)?(?:of\s+)?)?"
PLUS = r"(?:additional|incremental)"
HAUSSE_DE = r"(?:\bby\s+(?:an\s+additional\s+)?|\bup\s+to\s+an\s+additional\s+|\ban\s+additional\s+)"
FORMULES = {
    "hausse": [
        VERBE + r"\s+an?\s+" + PLUS + r"\s+(?:share\s+|stock\s+)?(?:repurchase\s+)?authori(?:[sz]ation|ty)\s+to\s+"
        r"(?:re)?purchase\s+(?:up\s+to\s+)?" + V,
        VERBE + r"\s+an?\s+" + PLUS + r"\s+" + V + r"\s+(?:for|of|in|to|under)\s+(?:" + SA + r"\s+)?" + QUALIF
        + OBJET + r"s?",
        VERBE + r"\s+an?\s+" + PLUS + r"\s+" + V + r"\s+" + OBJET,
        V + r"\s+(?:in\s+)?" + PLUS + r"\s+" + OBJET + r"\s+authori(?:ty|[sz]ation)\s+(?:was\s+|has\s+been\s+)?"
        r"(?:approved|authorized|authorised)",
        r"(?:increased|expanded|upsized)\s+" + SA + r"\s+" + QUALIF + PROGRAMME + PAREN + r"\s+by\s+(?:an\s+additional\s+)?"
        + V,
        VERBE + r"\s+an?\s+" + V + r"\s+(?:increase|expansion|addition)\s+(?:to|in|of)\s+" + SA + r"\s+" + QUALIF
        + PROGRAMME,
        VERBE + r"\s+an?\s+(?:increase|expansion)\s+(?:of|in\s+the\s+amount\s+of)\s+" + V + r"\s+(?:to|in)\s+" + SA
        + r"\s+" + QUALIF + PROGRAMME,
        # « approved the upsizing of its existing share repurchase program (…) by $1.5 billion » (Talen Energy),
        # « authorized an increase (the “Additional Authorization”) to its existing share repurchase program pursuant to
        # which the Company may purchase up to an additional $500.0 million » (CoreCivic)
        VERBE + r"\s+(?:the|an?)\s+(?:upsizing|upsize|increase|expansion)" + PAREN + r"\s+(?:of|to|in)\s+" + SA + r"\s+"
        + QUALIF + PROGRAMME + r"[^;]{0,250}?" + HAUSSE_DE + V,
        # « authorized an increase to its share repurchase program of $1 billion » (BorgWarner), « … program (the “Stock
        # Buyback Program”) of an additional $100 million » (BlackLine)
        VERBE + r"\s+an?\s+(?:increase|expansion)\s+(?:to|in)\s+" + SA + r"\s+" + QUALIF + PROGRAMME + PAREN
        + r"\s+(?:of|by)\s+(?:an\s+additional\s+)?" + V,
        # « approved a share repurchase authorization increase of $15 million » (ATN International)
        VERBE + r"\s+(?:a|an|the)\s+" + PROGRAMME + r"\s+(?:increase|expansion)\s+(?:of|in\s+the\s+amount\s+of)\s+" + V,
        # « has authorized the repurchase of up to an additional 832,000 shares » (HomeTrust)
        VERBE + r"\s+(?:the\s+)?(?:re)?purchase\s+of\s+up\s+to\s+an\s+additional\s+" + V,
        VERBE + r"\s+an?\s+authori[sz]ation\s+(?:for\s+the\s+Company\s+)?to\s+(?:re)?purchase\s+(?:up\s+to\s+)?"
        r"an\s+additional\s+" + V,
    ],
    "nouveau": [
        VERBE + r"\s+(?:a|an|the)\s+" + ADJ + PROGRAMME + PAREN + TROU + r"\b(?:up\s+to|of|for|totaling|totalling|"
        r"in\s+the\s+amount\s+of)\s+" + AGREGAT + r"(?:up\s+to\s+)?" + V,
        VERBE + r"\s+(?:a|an)\s+" + ADJ + V + PAREN + r"\s+" + OBJET + r"(?:\s+(?:program|programme|plan|"
        r"authori[sz]ation))?",
        # « approved a new $3.0 billion authorization to repurchase its common stock » (MetLife)
        VERBE + r"\s+(?:a|an)\s+" + ADJ + V + r"\s+(?:share\s+|stock\s+)?(?:repurchase\s+|buy-?back\s+)?"
        r"authori[sz]ation\s+to\s+(?:re)?purchase",
        VERBE + r"\s+(?:the\s+)?(?:re)?purchase\s+of\s+" + AGREGAT + r"up\s+to\s+" + V,
        VERBE + r"\s+an?\s+" + ADJ + r"(?:program|programme|plan)\s+to\s+(?:re)?purchase\s+(?:up\s+to\s+)?" + V,
        VERBE + r"\s+(?:the\s+Company|us|it|management)\s+to\s+(?:re)?purchase\s+" + AGREGAT + r"up\s+to\s+" + V,
    ],
    # Le nouveau plafond TOTAL (le montant ajouté n'est pas écrit) : « approved an increase to the Company's share
    # repurchase authorization to $1.5 billion » (Lear), « has increased our share buyback authorization back to $250
    # million » (Jefferies), « doubled the Company's share repurchase authorization to $16.0 billion » (Diamondback).
    # Gardé seulement si le dépôt n'annonce pas aussi un nouveau programme ou une hausse.
    "total": [
        VERBE + r"\s+(?:the|an?)\s+(?:increase|expansion|doubling)" + PAREN + r"\s+(?:to|in|of)\s+(?:" + SA + r"\s+)?"
        + QUALIF + PROGRAMME + PAREN + r"\s+(?:back\s+)?(?:up\s+)?to\s+(?:a\s+total\s+of\s+|an\s+aggregate\s+(?:of\s+)?)?"
        + V,
        r"(?:(?:refreshed|renewed)\s+and\s+)?(?:increased|expanded|upsized|replenished|raised|doubled|refreshed)\s+" + SA
        + r"\s+" + QUALIF + PROGRAMME + PAREN + r"\s+(?:back\s+)?(?:up\s+)?to\s+(?:a\s+total\s+of\s+|an\s+aggregate\s+"
        r"(?:of\s+)?)?" + V,
        # « approved an increase to Evertec's existing share repurchase authorization to permit future repurchases of up
        # to an aggregate of $150 million » (Evertec)
        VERBE + r"\s+an?\s+(?:increase|expansion)\s+to\s+" + SA + r"\s+" + QUALIF + PROGRAMME + r"[^;$]{0,80}?\bup\s+to\s+"
        r"(?:an\s+aggregate\s+of\s+|a\s+total\s+of\s+)?" + V,
    ],
}
FORMULES = {sorte: [re.compile(m, re.I) for m in motifs] for sorte, motifs in FORMULES.items()}
RACHAT = re.compile(r"repurchas|buy-?backs?|buy\s+back", re.I)
CONSEIL = re.compile(r"\bboard\b|\bdirectors\b", re.I)
AUTRE_TITRE = re.compile(r"\bnotes?\b|debentures?|\bbonds?\b|\bsenior\b|convertible|preferred|warrants?|trust\s+account"
                         r"|redemption|(?<!accelerated )(?<!accelerated share )repurchase\s+agreement|tender\s+offer"
                         r"|\bunits?\b(?!\s+of\s+(?:the\s+)?partnership)", re.I)
ANCIEN = re.compile(r"previously\s+(?:announced|reported|disclosed|authorized|authorised|approved|adopted)|\bprior\b"
                    r"|\bprevious\b|\bremain(?:ing|s|ed)?\b|available\s+under|\bas\s+of\b|\bhad\s+previously\b"
                    r"|since\s+(?:its\s+|the\s+)?inception|cumulative"
                    # une définition, pas une annonce (Exzeo : « Share Repurchase Program was the program which … »)
                    r"|\bwas\s+the\s+(?:program|programme|plan|authori[sz]ation)\b|\brefers?\s+to\b|\bmeans\b"
                    r"|\bdefined\s+as\b", re.I)
# Après la formule : « as previously announced » dit que ce n'est pas nouveau ; « prior », « replacing »… : la suite parle
# d'un autre programme (ex. LifeStance : « which replaces the Company's prior $100 million repurchase program approved
# … on February 24, 2026 » : cette date est celle de l'ancien programme, pas du nouveau)
DEJA_ANNONCE = re.compile(r"previously\s+(?:announced|reported|disclosed)|as\s+previously", re.I)
AUTRE_PROGRAMME = re.compile(r"\bprior\b|\bprevious\b|\breplac\w*|\bexisting\b|\bsupersed\w*|\bfollow\w*", re.I)
# Une autorisation qui dépend d'autre chose (ex. Inogen : « Subject to the closing of the transaction ») : pas encore réelle
CONDITION = re.compile(r"subject\s+to\s+(?:the\s+)?(?:closing|completion|consummation|approval)|upon\s+(?:the\s+)?"
                       r"(?:closing|completion|consummation)|contingent\s+(?:on|upon)|conditioned\s+(?:on|upon)", re.I)
# Une annonce RÉCENTE se reconnaît : une date de moins de 30 jours (ou à venir), « today », « has approved »… Sans ce
# signe, la phrase décrit souvent un programme déjà connu (diapo d'une présentation, avertissement légal, note).
RECENT = re.compile(r"\btoday\b|\brecently\b|\bannounc\w*|\b(?:has|have)\s+(?:also\s+|now\s+|recently\s+)?(?:approved|"
                    r"authorized|authorised|adopted|increased|expanded|upsized|doubled|refreshed|replenished|renewed)", re.I)
DATE = re.compile(r"\b(" + "|".join(MOIS) + r"|" + "|".join(MOIS_COURTS) + r")\.?(?:\s+(\d{1,2})(?:st|nd|rd|th)?)?"
                  r"(?:,?\s+(\d{4}))?\b")
ANNEE = re.compile(r"\b(20\d\d)\b")
# Pas de coupure de phrase après ces abréviations (« Accenture plc », « Inc. », « U.S. »)
ABREVIATIONS = {"Inc", "Corp", "Co", "Ltd", "Mr", "Ms", "Mrs", "Dr", "Jr", "Sr", "St", "No", "Nos", "U.S", "N.V", "S.A",
                "L.P", "L.L.C", "LLC", "plc", "approx", "vs", "e.g", "i.e", "U.K", "Bros", "Mfg", "Intl", "Hldgs", "Cos",
                "Ph.D", "Corps", "Assn", "Natl", "Svcs", "Grp", "Tech", "Ltda", "Pty", "Ave", "Blvd"}
FIN_DE_PHRASE = re.compile(
    r"[.!?][”\"’)]*\s+|\s+(?=[•●▪])"
    # Ligne de date d'un communiqué : « COLUMBIA, Mo., October 1, 2026 – American Outdoor Brands… », « /PRNewswire/ -- »
    r"|(?<=\d{4})\s*(?:/\s*[A-Za-z][A-Za-z .]*/)?\s*(?:–|—|--)\s*(?=[A-Z])|(?<=\d{4})\s+-\s+(?=[A-Z])|,\s+[–—]\s+(?=[A-Z])|\((?:BUSINESS|GLOBE)\s+(?:WIRE|NEWSWIRE)\)\s*(?:--|–|—)?\s*"
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


def dates_ecrites(texte: str, depose: date) -> list[tuple[date, bool]]:
    """Les dates écrites, (date, jour écrit). « September 2026 » : le 1er du mois (le plus ancien possible) ;
    « August 3 » sans année : l'année du dépôt (l'année d'avant si la date serait plus de 30 jours après le dépôt)."""
    out = []
    for m in DATE.finditer(texte):
        nom, jour, annee = m.group(1), m.group(2), m.group(3)
        if not jour and not annee:
            continue  # un mois seul (« In July ») : pas une date
        mois = MOIS.index(nom) + 1 if nom in MOIS else MOIS_COURTS[nom]
        try:
            if annee:
                d = date(int(annee), mois, int(jour) if jour else 1)
            else:
                d = date(depose.year, mois, int(jour))
                if (d - depose).days > JOURS_MAX:
                    d = date(depose.year - 1, mois, int(jour))
        except ValueError:
            continue
        out.append((d, bool(jour)))
    return out


def vieille_date(phrase: str, depose: date) -> str | None:
    """Une date de plus de 30 jours avant le dépôt, ou une année passée écrite seule (« 2025 Repurchase Program »)."""
    for d, _ in dates_ecrites(phrase, depose):
        if (depose - d).days > JOURS_MAX:
            return d.isoformat()
    for annee in ANNEE.findall(DATE.sub(" ", phrase)):
        if int(annee) < depose.year:
            return annee
    return None


def zone_du_programme(phrase: str, m: re.Match) -> str:
    """La phrase jusqu'à la fin de la formule, puis la suite tant qu'elle ne parle pas d'un autre programme."""
    suite = phrase[m.end():]
    autre = AUTRE_PROGRAMME.search(suite)
    return phrase[:m.end() + (autre.start() if autre else len(suite))]


def recente(phrase: str, depose: date) -> bool:
    """Un signe que l'annonce est récente : « today », « has approved »…, ou une date de moins de 30 jours (ou à venir)."""
    return bool(RECENT.search(phrase)) or any(-JOURS_AVANCE <= (depose - d).days <= JOURS_MAX
                                              for d, _ in dates_ecrites(phrase, depose))


def analyser(phrase: str, depose: date) -> dict:
    """{'sorte', 'dollars', 'actions', 'formule'} si la phrase annonce un rachat selon la règle stricte, sinon
    {'rejet': raison} (avec 'cle' quand une formule a été trouvée)."""
    if not RACHAT.search(phrase):
        return {"rejet": "pas un rachat"}
    if len(phrase) > PHRASE_MAX:
        return {"rejet": "trop longue (tableau)"}
    trouve = next(((sorte, m) for sorte, motifs in FORMULES.items() for motif in motifs
                   if (m := motif.search(phrase))), None)
    if trouve is None:
        return {"rejet": "aucune formule d'autorisation"}
    sorte, m = trouve
    dollars, actions = valeur(m)
    cle = (sorte, dollars, actions)
    if not CONSEIL.search(phrase):
        return {"rejet": "conseil pas nommé", "cle": cle}
    if t := AUTRE_TITRE.search(phrase):
        return {"rejet": f"autre titre : {t.group(0)}", "cle": cle}
    if c := CONDITION.search(phrase):
        return {"rejet": f"conditionnel : {c.group(0)}", "cle": cle}
    if a := ANCIEN.search(phrase[:m.end()]):
        return {"rejet": f"ancien programme : {a.group(0)}", "cle": cle}
    if d := DEJA_ANNONCE.search(phrase[m.end():]):
        return {"rejet": f"ancien programme : {d.group(0)}", "cle": cle}
    if v := vieille_date(zone_du_programme(phrase, m), depose):
        return {"rejet": f"ancienne date : {v}", "cle": cle}
    if not recente(phrase, depose):
        return {"rejet": "pas de signe d'une annonce récente", "cle": cle}
    if dollars is not None and dollars < 1_000_000:
        return {"rejet": "montant illisible", "cle": cle}
    return {"sorte": sorte, "dollars": dollars, "actions": actions, "formule": m.group(0)}




def decider(docs, depose: date) -> dict:
    """docs : [(sorte du document, texte)]. La même décision que le robot : un nouveau programme ou une hausse l'emporte
    sur un total ; toutes les phrases retenues disent la même chose ; le même programme daté de plus de 30 jours ailleurs
    dans le dépôt : rien ; moins de 10 M$ : rien."""
    trouves, vieilles = [], set()
    for typ, texte in docs:
        for p in phrases(texte):
            if not RACHAT.search(p):
                continue
            a = analyser(p, depose)
            if "sorte" in a:
                trouves.append({**a, "doc": typ, "phrase": p})
            elif a["rejet"].startswith("ancienne date"):
                vieilles.add(a["cle"])
    if any(t["sorte"] != "total" for t in trouves):
        trouves = [t for t in trouves if t["sorte"] != "total"]
    if not trouves:
        return {"statut": "rien"}
    cles = {(t["sorte"], t["dollars"], t["actions"]) for t in trouves}
    if len(cles) > 1:
        return {"statut": "contradictoire", "cles": sorted(map(str, cles))}
    cle = cles.pop()
    if cle in vieilles:
        return {"statut": "même programme daté de plus de 30 jours", "cle": str(cle)}
    if cle[1] is not None and cle[1] < MONTANT_MIN:
        return {"statut": "moins de 10 M$", "cle": str(cle)}
    return {"statut": "annonce", "sorte": cle[0], "dollars": cle[1], "actions": cle[2],
            "phrases": [(t["doc"], t["phrase"]) for t in trouves]}


def decision(trouves: list[dict]) -> dict:
    """Pour des extraits déjà retenus (contre-vérification d'une annonce publiée) : même sorte et même montant partout."""
    if any(t["sorte"] != "total" for t in trouves):
        trouves = [t for t in trouves if t["sorte"] != "total"]
    cles = {(t["sorte"], t["dollars"], t["actions"]) for t in trouves}
    if len(cles) != 1:
        return {"statut": "rien" if not cles else "contradictoire"}
    sorte, dollars, actions = cles.pop()
    return {"statut": "annonce", "sorte": sorte, "dollars": dollars, "actions": actions}


CANDIDAT = RACHAT
