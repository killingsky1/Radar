"""Essai hors ligne de la chasse (chasse.py) : un faux jeu au format du tournoi, fabriqué avec un signal CACHÉ exprès.

Contrôle positif : les achats où le dirigeant augmente sa part de plus de 100 % (« part » > 1, environ 1 achat sur 10)
sont suivis d'une hausse de 30 % de plus que le marché en 6 mois. Si tout le chemin est juste (indices, cibles, modèle
année par année, seuils, banc), le modèle doit trouver ce signal tout seul : chaque année, les 10 % les mieux notés font
mieux que tous les achats, et le portefeuille réussit le critère du plan (preuve que la barre est atteignable quand un
vrai signal existe). Contrôle négatif (fuite du futur) : le même jeu SANS signal ; aucune durée ne doit réussir, et la
corrélation moyenne doit rester près de 0 (un indice qui verrait le futur la ferait monter nettement).

Lancement : python labo/chasse/essai_chasse.py
"""

from __future__ import annotations

import gzip
import json
import math
import random
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ICI = Path(__file__).resolve().parent


def jours_ouvrables(a, b):
    d, sortie = date.fromisoformat(a), []
    while d <= date.fromisoformat(b):
        if d.weekday() < 5:
            sortie.append(d.isoformat())
        d += timedelta(days=1)
    return sortie


def fabriquer(dossier: Path, signal: bool, graine=11, achats=20000, compagnies=600, force=1.30):
    rnd = random.Random(graine)
    cal = jours_ouvrables("2015-01-02", "2026-09-15")
    idx = {j: i for i, j in enumerate(cal)}
    n = len(cal)

    def marche(derive, vol):
        p, v = [100.0], vol / math.sqrt(252)
        for _ in range(n - 1):
            p.append(p[-1] * math.exp(derive / 252 - v * v / 2 + v * rnd.gauss(0, 1)))
        return p

    spy, iwm = marche(0.08, 0.15), marche(0.07, 0.20)
    symboles = [f"S{i:03d}" for i in range(compagnies)]
    base = {s: marche(0.06, 0.40) for s in symboles}
    effet = {s: [0.0] * n for s in symboles}  # log-rendement de plus que le marché, ajouté après certains achats
    evenements = []
    for k in range(achats):
        s = rnd.choice(symboles)
        i = rnd.randrange(idx["2015-01-02"] + 260, idx["2026-06-30"])
        depot = cal[i]
        part = math.exp(rnd.gauss(-1.5, 1.2))
        if signal and part > 1.0:  # le signal caché : +30 % en 6 mois (126 jours de bourse), en douceur
            for j in range(i + 1, min(n, i + 127)):
                effet[s][j] += math.log(force) / 126
        cik = str(1000 + symboles.index(s))
        evenements.append({
            "id": f"F{k:05d}:achat", "sens": "achat", "depot": depot, "jour_premier": cal[i - 1], "jour_dernier": cal[i - 1],
            "cik": cik, "symbole": s, "symbole_ecrit": s, "nom": f"Compagnie {s}",
            "inities": [{"cik": str(50000 + k % 3000), "nom": "Initié", "roles": [rnd.choice(["dirigeant", "administrateur"])],
                         "titre": rnd.choice(["CEO", "CFO", "Director", "VP Sales", ""])}],
            "actions": 1000.0, "montant": round(math.exp(rnd.gauss(11, 1.5)), 2), "prix_moyen": 10.0, "apres": None,
            "avant": None, "part": round(part, 4), "nouvelle_position": rnd.random() < 0.1, "direct": True,
            "plan_10b5_1": None, "titres": ["Common Stock"], "lignes": 1, "routinier": rnd.random() < 0.12,
            "mois_routine": [], "groupe_30j": rnd.choice([1, 1, 1, 2, 3]), "achats_90j": rnd.randrange(4),
            "ventes_90j": rnd.randrange(4), "historique": {"cik": "x", "achats_avant": rnd.randrange(20),
                                                          "jours_depuis_achat_meme_cie": None},
            "cloture_avant": None, "actions_circulation": 50_000_000.0, "valeur_m": round(math.exp(rnd.gauss(6.5, 1.5)), 1),
            "bilan_initie": {"mesures": 0, "ecart_moyen": None, "part_gagnante": None}, "13d_90j": 0, "13g_90j": 0})
        evenements.append({**evenements[-1], "id": f"F{k:05d}b:vente", "sens": "vente", "part": None})
    # les prix : marche du symbole + effet cumulé ; présents 9 jours sur 10 (fichiers d'échecs), toujours pour SPY et IWM
    prix = {}
    for s in symboles:
        cumul, p = 0.0, []
        for j in range(n):
            cumul += effet[s][j]
            p.append(base[s][j] * math.exp(cumul))
        prix[s] = p
    prix["SPY"], prix["IWM"] = spy, iwm
    presents = {s: [True if s in ("SPY", "IWM") else rnd.random() < 0.9 for _ in range(n)] for s in prix}
    periodes = {"coffre": ("2016-01-01", "2023-06-30", "2015-01-01", "2015-07-01", "2023-09-15"),
                "decouverte": ("2023-07-01", "2026-06-30", "2022-07-01", "2022-07-01", "2026-09-15")}
    for nom, (debut, fin, contexte, prix_depuis, prix_jusqu_a) in periodes.items():
        dd = dossier / nom
        dd.mkdir(parents=True)
        (dd / "periode.json").write_text(json.dumps({"debut": debut, "fin": fin, "contexte_depuis": contexte}))
        evs = [e for e in evenements if contexte <= e["depot"] <= fin]
        with gzip.open(dd / "evenements.jsonl.gz", "wt", encoding="utf-8") as f:
            f.write("".join(json.dumps(e) + "\n" for e in evs))
        jours = [j for j in cal if prix_depuis <= j <= prix_jusqu_a]
        (dd / "calendrier.json").write_text(json.dumps(jours))
        with gzip.open(dd / "prix.jsonl.gz", "wt", encoding="utf-8") as f:
            for s, p in prix.items():
                ks = [idx[j] for j in jours if presents[s][idx[j]]]
                f.write(json.dumps({"s": s, "d": [cal[k].replace("-", "") for k in ks], "p": [round(p[k], 4) for k in ks],
                                    "q": [1000] * len(ks), "c": [f"C{s}"] * len(ks)}) + "\n")


def lancer(signal: bool):
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        fabriquer(t, signal)
        subprocess.run([sys.executable, str(ICI / "chasse.py"), "--coffre", str(t / "coffre"), "--decouverte",
                        str(t / "decouverte"), "--sortie", str(t / "sortie"), "--minimum", "300"], check=True,
                       stdout=subprocess.DEVNULL)
        return json.loads((t / "sortie" / "resultats.json").read_text())


def main():
    essais = []

    def verifier(nom, ok, detail):
        essais.append(ok)
        print(f"{'OK ' if ok else 'NON'} {nom} : {detail}")

    r = lancer(signal=True)
    verifier("53 indices calculés pour chaque achat", len(r["indices"]) == 53, len(r["indices"]))
    for h in ("63", "126", "252"):
        m = {a: v for a, v in r["durees"][h]["mesures"].items() if v.get("net_moyen_gardes") is not None}
        verifier(f"durée {h} : les 9 années testées", len(m) == 9, sorted(m))
        mieux = [a for a, v in m.items() if v["net_moyen_gardes"] > v["net_moyen_tous"]]
        corr = [v["correlation_rang"] for v in m.values()]
        verifier(f"durée {h} : signal caché trouvé chaque année (les 10 % gardés font mieux que tous les achats)",
                 len(mieux) == len(m) == 9, f"{len(mieux)} sur {len(m)}")
        verifier(f"durée {h} : corrélation de rang positive chaque année", all(c > 0 for c in corr), corr)
    neuf = r["durees"]["126"]["neuf_ans"]
    verifier("durée 126 (celle du signal) : le critère du plan est atteignable quand un vrai signal existe",
             neuf["reussi"], neuf)
    sans = lancer(signal=False)
    for h in ("63", "126", "252"):
        neuf0 = sans["durees"][h]["neuf_ans"]
        corr0 = [v["correlation_rang"] for v in sans["durees"][h]["mesures"].values()
                 if v.get("correlation_rang") is not None]
        moyenne = sum(corr0) / len(corr0)
        verifier(f"sans signal, durée {h} : le critère du plan n'est PAS réussi", not neuf0["reussi"], neuf0)
        verifier(f"sans signal, durée {h} : pas de fuite du futur (corrélation moyenne entre -0,05 et 0,05)",
                 abs(moyenne) < 0.05, f"{moyenne:.4f} ({corr0})")
    print(f"{sum(essais)}/{len(essais)} réussis")
    sys.exit(0 if all(essais) else 1)


if __name__ == "__main__":
    main()
