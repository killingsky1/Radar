"""Résultats de Radar (lot G) : chaque compagnie qui entre dans une liste (hausse ou baisse), son prix officiel de la SEC
au départ, puis 1 semaine (7 jours) et 1 mois (30 jours) plus tard, comparé au marché. Rien n'est deviné :

- Prix : ceux des fichiers d'échecs de livraison de la SEC (collecteurs/prix_sec.py) ; pour une date de règlement, la
  SEC donne la clôture de la veille. Un titre a un prix seulement les jours où il a des échecs de livraison.
- Départ : la 2e date de règlement après le jour de la suggestion (heure de Toronto). Sa veille est donc un jour de
  bourse APRÈS la suggestion : jamais une clôture que la suggestion pouvait connaître. Sans prix ce jour-là : les 2
  dates de règlement suivantes au plus (départ plus tard, jamais plus tôt).
- Arrivée : la 1re date de règlement, de 7 (ou 30) jours après le départ jusqu'à 3 jours plus tard, où le titre a un
  prix.
- Marché : SPY, sinon IVV, sinon VOO (3 fonds qui suivent le S&P 500), aux MÊMES deux dates. « A battu le marché » :
  hausse = la compagnie a fait mieux ; baisse = elle a fait moins bien.
- Pas comparable : CUSIP différent entre le départ et l'arrivée (regroupement d'actions, nouveau titre).
- À vérifier, hors du taux : un saut de plus de ×1,8 (ou de moins de ÷1,8) d'un prix au suivant, ou une variation de plus
  de +100 % ou de moins de −50 % : possible fractionnement ou prix erroné (la SEC ne garantit pas ses prix). Mesuré dans
  les fichiers de juillet à septembre 2026 : 172 symboles ont changé de CUSIP et 175 sauts de cette taille.
- En attente : la SEC n'a pas encore publié ces dates (1re moitié du mois : fin du mois ; 2e moitié : vers le 15 du mois
  suivant ; elle ne garantit pas la date).
Une compagnie compte une seule fois par sens tant qu'elle n'est pas sortie de la liste depuis 30 jours.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .collecteurs import prix_sec

HORIZONS = {"7": "1 semaine", "30": "1 mois"}
TOLERANCE_ARRIVEE = 3  # jours
DATES_DE_DEPART_EN_PLUS = 2
SAUT_MAX = 1.8
ECART_FONDS_MAX = 0.003  # 2 fonds du S&P 500 aux mêmes dates : variations à 0,3 point près, sinon pas de verdict
VARIATION_MIN, VARIATION_MAX = -0.5, 1.0
JOURS_SANS_NOUVELLE_ENTREE = 30
TORONTO = ZoneInfo("America/Toronto")


def chemin_historique(donnees) -> Path:
    return Path(donnees) / "resultats" / "suggestions.json"


def lire_historique(donnees) -> dict:
    c = chemin_historique(donnees)
    return json.loads(c.read_text(encoding="utf-8")) if c.exists() else {"entrees": []}


def noter_entrees(historique: dict, score: dict, maintenant: datetime) -> list[dict]:
    """Note les compagnies des listes publiées : « vue » = dernier jour (Toronto) où elle était dans sa liste. Une
    nouvelle entrée seulement si elle n'y était pas depuis plus de 30 jours ; retourne les nouvelles entrées."""
    aujourd_hui = maintenant.astimezone(TORONTO).date()
    nouvelles = []
    for sens, liste in (("hausse", score.get("hausse", [])), ("baisse", score.get("baisse", []))):
        for r in liste:
            les_siennes = [e for e in historique["entrees"] if e["symbole"] == r["symbole"] and e["sens"] == sens]
            derniere = max(les_siennes, key=lambda e: e["entree"], default=None)
            if derniere and date.fromisoformat(derniere["vue"]) >= aujourd_hui - timedelta(days=JOURS_SANS_NOUVELLE_ENTREE):
                derniere["vue"] = max(derniere["vue"], aujourd_hui.isoformat())
                continue
            e = {"symbole": r["symbole"], "nom": r.get("nom") or r["symbole"], "sens": sens,
                 "entree": r.get("depuis") or maintenant.isoformat(), "vue": aujourd_hui.isoformat(),
                 "note10": r.get("note10"), "methode": score.get("version")}
            historique["entrees"].append(e)
            nouvelles.append(e)
    return nouvelles


def jour_toronto(iso: str) -> str:
    return datetime.fromisoformat(iso).astimezone(TORONTO).date().strftime("%Y%m%d")


def plus_jours(aaaammjj: str, n: int) -> str:
    return (date(int(aaaammjj[:4]), int(aaaammjj[4:6]), int(aaaammjj[6:])) + timedelta(days=n)).strftime("%Y%m%d")


def iso(aaaammjj: str) -> str:
    return f"{aaaammjj[:4]}-{aaaammjj[4:6]}-{aaaammjj[6:]}"


def en_attente(jour_reglement: str) -> dict:
    return {"statut": "en_attente", "attendu_vers": prix_sec.mise_en_ligne_prevue(jour_reglement).isoformat()}


def depart(e: dict, prix: dict, jours: list[str], couvert: str | None) -> dict:
    """La date de règlement de départ (voir les règles plus haut), ou pourquoi il n'y en a pas (encore)."""
    jour = jour_toronto(e["entree"])
    candidates = [j for j in jours if j > jour][1:2 + DATES_DE_DEPART_EN_PLUS]  # 2e date après, puis 2 de plus au plus
    for j in candidates:
        if j in prix:
            return {"statut": "ok", "date": j, "prix": prix[j][0], "cusip": prix[j][1]}
    if len(candidates) < 1 + DATES_DE_DEPART_EN_PLUS:  # des dates nécessaires ne sont pas encore publiées
        return en_attente(plus_jours(max(jour, couvert or jour), 1))
    return {"statut": "pas_de_prix"}


def mesurer(e: dict, d: dict, prix: dict, marche: dict, jours: list[str], couvert: str | None, n: int) -> dict:
    cible, limite = plus_jours(d["date"], n), plus_jours(d["date"], n + TOLERANCE_ARRIVEE)
    arrivee = next((j for j in jours if cible <= j <= limite and j in prix), None)
    if arrivee is None:
        if couvert is None or couvert < limite:  # une partie de la fenêtre n'est pas encore publiée
            return en_attente(max(cible, plus_jours(couvert, 1)) if couvert else cible)
        return {"statut": "pas_de_prix"}
    a, b = prix[d["date"]], prix[arrivee]
    r = {"date": arrivee, "prix": b[0], "variation": round(b[0] / a[0] - 1, 4)}
    if a[1] != b[1]:
        return {**r, "statut": "pas_comparable",
                "pourquoi": f"nouveau code de titre (CUSIP {a[1]} → {b[1]}) : regroupement d'actions ou nouveau titre"}
    suite = [prix[j][0] for j in jours if d["date"] <= j <= arrivee and j in prix]
    saut = max((max(x / y, y / x) for x, y in zip(suite, suite[1:])), default=1)
    if saut > SAUT_MAX or not VARIATION_MIN <= r["variation"] <= VARIATION_MAX:
        return {**r, "statut": "a_verifier",
                "pourquoi": "saut de prix anormal : possible fractionnement d'actions ou prix erroné (la SEC ne garantit "
                            "pas ses prix)"}
    fonds = {f: round(marche[f][arrivee][0] / marche[f][d["date"]][0] - 1, 4) for f in prix_sec.MARCHE
             if d["date"] in marche.get(f, {}) and arrivee in marche.get(f, {})}
    if not fonds:
        return {**r, "statut": "mesure", "marche": None, "battu": None, "pourquoi": "pas de prix du marché à ces dates"}
    if max(fonds.values()) - min(fonds.values()) > ECART_FONDS_MAX:
        return {**r, "statut": "mesure", "marche": None, "battu": None,
                "pourquoi": f"les fonds du S&P 500 ne concordent pas ({fonds}) : pas de verdict"}
    choisi = next(f for f in prix_sec.MARCHE if f in fonds)
    m = fonds[choisi]
    battu = r["variation"] > m if e["sens"] == "hausse" else r["variation"] < m
    return {**r, "statut": "mesure", "marche": {"fonds": choisi, "variation": m}, "ecart": round(r["variation"] - m, 4),
            "battu": battu}


def calculer(donnees, maintenant: datetime) -> dict:
    historique = lire_historique(donnees)
    etat = prix_sec.lire_etat(donnees)
    jours, couvert = prix_sec.calendrier(etat), prix_sec.couvert_jusqu_au(etat)
    marche = {f: etat["prix"].get(f, {}) for f in prix_sec.MARCHE}
    lignes = []
    for e in sorted(historique["entrees"], key=lambda x: (x["entree"], x["sens"], x["symbole"])):
        prix = etat["prix"].get(e["symbole"], {})
        d = depart(e, prix, jours, couvert)
        ligne = {**e, "depart": d, "horizons": {}}
        for h in HORIZONS:
            ligne["horizons"][h] = (mesurer(e, d, prix, marche, jours, couvert, int(h)) if d["statut"] == "ok" else
                                    {"statut": d["statut"], **({"attendu_vers": d["attendu_vers"]} if "attendu_vers" in d
                                                               else {})})
        lignes.append(ligne)
    resume = {}
    for h in HORIZONS:
        for sens in ("hausse", "baisse"):
            mesures = [l["horizons"][h] for l in lignes if l["sens"] == sens and l["horizons"][h]["statut"] == "mesure"
                       and l["horizons"][h]["battu"] is not None]
            resume[f"{sens}_{h}"] = {"mesurees": len(mesures), "battu": sum(m["battu"] for m in mesures),
                                     "ecart_moyen": round(sum(m["ecart"] for m in mesures) / len(mesures), 4) if mesures
                                     else None,
                                     "en_attente": sum(l["horizons"][h]["statut"] == "en_attente" for l in lignes
                                                       if l["sens"] == sens)}
    attentes = [l["horizons"][h]["attendu_vers"] for l in lignes for h in HORIZONS if "attendu_vers" in l["horizons"][h]]
    return {
        "genere_a": maintenant.isoformat(), "lignes": lignes, "resume": resume, "horizons": HORIZONS,
        "prix_jusqu_au": iso(couvert) if couvert else None, "prochains_prix_vers": min(attentes) if attentes else None,
        "methode": [
            "Prix : les fichiers d'échecs de livraison de la SEC. Pour une date de règlement, la SEC donne la clôture de la "
            "veille ; un titre a un prix seulement les jours où il a des échecs de livraison. La SEC ne garantit pas que ces "
            "prix sont identiques aux clôtures publiées ailleurs.",
            "Départ : la clôture d'un jour de bourse APRÈS la suggestion (jamais une clôture que Radar connaissait).",
            "Arrivée : 7 jours (1 semaine) ou 30 jours (1 mois) après le départ, ou jusqu'à 3 jours plus tard s'il n'y a "
            "pas de prix ce jour-là.",
            "Marché : SPY, sinon IVV, sinon VOO (fonds qui suivent le S&P 500), aux mêmes dates. Hausse : battu si la "
            "compagnie a fait mieux que le marché ; baisse : si elle a fait moins bien.",
            "Pas de prix, nouveau code de titre (CUSIP) ou saut anormal (possible fractionnement ou prix erroné) : montré, "
            "mais hors du taux de réussite.",
            "Publication de la SEC : la 1re moitié d'un mois à la fin du mois, la 2e moitié vers le 15 du mois suivant.",
        ],
    }
