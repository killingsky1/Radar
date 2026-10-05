"""Type officiel de chaque émetteur noté, selon sa fiche SEC (data.sec.gov/submissions).

Un fonds enregistré auprès de la SEC (fonds fermé, fiducie de placement) dépose des rapports de fonds :
N-CSR, N-CSRS, NPORT-P ou N-CEN. Aucune compagnie ordinaire n'en dépose (mesuré le 3 octobre 2026 sur 513 fiches :
23 fonds, aucun avec un 10-K). Les études sur les initiés et les activistes portent sur des compagnies : le score met
les fonds à part. Les BDC (sociétés de développement d'affaires) déposent des 10-K comme les compagnies : elles restent.

Gardé dans data/sec/emetteurs.json et relu après 90 jours ; à chaque passage, seules les fiches manquantes sont lues.
Lot L : la fiche dit aussi quels rapports la compagnie dépose (américains : 10-K, 10-Q ; émetteur étranger : 20-F, 40-F,
6-K) : la taille en bourse est calculée seulement pour les compagnies américaines (voir collecteurs/taille.py). Les
fiches lues avant le lot L sont relues une fois.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

FORMULAIRES_FONDS = {"N-CSR", "N-CSRS", "NPORT-P", "N-CEN"}
RAPPORTS = {"10-K", "10-Q", "10-KT", "10-QT", "20-F", "40-F", "6-K"}
RELIRE_APRES_JOURS = 90
MAX_PAR_PASSAGE = 600  # 600 fiches à 5 par seconde : 2 minutes au plus


def chemin(donnees: Path) -> Path:
    return Path(donnees) / "sec" / "emetteurs.json"


def charger(donnees: Path) -> dict:
    p = chemin(donnees)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def fonds(donnees: Path) -> set[str]:
    """Les symboles des fonds enregistrés connus."""
    return {s for s, f in charger(donnees).items() if f.get("type") == "fonds"}


def classer(fiche: dict) -> tuple[str, list[str]]:
    """(« fonds » ou « compagnie », formulaires de fonds trouvés parmi les dépôts récents de la fiche officielle)."""
    formes = set((fiche.get("filings") or {}).get("recent", {}).get("form") or [])
    trouves = sorted(f for f in formes if f.split("/")[0] in FORMULAIRES_FONDS)
    return ("fonds" if trouves else "compagnie"), trouves


def rapports(fiche: dict) -> list[str]:
    """Les rapports périodiques que la compagnie dépose (parmi ses dépôts récents), sans les modifications (« /A »)."""
    formes = (fiche.get("filings") or {}).get("recent", {}).get("form") or []
    return sorted({f.split("/")[0] for f in formes} & RAPPORTS)


def rafraichir(ctx, symboles: set[str]) -> dict:
    """Lit les fiches manquantes (ou vieilles de plus de 90 jours) et met à jour le fichier. Retourne un bilan."""
    syms = ctx.cache.get("sec_symboles")  # liste officielle des symboles, chargée par les lecteurs SEC de ce passage
    if syms is None or ctx.client is None:
        return {"lues": 0, "raison": "liste des symboles de la SEC pas lue à ce passage"}
    connus = charger(ctx.donnees)
    aujourdhui = ctx.maintenant.date()
    limite = (aujourdhui - timedelta(days=RELIRE_APRES_JOURS)).isoformat()
    a_lire = sorted(s for s in symboles if s not in connus or connus[s].get("lu", "") < limite
                    or "rapports" not in connus[s])[:MAX_PAR_PASSAGE]
    lues, erreurs = 0, 0
    for s in a_lire:
        cote = syms.par_symbole(s)
        if cote is None:
            continue
        try:
            t = ctx.client.get(f"https://data.sec.gov/submissions/CIK{int(cote['cik']):010d}.json")
            fiche = json.loads(t.contenu)
            type_, trouves = classer(fiche)
        except Exception:  # noqa: BLE001 - une fiche illisible : on garde l'ancienne valeur (ou rien)
            erreurs += 1
            continue
        connus[s] = {"cik": int(cote["cik"]), "nom": cote["name"], "type": type_, "formulaires_fonds": trouves,
                     "rapports": rapports(fiche), "lu": aujourdhui.isoformat()}
        lues += 1
    if lues:
        p = chemin(ctx.donnees)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(connus, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {"lues": lues, "erreurs": erreurs}


def symboles_recents(evenements: list[dict], aujourdhui: date, jours: int = 90) -> set[str]:
    """Les symboles des infos validées publiées depuis `jours` jours (ceux que le score peut noter)."""
    depuis = (aujourdhui - timedelta(days=jours)).isoformat()
    return {t for e in evenements if e.get("published_on", "") >= depuis for t in e.get("tickers") or []}
