"""LEGISinfo (Parlement du Canada) : les étapes franchies par les projets de loi du gouvernement.

Une seule lecture : la liste officielle (JSON) des projets de loi de la session, avec la date de chaque étape
(1re, 2e et 3e lecture dans chaque chambre, sanction royale). robots.txt de www.parl.ca : permis (vérifié le
3 octobre 2026). Mesuré ce jour-là : 188 projets, dont 44 du gouvernement ; on suit seulement ceux-là.

Droit : reproduction exacte et non présentée comme officielle, à des fins non commerciales (permission du
Président de la Chambre des communes). Si Radar devient commercial : demander l'autorisation écrite ou retirer.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from ..models import Evenement
from ..validate import controle_source
from .gazette import details
from .regulateurs import canonique, deja

VERSION = "legisinfo-1"
SESSION = "45-1"  # 45e législature, 1re session : si elle se termine, la source tombe en panne (voir collecter)
LISTE = f"https://www.parl.ca/legisinfo/fr/projets-de-loi/json?parlsession={SESSION}"
FENETRE_JOURS = 30
TORONTO = ZoneInfo("America/Toronto")
ETAPES = (
    ("PassedHouseFirstReadingDateTime", "chambre-1", "première lecture à la Chambre des communes"),
    ("PassedHouseSecondReadingDateTime", "chambre-2", "adopté en deuxième lecture à la Chambre des communes"),
    ("PassedHouseThirdReadingDateTime", "chambre-3", "adopté en troisième lecture à la Chambre des communes"),
    ("PassedSenateFirstReadingDateTime", "senat-1", "première lecture au Sénat"),
    ("PassedSenateSecondReadingDateTime", "senat-2", "adopté en deuxième lecture au Sénat"),
    ("PassedSenateThirdReadingDateTime", "senat-3", "adopté en troisième lecture au Sénat"),
    ("ReceivedRoyalAssentDateTime", "sanction", "sanction royale : le projet devient loi"),
)


def du_gouvernement(p: dict) -> bool:
    return "Government Bill" in (p.get("BillDocumentTypeNameEn") or "")


def jour(iso: str | None) -> str | None:
    """« 2026-09-21T14:15:16-04:00 » -> 2026-09-21 (heure de l'Est). Les dates vides valent 0001-01-01."""
    if not iso or iso.startswith("0001-"):
        return None
    try:
        d = datetime.fromisoformat(iso)
    except ValueError:
        return None
    return (d.astimezone(TORONTO) if d.tzinfo else d).date().isoformat()


def evenements(p: dict) -> list[Evenement]:
    """Une info par étape datée d'un projet de loi du gouvernement."""
    code = p.get("NumberCode") or ""
    titre = (p.get("ShortTitle") or p.get("LongTitle") or "").strip()
    session = f"{p.get('ParliamentNumber')}-{p.get('SessionNumber')}"
    url = f"https://www.parl.ca/legisinfo/fr/projet-de-loi/{session}/{code.lower()}"
    evs = []
    for champ, cle, libelle in ETAPES:
        quand = jour(p.get(champ))
        if not quand:
            continue
        d = {"numero": code, "titre": titre, "titre_long": p.get("LongTitle") or "", "etape": libelle, "cle": cle,
             "champ": champ, "date_officielle": p.get(champ), "statut": p.get("StatusName") or "",
             "type": p.get("BillDocumentTypeName") or "", "type_en": p.get("BillDocumentTypeNameEn") or "",
             "sanction": bool(p.get("ReceivedRoyalAssent")), "session": session,
             "details": details(("Projet de loi", code), ("Titre", p.get("LongTitle") or ""), ("Étape", libelle),
                                ("Où il en est", p.get("StatusName") or ""))}
        evs.append(Evenement(
            source="legisinfo", official_id=f"{session}:{code}:{cle}", category="canada", kind="etape_projet_de_loi",
            title=f"Projet de loi {code} ({titre}) : {libelle}", occurred_on=quand, published_on=quand,
            official_url=url, sha256=canonique({k: d[k] for k in ("numero", "titre", "etape", "date_officielle")}),
            parser_version=VERSION, entities=["Parlement du Canada"], currency="CAD", data=d))
    return evs


@controle_source("legisinfo")
def controles_legisinfo(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "projet_du_gouvernement": "Government Bill" in (d.get("type_en") or ""),
        "etape_datee": bool(jour(d.get("date_officielle"))),
        "sanction_confirmee": d.get("cle") != "sanction" or bool(d.get("sanction")),
        "lien_legisinfo": bool(re.fullmatch(r"https://www\.parl\.ca/legisinfo/fr/projet-de-loi/\d+-\d+/[cs]-\d+",
                                            ev.official_url)),
    }


def collecter(ctx) -> list[Evenement]:
    projets = json.loads(ctx.client.get(LISTE).contenu.decode("utf-8-sig"))
    if not projets:
        raise RuntimeError("liste LEGISinfo vide")
    if not any(p.get("IsSessionOngoing") for p in projets):
        raise RuntimeError(f"la session {SESSION} est terminée : mettre à jour SESSION")
    limite = (ctx.maintenant.date() - timedelta(days=FENETRE_JOURS)).isoformat()
    lus = deja(ctx, "legisinfo")
    return [ev for p in projets if du_gouvernement(p) for ev in evenements(p)
            if ev.occurred_on >= limite and ev.official_id not in lus]
