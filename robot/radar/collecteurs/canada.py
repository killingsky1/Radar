"""Centre des nouvelles du gouvernement du Canada (fil Atom officiel, en français, gratuit, sans compte).

On garde seulement les communiqués et documents d'information (pas les avis aux médias, comptes rendus ni discours) :
- Militaire : Défense nationale et Agence de l'investissement pour la défense ;
- Canada : ministères qui touchent l'argent et les entreprises (Finances, Industrie, Ressources naturelles,
  grands projets, concurrence, énergie, commerce extérieur, approvisionnement, sûreté nucléaire).

L'empreinte SHA-256 est celle de l'entrée officielle du fil (titre, résumé, lien, date, ministère).
Format vérifié sur le vrai fil du 24 septembre au 2 octobre 2026 (200 entrées).
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from zoneinfo import ZoneInfo

from ..models import Evenement, empreinte
from ..store import Depot
from ..validate import controle_source

VERSION = "canada-1"
FIL = "https://api.io.canada.ca/io-server/gc/news/fr/v2?sort=publishedDate&orderBy=desc&pick=200&format=atom"
NS = {"a": "http://www.w3.org/2005/Atom"}
TYPES_GARDES = {"communiqués de presse", "documents d'information"}


def _cle(nom: str) -> str:
    return " ".join(nom.replace("’", "'").lower().split())


DEFENSE = {_cle(n) for n in ("Défense nationale", "Agence de l'investissement pour la défense")}
ECONOMIE = {_cle(n) for n in (
    "Ministère des Finances Canada", "Innovation, Sciences et Développement économique Canada",
    "Ressources naturelles Canada", "Unité de l'économie canadienne", "Bureau de la concurrence Canada",
    "Régie de l'énergie du Canada", "Tribunal canadien du commerce extérieur",
    "Services publics et Approvisionnement Canada", "Commission canadienne de sûreté nucléaire",
)}
# Affaires mondiales : surtout de la diplomatie ; on garde seulement le commerce et les sanctions.
AFFAIRES_MONDIALES = _cle("Affaires mondiales Canada")
MOTS_COMMERCE = re.compile(r"sanction|tarif|surtaxe|contre-mesure|droits de douane|libre-échange|accord commercial"
                           r"|exportation|importation", re.I)


def lire_fil(contenu: bytes) -> list[dict]:
    racine = ET.fromstring(contenu)
    entrees = []
    for e in racine.findall("a:entry", NS):
        lien = e.find("a:link", NS)
        cat = e.find("a:category", NS)
        auteur = e.find("a:author/a:name", NS)
        entrees.append({
            "titre": " ".join((e.findtext("a:title", "", NS)).split()),
            "id": (e.findtext("a:id", "", NS)).strip(),
            "lien": (lien.get("href") if lien is not None else "") or "",
            "resume": " ".join((e.findtext("a:summary", "", NS)).split()),
            "ministere": " ".join((auteur.text or "").split()) if auteur is not None else "",
            "type": (cat.get("term") if cat is not None else "") or "",
            "mis_a_jour": (e.findtext("a:updated", "", NS)).strip(),
        })
    return entrees


def categorie(entree: dict) -> str | None:
    if entree["type"] not in TYPES_GARDES:
        return None
    m = _cle(entree["ministere"])
    if m in DEFENSE:
        return "militaire"
    if m in ECONOMIE:
        return "canada"
    if m == AFFAIRES_MONDIALES and MOTS_COMMERCE.search(entree["titre"]):
        return "canada"
    return None


def identifiant(lien: str) -> str | None:
    """Le chemin officiel de la nouvelle, ex. ministere-defense-nationale/nouvelles/2026/10/titre.html."""
    m = re.fullmatch(r"https://www\.canada\.ca/fr/(.+\.html)", lien)
    return m.group(1) if m else None


def evenement(entree: dict, cat: str) -> Evenement | None:
    ident = identifiant(entree["lien"])
    try:
        quand = datetime.fromisoformat(entree["mis_a_jour"]).astimezone(ZoneInfo("America/Toronto")).date().isoformat()
    except ValueError:
        return None
    if not ident or not entree["titre"]:
        return None
    canon = json.dumps({k: entree[k] for k in ("titre", "resume", "lien", "ministere", "type", "mis_a_jour")},
                       ensure_ascii=False, sort_keys=True)
    return Evenement(
        source="nouvelles_defense_ca" if cat == "militaire" else "nouvelles_eco_ca",
        official_id=ident, category=cat, kind="nouvelle_officielle", title=entree["titre"],
        occurred_on=quand, published_on=quand, official_url=entree["lien"], sha256=empreinte(canon.encode("utf-8")),
        parser_version=VERSION, entities=[entree["ministere"]], currency="CAD",
        data={"ministere": entree["ministere"], "type": entree["type"], "resume": entree["resume"],
              "mis_a_jour": entree["mis_a_jour"], "id_fil": entree["id"]},
    )


def _controles(ev: Evenement) -> dict[str, bool]:
    return {
        "lien_identique_au_fil": ev.data.get("id_fil") == ev.official_url,
        "ministere_reconnu": _cle(ev.data.get("ministere", "")) in (DEFENSE | ECONOMIE | {AFFAIRES_MONDIALES}),
        "type_communique": ev.data.get("type") in TYPES_GARDES,
        "lien_ministere_coherent": "/nouvelles/" in ev.official_url,
    }


@controle_source("nouvelles_defense_ca")
def controles_defense(ev: Evenement) -> dict[str, bool]:
    return _controles(ev)


@controle_source("nouvelles_eco_ca")
def controles_eco(ev: Evenement) -> dict[str, bool]:
    return _controles(ev)


def _evenements(ctx, voulue: str) -> list[Evenement]:
    if "canada_fil" not in ctx.cache:
        ctx.cache["canada_fil"] = lire_fil(ctx.client.get(FIL).contenu)
    entrees = ctx.cache["canada_fil"]
    if not entrees:
        raise RuntimeError("fil des nouvelles vide")
    # La 1re lecture gagne : une nouvelle retouchée plus tard par le ministère garde sa 1re date.
    deja = Depot(ctx.donnees).ids_enregistres({"nouvelles_defense_ca", "nouvelles_eco_ca"})
    evs = []
    for e in entrees:
        cat = categorie(e)
        if cat == voulue:
            ev = evenement(e, cat)
            if ev and ev.official_id not in deja:
                evs.append(ev)
    return evs


def collecter_defense(ctx) -> list[Evenement]:
    return _evenements(ctx, "militaire")


def collecter_economie(ctx) -> list[Evenement]:
    return _evenements(ctx, "canada")
