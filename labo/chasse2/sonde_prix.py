"""Sonde des prix de la base (aucun site lu, aucun résultat de chasse) : les plus grands écarts d'un mois dans l'univers
des 1 000 plus grosses compagnies, et les plus grands sauts d'un jour (même code du titre, hors fractionnements
confirmés), avec les clôtures et les codes du titre autour. Pour trouver les prix erronés avant la chasse A.
Usage : python labo/chasse2/sonde_prix.py --base cache2/base --sortie labo/chasse2/sonde_prix.json"""
import argparse
import json
from pathlib import Path

import numpy as np

import chasse_b as b
import chasse_c
import commun as c


def autour(px, s, j, n=4):
    d = px.d[s]
    i = px.indice(s, j)
    return [[int(d[k]), round(float(px.p[s][k]), 4), px.c[s][k], round(float(px.f[s][k]), 4)]
            for k in range(max(i - n, 0), min(i + n + 1, len(d)))]


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--base", required=True)
    a.add_argument("--sortie", required=True)
    x = a.parse_args()
    px = c.Prix(x.base)
    carte, cies = b.Carte(x.base), b.charger_compagnies(x.base)
    inis, treize = b.charger_inities(x.base), b.charger_treize(x.base)
    meteo = chasse_c.meteo(x.base)
    fins = px.fins_de_mois(px.cal[0], px.cal[-1])

    def confirmer(s, avant, jour, n):
        cik = carte.au(jour // 100).get(s)
        if cik is None or cik not in cies:
            return False
        av, ap = cies[cik].actions_autour(avant, jour)
        return bool(av and ap) and abs((ap / av) / n - 1) <= 0.20
    for s in list(px.d):
        if s in ("SPY", "IWM", "SSO"):
            px.corriger(s, c.confirmer_fonds(px)) if s != "SPY" else px.corriger(s)
        else:
            px.corriger(s, confirmer)
    lignes, noms, _ = b.construire(px, carte, cies, inis, treize, meteo, fins, fins[1], c.entier(c.FIN))
    avec = sorted((l for l in lignes if l["cible"] is not None), key=lambda l: -abs(l["cible"]))
    mois = [{"mois": l["m"], "symbole": l["s"], "cik": l["cik"], "valeur_m": round(l["valeur_m"]), "ecart": round(l["cible"], 4),
             "clotures_debut": autour(px, l["s"], px.dernier(l["s"], l["m"], 5)[0])} for l in avec[:25]]
    # Sauts d'un jour (prix corrigés) des symboles de l'univers
    univers = sorted({l["s"] for l in lignes})
    sauts = []
    for s in univers:
        aj = px.ajustes(s)
        if len(aj) < 2:
            continue
        r = aj[1:] / aj[:-1]
        for k in np.nonzero((r > 3) | (r < 1 / 3))[0]:
            sauts.append((float(max(r[k], 1 / r[k])), s, int(px.d[s][k + 1])))
    sauts.sort(reverse=True)
    sortie = {"lignes_univers": len(lignes), "plus_grands_ecarts_mensuels": mois,
              "sauts_journaliers_x3": len(sauts),
              "plus_grands_sauts": [{"facteur": round(f, 2), "symbole": s, "jour": j, "clotures": autour(px, s, j)}
                                    for f, s, j in sauts[:40]]}
    Path(x.sortie).write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"sauts_x3": len(sauts), "top": [m["ecart"] for m in mois[:10]]}))


if __name__ == "__main__":
    main()
