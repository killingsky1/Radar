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
Lot L : chaque nouvelle entrée garde aussi ses raisons (les familles de sources qui comptent, la règle et les facteurs de
l'info retenue, la taille de la compagnie, la note sans le bonus de familles et sans le bonus de petite compagnie), pour
mesurer chaque signal à part (« par signal »). Les entrées d'avant le 5 octobre 2026 n'ont pas de raisons notées.
Lot M : les compagnies écartées de la liste « hausse » parce qu'elles valent moins de 100 M$ en bourse sont suivies de la
même façon (sens « ecartee »), à part : « a frappé juste » = elle a fait moins bien que le marché (la règle avait raison).
Elles ne comptent ni dans le taux de réussite des listes, ni dans le résumé par signal.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .collecteurs import prix_sec
from .score import NOTE_BAISSE, NOTE_HAUSSE, REGLES

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
    for sens, liste in (("hausse", score.get("hausse", [])), ("baisse", score.get("baisse", [])),
                        ("ecartee", score.get("ecartees", []))):
        for r in liste:
            les_siennes = [e for e in historique["entrees"] if e["symbole"] == r["symbole"] and e["sens"] == sens]
            derniere = max(les_siennes, key=lambda e: e["entree"], default=None)
            if derniere and date.fromisoformat(derniere["vue"]) >= aujourd_hui - timedelta(days=JOURS_SANS_NOUVELLE_ENTREE):
                derniere["vue"] = max(derniere["vue"], aujourd_hui.isoformat())
                continue
            e = {"symbole": r["symbole"], "nom": r.get("nom") or r["symbole"], "sens": sens,
                 "entree": r.get("depuis") or maintenant.isoformat(), "vue": aujourd_hui.isoformat(),
                 "note10": r.get("note10"), "methode": score.get("version"), **raisons(r, sens)}
            historique["entrees"].append(e)
            nouvelles.append(e)
    return nouvelles


def raisons(r: dict, sens: str) -> dict:
    """Pourquoi la compagnie entre dans la liste (lot L) : l'info retenue de chaque famille (règle, facteurs), la taille,
    et si elle serait entrée sans le bonus de familles ou sans le bonus de petite compagnie."""
    signaux = []
    for g in r.get("groupes") or []:
        i = next((i for i in g.get("infos") or [] if i.get("compte")), None)
        if i:
            signaux.append({"famille": g["famille"], "sens": g["sens"], "regle": i["regle"],
                            "facteurs": [f[0] for f in i.get("facteurs") or []]})
    x = {"signaux": signaux, "taille": (r.get("taille") or {}).get("taille")}
    for cle, nom in (("note10_sans_bonus", "grace_au_bonus"), ("note10_sans_taille", "grace_a_la_taille")):
        if r.get(cle) is not None and r.get("note10") is not None:
            x[cle] = r[cle]
            x[nom] = r[cle] > NOTE_BAISSE if sens == "baisse" else r[cle] < NOTE_HAUSSE
    return x


LIBELLES_SIGNAUX = {
    "plusieurs_familles": "Plusieurs familles de sources d'accord",
    "grace_au_bonus": "Entrée grâce au bonus de familles (+25 % par famille de plus)",
    "grace_a_la_taille": "Entrée grâce au bonus de petite compagnie (×1,5)",
    "taille:petite": "Petite compagnie (sous le 30e centile du NYSE)",
    "taille:moyenne": "Compagnie moyenne",
    "taille:grande": "Grande compagnie (70e centile du NYSE et plus)",
    "taille:inconnue": "Taille inconnue (compagnie étrangère, ou actions ou prix trop vieux)",
}


def cles_signal(l: dict) -> list[str] | None:
    """Les signaux d'une entrée, pour le résumé par signal ; None pour une entrée d'avant le lot L."""
    if "signaux" not in l:
        return None
    s = 1 if l["sens"] == "hausse" else -1
    memes = [x for x in l["signaux"] if x["sens"] == s]
    cles = [f"regle:{x['regle']}" for x in memes]
    cles += [f"facteur:{f}" for x in memes for f in x["facteurs"] if f != "Petite compagnie"]  # voir taille:petite
    cles += ["plusieurs_familles"] * (len(memes) >= 2)
    cles += [c for c in ("grace_au_bonus", "grace_a_la_taille") if l.get(c)]
    return sorted(set(cles)) + [f"taille:{l.get('taille') or 'inconnue'}"]


def libelle_signal(cle: str) -> str:
    if cle.startswith("regle:"):
        return REGLES.get(cle[6:], {}).get("libelle", cle[6:])
    if cle.startswith("facteur:"):
        return cle[8:]
    return LIBELLES_SIGNAUX.get(cle, cle)


def par_signal(lignes: list[dict]) -> dict:
    """{sens : {signal : {libelle, entrees, "7" : {mesurees, battu, ecart_moyen}, "30" : …}}} ; les entrées d'avant le lot
    L sont comptées à part (« sans_raisons »)."""
    sortie = {"hausse": {}, "baisse": {}, "sans_raisons": 0}
    for l in lignes:
        if l["sens"] not in ("hausse", "baisse"):  # écartées (lot M) : à part
            continue
        cles = cles_signal(l)
        if cles is None:
            sortie["sans_raisons"] += 1
            continue
        for c in cles:
            x = sortie[l["sens"]].setdefault(c, {"libelle": libelle_signal(c), "entrees": 0,
                                                **{h: {"mesurees": 0, "battu": 0, "ecarts": []} for h in HORIZONS}})
            x["entrees"] += 1
            for h in HORIZONS:
                m = l["horizons"][h]
                if m["statut"] == "mesure" and m.get("battu") is not None:
                    x[h]["mesurees"] += 1
                    x[h]["battu"] += m["battu"]
                    x[h]["ecarts"].append(m["ecart"])
    for sens in ("hausse", "baisse"):
        for x in sortie[sens].values():
            for h in HORIZONS:
                e = x[h].pop("ecarts")
                x[h]["ecart_moyen"] = round(sum(e) / len(e), 4) if e else None
    return sortie


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
    battu = r["variation"] > m if e["sens"] == "hausse" else r["variation"] < m  # baisse, écartée : moins bien que lui
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
        for sens in ("hausse", "baisse", "ecartee"):
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
        "par_signal": par_signal(lignes),
        "libelles_regles": {c: r["libelle"] for c, r in REGLES.items()},
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
            "Par signal : chaque entrée garde ses raisons depuis le 5 octobre 2026 (règle, facteurs, taille de la "
            "compagnie, bonus). Une entrée compte dans chacun de ses signaux. Peu d'entrées = résultat fragile.",
            "Écartées : les compagnies de moins de 100 M$ en bourse, hors de la liste « hausse » depuis la version 0.27, "
            "sont suivies de la même façon, à part. La règle a frappé juste quand la compagnie a fait moins bien que le "
            "marché.",
        ],
    }
