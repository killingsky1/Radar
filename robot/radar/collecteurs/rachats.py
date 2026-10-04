"""Rachats d'actions (lot H) : information seulement, 0 point dans la note.

1. Annonces (source « sec_rachats ») : un 8-K où le conseil d'administration AUTORISE la compagnie à racheter ses
   actions jusqu'à un plafond. Ce n'est pas un achat fait : la compagnie peut racheter moins, ou rien, souvent sur
   plusieurs années. Trois sortes : nouveau programme, hausse (le montant ajouté) et plafond total (« porté à X » :
   seulement si le dépôt n'écrit pas aussi le montant ajouté).
   Lecture : comme les participations du gouvernement, les 8-K du jour des compagnies cotées qui ont un point 2.02
   (résultats), 7.01 (communication au marché) ou 8.01 (autres événements) ; le document principal et les communiqués
   joints (EX-99), lus une seule fois par passage pour les deux lecteurs.
   Règle stricte (version 2) : une annonce est publiée seulement si une même phrase contient
   - une formule d'autorisation (« approved a new $X share repurchase program », « approved an additional
     authorization to repurchase up to $X », « authorized an increase to its share repurchase program of $X »,
     « approved an increase to the Company's share repurchase authorization to $X »…) ;
   - le conseil (« Board » ou « directors ») ;
   - un signe que l'annonce est RÉCENTE : une date de moins de 30 jours (ou à venir), « today », « has approved »…
     (sans ce signe, la phrase décrit souvent un programme déjà connu : diapo d'une présentation, avertissement légal,
     note de bas de page) ;
   - avant la fin de la formule, aucun mot qui montre un ancien programme (« previously announced », « remaining »,
     « prior », « as of », « was the program »…), ni « as previously announced » après ; nulle part, une autre sorte de
     titre (dette, actions privilégiées, bons de souscription, fiducie d'une SPAC, entente de rachat) ni une condition
     (« subject to the closing ») ;
   - aucune date de plus de 30 jours avant le dépôt pour CE programme (un mois sans jour compte pour le 1er du mois),
     ni une année passée écrite seule (« 2025 Repurchase Program ») ; une date écrite après « prior », « replacing »…
     est celle d'un autre programme et ne compte pas.
   Toutes les phrases retenues d'un même dépôt doivent dire la même chose (sorte et montant), sinon rien ; si le même
   programme est daté de plus de 30 jours ailleurs dans le dépôt, rien. La même annonce dans un autre 8-K de la
   compagnie (30 jours) : une seule fois. Seulement 10 M$ et plus (un nombre d'actions : dans le fil seulement, sans
   montant).
   Mesuré au labo (labo/mesure_lotH.py), dépôts lus en entier et revus à la main :
   - 10 jours (21 sept. au 2 oct. 2026 : 1 922 8-K, 981 lus) : 9 vraies annonces, 9 trouvées, aucune de trop ;
   - 1re mesure témoin (3 au 7 août 2026, 1 852 lus) avec la version 1 : 28 retenues dont 6 erreurs (3 programmes
     déjà connus décrits dans une diapo, un avertissement légal ou une note ; 1 mauvaise sorte ; 2 programmes de juin)
     et 2 douteuses (juillet), 14 vraies manquées ; la version 2 corrige ces cas (tests) ;
   - 2e mesure témoin (28 au 31 juillet 2026, jamais regardée) avec la version 2 : labo/resultats-lotH-temoin2.
2. Rachats faits (source « sec_rachats_xbrl ») : l'argent dépensé pour racheter ses actions pendant un exercice,
   déclaré par la compagnie dans son rapport annuel (étiquette XBRL « PaymentsForRepurchaseOfCommonStock »), lu sur
   l'API officielle de la SEC (data.sec.gov, « frames ») : un seul fichier pour toutes les compagnies. Montré sur la
   fiche des compagnies des listes.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from .. import emetteurs
from ..models import Evenement
from ..store import Depot
from ..validate import controle_source
from .gazette import details
from .participations import documents_8k, entete_8k
from .regulateurs import canonique
from .sec import empreinte_entete, lire_8k, lire_journees, nombre_fr, symboles
from .usaspending import argent

VERSION = "rachats-1"
# Descriptions officielles EDGAR (« ITEM INFORMATION » de l'en-tête)
POINTS_EDGAR = {"results of operations and financial condition": "2.02", "regulation fd disclosure": "7.01",
                "other events": "8.01"}
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


def points(entete: str) -> list[str]:
    """Les points 2.02, 7.01 et 8.01 écrits dans l'en-tête officiel du dépôt."""
    vus = []
    for desc in re.findall(r"ITEM INFORMATION:\s*([^\n<]+)", entete):
        p = POINTS_EDGAR.get(desc.strip().lower())
        if p and p not in vus:
            vus.append(p)
    return vus


def plafond(dollars: float | None, actions: float | None) -> str:
    return argent(dollars) if dollars is not None else f"{nombre_fr(actions)} actions"


def titre(nom: str, sorte: str, dollars: float | None, actions: float | None) -> str:
    if sorte == "hausse":
        return f"{nom} : programme de rachat d'actions augmenté de {plafond(dollars, actions)}"
    if sorte == "total":
        return f"{nom} : programme de rachat d'actions porté à {plafond(dollars, actions)} au total"
    return f"{nom} : nouveau programme de rachat d'actions, jusqu'à {plafond(dollars, actions)}"


def retenir(documents_lus, depose: date) -> tuple[list, tuple | None]:
    """`documents_lus` : [(adresse, sorte du document, texte)]. Retourne les documents retenus [(adresse, sorte,
    [(phrase, analyse)])] et la clé (sorte, dollars, actions) de l'annonce ; clé None s'il n'y a rien, si les phrases ne
    disent pas la même chose (rien plutôt que faux) ou si c'est moins de 10 M$."""
    documents, vieilles = [], set()
    for url, sorte, texte in documents_lus:
        trouves = []
        for p in phrases(texte):
            if not RACHAT.search(p):
                continue
            a = analyser(p, depose)
            if "sorte" in a:
                trouves.append((p, a))
            elif a["rejet"].startswith("ancienne date"):
                vieilles.add(a["cle"])
        if trouves:
            documents.append((url, sorte, trouves))
    if any(a["sorte"] != "total" for _, _, ts in documents for _, a in ts):
        # Un nouveau programme ou une hausse : le nouveau total, s'il est écrit aussi, décrit le même geste
        documents = [(u, s, [(p, a) for p, a in ts if a["sorte"] != "total"]) for u, s, ts in documents]
        documents = [x for x in documents if x[2]]
    cles = {(a["sorte"], a["dollars"], a["actions"]) for _, _, ts in documents for _, a in ts}
    if len(cles) != 1:
        return documents, None
    cle = cles.pop()
    if cle in vieilles:
        return documents, None  # le même programme, daté de plus de 30 jours ailleurs dans le dépôt (ex. Trupanion)
    if cle[1] is not None and cle[1] < MONTANT_MIN:
        return documents, None
    return documents, cle


def annonces_connues(ctx) -> dict:
    """{(symbole, sorte, dollars, actions) : [(jour, numéro)]} des annonces déjà publiées (lues une fois par passage)."""
    if "rachats_connus" not in ctx.cache:
        connues = {}
        for d in Depot(ctx.donnees).lire("evenements"):
            if d["source"] == "sec_rachats" and d.get("tickers"):
                x = d["data"]
                connues.setdefault((d["tickers"][0], x.get("sorte"), x.get("dollars"), x.get("actions")), []).append(
                    (d["published_on"], d["official_id"]))
        ctx.cache["rachats_connus"] = connues
    return ctx.cache["rachats_connus"]


def lire_un(ctx, depot) -> list[Evenement]:
    entete = entete_8k(ctx, depot)
    lus = points(entete)
    if not lus:
        return []
    f = lire_8k(entete)
    syms = symboles(ctx)
    cik, cote = next(((c, syms.cote(c)) for c, _ in f["filers"] if syms.cote(c)), (None, None))
    if cote is None:
        return []  # comme le lecteur des 8-K : seulement les compagnies cotées
    depose = date.fromisoformat(depot.depose)
    documents, cle = retenir(documents_8k(ctx, depot, depot.filers[0][0]), depose)
    if cle is None:
        return []
    sorte, dollars, actions = cle
    # La même annonce dans un autre 8-K de la compagnie (ex. le communiqué au point 7.01, puis le point 8.01) : une fois
    connues = annonces_connues(ctx).setdefault((cote["ticker"], *cle), [])
    if any(acc != depot.acc and abs((depose - date.fromisoformat(jour)).days) <= JOURS_MEME_ANNONCE for jour, acc in connues):
        return []
    connues.append((depot.depose, depot.acc))
    extraits = [p for _, _, ts in documents for p, _ in ts]
    # Date de l'autorisation : la seule date complète des extraits dans les 30 jours avant le dépôt (ex. « On September
    # 30, 2026, the Board… »), sinon le jour du dépôt. Pas la « période » de l'en-tête : elle peut venir d'un autre point
    # du même 8-K (ex. National Bank Holdings : dépréciation du 28 septembre, rachat autorisé le 30).
    dates = {d for x in extraits for d, jour in dates_ecrites(x, depose) if jour and 0 <= (depose - d).days <= JOURS_MAX}
    quand = dates.pop().isoformat() if len(dates) == 1 else depot.depose
    d = {"cik": cik, "points": lus, "sorte": sorte, "dollars": dollars, "actions": actions,
         "documents": [{"url": url, "type": s, "extraits": list(dict.fromkeys(p for p, _ in ts))[:3]}
                       for url, s, ts in documents],
         "formules": list(dict.fromkeys(a["formule"] for _, _, ts in documents for _, a in ts)),
         "details": details(("Compagnie", cote["name"]), ("Sorte", SORTES[sorte]),
                            (LIBELLES_PLAFOND[sorte], plafond(dollars, actions)),
                            ("Points du 8-K", ", ".join(lus)),
                            *[(f"Extrait ({s})", p) for _, s, ts in documents for p in list(dict.fromkeys(x for x, _ in ts))[:2]])}
    return [Evenement(
        source="sec_rachats", official_id=depot.acc, category="compagnies", kind="rachat_annonce",
        title=titre(cote["name"], sorte, dollars, actions),
        occurred_on=quand, published_on=depot.depose,
        official_url=depot.page_officielle(depot.filers[0][0]),
        sha256=canonique({"entete": empreinte_entete(entete), "extraits": extraits}),
        parser_version=VERSION, tickers=[cote["ticker"]], entities=[cote["name"]],
        amount_min=dollars, amount_max=dollars, data=d,
        notes=["Un plafond autorisé par le conseil d'administration, pas un achat fait : la compagnie peut racheter "
               "moins, ou rien, souvent sur plusieurs années.",
               "Les rachats vraiment faits sont déclarés plus tard, dans les rapports trimestriels et annuels (10-Q, "
               "10-K)."])]


@controle_source("sec_rachats")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    extraits = [x for doc in d.get("documents") or [] for x in doc["extraits"]]
    relus = [analyser(x, date.fromisoformat(ev.published_on)) for x in extraits]
    cles = {(a["sorte"], a["dollars"], a["actions"]) for a in relus if "sorte" in a}
    return {
        "extrait_officiel": bool(extraits),
        "formule_d_autorisation": bool(relus) and all("sorte" in a for a in relus),
        "conseil_nomme": bool(extraits) and all(CONSEIL.search(x) for x in extraits),
        "meme_montant_partout": cles == {(d.get("sorte"), d.get("dollars"), d.get("actions"))},
        "point_8k_des_rachats": bool(set(d.get("points") or []) & set(POINTS_EDGAR.values())),
        "compagnie_cotee": bool(ev.tickers),
        "rachat_de_10_millions_et_plus": (d.get("dollars") or 0) >= MONTANT_MIN
        or (d.get("dollars") is None and (d.get("actions") or 0) > 0),
    }


def collecter(ctx) -> list[Evenement]:
    return lire_journees(ctx, "sec_rachats", {"8-K"}, lire_un)


# ---------- Rachats vraiment faits : rapports annuels (XBRL), API officielle de la SEC ----------

FRAMES = "https://data.sec.gov/api/xbrl/frames/us-gaap/PaymentsForRepurchaseOfCommonStock/USD/CY{annee}.json"


def annee_xbrl(jour: date) -> int:
    """La dernière année civile presque complète : les rapports annuels (10-K) arrivent jusqu'à 90 jours après la fin
    de l'exercice. Avant avril, on garde l'année d'avant."""
    return jour.year - 1 if jour.month >= 4 else jour.year - 2


def chemin_xbrl(donnees) -> Path:
    return Path(donnees) / "sec" / "rachats_xbrl.json"


def collecter_xbrl(ctx) -> list[Evenement]:
    """Un seul fichier officiel pour toutes les compagnies. Pour chacune, la SEC prend l'exercice qui colle le mieux à
    l'année civile (ex. Apple : du 29 sept. 2024 au 27 sept. 2025) ; les dates sont gardées et montrées."""
    annee = annee_xbrl(ctx.maintenant.date())
    adresse = FRAMES.format(annee=annee)
    r = json.loads(ctx.client.get(adresse).contenu)
    if (r.get("tag"), r.get("ccp"), r.get("uom")) != ("PaymentsForRepurchaseOfCommonStock", f"CY{annee}", "USD") \
            or not r.get("data"):
        raise RuntimeError("réponse inattendue de l'API de la SEC (format changé ?)")
    nouveau = {"cadre": f"CY{annee}", "adresse": adresse,
               "par_cik": {str(x["cik"]): [x["val"], x["start"], x["end"], x["accn"]] for x in r["data"]}}
    c = chemin_xbrl(ctx.donnees)
    if not c.exists() or json.loads(c.read_text(encoding="utf-8")) != nouveau:  # réécrit seulement s'il change
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps(nouveau, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
                     encoding="utf-8")
    return []


def pour_app(donnees, symboles_listes: list[str]) -> dict:
    """Le fichier de l'app (data/app/rachats.json) : les rachats faits des compagnies des listes (CIK selon leur fiche
    SEC, voir emetteurs.py). Un montant négatif est une erreur du déclarant : pas montré."""
    c = chemin_xbrl(donnees)
    if not c.exists():
        return {}
    x = json.loads(c.read_text(encoding="utf-8"))
    ciks = {s: f.get("cik") for s, f in emetteurs.charger(donnees).items()}
    par_symbole = {}
    for s in symboles_listes:
        cik = ciks.get(s)
        v = x["par_cik"].get(str(cik)) if cik else None
        if v is None:
            par_symbole[s] = {"cik": cik}
            continue
        montant, debut, fin, accn = v
        par_symbole[s] = {"cik": cik, "debut": debut, "fin": fin, "accn": accn,
                          "lien": f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn.replace('-', '')}/{accn}-index.htm",
                          **({"montant": montant} if montant >= 0 else {"illisible": True})}
    return {"cadre": x["cadre"], "source": x["adresse"], "etiquette": "PaymentsForRepurchaseOfCommonStock",
            "par_symbole": par_symbole}
