"""Chef d'orchestre : fait rouler les lecteurs, valide, enregistre, puis prépare l'app.

Utilisation : python -m radar.run --donnees ../data [--passage auto|matin|…] [--sources sec_form4,war_contrats]
Une source qui plante tombe « en panne » sans arrêter les autres.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from . import emetteurs
from .collecteurs import COLLECTEURS
from .http import ClientPoli, ErreurSource
from .models import Evenement
from .publish import publier
from .recoupement import marquer_doublons_form4, recouper
from .registry import PASSAGES, SOURCES
from .store import Depot
from .validate import valider

CONFIG = Path(__file__).resolve().parent.parent / "config.json"

# Un site qui refuse le robot (erreur 401 ou 403) : on respecte. Un refus isolé peut être passager (ex. le Registre
# fédéral le 3 octobre 2026 : lu à 00 h 05, 403 à 00 h 11, lu normalement au passage suivant) ; deux refus de suite, à
# au moins 1 heure d'écart, sont un vrai refus : la source est mise en pause 7 jours, puis on réessaie une seule fois,
# en lisant d'abord le robots.txt du site (refusé ou illisible = on attend encore 7 jours).
REFUS = re.compile(r"HTTP (401|403)$")
ECART_REFUS = timedelta(hours=1)
PAUSE_REFUS = timedelta(days=7)
AGENT = "Radar projet personnel"


def noter_refus(e: dict, code: int, maintenant: datetime) -> None:
    r = e.get("refus")
    if r is None:
        e["refus"] = {"depuis": maintenant.isoformat(), "code": code, "essais": 1, "dernier_refus": maintenant.isoformat(),
                      "confirme": False}
        return
    if not r["confirme"] and maintenant - datetime.fromisoformat(r["dernier_refus"]) < ECART_REFUS:
        return  # trop proche du 1er refus (ex. deux lancements de suite) : ce n'est pas une 2e preuve
    r.update(code=code, essais=r["essais"] + 1, dernier_refus=maintenant.isoformat())
    if r["essais"] >= 2:
        r["confirme"] = True
        r["prochain_essai"] = (maintenant + PAUSE_REFUS).isoformat()


def refus_d_avant(e: dict) -> None:
    """État écrit avant cette règle : une dernière erreur 401/403 plus récente que la dernière réussite = 1er refus."""
    erreur, tentative = e.get("derniere_erreur") or "", e.get("derniere_tentative")
    m = REFUS.search(erreur)
    if "refus" not in e and m and tentative and (e.get("dernier_succes") or "") < tentative:
        e["refus"] = {"depuis": tentative, "code": int(m.group(1)), "essais": 1, "dernier_refus": tentative,
                      "confirme": False}


def robots_permet(client, site: str) -> tuple[bool, str]:
    """Le robots.txt du site permet-il de lire `site` ? Absent (404) = permis ; refusé ou illisible = non."""
    racine = f"{urlparse(site).scheme}://{urlparse(site).netloc}"
    try:
        texte = client.get(racine + "/robots.txt").contenu.decode("utf-8", "replace")
    except ErreurSource as exc:
        if str(exc).endswith("HTTP 404"):
            return True, "pas de robots.txt"
        return False, f"robots.txt refusé ou illisible ({str(exc).rsplit(' : ', 1)[-1]})"
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(texte.splitlines())
    if rp.can_fetch(AGENT, site):
        return True, "robots.txt permet"
    return False, "robots.txt ne permet pas"


@dataclass
class Contexte:
    client: object
    maintenant: datetime
    donnees: Path
    cache: dict = field(default_factory=dict)  # partagé entre les lecteurs d'un même passage (ex. index SEC)


def passage_auto(maintenant: datetime) -> str:
    """Le passage selon l'heure de l'Est (le robot roule 5 fois par jour de semaine)."""
    heure = maintenant.astimezone(ZoneInfo("America/Toronto")).hour
    if heure < 8:
        return "matin"
    if heure < 11:
        return "jour"
    if heure < 15:
        return "midi"
    if heure < 20:
        return "soir"
    return "nuit"


def _charger_json(chemin: Path) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def revalider(donnees: Path, maintenant: datetime) -> dict:
    tous = Depot(donnees).lire("evenements") + Depot(donnees).lire("a_verifier")
    evenements = [valider(Evenement.from_dict(d), maintenant.date()) for d in tous]
    return Depot(donnees).enregistrer(evenements)


def executer(donnees, passage=None, seulement=None, collecteurs=None, client=None, maintenant=None) -> dict:
    donnees = Path(donnees)
    collecteurs = COLLECTEURS if collecteurs is None else collecteurs
    maintenant = maintenant or datetime.now(timezone.utc).replace(microsecond=0)
    chemin_etat = donnees / "etat_sources.json"
    etat = _charger_json(chemin_etat)
    depot = Depot(donnees)
    ctx = Contexte(client=client, maintenant=maintenant, donnees=donnees)

    rapport = {}
    for sid, collecteur in collecteurs.items():
        if seulement and sid not in seulement:
            continue
        if passage and passage not in SOURCES[sid].passages:
            continue
        e = etat.setdefault(sid, {})
        refus_d_avant(e)
        refus = e.get("refus")
        if refus and refus["confirme"]:
            if maintenant < datetime.fromisoformat(refus["prochain_essai"]):
                rapport[sid] = {"ok": False, "refusee_depuis": refus["depuis"]}
                continue  # le site refuse le robot : on ne le sollicite pas pendant la pause
            permis, pourquoi = robots_permet(client, SOURCES[sid].site)
            refus["robots"] = pourquoi
            if not permis:
                refus.update(dernier_refus=maintenant.isoformat(), prochain_essai=(maintenant + PAUSE_REFUS).isoformat())
                e["derniere_tentative"] = maintenant.isoformat()
                rapport[sid] = {"ok": False, "refusee_depuis": refus["depuis"], "robots": pourquoi}
                continue
        e["derniere_tentative"] = maintenant.isoformat()
        try:
            evenements = list(collecteur(ctx))
            for ev in evenements:
                valider(ev, maintenant.date())
            bilan = depot.enregistrer(evenements)
        except Exception as exc:  # isole la panne à cette source
            e["derniere_erreur"] = f"{type(exc).__name__}: {exc}"[:300]
            m = REFUS.search(str(exc))
            if m:
                noter_refus(e, int(m.group(1)), maintenant)
            rapport[sid] = {"ok": False, "erreur": e["derniere_erreur"]}
            continue
        e.pop("refus", None)  # lecture réussie : le site accepte de nouveau le robot
        e["dernier_succes"] = maintenant.isoformat()
        e["derniere_erreur"] = None
        e["compte"] = {"recus": len(evenements), "a_verifier": sum(ev.badge == "a_verifier" for ev in evenements)}
        dates = [ev.published_on for ev in evenements if ev.published_on]
        if e.get("dernier_contenu"):
            dates.append(e["dernier_contenu"])
        if dates:
            e["dernier_contenu"] = max(dates)
        rapport[sid] = {"ok": True, **bilan}

    # Type officiel des émetteurs notés (fonds enregistrés mis à part du score). Jamais bloquant.
    try:
        tous = Depot(donnees).lire("evenements")
        bilan = emetteurs.rafraichir(ctx, emetteurs.symboles_recents(tous, maintenant.date()))
        if bilan.get("lues") or bilan.get("erreurs"):
            print(f"Types d'émetteurs (fiches SEC) : {bilan}")
    except Exception as exc:  # noqa: BLE001
        print(f"Types d'émetteurs : erreur, l'ancien fichier est gardé ({type(exc).__name__}: {exc})")

    # Deux sources officielles qui publient le même acte : liées (badge « Confirmé »).
    liees = recouper(donnees)
    if liees:
        print(f"Recoupement : {liees} info(s) reliée(s) à une 2e source officielle")

    # La même transaction déclarée par plusieurs entités liées (ex. un fonds et ses gestionnaires) : une seule ligne.
    doublons = marquer_doublons_form4(donnees)
    if doublons:
        print(f"Doublons : {doublons} formulaire(s) 4 relié(s) à la même transaction déjà déclarée")

    # Les contrôles s'améliorent : on les réapplique aux infos déjà publiées (une info peut retourner « à vérifier »).
    bilan = revalider(donnees, maintenant)
    if bilan["modifies"]:
        print(f"Revérification des infos déjà publiées : {bilan['modifies']} changée(s) de statut")

    chemin_etat.parent.mkdir(parents=True, exist_ok=True)
    chemin_etat.write_text(json.dumps(etat, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    publier(donnees, etat, set(collecteurs), maintenant, ctx.cache.get("sec_symboles"))
    return rapport


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Robot Radar")
    p.add_argument("--donnees", default="../data")
    p.add_argument("--passage", choices=("auto",) + PASSAGES)
    p.add_argument("--sources", help="liste séparée par des virgules")
    args = p.parse_args(argv)

    maintenant = datetime.now(timezone.utc).replace(microsecond=0)
    passage = passage_auto(maintenant) if args.passage == "auto" else args.passage
    contact = os.environ.get("RADAR_CONTACT") or _charger_json(CONFIG).get("contact", "")
    client = ClientPoli(contact)
    seulement = args.sources.split(",") if args.sources else None

    rapport = executer(args.donnees, passage, seulement, client=client, maintenant=maintenant)
    print(f"Passage : {passage or 'tous'} — {len(rapport)} source(s) lue(s)")
    for sid, r in rapport.items():
        print(f"  {sid}: {r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
