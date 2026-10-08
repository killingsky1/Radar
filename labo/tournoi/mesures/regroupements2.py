"""Mesure 2 (8 octobre 2026) : la règle du robot (étape 1, « données sûres ») rejouée sur les vrais fichiers du labo.

Pour chaque achat de dirigeant du jeu (découverte 2023-2026 ou coffre-fort 2016-2023), on refait ce que le robot aurait
su le jour du dépôt, puis on appelle le VRAI code du robot (radar.collecteurs.taille.classer, branche travail) :
- fichiers d'échecs de livraison publiés avant ce jour (la SEC : 1re moitié du mois publiée à la fin du mois, 2e moitié
  vers le 15 du mois suivant, voir prix_sec.mise_en_ligne_prevue) ; le prix = le plus récent des 2 derniers (comme le
  robot) ;
- historique des CUSIP = les fichiers publiés des 400 derniers jours (le départ du robot, le pire cas) ; aussi refait avec
  tous les fichiers publiés depuis juillet 2015 (le robot après des années), pour voir si 400 jours suffisent ;
- nombre d'actions = le fait dei:EntityCommonStockSharesOutstanding DÉPOSÉ au plus tard ce jour-là avec la date la plus
  récente (comme companyconcept dans le robot) ;
- seuils du NYSE = le mois d'avant dans le fichier de Kenneth French (copie du robot : tests/fixtures/lotL).
Trois règles comparées : « avant » (robot 0.27.0, sans historique), « inconnue » (taille inconnue dès qu'un CUSIP change
après les actions, la règle annoncée le 8 octobre) et « époque » (le code de la branche travail : le prix de la même
époque que les actions ; les deux valeurs possibles si on ne sait pas, taille connue seulement si elles s'accordent).

La « vraie » valeur, pour juger seulement (jamais pour décider) : le 1er nombre d'actions déclaré à une date entre le dépôt
et 120 jours plus tard (déposé n'importe quand) × la dernière clôture de la SEC au plus 10 jours avant le dépôt, si aucun
autre CUSIP n'est vu entre les deux dates.
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import sys
import zipfile
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

VIDES = {"NONE", "NA", "N-A", "NULL", "N", "TBD", ""}  # comme donnees.py
TROP_PETITE = 100  # M$, comme score.py


def symbole(s):
    """Comme donnees.symbole(sec.normaliser_symbole(s)) : le format des achats du jeu."""
    s = (s or "").strip().upper().replace(".", "-")
    s = re.split(r"[\s,;]+", s)[0] if s else ""
    s = s.replace(".", "-").replace("/", "-")
    return s if s not in VIDES and re.fullmatch(r"[A-Z][A-Z0-9-]{0,9}", s) else None


def lire(chemin):
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        for l in f:
            yield json.loads(l)


def seuils_par_mois(chemin):
    """{AAAAMM : (p30, p70)} de tous les mois du fichier de Kenneth French."""
    with zipfile.ZipFile(chemin) as z:
        texte = z.read(z.namelist()[0]).decode("latin-1")
    sortie = {}
    for l in texte.splitlines():
        if re.match(r"\s*\d{6}\s*,", l):
            m = [x.strip() for x in l.split(",")]
            if len(m) == 22:
                c = [float(v) for v in m[2:]]
                sortie[m[0]] = (c[5], c[13])
    return sortie


def fusion(resumes):
    """L'historique d'un symbole à partir des résumés de plusieurs fichiers (même résultat que ta.ajouter_lignes sur toutes
    leurs lignes : les fichiers ne partagent aucune date de règlement)."""
    h = {}
    for r in resumes:
        for cu, v in r.items():
            w = h.get(cu)
            if w is None:
                h[cu] = list(v)
                continue
            w[0], w[1] = min(w[0], v[0]), max(w[1], v[1])
            if v[2] is not None and (w[2] is None or v[2] > w[2]):
                w[2], w[3] = v[2], v[3]
    return h


def decision(r):
    """(écartée par la règle des 100 M$, bonus de petite compagnie, taille) d'un résultat de classer, None si inconnue."""
    if r is None or not r.get("taille"):
        return (False, False, None)
    return (r["valeur_m"] < TROP_PETITE, r["taille"] == "petite", r["taille"])


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
    achats = [e for e in lire(d / "evenements.jsonl.gz")
              if e["sens"] == "achat" and periode["debut"] <= e["depot"] <= periode["fin"] and e.get("symbole")
              and e.get("cik")]
    voulus = {e["symbole"] for e in achats}
    seuils = seuils_par_mois(Path(x.robot) / "tests" / "fixtures" / "lotL" / "ME_Breakpoints_CSV.zip")
    debut_h = (date.fromisoformat(periode["debut"]) - timedelta(days=ta.HISTOIRE_JOURS + 31)).strftime("%Y%m%d")
    cles = sorted(p.stem for p in Path(x.ftd).glob("*.zip") if re.fullmatch(r"\d{6}[ab]", p.stem))
    cles = [c for c in cles if ps.periode(c)[1] >= debut_h]
    resume, prix_f, lignes = {}, {}, defaultdict(list)
    for c in cles:
        contenu = (Path(x.ftd) / f"{c}.zip").read_bytes()
        rangs = []
        for jour, cusip, s, p in ta.lire_lignes(contenu):
            s = symbole(s)
            if s in voulus:
                rangs.append((jour, cusip, s, p))
                lignes[s].append((jour, cusip, p))
        r = {}
        ta.ajouter_lignes(r, rangs)  # le vrai code du robot
        resume[c] = r
        pf = {}
        for jour, cusip, s, p in rangs:  # comme ta.lire_prix : le plus récent prix du fichier, la 1re ligne si égalité
            if p is not None and (s not in pf or jour > pf[s][0]):
                pf[s] = [jour, p, cusip]
        prix_f[c] = pf
    for s in lignes:
        lignes[s].sort(key=lambda l: (l[0], l[1]))  # (le prix peut être None : jamais comparé)
    jours_de = {s: [l[0] for l in ls] for s, ls in lignes.items()}
    pub = {c: ps.mise_en_ligne_prevue(ps.periode(c)[0]) for c in cles}
    par_pub = sorted(cles, key=lambda c: (pub[c], c))
    dates_pub = [pub[c] for c in par_pub]

    faits = {}
    for r in lire(d / "finances.jsonl.gz"):
        fs = (r.get("actions") or {}).get("EntityCommonStockSharesOutstanding") or []
        faits[r["cik"]] = [(f[1], f[2], f[4]) for f in fs if f[1] and f[2] and f[4] and f[2] > 0]  # (fin, actions, dépôt)

    n, ex, ecarts = Counter(), defaultdict(list), Counter()
    juge = {k: Counter() for k in ("avant", "inconnue", "epoque", "epoque_tout")}
    fiche = {"rapports": ["10-K", "10-Q"]}
    for e in achats:
        s, cik, X = e["symbole"], e["cik"], date.fromisoformat(e["depot"])
        k = bisect_left(dates_pub, X)  # fichiers publiés AVANT le jour du dépôt
        publies = sorted(par_pub[:k])
        if len(publies) < 2:
            n["pas assez de fichiers publiés"] += 1
            continue
        prix = None
        for c in publies[-2:]:  # comme le robot : le plus récent des 2 derniers fichiers
            p = prix_f[c].get(s)
            if p and (prix is None or p[0] > prix[0]):
                prix = p
        connus = [f for f in faits.get(cik, []) if f[2] <= e["depot"]]
        if not connus:
            n["pas de nombre d'actions (dei) déposé avant"] += 1
            continue
        fin, val, _ = max(connus, key=lambda f: (f[0], f[2]))
        mois = (X.replace(day=1) - timedelta(days=1)).strftime("%Y%m")
        p30, p70 = seuils.get(mois) or seuils[max(m for m in seuils if m <= mois)]
        t = {"seuils": {"mois": mois, "p30": p30, "p70": p70}, "actions": {str(cik): [val, fin]},
             "prix": {s: prix} if prix else {}}
        f = {**fiche, "cik": cik}
        r0 = ta.classer(f, t, s, X)
        if not r0.get("taille"):
            n["taille inconnue même avant (actions, prix…)"] += 1
            continue
        n["achats avec une taille calculée par le robot 0.27.0"] += 1
        limite = (X - timedelta(days=ta.HISTOIRE_JOURS)).strftime("%Y%m%d")
        dans = [c for c in publies if ps.periode(c)[1] >= limite]
        h = fusion(resume[c].get(s, {}) for c in dans)
        cus = {"debut": min(ps.periode(c)[0] for c in dans), "symboles": {s: h}}
        r2 = ta.classer(f, t, s, X, cus)
        h_tout = fusion(resume[c].get(s, {}) for c in publies)
        r2t = ta.classer(f, t, s, X, {"debut": min(ps.periode(c)[0] for c in publies), "symboles": {s: h_tout}})
        ep = ta.epoque(h, prix[2], fin.replace("-", ""))
        if r2.get("valeur_max"):
            n["époque : maximum sûr (regroupement probable)"] += 1
        cas = ep["cas"] + (f" ({ep['pourquoi']})" if ep["cas"] == "inconnue" else "")
        if ep["cas"] in ("ancien", "deux"):
            cas += " : taille connue" if r2.get("taille") else " : taille inconnue"
        n[f"cas « {cas} »"] += 1
        if (r2.get("taille"), r2.get("valeur_m")) != (r2t.get("taille"), r2t.get("valeur_m")):
            n["résultat différent avec tout l'historique (pas seulement 400 jours)"] += 1
            if len(ex["400 jours contre tout l'historique"]) < 15:
                ex["400 jours contre tout l'historique"].append({"symbole": s, "depot": e["depot"], "r400": r2,
                                                                  "rtout": r2t})
        a_risque = ep["cas"] != "meme"
        if r2.get("raison") and not a_risque:
            n["inconnue pour une autre raison de l'historique"] += 1
        # la « vraie » valeur
        apres = sorted((fx for fx in faits.get(cik, []) if e["depot"] <= fx[0] <= (X + timedelta(days=120)).isoformat()),
                       key=lambda fx: (fx[0], fx[2]))
        ls = lignes.get(s, [])
        j = bisect_left(jours_de.get(s, []), (X + timedelta(days=1)).strftime("%Y%m%d")) - 1
        while j >= 0 and ls[j][2] is None:
            j -= 1
        vraie = None
        if apres and j >= 0 and ls[j][0] >= (X - timedelta(days=10)).strftime("%Y%m%d"):
            jv, cv, pv = ls[j]
            fin_v = apres[0][0].replace("-", "")
            autres = [l for l in ls if jv < l[0] <= fin_v and l[1] != cv]
            if not autres:
                vraie = apres[0][1] * pv / 1e6
        cle_j = "à risque" if a_risque else "sans changement de CUSIP"
        if vraie is None:
            n[f"vraie valeur inconnue ({cle_j})"] += 1
            continue
        n[f"vraie valeur connue ({cle_j})"] += 1
        vrai = (vraie < TROP_PETITE, vraie < p30, "petite" if vraie < p30 else "grande" if vraie >= p70 else "moyenne")
        regles = {"avant": r0, "inconnue": None if a_risque else r0, "epoque": r2, "epoque_tout": r2t}
        for nom, r in regles.items():
            ecartee, bonus, taille = decision(r)
            c = juge[nom]
            c[f"{cle_j} : achats jugés"] += 1
            c[f"{cle_j} : taille inconnue"] += taille is None
            c[f"{cle_j} : taille juste"] += taille == vrai[2]
            c[f"{cle_j} : taille fausse"] += taille is not None and taille != vrai[2]
            c[f"{cle_j} : gardée à tort (vraie valeur sous 100 M$)"] += vrai[0] and not ecartee
            c[f"{cle_j} : écartée à tort (vraie valeur de 100 M$ ou plus)"] += ecartee and not vrai[0]
            c[f"{cle_j} : bonus petite à tort"] += bonus and not vrai[1]
            c[f"{cle_j} : bonus petite manqué"] += vrai[1] and not bonus
            if nom == "epoque" and a_risque:
                for err, oui in (("gardée à tort", vrai[0] and not ecartee), ("écartée à tort", ecartee and not vrai[0]),
                                 ("bonus à tort", bonus and not vrai[1]), ("taille fausse", taille and taille != vrai[2])):
                    if oui and len(ex[f"erreur époque : {err}"]) < 15:
                        ex[f"erreur époque : {err}"].append({
                            "symbole": s, "depot": e["depot"], "cas": cas, "actions": [val, fin], "prix": prix,
                            "historique": h, "avant": r0.get("valeur_m"),
                            "epoque": {k: r2.get(k) for k in ("taille", "valeur_m", "valeur_min_m", "valeur_max", "raison")},
                            "vraie_valeur_m": round(vraie, 1), "vraie_taille": vrai[2]})
        if a_risque and len(ex[cas]) < 12:
            ex[cas].append({"symbole": s, "depot": e["depot"], "actions": [val, fin], "prix": prix,
                            "historique": h, "avant": {k: r0.get(k) for k in ("taille", "valeur_m")},
                            "epoque": {k: r2.get(k) for k in ("taille", "valeur_m", "valeur_min_m", "valeur_max", "raison", "note")},
                            "vraie_valeur_m": round(vraie, 1), "vraie_taille": vrai[2]})
        if a_risque and r2.get("valeur_m") and vraie:
            q = r2["valeur_m"] / vraie
            ecarts["époque : valeur dans ±50 % de la vraie" if 0.5 <= q <= 1.5 else "époque : valeur hors de ±50 %"] += 1
        if a_risque and r0.get("valeur_m") and vraie:
            q = r0["valeur_m"] / vraie
            ecarts["avant : valeur dans ±50 % de la vraie" if 0.5 <= q <= 1.5 else "avant : valeur hors de ±50 %"] += 1

    # Chevauchements dans tout l'historique : l'ancien CUSIP encore vu après l'arrivée du nouveau ?
    chev = Counter()
    tout = defaultdict(dict)
    for c in cles:
        for s, r in resume[c].items():
            tout[s] = fusion([tout[s], r])
    ecart_jours = []
    for s, h in tout.items():
        suite = sorted(h.items(), key=lambda kv: kv[1][0])
        for (ca, va), (cn, vn) in zip(suite, suite[1:]):
            chev["changements de CUSIP (symboles des achats)"] += 1
            if va[1] >= vn[0]:
                chev["ancien encore vu après l'arrivée du nouveau"] += 1
            else:
                ecart_jours.append((date.fromisoformat(f"{vn[0][:4]}-{vn[0][4:6]}-{vn[0][6:]}") -
                                    date.fromisoformat(f"{va[1][:4]}-{va[1][4:6]}-{va[1][6:]}")).days)
    ecart_jours.sort()
    q = (lambda p: ecart_jours[int(p * (len(ecart_jours) - 1))] if ecart_jours else None)
    Path(x.sortie).write_text(json.dumps({
        "periode": periode, "fichiers_lus": [cles[0], cles[-1], len(cles)], "compte": dict(n), "juge": {k: dict(v) for k, v in juge.items()},
        "ecarts_de_valeur": dict(ecarts), "chevauchements": dict(chev),
        "jours_entre_dernier_ancien_et_premier_nouveau": {"mediane": q(0.5), "p10": q(0.1), "p90": q(0.9)},
        "exemples": ex}, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"compte": dict(n), "juge": {k: dict(v) for k, v in juge.items()}}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
