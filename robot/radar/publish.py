"""Prépare les fichiers JSON que l'app iPhone lit (data/app/)."""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from . import __version__, argent, emetteurs
from .collecteurs import congres, lobbying
from .health import LIBELLES, statut
from .registry import SOURCES
from .score import calculer, jour_de_calcul
from .store import Depot

MAX_PAR_CATEGORIE = 150  # chaque catégorie garde ses infos les plus récentes (les élus ne cachent pas le reste)
MAX_A_VERIFIER = 100
PHASE_ACTUELLE = 1


def _ecrire(chemin: Path, contenu) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _ecrire_compact(chemin: Path, contenu) -> None:
    """Fichiers lus par l'iPhone et refaits à chaque passage (section Argent) : sans espaces, pour peser moins."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n",
                      encoding="utf-8")


def _plus_recent(d: dict):
    return (d["published_on"], d["collected_at"], d["id"])


def publier(donnees: Path, etat: dict, branchees: set[str], maintenant: datetime, symboles=None) -> None:
    """`symboles` : la liste officielle de la SEC si un lecteur l'a lue à ce passage (noms des compagnies du score)."""
    depot = Depot(donnees)
    # Un acte publié par 2 sources (ex. Maison-Blanche puis Registre) n'apparaît qu'une fois, avec sa confirmation.
    # Même chose pour la même transaction déclarée par plusieurs entités liées (formulaires 4) : une seule ligne.
    # Le score, lui, voit toutes les déclarations (comme avant) : il compte déjà une seule fois le même achat, et garde
    # le rôle le plus informatif (ex. l'administrateur plutôt que son fonds, actionnaire de 10 %).
    pour_score = sorted((e for e in depot.lire("evenements") if not e.get("data", {}).get("meme_acte_que")),
                        key=_plus_recent, reverse=True)
    fil = [e for e in pour_score if not e.get("data", {}).get("meme_transaction_que")]
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
    # Section « Argent » : les vrais montants des 30 derniers jours (chaque transaction une fois), et les infos
    # complètes à part (l'app les charge seulement quand on touche une ligne). En cas d'erreur : ancien fichier gardé.
    try:
        lignes, infos = argent.preparer(fil, jour_de_calcul(maintenant))
        _ecrire_compact(donnees / "app" / "argent.json", lignes)
        _ecrire_compact(donnees / "app" / "argent_infos.json", infos)
    except Exception as exc:  # noqa: BLE001
        print(f"Argent : erreur, l'ancien fichier est gardé ({type(exc).__name__}: {exc})")
    # Chefs, comités et votes des élus (listes officielles du Congrès). En cas d'erreur : aucun chef, donc aucun bonus.
    chefs: set[str] = set()
    try:
        elus = congres.pour_app(donnees, fil)
        _ecrire(donnees / "app" / "elus.json", elus)
        chefs = {nom for nom, info in elus["par_elu"].items() if info["chef"]}
    except Exception as exc:  # noqa: BLE001
        print(f"Élus : erreur, fichier de l'app pas mis à jour ({type(exc).__name__}: {exc})")
    # Le score : calculé sur TOUTES les infos validées ; la liste précédente sert à savoir qui vient d'entrer.
    # S'il plante, les infos sont quand même publiées et l'ancien score reste (l'app montre son heure de calcul).
    chemin = donnees / "app" / "aujourdhui.json"
    try:
        precedent = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else None
        _ecrire(chemin, calculer(pour_score, maintenant, precedent, symboles, fonds=emetteurs.fonds(donnees), chefs=chefs))
    except Exception as exc:  # noqa: BLE001
        print(f"Score : erreur, l'ancien calcul est gardé ({type(exc).__name__}: {exc})")
    # Lobbying des compagnies des listes (celles du score publié)
    try:
        score = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
        symboles_listes = [x["symbole"] for liste in ("hausse", "baisse") for x in score.get(liste, [])]
        _ecrire(donnees / "app" / "lobbying.json", lobbying.pour_app(donnees, symboles_listes, maintenant))
    except Exception as exc:  # noqa: BLE001
        print(f"Lobbying : erreur, fichier de l'app pas mis à jour ({type(exc).__name__}: {exc})")
