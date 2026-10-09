"""Mesure 3 (9 octobre 2026), étape 2 : le prix du formulaire 4 quand la SEC n'a pas de prix depuis 60 jours.

1. Fiabilité : prix moyen d'un achat ou d'une vente de dirigeant fait en un seul jour (formulaire 4) ÷ clôture de la SEC
   de ce jour-là (série de prix du labo, rangée à la date de clôture).
2. Fréquence : achats de dirigeants dont la taille serait connue SAUF le prix (compagnie qui dépose des 10-K/10-Q, nombre
   d'actions dei de 200 jours ou moins, 500 000 ou plus) et pour lesquels le robot n'aurait aucun prix de la SEC de 60 jours
   ou moins (les 2 derniers fichiers publiés le jour du dépôt, comme le robot).
3. Dans ces cas : un prix de formulaire 4 existe-t-il (achat ou vente du même émetteur, transaction de 60 jours ou moins,
   déposé au plus tard le jour du dépôt) ? La taille qu'il donne est-elle la même qu'avec la 1re clôture de la SEC après le
   dépôt (30 jours ou moins, même nombre d'actions) ? Et voit-on un changement de code du titre (CUSIP) autour ?
Lecture seulement du cache du labo (aucun site lu).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from regroupements2 import lire, seuils_par_mois, symbole  # noqa: E402

AMERICAINS = {"10-K", "10-Q", "10-KT", "10-QT", "10-K/A", "10-Q/A"}
ETRANGERS = {"20-F", "40-F", "6-K", "20-F/A", "40-F/A"}


def quantile(xs, q):
    xs = sorted(xs)
    return xs[int(q * (len(xs) - 1))] if xs else None


def iso8(j):
    return date(int(str(j)[:4]), int(str(j)[4:6]), int(str(j)[6:8]))


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--donnees", required=True)
    a.add_argument("--ftd", required=True)
    a.add_argument("--robot", required=True)
    a.add_argument("--sortie", required=True)
    x = a.parse_args()
    sys.path.insert(0, str(Path(x.robot).resolve()))
    from radar.collecteurs import prix_sec as ps
    from radar.collecteurs import taille as ta

    d = Path(x.donnees)
    periode = json.loads((d / "periode.json").read_text())
    evs = [e for e in lire(d / "evenements.jsonl.gz") if e.get("cik")]
    achats = [e for e in evs if e["sens"] == "achat" and periode["debut"] <= e["depot"] <= periode["fin"] and e.get("symbole")]
    voulus = {e["symbole"] for e in achats}
    seuils = seuils_par_mois(Path(x.robot) / "tests" / "fixtures" / "lotL" / "ME_Breakpoints_CSV.zip")

    # Prix des formulaires 4 par émetteur : (jour de la dernière transaction, dépôt, prix moyen, sens, titres, un seul jour)
    f4 = defaultdict(list)
    for e in evs:
        if e.get("prix_moyen") and e["prix_moyen"] > 0 and e.get("jour_dernier"):
            f4[e["cik"]].append((e["jour_dernier"], e["depot"], e["prix_moyen"], e["sens"], tuple(e.get("titres") or ()),
                                 e.get("jour_premier") == e["jour_dernier"]))
    for v in f4.values():
        v.sort()

    # Série de clôtures de la SEC (labo : rangées à la date de clôture), pour la fiabilité et la « vraie » clôture après
    serie = {}
    for r in lire(d / "prix.jsonl.gz"):
        serie[r["s"]] = ([int(j) for j in r["d"]], r["p"], r["c"])

    # 1. Fiabilité : prix du formulaire 4 d'une transaction d'un seul jour ÷ clôture de la SEC du même jour
    ecarts, ecarts_sens, gros = [], defaultdict(list), []
    for e in evs:
        s = e.get("symbole")
        if not s or s not in serie or not e.get("prix_moyen") or e.get("jour_premier") != e.get("jour_dernier") or not e.get("jour_dernier"):
            continue
        jours, prix, cus = serie[s]
        j = int(e["jour_dernier"].replace("-", ""))
        k = bisect_left(jours, j)
        if k < len(jours) and jours[k] == j and prix[k] > 0:
            r = e["prix_moyen"] / prix[k]
            ecarts.append(r)
            ecarts_sens[e["sens"]].append(r)
            if abs(r - 1) > 0.25 and len(gros) < 25:
                gros.append({"symbole": s, "sens": e["sens"], "jour": e["jour_dernier"], "prix_f4": e["prix_moyen"],
                             "cloture_sec": prix[k], "titres": e.get("titres"), "id": e["id"]})

    def part(rs, lim):
        return round(sum(abs(r - 1) <= lim for r in rs) / len(rs), 4) if rs else None

    fiabilite = {"transactions comparées": len(ecarts),
                 "à 2 % ou moins": part(ecarts, 0.02), "à 5 % ou moins": part(ecarts, 0.05),
                 "à 10 % ou moins": part(ecarts, 0.10), "à 25 % ou moins": part(ecarts, 0.25),
                 "écart médian": round(quantile([abs(r - 1) for r in ecarts], 0.5) or 0, 4),
                 "écart au 95e centile": round(quantile([abs(r - 1) for r in ecarts], 0.95) or 0, 4),
                 "par sens": {k: {"n": len(v), "à 5 % ou moins": part(v, 0.05), "à 25 % ou moins": part(v, 0.25)}
                              for k, v in ecarts_sens.items()},
                 "exemples d'écarts de plus de 25 %": gros}

    # Le robot : fichiers d'échecs publiés le jour du dépôt, le prix le plus récent des 2 derniers
    debut_h = (date.fromisoformat(periode["debut"]) - timedelta(days=120)).strftime("%Y%m%d")
    cles = sorted(p.stem for p in Path(x.ftd).glob("*.zip") if re.fullmatch(r"\d{6}[ab]", p.stem))
    cles = [c for c in cles if ps.periode(c)[1] >= debut_h]
    prix_f = {}
    for c in cles:
        pf = {}
        for jour, cusip, s, p in ta.lire_lignes((Path(x.ftd) / f"{c}.zip").read_bytes()):
            s = symbole(s)
            if s in voulus and p is not None and (s not in pf or jour > pf[s][0]):
                pf[s] = [jour, p, cusip]
        prix_f[c] = pf
    pub = {c: ps.mise_en_ligne_prevue(ps.periode(c)[0]) for c in cles}
    par_pub = sorted(cles, key=lambda c: (pub[c], c))
    dates_pub = [pub[c] for c in par_pub]

    faits, formes = {}, defaultdict(set)
    for r in lire(d / "finances.jsonl.gz"):
        fs = (r.get("actions") or {}).get("EntityCommonStockSharesOutstanding") or []
        faits[r["cik"]] = [(f[1], f[2], f[4]) for f in fs if f[1] and f[2] and f[4] and f[2] > 0]
        for f in fs:
            if len(f) > 5 and f[5]:
                formes[r["cik"]].add(f[5])

    n, ex = Counter(), defaultdict(list)
    accord = Counter()
    for e in achats:
        s, cik, X = e["symbole"], e["cik"], date.fromisoformat(e["depot"])
        fo = formes.get(cik, set())
        if fo & ETRANGERS or not fo & AMERICAINS:
            n["hors calcul : étrangère ou sans 10-K/10-Q"] += 1
            continue
        connus = [f for f in faits.get(cik, []) if f[2] <= e["depot"]]
        if not connus:
            n["hors calcul : pas de nombre d'actions"] += 1
            continue
        fin, val, _ = max(connus, key=lambda f: (f[0], f[2]))
        if date.fromisoformat(fin) < X - timedelta(days=200) or val < 500_000:
            n["hors calcul : actions trop vieilles ou moins de 500 000"] += 1
            continue
        n["achats calculables sauf peut-être le prix"] += 1
        k = bisect_left(dates_pub, X)
        prix = None
        for c in sorted(par_pub[:k])[-2:]:
            p = prix_f[c].get(s)
            if p and (prix is None or p[0] > prix[0]):
                prix = p
        if prix and iso8(prix[0]) >= X - timedelta(days=60):
            n["prix de la SEC de 60 jours ou moins (taille connue aujourd'hui)"] += 1
            continue
        n["SANS prix de la SEC de 60 jours ou moins (taille inconnue aujourd'hui)"] += 1
        lim = (X - timedelta(days=60)).isoformat()
        cands = [t for t in f4.get(cik, []) if t[1] <= e["depot"] and t[0] >= lim]
        if not cands:
            n["  … et aucun prix de formulaire 4 de 60 jours ou moins"] += 1
            continue
        jt, dt, p4, sens, titres, un_jour = max(cands)
        n["  … avec un prix de formulaire 4 de 60 jours ou moins"] += 1
        n[f"  … dont le prix le plus récent vient d'un(e) {sens}"] += 1
        age = (X - date.fromisoformat(jt)).days
        n["  … âge du prix ≤ 7 jours" if age <= 7 else "  … âge du prix 8 à 30 jours" if age <= 30 else "  … âge du prix 31 à 60 jours"] += 1
        mois = (X.replace(day=1) - timedelta(days=1)).strftime("%Y%m")
        p30, p70 = seuils.get(mois) or seuils[max(m for m in seuils if m <= mois)]
        v4 = val * p4 / 1e6
        cat = lambda v: "petite" if v < p30 else "grande" if v >= p70 else "moyenne"  # noqa: E731
        # « vraie » clôture : la 1re de la SEC après le dépôt (30 jours ou moins)
        vraie = None
        if s in serie:
            jours, px, cus = serie[s]
            i = bisect_right(jours, int(e["depot"].replace("-", "")))
            if i < len(jours) and iso8(jours[i]) <= X + timedelta(days=30):
                vraie = (jours[i], px[i], cus[i])
                # changement de CUSIP entre la transaction et cette clôture, ou depuis 120 jours avant les actions ?
                a0 = int((min(date.fromisoformat(jt), date.fromisoformat(fin)) - timedelta(days=120)).strftime("%Y%m%d"))
                vus = {cus[m] for m in range(bisect_left(jours, a0), i + 1)}
                if len(vus) > 1:
                    n["  … CUSIP changé autour (prix ou actions peut-être d'une autre époque)"] += 1
        if not vraie:
            n["  … pas de clôture de la SEC dans les 30 jours après (pas de vérité)"] += 1
            continue
        vv = val * vraie[1] / 1e6
        accord["comparés"] += 1
        accord["même taille"] += cat(v4) == cat(vv)
        accord["même côté de 100 M$"] += (v4 < 100) == (vv < 100)
        accord["prix à 25 % ou moins de la clôture d'après"] += abs(p4 / vraie[1] - 1) <= 0.25
        if (cat(v4) != cat(vv) or (v4 < 100) != (vv < 100)) and len(ex["désaccords"]) < 20:
            ex["désaccords"].append({"symbole": s, "depot": e["depot"], "actions": [val, fin], "prix_f4": [jt, p4, sens],
                                     "cloture_apres": vraie[:2], "valeur_f4_m": round(v4, 1), "valeur_apres_m": round(vv, 1)})
        elif len(ex["accords"]) < 8:
            ex["accords"].append({"symbole": s, "depot": e["depot"], "prix_f4": [jt, p4, sens], "cloture_apres": vraie[:2],
                                  "valeur_f4_m": round(v4, 1), "taille": cat(v4)})
    sortie = {"periode": periode, "fiabilite": fiabilite, "compte": dict(n), "accord": dict(accord), "exemples": ex}
    Path(x.sortie).write_text(json.dumps(sortie, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: sortie[k] for k in ("compte", "accord")}, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in fiabilite.items() if k != "exemples d'écarts de plus de 25 %"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
