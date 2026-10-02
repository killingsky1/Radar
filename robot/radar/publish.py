"""Prépare les fichiers JSON que l'app iPhone lit (data/app/)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from . import __version__
from .health import LIBELLES, statut
from .registry import SOURCES
from .store import Depot

MAX_PAR_CATEGORIE = 150  # chaque catégorie garde ses infos les plus récentes (les élus ne cachent pas le reste)
MAX_A_VERIFIER = 100
PHASE_ACTUELLE = 1


def _ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _plus_recent(d: dict):
    return (d["published_on"], d["collected_at"], d["id"])


def publier(donnees: Path, etat: dict, branchees: set[str], maintenant: datetime) -> None:
    depot = Depot(donnees)
    fil = sorted(depot.lire("evenements"), key=_plus_recent, reverse=True)
    a_verifier = sorted(depot.lire("a_verifier"), key=_plus_recent, reverse=True)

    sources = []
    for s in SOURCES.values():
        code, explication = statut(s.id, etat.get(s.id), s.id in branchees, maintenant)
        e = etat.get(s.id, {})
        sources.append({
            "id": s.id, "nom": s.nom, "categorie": s.categorie, "phase": s.phase, "site": s.site,
            "officielle": s.officielle, "statut": code, "libelle": LIBELLES[code], "explication": explication,
            "dernier_succes": e.get("dernier_succes"), "dernier_contenu": e.get("dernier_contenu"),
            "compte": e.get("compte"),
        })

    # Les compteurs de l'accueil sont calculés ici, sur TOUTES les infos (l'app ne reçoit que les plus récentes),
    # et selon la date de publication officielle (pas l'heure où le robot les a lues).
    depuis = (maintenant.date() - timedelta(days=30)).isoformat()
    recentes = [e for e in fil if e["published_on"] >= depuis]
    dernier_jour = max((e["published_on"] for e in fil), default=None)
    compteurs = {
        "dernier_jour": dernier_jour,
        "publiees_dernier_jour": sum(1 for e in fil if e["published_on"] == dernier_jour),
        "total_30j": len(recentes),
        "confirmees_30j": sum(1 for e in recentes if e["badge"] == "confirme"),
        "par_categorie_30j": dict(Counter(e["category"] for e in recentes)),
    }

    actives = [s for s in SOURCES.values() if not s.ecartee]
    meta = {
        "genere_a": maintenant.isoformat(),
        "version": __version__,
        "phase": PHASE_ACTUELLE,
        "sources_total": len(actives),
        "sources_branchees": len([s for s in actives if s.id in branchees]),
        "evenements_3_mois": len(fil),
        "a_verifier_3_mois": len(a_verifier),
        "compteurs": compteurs,
    }
    _ecrire(donnees / "app" / "meta.json", meta)
    _ecrire(donnees / "app" / "sources.json", sources)
    par_cat: Counter = Counter()
    fil_app = []
    for e in fil:  # déjà du plus récent au plus vieux
        par_cat[e["category"]] += 1
        if par_cat[e["category"]] <= MAX_PAR_CATEGORIE:
            fil_app.append(e)
    _ecrire(donnees / "app" / "fil.json", fil_app)
    _ecrire(donnees / "app" / "a_verifier.json", a_verifier[:MAX_A_VERIFIER])
    _ecrire(donnees / "app" / "aujourdhui.json", {
        "top": [], "eviter": [], "note": "Les suggestions arrivent quand le score sera prêt (phase 5).",
    })
