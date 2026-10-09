"""Chasse A — lire les rapports annuels (« Lazy Prices », labo/chasse2/PLAN.md).

Un 10-K d'une compagnie de l'univers (les 1 000 plus grosses à la dernière fin de mois avant son dépôt) « ne change
pas » si sa similarité avec le 10-K précédent est dans les 20 % les plus hautes des 10-K de l'univers déposés les 12 mois
d'AVANT. Achat à la clôture du 1er jour de bourse après le dépôt (3 jours de plus au plus), gardé 252 jours de bourse ;
10 positions au plus ; à places égales, la plus haute similarité d'abord ; l'argent qui attend dans SPY ; frais du banc.
Usage : python labo/chasse2/chasse_a.py --base cache2/base --similarites cache2/a/similarites.jsonl --sortie labo/chasse2/resultats_a
"""
from __future__ import annotations

import argparse
import json
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np

import chasse_b as b
import commun as c

PART = 0.20          # les 20 % les plus hautes
MIN_HISTOIRE = 50    # au moins 50 similarités les 12 mois d'avant pour fixer le seuil
DUREE = 252
POSITIONS = 10
TOL_ENTREE, TOL_SORTIE = 3, 10


def univers_par_mois(px, carte, cies, fins):
    """{fin de mois : {cik : (symbole, valeur en M$)}} : les 1 000 plus grosses (même calcul que la chasse B)."""
    sortie = {}
    for m in fins:
        candidats = []
        for s, cik in carte.au(m // 100).items():
            if s not in px.d or cik not in cies:
                continue
            x = px.dernier(s, m, b.TOL_MOIS)
            if not x or x[1] < b.PRIX_MIN:
                continue
            n = cies[cik].nb_actions(m)
            if n:
                candidats.append((x[1] * n / 1e6, s, cik))
        candidats.sort(reverse=True)
        sortie[m] = {cik: (s, v) for v, s, cik in candidats[:b.UNIVERS]}
    return sortie


def signaux(similarites, univers, fins):
    """Les 10-K de l'univers avec une similarité, leur seuil (20 % les plus hautes des 12 mois d'avant) et le signal."""
    candidats = []
    for r in similarites:
        if r.get("similarite") is None:
            continue
        j = c.entier(r["depot"])
        k = bisect_left(fins, j) - 1  # dernière fin de mois AVANT le dépôt
        if k < 0 or r["cik"] not in univers.get(fins[k], {}):
            continue
        s, v = univers[fins[k]][r["cik"]]
        candidats.append({"jour": j, "cik": r["cik"], "symbole": s, "valeur_m": v, "similarite": r["similarite"]})
    candidats.sort(key=lambda x: x["jour"])
    jours = [x["jour"] for x in candidats]
    for x in candidats:
        debut = c.entier((date.fromisoformat(c.iso(x["jour"])) - timedelta(days=365)).isoformat())
        avant = [y["similarite"] for y in candidats[bisect_left(jours, debut):bisect_left(jours, x["jour"])]]
        x["seuil"] = float(np.quantile(avant, 1 - PART)) if len(avant) >= MIN_HISTOIRE else None
        x["signal"] = x["seuil"] is not None and x["similarite"] >= x["seuil"]
        # pour comprendre seulement (pas jugé) : les 20 % qui changent le plus (similarité la plus basse)
        bas = float(np.quantile(avant, PART)) if len(avant) >= MIN_HISTOIRE else None
        x["change_beaucoup"] = bas is not None and x["similarite"] <= bas
    return candidats


def simuler(px, cands, frais):
    jours = [j for j in px.cal if c.entier(c.DEBUT) <= j <= c.entier(c.FIN)]
    spy_px, dernier = {}, None
    spy_d = {int(j): px.corrige("SPY", i) for i, j in enumerate(px.d["SPY"])}
    for j in px.cal:
        dernier = spy_d.get(j, dernier)
        spy_px[j] = dernier
    a_faire = defaultdict(list)  # jour d'achat prévu → signaux (le 1er jour de bourse après le dépôt)
    for x in cands:
        if x["signal"]:
            r = bisect_right(px.cal, x["jour"])
            if r < len(px.cal) and c.entier(c.DEBUT) <= px.cal[r] <= c.entier(c.FIN):
                a_faire[px.cal[r]].append(x)
    tenus = {}  # symbole → [parts, valeur M$, indice de sortie prévue dans le calendrier]
    argent, spy_parts, valeurs, journal = c.CAPITAL, 0.0, [], Counter()

    def prix_corrige(s, j, tol):
        x = px.dernier(s, j, tol)
        return (x[0], px.corrige(s, px.indice(s, x[0]))) if x else None

    attente = []  # signaux qui attendent une clôture (3 jours de plus au plus)
    for i, j in enumerate(jours):
        rang = px.pos[j]
        for s in [s for s, t in tenus.items() if rang >= t[2]]:  # sorties prévues (sinon la dernière clôture)
            x = px.dernier(s, j, TOL_SORTIE) or px.dernier(s, j, 10**6)
            p = px.corrige(s, px.indice(s, x[0]))
            montant = tenus[s][0] * p
            argent += montant - c.cout(montant, tenus[s][1], frais)
            del tenus[s]
            journal["ventes"] += 1
        attente = [x for x in attente if px.pos[j] - x["prevu"] <= TOL_ENTREE]
        for x in sorted(a_faire.get(j, []), key=lambda x: -x["similarite"]):
            attente.append({**x, "prevu": rang})
        restants = []
        for x in sorted(attente, key=lambda x: -x["similarite"]):
            journal["signaux vus"] += x.get("vu", 0) == 0
            x["vu"] = 1
            if x["symbole"] in tenus:
                journal["déjà en portefeuille"] += 1
                continue
            if len(tenus) >= POSITIONS:
                journal["places pleines"] += 1
                continue
            cl = px.premier(x["symbole"], j, 0)
            if not cl:
                restants.append(x)
                continue
            total = argent + spy_parts * (spy_px[j] or 0) + sum(
                t[0] * (prix_corrige(s, j, 10**6) or (0, 0))[1] for s, t in tenus.items())
            montant = total / POSITIONS
            if argent < montant and spy_parts:
                besoin = min(montant - argent, spy_parts * spy_px[j])
                spy_parts -= besoin / spy_px[j]
                argent += besoin - c.cout(besoin, 1e9, frais)
            montant = min(montant, argent)
            if montant < 50:
                journal["sans argent"] += 1
                continue
            p = px.corrige(x["symbole"], px.indice(x["symbole"], cl[0]))
            tenus[x["symbole"]] = [(montant - c.cout(montant, x["valeur_m"], frais)) / p, x["valeur_m"], rang + DUREE]
            argent -= montant
            journal["achats"] += 1
        attente = restants
        if argent >= b.MIN_SPY and spy_px[j]:
            spy_parts += (argent - c.cout(argent, 1e9, frais)) / spy_px[j]
            argent = 0.0
        valeur = argent + spy_parts * (spy_px[j] or 0) + sum(
            t[0] * (prix_corrige(s, j, 10**6) or (0, 0))[1] for s, t in tenus.items())
        valeurs.append((j, valeur))
    return valeurs, {j: spy_px[j] for j in jours}, dict(journal)


def comprendre(px, cands):
    """Pour comprendre (pas pour juger) : rendement sur 252 jours moins SPY, signaux contre les autres, par année."""
    par = defaultdict(lambda: {"signal": [], "autres": [], "change_beaucoup": []})
    for x in cands:
        if x["seuil"] is None:
            continue
        r = bisect_right(px.cal, x["jour"])
        if r + DUREE >= len(px.cal):
            continue
        a, z = px.premier(x["symbole"], px.cal[r], TOL_ENTREE), px.dernier(x["symbole"], px.cal[r + DUREE], 10**6)
        sa, sz = px.dernier("SPY", px.cal[r], 5), px.dernier("SPY", px.cal[r + DUREE], 5)
        if not (a and z and sa and sz) or z[0] <= a[0]:
            continue
        ecart = px.rendement(x["symbole"], a[0], z[0]) - px.rendement("SPY", sa[0], sz[0])
        par[c.annee(x["jour"])]["signal" if x["signal"] else "autres"].append(ecart)
        if x["change_beaucoup"]:
            par[c.annee(x["jour"])]["change_beaucoup"].append(ecart)
    return {a: {k: {"n": len(v), "moyenne": round(float(np.mean(v)), 4) if v else None,
                    "mediane": round(float(np.median(v)), 4) if v else None} for k, v in d.items()}
            for a, d in sorted(par.items())}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--base", required=True)
    a.add_argument("--similarites", required=True)
    a.add_argument("--sortie", required=True)
    x = a.parse_args()
    px = c.Prix(x.base)
    carte, cies = b.Carte(x.base), b.charger_compagnies(x.base)

    def confirmer(s, avant, jour, n):
        cik = carte.au(jour // 100).get(s)
        if cik is None or cik not in cies:
            return False
        av, ap = cies[cik].actions_autour(avant, jour)
        return bool(av and ap) and abs((ap / av) / n - 1) <= 0.20
    fract = []
    for s in list(px.d):
        fract += px.corriger(s) if s == "SPY" else px.corriger(s, c.confirmer_fonds(px) if s in ("IWM", "SSO") else confirmer)
    fins = px.fins_de_mois(px.cal[0], px.cal[-1])
    univers = univers_par_mois(px, carte, cies, fins)
    sims = [json.loads(l) for l in Path(x.similarites).read_text().splitlines() if l.strip()]
    cands = signaux(sims, univers, fins)
    resultats = {"plan": "labo/chasse2/PLAN.md (chasse A)", "dix_k_avec_similarite": sum(1 for s in sims if s.get("similarite") is not None),
                 "dix_k_de_l_univers": len(cands), "signaux": sum(1 for x in cands if x["signal"]),
                 "fractionnements": len(fract), "pour_comprendre": comprendre(px, cands), "prix_retires": px.retires}
    for nom, frais in c.FRAIS.items():
        valeurs, spy, journal = simuler(px, cands, frais)
        j = c.juger(valeurs, spy)
        resultats[nom] = {**j, "ordres": journal}
        print(f"chasse A, frais {nom} : {json.dumps({k: j[k] for k in ('total', 'examen_2012_2017', 'annees_gagnees', 't_mensuel', 'reussi')}, ensure_ascii=False)}",
              flush=True)
    Path(x.sortie).mkdir(parents=True, exist_ok=True)
    (Path(x.sortie) / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n",
                                                   encoding="utf-8")


if __name__ == "__main__":
    main()
