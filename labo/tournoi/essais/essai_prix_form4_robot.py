"""Essai hors ligne de mesures/prix_form4_robot.py : un mini-jeu fabriqué, 6 cas dont on connaît la réponse d'avance.

AAA : pas de prix de la SEC depuis 60 jours, achat à 4,80 $ (formulaire 4) : 48 M$, petite ; vraie : 5,00 $ × 10,2 M
      = 51 M$, petite → juste (écartée sous 100 M$ et bonus, comme la vraie).
BBB : regroupement (nouveau CUSIP vu le 20 avril, après les actions du 31 mars, fichier publié vers le 15 mai) : taille
      inconnue (époque).
CCC : jamais vu dans les fichiers d'échecs avant l'achat (symbole absent de l'historique) : 3,00 $ × 30 M = 90 M$.
DDD : dernier prix de la SEC 10,00 $ (1er février), formulaire 4 à 1,00 $ (erreur) : 20 M$ au lieu de 200 M$ → écartée
      et bonus à tort sans garde-fou ; les garde-fous ×2, ×3 et ×5 l'arrêtent ; ×10 la laisse passer (0,1 = la limite).
EEE : seul formulaire 4 sur des actions privilégiées : aucun prix de secours, reste inconnue.
FFF : prix de la SEC récent : rien ne change.
GGG : comme BBB, mais le nouveau CUSIP est vu le 20 mai : fichier publié vers le 15 juin, PAS ENCORE CONNU le 5 juin (les
      fichiers d'échecs ont 2 à 6 semaines de retard, le formulaire 4 non) : l'époque ne le voit pas ; formulaire 4 à
      20,00 $ contre 2,00 $ pour le dernier prix de la SEC : les garde-fous ×2, ×3 et ×5 l'arrêtent, ×10 non (la limite).
Lancement : python labo/tournoi/essais/essai_prix_form4_robot.py --robot <dossier robot de la branche travail>
"""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys
import tempfile
import zipfile
from datetime import date, timedelta
from pathlib import Path

ENTETE = "SETTLEMENT DATE|CUSIP|SYMBOL|QUANTITY (FAILS)|DESCRIPTION|PRICE"
X = "2024-06-05"  # jour du dépôt des achats


def jours(debut, fin, pas=7):
    d = date.fromisoformat(debut)
    while d <= date.fromisoformat(fin):
        if d.weekday() < 5:
            yield d.strftime("%Y%m%d")
        d += timedelta(days=pas)


def fabriquer(dossier: Path):
    lignes = {}  # (AAAAMMJJ) -> [lignes]

    def ajouter(j, cusip, s, prix):
        lignes.setdefault(j, []).append(f"{j}|{cusip}|{s}|1000|{s} INC|{prix}")

    for j in jours("2023-01-02", "2024-12-31", 3):
        ajouter(j, "CUSIPSPY0", "SPY", "450.00")
    for j in jours("2023-01-02", "2024-01-15"):
        ajouter(j, "AAA000001", "AAA", "4.50")
    for j in jours("2024-06-10", "2024-08-01"):
        ajouter(j, "AAA000001", "AAA", "5.00")
    for j in jours("2023-01-02", "2024-03-01"):
        ajouter(j, "BBB000001", "BBB", "2.00")
    ajouter("20240422", "BBB000002", "BBB", ".")  # nouveau CUSIP vu, sans prix (fichier 202404b)
    for j in jours("2024-06-10", "2024-08-01"):
        ajouter(j, "BBB000002", "BBB", "20.00")
    for j in jours("2023-01-02", "2024-03-01"):
        ajouter(j, "GGG000001", "GGG", "2.00")
    ajouter("20240520", "GGG000002", "GGG", ".")  # fichier 202405b : publié après le 5 juin
    for j in jours("2024-06-10", "2024-08-01"):
        ajouter(j, "GGG000002", "GGG", "20.00")
    for j in jours("2024-06-10", "2024-08-01"):
        ajouter(j, "CCC000001", "CCC", "3.10")
    for j in jours("2023-06-01", "2024-02-01"):
        ajouter(j, "DDD000001", "DDD", "10.00")
    for j in jours("2024-06-10", "2024-08-01"):
        ajouter(j, "DDD000001", "DDD", "10.00")
    for j in jours("2023-01-02", "2024-12-31"):
        ajouter(j, "FFF000001", "FFF", "50.00")
    ftd = dossier / "ftd"
    ftd.mkdir(parents=True)
    for a in (2023, 2024):
        for m in range(1, 13):
            for moitie, (d1, d2) in (("a", (1, 15)), ("b", (16, 31))):
                cle = f"{a}{m:02d}{moitie}"
                contenu = [ENTETE] + [l for j in sorted(lignes) if j[:6] == cle[:6] and d1 <= int(j[6:]) <= d2
                                      for l in lignes[j]] + ["Trailer total quantity of shares 1"]
                with zipfile.ZipFile(ftd / f"{cle}.zip", "w") as z:
                    z.writestr(f"cnsfails{cle}.txt", "\n".join(contenu) + "\n")

    d = dossier / "jeu"
    d.mkdir()
    (d / "periode.json").write_text(json.dumps({"debut": "2024-01-01", "fin": "2024-12-31"}))
    fi = [{"cik": cik, "actions": {"EntityCommonStockSharesOutstanding": [
        [None, "2024-03-31", n, None, "2024-05-10", "10-Q"], [None, "2024-06-30", n2, None, "2024-08-10", "10-Q"]]}}
        for cik, n, n2 in (("1001", 10_000_000, 10_200_000), ("1002", 50_000_000, 5_000_000),
                           ("1003", 30_000_000, 30_000_000), ("1004", 20_000_000, 20_000_000),
                           ("1005", 10_000_000, 10_000_000), ("1006", 10_000_000, 10_000_000),
                           ("1007", 50_000_000, 5_000_000))]
    with gzip.open(d / "finances.jsonl.gz", "wt") as f:
        f.write("".join(json.dumps(r) + "\n" for r in fi))

    def achat(cik, s, prix, actions, titre="Common Stock", jour="2024-06-04", depot=X):
        return {"id": f"{cik}-{jour}:achat", "sens": "achat", "depot": depot, "jour_premier": jour, "jour_dernier": jour,
                "cik": cik, "symbole": s, "actions": actions, "montant": round(prix * actions, 2), "prix_moyen": prix,
                "titres": [titre]}

    evs = [achat("1001", "AAA", 4.80, 100_000), achat("1002", "BBB", 20.0, 10_000), achat("1003", "CCC", 3.0, 50_000),
           achat("1004", "DDD", 1.0, 100_000), achat("1005", "EEE", 25.0, 10_000, "Series A Preferred Stock"),
           achat("1006", "FFF", 50.0, 1_000), achat("1007", "GGG", 20.0, 10_000)]
    with gzip.open(d / "evenements.jsonl.gz", "wt") as f:
        f.write("".join(json.dumps(e) + "\n" for e in evs))
    return d, ftd


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--robot", required=True)
    x = a.parse_args()
    mesure = Path(__file__).resolve().parent.parent / "mesures" / "prix_form4_robot.py"
    with tempfile.TemporaryDirectory() as t:
        d, ftd = fabriquer(Path(t))
        sortie = Path(t) / "sortie.json"
        subprocess.run([sys.executable, "-I", str(mesure), "--donnees", str(d), "--ftd", str(ftd), "--robot", x.robot,
                        "--sortie", str(sortie)], check=True, stdout=subprocess.DEVNULL)
        r = json.loads(sortie.read_text())
    c, j = r["compte"], r["juge"]
    essais = []

    def verifier(nom, obtenu, attendu):
        essais.append(obtenu == attendu)
        print(f"{'OK ' if obtenu == attendu else 'NON'} {nom} : {obtenu!r}" + ("" if obtenu == attendu else f" (attendu {attendu!r})"))

    verifier("prix de la SEC récent, rien ne change (FFF)",
             c.get("achats avec un prix de la SEC de 60 jours ou moins, ou inconnus pour une autre raison"), 1)
    verifier("aucune erreur de changement", c.get("ERREUR : résultat changé alors qu'il y avait un prix de la SEC"), None)
    verifier("sans prix de la SEC (AAA, BBB, CCC, DDD, EEE, GGG)",
             c.get("achats SANS prix de la SEC de 60 jours ou moins (taille inconnue en 0.27.1)"), 6)
    verifier("sans prix de formulaire 4 (EEE, privilégiées)", c.get("  … sans prix de formulaire 4 (reste inconnue)"), 1)
    verifier("avec un prix de formulaire 4", c.get("  … avec un prix de formulaire 4"), 5)
    verifier("CCC absent de l'historique", c.get("  … symbole ABSENT de l'historique des CUSIP (400 jours)"), 1)
    verifier("BBB inconnue (époque)", c.get("  … taille inconnue : changement de CUSIP (époque)"), 1)
    verifier("DDD et GGG arrêtées par ×2", c.get("  … écartées par le garde-fou ×2"), 2)
    verifier("DDD et GGG arrêtées par ×5", c.get("  … écartées par le garde-fou ×5"), 2)
    verifier("DDD et GGG passent ×10 (limite)", c.get("  … écartées par le garde-fou ×10"), None)
    verifier("jugés : AAA, BBB, CCC, DDD, GGG", c.get("  … vraie valeur connue (jugés)"), 5)
    t0, t1 = j["0.27.1 (aujourd'hui) | tous"], j["0.27.2 garde-fou aucun | tous"]
    verifier("0.27.1 : 5 inconnues", t0.get("taille inconnue"), 5)
    # vraies : AAA 51 M$, BBB 100 M$ (5 M × 20 $), CCC 93 M$, DDD 200 M$, GGG 100 M$ ; toutes petites (30e centile du
    # NYSE : plus de 1 G$)
    verifier("seuil", r["exemples"]["erreur 0.27.2 : écartée à tort"][0]["classe"]["taille"], "petite")
    verifier("0.27.1 : gardées à tort (AAA, CCC)", t0.get("gardée à tort (vraie valeur sous 100 M$)"), 2)
    verifier("0.27.1 : bonus manqués (les 5)", t0.get("bonus petite manqué"), 5)
    # GGG : 50 M d'actions d'avant × 20 $ d'après = 1 000 M$ (10 fois trop), petite quand même : décisions justes par
    # chance, comptée « taille juste »
    verifier("0.27.2 : GGG valeur 10 fois trop haute, taille juste par chance",
             t1.get("taille juste"), 4)
    verifier("0.27.2 : gardées à tort (aucune)", t1.get("gardée à tort (vraie valeur sous 100 M$)"), 0)
    verifier("0.27.2 : écartée à tort (DDD)", t1.get("écartée à tort (vraie valeur de 100 M$ ou plus)"), 1)
    verifier("0.27.2 : bonus manqué (BBB, inconnue)", t1.get("bonus petite manqué"), 1)
    verifier("0.27.2 : bonus à tort (aucun : DDD est vraiment petite)", t1.get("bonus petite à tort"), 0)
    t3 = j["0.27.2 garde-fou ×3 | tous"]
    verifier("0.27.2 ×3 : plus d'écartée à tort", t3.get("écartée à tort (vraie valeur de 100 M$ ou plus)"), 0)
    ta = j["0.27.2 garde-fou aucun, symbole absent = inconnue | tous"]
    verifier("absent = inconnue : CCC redevient gardée à tort", ta.get("gardée à tort (vraie valeur sous 100 M$)"), 1)
    ex = r["exemples"]["erreur 0.27.2 : écartée à tort"]
    verifier("exemple DDD", [(e["symbole"], e["prix_f4"], e["garde_fous"]) for e in ex],
             [("DDD", ["20240604", 1.0], {"2": False, "3": False, "5": False, "10": True})])
    print(f"{sum(essais)}/{len(essais)} réussis")
    sys.exit(0 if all(essais) else 1)


if __name__ == "__main__":
    main()
