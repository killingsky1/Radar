"""Chef d'orchestre : fait rouler les lecteurs, valide, enregistre, puis prépare l'app.

Utilisation : python -m radar.run --donnees ../data [--passage auto|matin|…] [--sources sec_form4,war_contrats]
Une source qui plante tombe « en panne » sans arrêter les autres.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .collecteurs import COLLECTEURS
from .http import ClientPoli
from .models import Evenement
from .publish import publier
from .recoupement import recouper
from .registry import PASSAGES, SOURCES
from .store import Depot
from .validate import valider

CONFIG = Path(__file__).resolve().parent.parent / "config.json"


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
        e["derniere_tentative"] = maintenant.isoformat()
        try:
            evenements = list(collecteur(ctx))
            for ev in evenements:
                valider(ev, maintenant.date())
            bilan = depot.enregistrer(evenements)
        except Exception as exc:  # isole la panne à cette source
            e["derniere_erreur"] = f"{type(exc).__name__}: {exc}"[:300]
            rapport[sid] = {"ok": False, "erreur": e["derniere_erreur"]}
            continue
        e["dernier_succes"] = maintenant.isoformat()
        e["derniere_erreur"] = None
        e["compte"] = {"recus": len(evenements), "a_verifier": sum(ev.badge == "a_verifier" for ev in evenements)}
        dates = [ev.published_on for ev in evenements if ev.published_on]
        if e.get("dernier_contenu"):
            dates.append(e["dernier_contenu"])
        if dates:
            e["dernier_contenu"] = max(dates)
        rapport[sid] = {"ok": True, **bilan}

    # Deux sources officielles qui publient le même acte : liées (badge « Confirmé »).
    liees = recouper(donnees)
    if liees:
        print(f"Recoupement : {liees} info(s) reliée(s) à une 2e source officielle")

    # Les contrôles s'améliorent : on les réapplique aux infos déjà publiées (une info peut retourner « à vérifier »).
    bilan = revalider(donnees, maintenant)
    if bilan["modifies"]:
        print(f"Revérification des infos déjà publiées : {bilan['modifies']} changée(s) de statut")

    chemin_etat.parent.mkdir(parents=True, exist_ok=True)
    chemin_etat.write_text(json.dumps(etat, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    publier(donnees, etat, set(collecteurs), maintenant)
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
