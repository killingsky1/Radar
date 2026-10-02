"""Maison-Blanche : actions présidentielles (fil RSS officiel de whitehouse.gov, gratuit, sans compte).

Le jour même de la signature, souvent 2 à 4 jours AVANT le Registre fédéral. Quand le Registre publie
le même acte, le recoupement (recoupement.py) relie les deux : l'info devient « Confirmée ».

On garde : décrets, proclamations, mémorandums. On laisse de côté les nominations et les journées
commémoratives (« Labor Day, 2026 »).
Format vérifié sur le vrai fil du 26 août au 2 octobre 2026 (30 actions par page).
"""

from __future__ import annotations

import html
import json
import re
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

from ..models import Evenement, empreinte
from ..store import Depot
from ..validate import controle_source
from .registre import commemoratif

VERSION = "maison-blanche-1"
FIL = "https://www.whitehouse.gov/presidential-actions/feed/"
CATEGORIES = {  # catégorie officielle -> (sorte, libellé)
    "Executive Orders": ("decret", "Décret présidentiel"),
    "Proclamations": ("proclamation", "Proclamation présidentielle"),
    "Presidential Memoranda": ("memorandum", "Mémorandum présidentiel"),
}
LIEN = re.compile(r"https://www\.whitehouse\.gov/presidential-actions/(\d{4}/\d\d/[a-z0-9-]+)/?")


def _texte(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment or "")).split())


def lire_fil(contenu: bytes) -> list[dict]:
    t = contenu.decode("utf-8", "replace")
    actions = []
    for item in re.findall(r"<item>(.*?)</item>", t, re.S):
        def champ(nom):
            m = re.search(rf"<{nom}>(.*?)</{nom}>", item, re.S)
            return re.sub(r"^<!\[CDATA\[|\]\]>$", "", m.group(1).strip()) if m else ""

        corps = re.search(r"<content:encoded><!\[CDATA\[(.*?)\]\]></content:encoded>", item, re.S)
        paragraphes = [_texte(p) for p in re.findall(r"<p[^>]*>(.*?)</p>", corps.group(1) if corps else "", re.S)]
        actions.append({
            "titre": _texte(champ("title")),
            "lien": champ("link"),
            "publie": champ("pubDate"),
            "guid": champ("guid"),
            "categories": [re.sub(r"^<!\[CDATA\[|\]\]>$", "", c.strip()) for c in re.findall(r"<category>(.*?)</category>", item, re.S)],
            # Le texte officiel commence au 1er paragraphe en majuscules (« BY THE PRESIDENT… », « A PROCLAMATION »…)
            "texte": " ".join(p for p in paragraphes if p and not p.startswith("Select Category")),
        })
    return actions


def choisir(action: dict) -> tuple[str, str] | None:
    officielle = next((c for c in action["categories"] if c in CATEGORIES), None)
    if officielle is None:
        return None
    sorte, libelle = CATEGORIES[officielle]
    if sorte == "proclamation" and commemoratif(action["titre"]):
        return None  # journée, semaine ou mois commémoratif, hommage
    return sorte, libelle


def evenement(action: dict, choix: tuple[str, str]) -> Evenement | None:
    m = LIEN.fullmatch(action["lien"])
    try:
        quand = parsedate_to_datetime(action["publie"]).astimezone(ZoneInfo("America/New_York")).date().isoformat()
    except (TypeError, ValueError):
        return None
    if not m or not action["titre"]:
        return None
    sorte, libelle = choix
    canon = json.dumps({k: action[k] for k in ("titre", "lien", "publie", "guid", "categories", "texte")},
                       ensure_ascii=False, sort_keys=True)
    return Evenement(
        source="maison_blanche", official_id=m.group(1), category="gouvernement", kind=sorte,
        title=f"{libelle} : {action['titre']}", occurred_on=quand, published_on=quand,
        official_url=action["lien"], sha256=empreinte(canon.encode("utf-8")), parser_version=VERSION,
        entities=["The White House"],
        data={"titre_officiel": action["titre"], "categories": action["categories"], "guid": action["guid"],
              "resume": action["texte"][:600], "sorte": sorte},
    )


@controle_source("maison_blanche")
def controles(ev: Evenement) -> dict[str, bool]:
    return {
        "lien_d_une_action_presidentielle": bool(LIEN.fullmatch(ev.official_url)),
        "categorie_officielle_reconnue": any(c in CATEGORIES for c in ev.data.get("categories", [])),
        "texte_officiel_lu": len(ev.data.get("resume", "")) >= 40,
    }


def collecter(ctx) -> list[Evenement]:
    actions = lire_fil(ctx.client.get(FIL).contenu)
    if not actions:
        raise RuntimeError("fil de la Maison-Blanche vide")
    deja = Depot(ctx.donnees).ids_enregistres({"maison_blanche"})  # la 1re lecture gagne
    evs = []
    for a in actions:
        choix = choisir(a)
        ev = evenement(a, choix) if choix else None
        if ev and ev.official_id not in deja:
            evs.append(ev)
    return evs
