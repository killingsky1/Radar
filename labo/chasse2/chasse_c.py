"""Chasse C — la météo des initiés de toute la bourse (labo/chasse2/PLAN.md).

Chaque jour : parmi les formulaires 4 (achat P ou vente S en bourse) déposés les 30 jours civils d'avant, jusqu'à la
veille, part des compagnies avec un achat parmi les compagnies avec un achat ou une vente. Son rang parmi ses valeurs
des 5 années d'avant (jours ouvrables, lundi au vendredi). Normalement : SPY. Rang ≥ 90 % : SSO (S&P 500 deux fois par
jour) pour les 126 jours de bourse suivants (renouvelé si le rang est encore ≥ 90 % le dernier jour), puis SPY.
Usage : python labo/chasse2/chasse_c.py --base cache2/base --sortie labo/chasse2/resultats_c
"""
from __future__ import annotations

import argparse
import json
from bisect import bisect_left, bisect_right, insort
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import commun as c

FENETRE = 30
HISTOIRE_ANS = 5
SEUIL = 0.90
DUREE = 126
SSO_FRAIS_AN = 0.0089
COUVERTURE_MIN = 0.90


def meteo(base, jusqu_a=None):
    """{jour (AAAA-MM-JJ, chaque jour civil) : part des compagnies avec un achat parmi celles avec un achat ou une vente,
    dépôts des 30 jours d'avant jusqu'à la veille}."""
    achats, ventes = defaultdict(set), defaultdict(set)
    for r in c.lire_jsonl(Path(base) / "inities.jsonl.gz"):
        (achats if r[3] == "achat" else ventes)[r[0]].add(r[1])
    jours = sorted(set(achats) | set(ventes))
    ca, cv = Counter(), Counter()
    j = date.fromisoformat(jours[0])
    fin = date.fromisoformat(jusqu_a) if jusqu_a else date.fromisoformat(jours[-1]) + timedelta(days=1)
    sortie = {}
    while j <= fin:
        entre, sort = (j - timedelta(days=1)).isoformat(), (j - timedelta(days=FENETRE + 1)).isoformat()
        for compte, depots in ((ca, achats), (cv, ventes)):
            compte.update(depots.get(entre, ()))
            for cik in depots.get(sort, ()):
                compte[cik] -= 1
                if compte[cik] <= 0:
                    del compte[cik]
        a, v = len(ca), len(cv)
        sortie[j.isoformat()] = a / (a + v) if a + v else None
        j += timedelta(days=1)
    return sortie


def rangs(serie):
    """{jour ouvrable : rang (0 à 1) de la valeur du jour parmi celles des jours ouvrables des 5 années d'avant}."""
    jours = sorted(j for j, v in serie.items() if v is not None and date.fromisoformat(j).weekday() < 5)
    passe, entres, k, sortie = [], [], 0, {}
    for j in jours:
        limite = (date.fromisoformat(j) - timedelta(days=round(365.25 * HISTOIRE_ANS))).isoformat()
        while k < len(entres) and entres[k][0] < limite:
            v = entres[k][1]
            del passe[bisect_left(passe, v)]
            k += 1
        if entres and entres[0][0] < limite or k > 0:  # 5 années complètes derrière
            v = serie[j]
            n = len(passe)
            sortie[j] = (bisect_left(passe, v) + (bisect_right(passe, v) - bisect_left(passe, v)) / 2) / n if n else None
        insort(passe, serie[j])
        entres.append((j, serie[j]))
    return sortie


def corrigees(px, s):
    """{jour : clôture corrigée} (codes du titre enchaînés, fractionnements confirmés : labo/chasse2/PLAN.md)."""
    return {j: px.corrige(s, i) for i, j in enumerate(px.d[s])}


def series_sso(px, jours):
    """Clôtures de SSO aux jours voulus : les vraies si SSO a une clôture au moins 90 % des jours, sinon un SSO calculé
    (2 fois le rendement de SPY du jour, moins 0,89 % par année)."""
    vrais = set(px.d.get("SSO", []))
    couverture = sum(1 for j in jours if j in vrais) / len(jours)
    spy = corrigees(px, "SPY")
    if couverture >= COUVERTURE_MIN:
        ss = corrigees(px, "SSO")
        sortie, dernier = {}, None
        for j in jours:
            dernier = ss.get(j, dernier)
            sortie[j] = dernier
        return sortie, {"source": "vraies clôtures de SSO", "couverture": round(couverture, 4)}
    sortie, v, avant = {}, 100.0, None
    for j in jours:
        if avant is not None and j in spy and avant in spy:
            v *= 1 + 2 * (spy[j] / spy[avant] - 1) - SSO_FRAIS_AN / 252
        sortie[j] = v
        if j in spy:
            avant = j
    return sortie, {"source": "SSO calculé (2 × SPY par jour − 0,89 %/an)", "couverture": round(couverture, 4)}


def simuler(px, rang, frais):
    jours = [j for j in px.cal if c.entier(c.DEBUT) <= j <= c.entier(c.FIN)]
    spy = {}
    dernier = None
    spy_vrai = corrigees(px, "SPY")
    for j in jours:
        dernier = spy_vrai.get(j, dernier)
        spy[j] = dernier
    sso, info_sso = series_sso(px, jours)
    prix = {"SPY": spy, "SSO": sso}
    tenu, parts, argent = "SPY", 0.0, c.CAPITAL
    fin_pari, valeurs, episodes, paris = None, [], [], defaultdict(bool)

    def acheter(t, j, montant):
        return (montant - c.cout(montant, 1e9, frais)) / prix[t][j]

    parts = acheter("SPY", jours[0], argent)
    for i, j in enumerate(jours):
        r = rang.get(c.iso(j))
        if tenu == "SPY" and r is not None and r >= SEUIL:
            montant = parts * prix["SPY"][j]
            montant -= c.cout(montant, 1e9, frais)
            parts, tenu, fin_pari = acheter("SSO", j, montant), "SSO", i + DUREE
            episodes.append({"debut": c.iso(j), "rang": round(r, 4)})
        elif tenu == "SSO" and i >= fin_pari:
            if r is not None and r >= SEUIL:
                fin_pari = i + DUREE
                episodes[-1].setdefault("renouvele", []).append(c.iso(j))
            else:
                montant = parts * prix["SSO"][j]
                montant -= c.cout(montant, 1e9, frais)
                parts, tenu = acheter("SPY", j, montant), "SPY"
                episodes[-1]["fin"] = c.iso(j)
        if tenu == "SSO":
            paris[c.annee(j)] = True
        valeurs.append((j, parts * prix[tenu][j]))
    return valeurs, spy, episodes, dict(paris), info_sso


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--base", required=True)
    a.add_argument("--sortie", required=True)
    x = a.parse_args()
    px = c.Prix(x.base, symboles={"SPY", "SSO"})
    px.corriger("SPY")
    fractionnements = px.corriger("SSO", c.confirmer_fonds(px)) if "SSO" in px.d else []
    serie = meteo(x.base)
    rang = rangs(serie)
    resultats = {"plan": "labo/chasse2/PLAN.md (chasse C)", "meteo_du": min(rang), "meteo_au": max(rang),
                 "fractionnements_sso": fractionnements, "prix_retires": px.retires}
    for nom, frais in c.FRAIS.items():
        valeurs, spy, episodes, paris, info_sso = simuler(px, rang, frais)
        j = c.juger(valeurs, spy, paris)
        resultats[nom] = {**j, "episodes": episodes, "sso": info_sso}
        print(f"chasse C, frais {nom} : {json.dumps({k: j[k] for k in ('total', 'examen_2012_2017', 'annees_gagnees', 't_mensuel', 'reussi')}, ensure_ascii=False)}")
    Path(x.sortie).mkdir(parents=True, exist_ok=True)
    (Path(x.sortie) / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n",
                                                   encoding="utf-8")


if __name__ == "__main__":
    main()
