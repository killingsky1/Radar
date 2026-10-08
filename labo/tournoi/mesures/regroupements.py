"""Mesure (lecture seulement) : la valeur en bourse d'un achat d'initié utilise-t-elle un nombre d'actions daté d'AVANT
un changement de titre (CUSIP) ? C'est le signe d'un regroupement d'actions (ou d'un fractionnement) fait après le
dernier rapport : le nombre d'actions est alors d'avant, le prix d'après, et la valeur est fausse.

Pour chaque achat de la période qui a une valeur en bourse :
- D = la date (page couverture) du nombre d'actions utilisé (EntityCommonStockSharesOutstanding, le dernier déposé au
  plus tard le jour du dépôt) ;
- le CUSIP de la clôture utilisée (la veille du dépôt) ; s'il a été vu pour la 1re fois APRÈS D et qu'un autre CUSIP
  existait avant pour ce symbole, le nombre d'actions est peut-être d'avant le changement : « à risque ».
- Pour chaque cas : le saut du prix au changement (1er prix du nouveau CUSIP ÷ dernier prix de l'ancien) : ≥ 1,8 =
  regroupement probable (la valeur est trop haute d'autant), ≤ 0,55 = fractionnement probable (trop basse).

Usage : python mesures/regroupements.py --donnees cache/decouverte --sortie mesures/regroupements.json
"""
import argparse
import gzip
import json
from bisect import bisect_right
from collections import Counter
from pathlib import Path


def lire(chemin):
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        for l in f:
            yield json.loads(l)


def iso(n):
    s = str(n)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--donnees", required=True)
    a.add_argument("--sortie", required=True)
    x = a.parse_args()
    d = Path(x.donnees)
    periode = json.loads((d / "periode.json").read_text())
    prix = {r["s"]: ([iso(v) for v in r["d"]], r["p"], r["c"]) for r in lire(d / "prix.jsonl.gz")}
    faits = {}
    for r in lire(d / "finances.jsonl.gz"):
        faits[r["cik"]] = sorted(((f[4], f[1], f[2]) for f in (r.get("actions") or {}).get(
            "EntityCommonStockSharesOutstanding", []) if f[1] and f[4] and f[2]), key=lambda t: (t[0], t[1]))
    n = Counter()
    cas = []
    for e in lire(d / "evenements.jsonl.gz"):
        if e["sens"] != "achat" or not (periode["debut"] <= e["depot"] <= periode["fin"]) or e.get("valeur_m") is None:
            continue
        n["achats avec valeur en bourse"] += 1
        s, ca = e["symbole"], e.get("cloture_avant")
        if not s or not ca or s not in prix:
            n["sans série de prix"] += 1
            continue
        connus = [f for f in faits.get(e["cik"], []) if f[0] <= e["depot"]]
        if not connus:
            n["nombre d'actions introuvable dans les finances (vient d'un autre formulaire)"] += 1
            continue
        depose, fin, val = max(connus, key=lambda t: (t[0], t[1]))
        if abs(val - (e.get("actions_circulation") or 0)) > 0.5:
            n["nombre d'actions différent de celui de l'événement"] += 1
        jours, ps, cs = prix[s]
        k = bisect_right(jours, ca[0]) - 1
        if k < 0:
            n["sans série de prix"] += 1
            continue
        cusip = cs[k]
        premier = next(i for i in range(len(cs)) if cs[i] == cusip)
        autres_avant = [i for i in range(premier) if cs[i] != cusip]
        if not autres_avant or jours[premier] <= fin:
            n["sûrs (pas de changement de CUSIP après la date du nombre d'actions)"] += 1
            continue
        n["à risque (CUSIP vu pour la 1re fois après la date du nombre d'actions)"] += 1
        i_ancien = autres_avant[-1]
        saut = ps[premier] / ps[i_ancien] if ps[i_ancien] else None
        genre = ("regroupement probable" if saut and saut >= 1.8 else "fractionnement probable" if saut and saut <= 0.55
                 else "autre (nom, fusion…)")
        n[genre] += 1
        vraie = e["valeur_m"] / saut if saut and genre != "autre (nom, fusion…)" else None
        if genre == "regroupement probable" and e["valeur_m"] >= 100 and vraie is not None and vraie < 100:
            n["regroupement : passait la règle des 100 M$ à tort"] += 1
        if len(cas) < 40:
            cas.append({"symbole": s, "depot": e["depot"], "actions": val, "date_actions": fin, "cusip_ancien": cs[i_ancien],
                        "dernier_jour_ancien": jours[i_ancien], "cusip_nouveau": cusip, "premier_jour_nouveau": jours[premier],
                        "saut_du_prix": round(saut, 3) if saut else None, "genre": genre, "valeur_m_calculee": e["valeur_m"],
                        "valeur_m_corrigee_approx": round(vraie, 1) if vraie else None})
    total = n["achats avec valeur en bourse"]
    sortie = {"periode": periode, "compte": dict(n),
              "part_a_risque": round(n["à risque (CUSIP vu pour la 1re fois après la date du nombre d'actions)"] / total, 5)
              if total else None, "exemples": cas}
    Path(x.sortie).parent.mkdir(parents=True, exist_ok=True)
    Path(x.sortie).write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in sortie.items() if k != "exemples"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
