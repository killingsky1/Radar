"""Douane américaine (U.S. Customs and Border Protection, CBP) : messages officiels CSMS (Cargo Systems Messaging
Service) sur les surtaxes et les interdictions d'importation (Section 232, 301, 338, IEEPA, proclamations).

Flux RSS officiel des 100 derniers messages (GovDelivery, pour la douane ; pas de robots.txt : permis), lu matin et
soir. Mesuré le 3 octobre 2026 : 8 messages sur 100 (du 31 juillet au 1er octobre) portent sur des surtaxes ou des
interdictions d'importation ; les autres : maintenances, codes d'erreur, contingents, webinaires.

Politique de la douane (lue le 3 octobre 2026) : « Unless a copyright is indicated, information on the U.S. Customs and
Border Protection website is in the public domain […] We request only that the CBP be cited as the source of the
information ». Page CSMS : « such guidance documents are not binding and lack the force and effect of law, except as
authorized by law or as incorporated into a contract » : l'acte officiel reste la proclamation ou l'avis au Registre
fédéral (déjà lus par Radar). Aucune date « en vigueur » n'est calculée : un message en cite souvent plusieurs.
"""

from __future__ import annotations

import html
import re
import xml.etree.ElementTree as ET
from datetime import timedelta
from email.utils import parsedate_to_datetime

from ..models import Evenement
from ..validate import controle_source
from .gazette import details, extrait
from .regulateurs import NEW_YORK, canonique, deja

VERSION = "douane-1"
FLUX = "https://content.govdelivery.com/accounts/USDHSCBP/widgets/USDHSCBP_WIDGET_2.rss"
MESSAGES = "https://content.govdelivery.com/accounts/USDHSCBP/bulletins/"
SUJET = re.compile(r"\bSection\s+(?:122|201|232|301|338)\b|\bIEEPA\b|\b(?:Additional|Reciprocal)\s+(?:Duties|Tariffs?)\b"
                   r"|\bTariffs?\b(?!\s+Rate\s+Quota)|\bDuties\s+on\b|\bImport\s+Ban\b|Excluded\s+from\s+Importation"
                   r"|\bProclamations?\s+\d{5}", re.I)
TECHNIQUE = re.compile(r"\bErrors?\b|\bCATAIR\b|\bQuota\s+Bulletin\b|\bWebinars?\b|\bMaintenance\b"
                       r"|Order\s+of\s+Reporting|\bTest\b", re.I)
TITRE = re.compile(r"CSMS\s*#\s*(\d+)\s*[-–]\s*(.+)", re.S)
BLOCS = re.compile(r"(?i)<\s*/?\s*(?:br|p|div|li|tr|td|th|table|h\d)\b[^>]*>")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre")


def texte_message(fragment: str) -> str:
    """Texte d'un message : un espace entre les blocs (paragraphes, cellules), rien pour une balise dans une ligne
    (sinon « remov<span>e</span> » donnerait « remov e »)."""
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>|<!--.*?-->", " ", fragment or "")
    t = re.sub(r"<[^>]+>", "", BLOCS.sub(" ", t))
    return " ".join(html.unescape(t).replace("\xa0", " ").split())


def sujet(titre: str) -> bool:
    """Surtaxes ou interdiction d'importation ; pas les messages techniques (codes d'erreur, contingents, essais)."""
    return bool(SUJET.search(titre or "")) and not TECHNIQUE.search(titre or "")


def proclamations(t: str) -> list[str]:
    """Les numéros de proclamations cités (« Proclamation 11020 », « Proclamations 11046, 11047, and 11048 »)."""
    nums = []
    for m in re.finditer(r"\bProc(?:lamation)?s?\.?\s+((?:No\.\s*)?\d{5}(?:(?:\s*,\s*(?:and\s+)?|\s+and\s+)\d{5})*)", t):
        for n in re.findall(r"\d{5}", m.group(1)):
            if n not in nums:
                nums.append(n)
    return nums


def lire_flux(contenu: bytes) -> list[dict]:
    messages = []
    for it in ET.fromstring(contenu).iter("item"):
        titre = " ".join((it.findtext("title") or "").split())
        m = TITRE.fullmatch(titre)
        messages.append({"titre": titre, "numero": m.group(1) if m else None,
                         "titre_officiel": m.group(2).strip() if m else None,
                         "guid": (it.findtext("guid") or "").strip(), "lien": (it.findtext("link") or "").strip(),
                         "envoi": parsedate_to_datetime(it.findtext("pubDate")),
                         "texte": texte_message(it.findtext("description") or "")})
    return messages


def heure_fr(moment) -> str:
    t = moment.astimezone(NEW_YORK)
    return f"{t.day}{'er' if t.day == 1 else ''} {MOIS[t.month - 1]} {t.year} à {t.hour} h {t.minute:02d} (heure de New York)"


def evenement(x: dict) -> Evenement:
    t = x["texte"]
    debut = re.search(r"(?:This message|The purpose of this message)\b", t)
    ext = extrait(t[debut.start():], 420) if debut else ""
    procs = proclamations(t)
    codes = sorted(set(re.findall(r"\b9903\.\d\d\.\d\d\b", t)))
    jour = x["envoi"].astimezone(NEW_YORK).date().isoformat()
    d = {"numero": x["numero"], "guid": x["guid"], "titre_officiel": x["titre_officiel"],
         "envoye_le": x["envoi"].isoformat(), "proclamations": procs, "codes_9903": codes, "extrait": ext,
         "details": details(("Message", f"CSMS # {x['numero']}"), ("Envoyé", heure_fr(x["envoi"])),
                            ("Proclamations citées", ", ".join(procs)),
                            ("Numéros du tarif cités (chapitre 99)",
                             ", ".join(codes[:12]) + (f" et {len(codes) - 12} autres" if len(codes) > 12 else "")),
                            ("Extrait", ext))}
    return Evenement(
        source="tarifs", official_id=x["numero"], category="gouvernement", kind="directive_douane",
        title=f"Douane américaine : {x['titre_officiel']}", occurred_on=jour, published_on=jour, official_url=x["lien"],
        sha256=canonique({"titre": x["titre"], "texte": t}), parser_version=VERSION,
        entities=["U.S. Customs and Border Protection"], data=d,
        notes=["Directive de la douane : elle applique une décision officielle (proclamation, avis au Registre "
               "fédéral) sans la remplacer."])


@controle_source("tarifs")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "numero_csms": bool(d.get("numero")) and d.get("numero") == d.get("guid") == ev.official_id,
        "lien_du_message": ev.official_url.startswith(MESSAGES),
        "sujet_surtaxes": sujet(d.get("titre_officiel") or ""),
        "date_d_envoi_lue": bool(d.get("envoye_le")),
    }


def collecter(ctx) -> list[Evenement]:
    messages = lire_flux(ctx.client.get(FLUX).contenu)
    # La douane envoie plusieurs messages par semaine : un flux court ou sans message récent est une erreur.
    recent = max((x["envoi"] for x in messages), default=None)
    if len(messages) < 20 or recent is None or recent < ctx.maintenant - timedelta(days=14):
        raise RuntimeError(f"flux CSMS incomplet ou figé ({len(messages)} messages, dernier : {recent})")
    lus = deja(ctx, "tarifs", mois_max=4)
    return [evenement(x) for x in messages if x["numero"] and sujet(x["titre_officiel"]) and x["numero"] not in lus]
