"""Un FAUX jeu de recherche, au format exact du vrai (voir dictionnaire.md), fait au hasard (graine fixe).

Pour programmer et comparer les règles AVANT que les vraies données existent : aucun vrai prix, aucun vrai dépôt, donc
rien à apprendre sur ce qui marche. Prix en marche au hasard (rares pour les petites compagnies, regroupements
d'actions avec changement de CUSIP), achats et ventes d'initiés (avec des groupes), finances, 13D/13G, 1 an de contexte.

Usage : python faux_jeu.py <dossier> [graine]
"""
import gzip
import json
import math
import random
import sys
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

CONTEXTE, DEBUT, FIN, FIN_PRIX = "2022-07-01", "2023-07-01", "2026-06-30", "2026-09-15"
TITRES = [("Chief Executive Officer", ["dirigeant"]), ("CEO/President", ["administrateur", "dirigeant"]),
          ("EVP, CFO", ["dirigeant"]), ("Chief Financial Officer", ["dirigeant"]), ("COO", ["dirigeant"]),
          ("General Counsel", ["dirigeant"]), ("", ["administrateur"]), ("", ["administrateur"]),
          ("Chairman of the Board", ["administrateur"]), ("", ["actionnaire de 10 %"]), ("", ["administrateur", "autre"])]


def jours_ouvrables(a, b):
    j, fin, sortie = date.fromisoformat(a), date.fromisoformat(b), []
    while j <= fin:
        if j.weekday() < 5:
            sortie.append(j.isoformat())
        j += timedelta(days=1)
    return sortie


def fabriquer(dossier, graine=7):
    r = random.Random(graine)
    cal = jours_ouvrables(CONTEXTE, FIN_PRIX)
    # --- Marché : SPY, IVV, VOO (même indice), IWM (petites compagnies, plus volatil)
    prix, niveau, petites = {}, 400.0, 180.0
    series = {"SPY": [], "IWM": []}
    for j in cal:
        choc = r.gauss(0.0004, 0.011)
        niveau *= 1 + choc
        petites *= 1 + 1.2 * choc + r.gauss(-0.0001, 0.007)
        series["SPY"].append(niveau)
        series["IWM"].append(petites)
    for s, base, cusip in (("SPY", "SPY", "78462F103"), ("IVV", "SPY", "464287200"), ("VOO", "SPY", "922908363"),
                           ("IWM", "IWM", "464287655")):
        k = 1.0 if s in ("SPY", "IWM") else (1.09 if s == "IVV" else 0.92)
        prix[s] = [(j, round(p * k, 4), cusip, r.randint(0, 50000)) for j, p in zip(cal, series[base])]
    # --- Compagnies : taille de 20 M$ à 200 G$, prix rares pour les petites
    cies = []
    for i in range(140):
        valeur = math.exp(r.uniform(math.log(20), math.log(200000)))
        p0 = math.exp(r.uniform(math.log(1.5), math.log(250)))
        cies.append({"cik": str(1000001 + i), "s": f"F{i:03d}", "nom": f"Fausse Compagnie {i} Inc",
                     "actions": valeur * 1e6 / p0, "p0": p0, "vol": 0.035 if valeur < 300 else 0.022 if valeur < 2000 else 0.015,
                     "presence": 0.35 if valeur < 300 else 0.75 if valeur < 2000 else 0.97, "beta": r.uniform(0.6, 1.5)})
    for c in cies:
        p, cusip, lignes, regroupe = c["p0"], f"F{c['cik']}1", [], r.random() < 0.04
        jour_reg = cal[r.randrange(200, len(cal) - 100)] if regroupe else None
        for j, m in zip(cal, series["SPY"]):
            p *= 1 + r.gauss(0, c["vol"]) + c["beta"] * 0.0003
            p = max(p, 0.05)
            if j == jour_reg:  # regroupement 1 pour 10 : prix ×10, nouveau CUSIP, même valeur
                p *= 10
                c["actions"] /= 10
                cusip = cusip[:-1] + "2"
            if r.random() < c["presence"] or j == jour_reg:
                lignes.append((j, round(p, 4), cusip, r.randint(1, 200000)))
        prix[c["s"]] = lignes
    # --- Initiés de chaque compagnie
    for c in cies:
        c["inities"] = [{"cik": str(2000000 + int(c["cik"]) * 10 + k), "nom": f"Initie {c['s']}-{k}",
                         "roles": list(TITRES[k % len(TITRES)][1]), "titre": TITRES[k % len(TITRES)][0]} for k in range(6)]
    # --- Dépôts de formulaires 4 : au hasard, plus des groupes (3 à 5 initiés en 3 semaines)
    jours_dep = jours_ouvrables(CONTEXTE, FIN)
    bruts = []
    for _ in range(2600):
        bruts.append((r.choice(cies), r.choice(jours_dep), "achat" if r.random() < 0.55 else "vente", None))
    for _ in range(45):
        c, j0 = r.choice(cies), r.randrange(len(jours_dep) - 20)
        for k in r.sample(range(6), r.randint(3, 5)):
            bruts.append((c, jours_dep[j0 + r.randrange(15)], "achat", k))
    evs, tenue = [], defaultdict(float)
    for n, (c, depot, sens, k) in enumerate(sorted(bruts, key=lambda x: (x[1], x[0]["cik"]))):
        ini = c["inities"][k if k is not None else r.randrange(6)]
        px = [x for x in prix[c["s"]] if x[0] <= depot][-1:] or prix[c["s"]][:1]
        prix_moy = round(px[0][1] * r.uniform(0.97, 1.03), 4)
        actions = round(r.choice([500, 1000, 2500, 5000, 10000, 50000, 200000]) * r.uniform(0.5, 1.5))
        cle = (ini["cik"], c["cik"])
        avant = tenue[cle] if tenue[cle] or r.random() < 0.6 else 0.0
        if not tenue[cle] and avant == 0.0 and sens == "achat" and r.random() < 0.7:
            avant = float(round(actions * r.uniform(0.5, 30)))
        if sens == "vente":
            avant = max(avant, actions * r.uniform(1, 10))
        apres = avant + actions if sens == "achat" else avant - actions
        tenue[cle] = apres
        jour_tr = (date.fromisoformat(depot) - timedelta(days=r.randint(0, 3))).isoformat()
        evs.append({"id": f"0009{n:06d}-{depot[2:4]}-{n:06d}:{sens}", "sens": sens, "depot": depot,
                    "jour_premier": jour_tr, "jour_dernier": jour_tr, "cik": c["cik"], "symbole": c["s"],
                    "symbole_ecrit": c["s"], "nom": c["nom"], "inities": [dict(ini)], "actions": float(actions),
                    "montant": round(actions * prix_moy, 2), "prix_moyen": prix_moy, "apres": round(apres, 4),
                    "avant": round(avant, 4), "part": round(actions / avant, 6) if avant > 0.5 else None,
                    "nouvelle_position": sens == "achat" and avant <= 0.5, "direct": r.random() < 0.8,
                    "plan_10b5_1": None if depot < "2023-04-01" else (r.random() < (0.1 if sens == "achat" else 0.5)),
                    "titres": ["Common Stock"], "lignes": 1})
    # --- Champs calculés comme dans donnees.py (à partir du passé seulement)
    par_cie = defaultdict(list)
    for e in evs:
        par_cie[e["cik"]].append(e)
    for liste in par_cie.values():
        depots = [e["depot"] for e in liste]
        for e in liste:
            j = date.fromisoformat(e["depot"])
            d30, d90 = (j - timedelta(days=30)).isoformat(), (j - timedelta(days=90)).isoformat()
            fen30 = liste[bisect_left(depots, d30):bisect_right(depots, e["depot"])]
            avant90 = liste[bisect_left(depots, d90):bisect_left(depots, e["depot"])]
            if e["sens"] == "achat":
                e["groupe_30j"] = len({i["cik"] for x in fen30 if x["sens"] == "achat" for i in x["inities"]})
            e["achats_90j"] = sum(x["sens"] == "achat" for x in avant90)
            e["ventes_90j"] = sum(x["sens"] == "vente" for x in avant90)
    deja = defaultdict(list)
    for e in evs:
        e["routinier"] = r.random() < 0.15
        e["mois_routine"] = sorted(r.sample(range(1, 13), 2)) if e["routinier"] else []
        if e["sens"] == "achat":
            i = e["inities"][0]
            meme = [d for d in deja[(i["cik"], e["cik"])] if d < e["depot"]]
            e["historique"] = {"cik": i["cik"], "achats_avant": len([1 for (a, _), v in deja.items() if a == i["cik"]
                                                                       for d in v if d < e["depot"]]) + r.randint(0, 8),
                               "jours_depuis_achat_meme_cie": (date.fromisoformat(e["depot"]) - date.fromisoformat(meme[-1])).days
                               if meme else None}
            m = r.randint(0, 12)
            e["bilan_initie"] = {"mesures": m, "ecart_moyen": round(r.gauss(0.005, 0.04), 4) if m else None,
                                 "part_gagnante": round(r.randint(0, m) / m, 4) if m else None}
            deja[(i["cik"], e["cik"])].append(e["depot"])
    actions_de = {c["cik"]: c["actions"] for c in cies}
    for e in evs:
        lignes = prix[e["symbole"]]
        veille = (date.fromisoformat(e["depot"]) - timedelta(days=1)).isoformat()
        k = bisect_right([x[0] for x in lignes], veille) - 1
        ok = k >= 0 and (date.fromisoformat(veille) - date.fromisoformat(lignes[k][0])).days <= 30
        e["cloture_avant"] = [lignes[k][0], lignes[k][1], lignes[k][2]] if ok else None
        e["actions_circulation"] = round(actions_de[e["cik"]])
        e["valeur_m"] = round(actions_de[e["cik"]] * lignes[k][1] / 1e6, 2) if ok else None
    # --- 13D et 13G
    treize = defaultdict(list)
    for _ in range(160):
        c = r.choice(cies)
        treize[c["cik"]].append([r.choice(jours_dep), r.choice(["13D", "13D/A", "13G", "13G/A"])])
    for v in treize.values():
        v.sort()
    for e in evs:
        d90 = (date.fromisoformat(e["depot"]) - timedelta(days=90)).isoformat()
        fen = [f for j, f in treize.get(e["cik"], []) if d90 <= j <= e["depot"]]
        e["13d_90j"], e["13g_90j"] = fen.count("13D"), fen.count("13G")
    # --- Finances (comme companyfacts : 10-Q chaque trimestre, 10-K chaque exercice), utilisables à leur date de dépôt
    finances = {}
    fins_trim = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}
    for c in cies:
        faits, actif = defaultdict(list), c["actions"] * c["p0"] * r.uniform(0.3, 2.5)
        c["revenus"] = "Revenues" if r.random() < 0.6 else "RevenueFromContractWithCustomerExcludingAssessedTax"
        for an in range(2020, 2027):
            revenus_an = benefice_an = 0.0
            for q in (1, 2, 3, 4):
                fin_q = date(an, *fins_trim[q])
                if fin_q.isoformat() > FIN:
                    break
                debut_q = (date(an, 1, 1) if q == 1 else date(an, *fins_trim[q - 1]) + timedelta(days=1))
                forme = "10-K" if q == 4 else "10-Q"
                depose = (fin_q + timedelta(days=r.randint(55, 88) if q == 4 else r.randint(30, 44))).isoformat()
                accn = f"0009{c['cik']}-{depose[2:4]}-{q:06d}"
                actif *= r.uniform(0.95, 1.06)
                passif = actif * r.uniform(0.2, 0.95)
                revenus = actif * r.uniform(0.05, 0.4)
                benefice = revenus * r.gauss(0.04, 0.12)
                revenus_an += revenus
                benefice_an += benefice
                for concept, v in (("Assets", actif), ("Liabilities", passif), ("StockholdersEquity", actif - passif),
                                   ("AssetsCurrent", actif * 0.4), ("LiabilitiesCurrent", passif * r.uniform(0.2, 0.7)),
                                   ("LongTermDebtNoncurrent", passif * r.uniform(0, 0.5))):
                    faits[concept].append([None, fin_q.isoformat(), round(v), accn, depose, forme])
                durees = [(debut_q.isoformat(), benefice, revenus)]
                if q == 4:  # le 10-K donne l'exercice entier (et le 4e trimestre)
                    durees.append((f"{an}-01-01", benefice_an, revenus_an))
                for deb, ben, rev in durees:
                    for concept, v in (("NetIncomeLoss", ben),
                                       ("NetCashProvidedByUsedInOperatingActivities", ben + rev * r.gauss(0.03, 0.05)),
                                       (c["revenus"], rev), ("GrossProfit", rev * r.uniform(0.2, 0.6))):
                        faits[concept].append([deb, fin_q.isoformat(), round(v), accn, depose, forme])
        finances[c["cik"]] = {k: sorted(v, key=lambda x: (x[1], x[0] or "")) for k, v in faits.items()}
    # --- Écriture, au format de donnees.py
    d = Path(dossier)
    d.mkdir(parents=True, exist_ok=True)
    evs.sort(key=lambda e: (e["depot"], e["id"]))
    with gzip.open(d / "evenements.jsonl.gz", "wt", encoding="utf-8") as f:
        for e in evs:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    with gzip.open(d / "prix.jsonl.gz", "wt", encoding="utf-8") as f:
        for s, lignes in sorted(prix.items()):
            f.write(json.dumps({"s": s, "d": [int(x[0].replace("-", "")) for x in lignes], "p": [x[1] for x in lignes],
                                "q": [x[3] for x in lignes], "c": [x[2] for x in lignes]}) + "\n")
    with gzip.open(d / "finances.jsonl.gz", "wt", encoding="utf-8") as f:
        for cik, faits in sorted(finances.items()):
            f.write(json.dumps({"cik": cik, "faits": faits}) + "\n")
    with gzip.open(d / "13d13g.jsonl.gz", "wt", encoding="utf-8") as f:
        for cik, v in sorted(treize.items()):
            f.write(json.dumps({"cik": cik, "depots": v}) + "\n")
    (d / "calendrier.json").write_text(json.dumps(cal), encoding="utf-8")
    (d / "periode.json").write_text(json.dumps({"debut": DEBUT, "fin": FIN, "contexte_depuis": CONTEXTE}), encoding="utf-8")
    (d / "LISEZ-MOI.txt").write_text("FAUX jeu de recherche (au hasard, graine fixe) : pour programmer et comparer les "
                                     "règles. Aucun vrai prix, aucun vrai dépôt.\n", encoding="utf-8")
    return len(evs)


if __name__ == "__main__":
    n = fabriquer(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 7)
    print(f"faux jeu : {n} dépôts → {sys.argv[1]}")
