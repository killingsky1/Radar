"""Lot H : détecteur STRICT des annonces de rachat d'actions dans un 8-K (prototype du labo, indépendant du robot).

Une annonce est retenue seulement si UNE phrase contient tout ceci :
- une formule d'autorisation (« approved a new $X share repurchase program », « an additional authorization to
  repurchase up to $X », « $X in additional share repurchase authority approved by »…) ;
- le conseil d'administration (« Board » ou « directors ») ;
- aucun mot qui montre un ancien programme décrit de nouveau (« previously announced », « remaining », « prior »…)
  avant la fin de la formule, et aucune autre sorte de titre (dette, actions privilégiées, bons, fiducie de SPAC…) ;
- aucune date de plus de 60 jours avant le dépôt (ni une année passée seule).
"""
import re
from datetime import date

MOIS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November",
        "December"]
DOL = (r"(?<![A-Za-z])(?:US)?\$\s?(?P<n>\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
       r"(?:\s*(?P<u>million|billion|thousand|bn\b|mm\b|[MB]\b))?")
ACT = r"(?P<a>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?\s*million)\s+(?:(?:of\s+)?(?:its|our|the\s+Company['’]s)\s+)?(?:outstanding\s+)?(?:ordinary\s+|common\s+|Class\s+[A-C]\s+(?:common\s+)?)?(?:shares|stock)"
V = f"(?:{DOL}|{ACT})"
VERBE = r"(?:approved|authorized|authorised|adopted)"
OBJET = r"(?:share\s+|stock\s+|equity\s+)?(?:repurchase|buy-?back)"
PROG = OBJET + r"\s+(?:program|programme|plan|authori[sz]ation)"
TROU = r"(?:(?!dividend|\bnotes?\b|debt)[^.$;]){0,80}?"
AGREGAT = r"(?:an?\s+(?:aggregate|total)\s+(?:amount\s+)?(?:of\s+)?)?"
NOUVEAU = [
    VERBE + r"\s+(?:a|an|the)\s+(?:new\s+)?" + PROG + TROU + r"\b(?:up\s+to|of|for|totaling|totalling|in\s+the\s+amount\s+of)\s+" + AGREGAT + r"(?:up\s+to\s+)?" + V,
    VERBE + r"\s+(?:a|an)\s+(?:new\s+)?" + V + r"\s+" + OBJET + r"(?:\s+(?:program|programme|plan|authori[sz]ation))?",
    VERBE + r"\s+(?:the\s+)?(?:re)?purchase\s+of\s+" + AGREGAT + r"up\s+to\s+" + V,
    VERBE + r"\s+an?\s+(?:new\s+)?(?:program|programme|plan)\s+to\s+(?:re)?purchase\s+(?:up\s+to\s+)?" + V,
    VERBE + r"\s+(?:the\s+Company|us|it|management)\s+to\s+(?:re)?purchase\s+" + AGREGAT + r"up\s+to\s+" + V,
    V + r"\s+(?:new\s+)?" + PROG + r"\s+(?:was\s+|has\s+been\s+)?(?:approved|authorized|authorised)\s+by",
]
PLUS = r"(?:additional|incremental)"
HAUSSE = [
    VERBE + r"\s+an?\s+" + PLUS + r"\s+(?:share\s+|stock\s+)?(?:repurchase\s+)?authori(?:[sz]ation|ty)\s+to\s+(?:re)?purchase\s+(?:up\s+to\s+)?" + V,
    VERBE + r"\s+an?\s+" + PLUS + r"\s+" + V + r"\s+(?:for|of|in|to|under)\s+(?:the\s+|its\s+|our\s+)?(?:existing\s+)?" + OBJET + r"s?",
    VERBE + r"\s+an?\s+" + PLUS + r"\s+" + V + r"\s+" + OBJET,
    V + r"\s+(?:in\s+)?" + PLUS + r"\s+" + OBJET + r"\s+authori(?:ty|[sz]ation)\s+(?:was\s+|has\s+been\s+)?(?:approved|authorized|authorised)",
    r"(?:increased|expanded|upsized)\s+(?:its|the|our|the\s+Company['’]s)\s+(?:existing\s+)?" + PROG + r"\s+by\s+(?:an\s+additional\s+)?" + V,
    VERBE + r"\s+an?\s+" + V + r"\s+(?:increase|expansion|addition)\s+(?:to|in|of)\s+(?:its|the|our)\s+(?:existing\s+)?" + PROG,
    VERBE + r"\s+an?\s+(?:increase|expansion)\s+(?:of|in\s+the\s+amount\s+of)\s+" + V + r"\s+(?:to|in)\s+(?:its|the|our)\s+(?:existing\s+)?" + PROG,
]
TITRES = re.compile(r"\bnotes?\b|debentures?|\bbonds?\b|\bsenior\b|convertible|preferred|warrants?|trust\s+account"
                    r"|redemption|repurchase\s+agreement|tender\s+offer|\bunits?\b(?!\s+of\s+(?:the\s+)?partnership)", re.I)
ANCIEN = re.compile(r"previously\s+(?:announced|reported|disclosed|authorized|authorised|approved|adopted)|\bprior\b"
                    r"|\bprevious\b|\bremain(?:ing|s|ed)?\b|available\s+under|\bas\s+of\b|\bhad\s+(?:previously\s+)?"
                    r"(?:approved|authorized|authorised)|since\s+(?:its\s+|the\s+)?inception|cumulative", re.I)
CANDIDAT = re.compile(r"repurchas|buy-?backs?|buy\s+back", re.I)
CONSEIL = re.compile(r"\bboard\b|\bdirectors\b", re.I)
DATE = re.compile(r"\b(" + "|".join(MOIS) + r")(?:\s+(\d{1,2}),?)?\s+(\d{4})\b")
ANNEE = re.compile(r"\b(20\d\d)\b")
ABREV = {"Inc", "Corp", "Co", "Ltd", "Mr", "Ms", "Mrs", "Dr", "Jr", "Sr", "St", "No", "Nos", "U.S", "N.V", "S.A", "L.P",
         "L.L.C", "LLC", "plc", "approx", "vs", "e.g", "i.e", "U.K", "Bros", "Mfg", "Intl", "Hldgs", "Cos", "Ph.D",
         "Corps", "Inc.,", "Assn", "Natl", "Svcs", "Grp", "Tech", "Ltda", "Pty", "Ave", "Blvd"}
FIN = re.compile(r"[.!?][”\"’)]*\s+|\s+(?=[•●▪])")


def phrases(t: str) -> list[str]:
    """Phrases d'un texte ; pas de coupure après une abréviation (« Inc. », « U.S. ») ni avant une minuscule."""
    out, debut = [], 0
    for m in FIN.finditer(t):
        if t[m.start()] == ".":
            mot = re.search(r"([A-Za-z.]+)$", t[debut:m.start()])
            mot = mot.group(1) if mot else ""
            suite = t[m.end():m.end() + 1]
            if mot in ABREV or re.fullmatch(r"[A-Z]", mot) or (suite and (suite.islower() or suite.isdigit())):
                continue
        p = t[debut:m.end()].strip()
        if p:
            out.append(p)
        debut = m.end()
    if t[debut:].strip():
        out.append(t[debut:].strip())
    return out


def valeur(m) -> tuple[float | None, float | None]:
    """(dollars, actions) d'une formule trouvée."""
    if m.group("n"):
        n = float(m.group("n").replace(",", ""))
        u = (m.group("u") or "").lower()
        mult = {"million": 1e6, "m": 1e6, "mm": 1e6, "billion": 1e9, "bn": 1e9, "b": 1e9, "thousand": 1e3}.get(u, 1)
        return n * mult, None
    a = m.group("a")
    return None, float(a.replace(",", "").replace("million", "").strip()) * (1e6 if "million" in a else 1)


def vieille_date(phrase: str, depose: date) -> str | None:
    """Une date de plus de 60 jours avant le dépôt, ou une année passée écrite seule : un ancien programme."""
    for mo, j, a in DATE.findall(phrase):
        d = date(int(a), MOIS.index(mo) + 1, min(int(j), 28) if j else 28)
        if (depose - d).days > 60:
            return f"{mo} {j + ', ' if j else ''}{a}"
    reste = DATE.sub(" ", phrase)
    for a in ANNEE.findall(reste):
        if int(a) < depose.year:
            return a
    return None


def analyser(phrase: str, depose: date) -> dict:
    """{'sorte': 'nouveau'|'hausse', 'dollars', 'actions', 'formule'} ou {'rejet': raison}."""
    if not CANDIDAT.search(phrase):
        return {"rejet": "pas un rachat"}
    if len(phrase) > 1500:
        return {"rejet": "phrase trop longue (tableau ?)"}
    trouve = None
    for sorte, motifs in (("hausse", HAUSSE), ("nouveau", NOUVEAU)):
        for motif in motifs:
            m = re.search(motif, phrase, re.I)
            if m:
                trouve = (sorte, m)
                break
        if trouve:
            break
    if not trouve:
        return {"rejet": "aucune formule d'autorisation"}
    sorte, m = trouve
    if not CONSEIL.search(phrase):
        return {"rejet": "conseil d'administration pas nommé"}
    t = TITRES.search(phrase)
    if t:
        return {"rejet": f"autre titre : « {t.group(0)} »"}
    a = ANCIEN.search(phrase[:m.end()])
    if a:
        return {"rejet": f"ancien programme : « {a.group(0)} »"}
    v = vieille_date(phrase, depose)
    if v:
        return {"rejet": f"ancienne date : « {v} »"}
    dollars, actions = valeur(m)
    if dollars is not None and dollars < 1_000_000:
        return {"rejet": f"montant illisible ({dollars:g} $)"}
    return {"sorte": sorte, "dollars": dollars, "actions": actions, "formule": m.group(0)}


def decision(trouves: list[dict]) -> dict:
    """Une annonce par dépôt : toutes les phrases retenues doivent dire la même chose (sorte et montant)."""
    if not trouves:
        return {"statut": "rien"}
    cles = {(t["sorte"], t["dollars"], t["actions"]) for t in trouves}
    if len(cles) > 1:
        return {"statut": "contradictoire", "cles": sorted(map(str, cles))}
    sorte, dollars, actions = cles.pop()
    return {"statut": "annonce", "sorte": sorte, "dollars": dollars, "actions": actions}
