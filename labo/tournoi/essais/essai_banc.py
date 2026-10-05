"""Essai du banc d'essai du tournoi sur des données faites à la main, où la bonne réponse est connue d'avance."""
import gzip
import json
import shutil
import sys
import types
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import banc  # noqa: E402

ICI = Path(__file__).parent / "tmp_banc"
ok = []


def verifier(nom, condition, detail=""):
    ok.append(bool(condition))
    print(f"{'OK    ' if condition else 'ÉCHEC '} {nom} {detail}")


JOURS = []
j = date(2023, 7, 3)
while j <= date(2023, 12, 29):
    if j.weekday() < 5:
        JOURS.append(j.isoformat())
    j += timedelta(days=1)


def ecrire(evenements, prix):
    shutil.rmtree(ICI, ignore_errors=True)
    ICI.mkdir()
    with gzip.open(ICI / "evenements.jsonl.gz", "wt") as f:
        for e in evenements:
            f.write(json.dumps(e) + "\n")
    with gzip.open(ICI / "prix.jsonl.gz", "wt") as f:
        for s, lignes in prix.items():
            f.write(json.dumps({"s": s, "d": [int(x[0].replace("-", "")) for x in lignes], "p": [x[1] for x in lignes],
                                "c": [x[2] for x in lignes], "q": [0] * len(lignes)}) + "\n")
    (ICI / "calendrier.json").write_text(json.dumps(JOURS))
    return banc.Donnees(ICI)


def ev(id_, symbole, depot, valeur_m=None):
    return {"id": id_, "sens": "achat", "depot": depot, "symbole": symbole, "cik": id_, "valeur_m": valeur_m,
            "inities": []}


def regle(**x):
    r = types.SimpleNamespace(ID="essai", garder=lambda e, ctx: True, ARGENT_QUI_ATTEND="rien", MAX_POSITIONS=1, DUREE=21)
    for k, v in x.items():
        setattr(r, k, v)
    return r


SPY = [(j, 100.0, "S") for j in JOURS]
# AAA : 10 $ jusqu'au 2023-08-01, puis 11 $ (+10 %)
AAA = [(j, 10.0 if j < "2023-08-02" else 11.0, "A") for j in JOURS]

# 1. Une transaction simple : dépôt lundi 10 juillet → achat à la clôture du mardi 11 → vente 21 jours de bourse après
d = ecrire([ev("a", "AAA", "2023-07-10")], {"SPY": SPY, "AAA": AAA})
t, v, ouvertes = banc.simuler(regle(), d, debut="2023-07-03")
x = t[0]
sortie = JOURS[JOURS.index("2023-07-11") + 21]
verifier("Achat à la clôture du 1er jour de bourse APRÈS le dépôt", x["achat"] == "2023-07-11", x["achat"])
verifier("Vente 21 jours de bourse plus tard", x["vente"] == sortie, f"{x['vente']} (attendu {sortie})")
verifier("Rendement +10 %, marché 0 %, écart +10 %", (x["rendement"], x["marche"], x["ecart"]) == (0.1, 0.0, 0.1))
investi = (10000 - 10) * (1 - 0.01)          # 10 $ de frais, puis 1 % de demi-écart (taille inconnue)
vendu = investi * 1.1 * (1 - 0.01) - 10      # 1 % de demi-écart et 10 $ à la vente
verifier("Frais : 10 $ + 1 % à l'achat ET à la vente (taille inconnue)", abs(v[-1][1] - vendu) < 0.01,
         f"{v[-1][1]:.2f} contre {vendu:.2f}")
s = banc.statistiques(t, v, d, ouvertes)
verifier("Statistiques : portefeuille total = valeur finale ÷ 10 000 − 1", s["total"]["portefeuille"] == round(vendu / 10000 - 1, 4))

# 2. Prix rares : BBB a un prix un jour sur 4 → achat au 1er jour AVEC prix (3 jours de bourse au plus)
BBB = [(j, 20.0, "B") for i, j in enumerate(JOURS) if i % 4 == 0]
d = ecrire([ev("b", "BBB", "2023-07-10")], {"SPY": SPY, "BBB": BBB})
t, v, _ = banc.simuler(regle(), d, debut="2023-07-03")
premier_prix = next(j for j, _, _ in BBB if j >= "2023-07-11")
verifier("Prix rares : achat au 1er jour de bourse avec un prix (au plus 3 jours après)",
         t and t[0]["achat"] == premier_prix, f"{t[0]['achat'] if t else None} (attendu {premier_prix})")
CCC = [("2023-07-20", 5.0, "C"), ("2023-09-01", 5.0, "C")]  # 1er prix 7 jours de bourse après le 11 juillet
d = ecrire([ev("c", "CCC", "2023-07-10")], {"SPY": SPY, "CCC": CCC})
t, v, _ = banc.simuler(regle(), d, debut="2023-07-03")
verifier("Prix trop rares (aucun dans les 3 jours de bourse) : pas acheté, l'argent reste", not t and abs(v[-1][1] - 10000) < 1e-6)

# 3. Changement de CUSIP (regroupement 1 pour 10) : 1 $ → 10 $ sans changement de valeur → rendement 0, pas +900 %
DDD = [(j, 1.0 if j < "2023-07-20" else 10.0, "D1" if j < "2023-07-20" else "D2") for j in JOURS]
d = ecrire([ev("d", "DDD", "2023-07-10")], {"SPY": SPY, "DDD": DDD})
t, v, _ = banc.simuler(regle(), d, debut="2023-07-03")
verifier("CUSIP changé : rendement enchaîné (0 %), pas +900 %", t and t[0]["rendement"] == 0.0, str(t[0]["rendement"] if t else None))

# 4. Garde-fou contre le futur
def triche(e, ctx):
    ctx.cloture("AAA", "2023-08-15")
    return True


d = ecrire([ev("a", "AAA", "2023-07-10")], {"SPY": SPY, "AAA": AAA})
try:
    banc.simuler(regle(garder=triche), d, debut="2023-07-03")
    verifier("Une règle qui regarde le futur est arrêtée", False)
except banc.Futur as exc:
    verifier("Une règle qui regarde le futur est arrêtée", True, str(exc))

# 5. Météo : investir() faux → aucun achat ; l'argent attend
t, v, _ = banc.simuler(regle(investir=lambda jour, ctx: False), d, debut="2023-07-03")
verifier("Météo défavorable : aucun achat", not t and abs(v[-1][1] - 10000) < 1e-6)

# 6. Vente plus tôt : seuil de perte −10 % décidé sur la clôture de la VEILLE, vendu à la clôture du jour
EEE = [(j, 10.0 if j < "2023-07-17" else 8.0, "E") for j in JOURS]
d = ecrire([ev("e", "EEE", "2023-07-10")], {"SPY": SPY, "EEE": EEE})


def stop(pos, jour, ctx):
    c = ctx.cloture(pos["s"])
    return c is not None and c[1] <= pos["entree"][1] * 0.9


t, v, _ = banc.simuler(regle(sortir_avant=stop), d, debut="2023-07-03")
verifier("Seuil de perte : vu à la clôture du 17 juillet, vendu à celle du 18 (pas le même jour)",
         t and t[0]["vente"] == "2023-07-18" and t[0]["plus_tot"] and t[0]["rendement"] == -0.2,
         str(t[0] if t else None))

# 7. Plusieurs positions : 2 places, 3 signaux le même jour → les 2 premiers ; l'argent qui attend suit SPY
SPY2 = [(j, 100.0 * 1.001 ** i, "S") for i, j in enumerate(JOURS)]
d = ecrire([ev("a", "AAA", "2023-07-10"), ev("b", "AAA2", "2023-07-10"), ev("c", "AAA3", "2023-07-10")],
           {"SPY": SPY2, "AAA": AAA, "AAA2": AAA, "AAA3": AAA})
t, v, _ = banc.simuler(regle(MAX_POSITIONS=2, ARGENT_QUI_ATTEND="SPY"), d, debut="2023-07-03")
verifier("2 places : les 2 premiers signaux (par dépôt puis numéro), pas le 3e", sorted(x["id"] for x in t) == ["a", "b"])
m = t[0]["marche"]
verifier("Marché aux mêmes dates : SPY de l'achat à la vente", abs(m - (1.001 ** 21 - 1)) < 1e-3, str(m))
s = banc.statistiques(t, v, d, [])
verifier("Écart mensuel : calculé sur les fins de mois", s["total"]["mois"] >= 4, str(s["total"]))
# 8. Réglages par règle : tolérance d'entrée 0, frais du SPY, une entrée par symbole, priorité
BBB = [(j, 20.0, "B") for i, j in enumerate(JOURS) if i % 4 == 0]
d = ecrire([ev("b", "BBB", "2023-07-10")], {"SPY": SPY, "BBB": BBB})
premier_prix = next(j for j, _, _ in BBB if j >= "2023-07-11")
t, v, _ = banc.simuler(regle(TOLERANCE_ENTREE=0), d, debut="2023-07-03")
verifier("TOLERANCE_ENTREE = 0 : pas de prix le jour prévu → pas acheté", (premier_prix != "2023-07-11") and not t)
d = ecrire([ev("a", "AAA", "2023-07-10")], {"SPY": SPY, "AAA": AAA})
t, v, _ = banc.simuler(regle(ARGENT_QUI_ATTEND="SPY"), d, debut="2023-07-03")
montant = 10000 - 10 - 10                        # 10 $ pour vendre du SPY, 10 $ pour l'achat
attendu = montant * 0.99 * 1.1 * 0.99 - 10 - 10  # 10 $ pour la vente, 10 $ pour racheter du SPY
verifier("Argent dans le SPY : 10 $ de plus à l'achat et à la vente", abs(v[-1][1] - attendu) < 0.01,
         f"{v[-1][1]:.2f} contre {attendu:.2f}")
d = ecrire([ev("a", "AAA", "2023-07-10"), ev("a2", "AAA", "2023-07-24")], {"SPY": SPY, "AAA": AAA})
t, v, _ = banc.simuler(regle(DUREE=5, UNE_ENTREE_PAR_SYMBOLE_JOURS=30), d, debut="2023-07-03")
verifier("Une entrée par symbole sur 30 jours : le 2e signal (14 jours après) est sauté", [x["id"] for x in t] == ["a"])
t, v, _ = banc.simuler(regle(DUREE=5), d, debut="2023-07-03")
verifier("Sans ce réglage : les 2 signaux sont achetés", [x["id"] for x in t] == ["a", "a2"])
d = ecrire([ev("a", "AAA", "2023-07-10"), ev("b", "AAA2", "2023-07-10"), ev("c", "AAA3", "2023-07-10")],
           {"SPY": SPY, "AAA": AAA, "AAA2": AAA, "AAA3": AAA})
t, v, _ = banc.simuler(regle(priorite=lambda e, ctx: {"a": 1, "b": 3, "c": 2}[e["id"]]), d, debut="2023-07-03")
verifier("Priorité : 1 place, 3 signaux → le plus prioritaire (b)", [x["id"] for x in t] == ["b"])
# 9. Une règle qui se souvient des dépôts vus dans garder() ne voit jamais le futur (dépôts lus au fil des jours) ;
#    evenements_marche() ne donne que le passé
EVS9 = [ev(f"e{i}", "AAA", j) for i, j in enumerate(["2023-07-05", "2023-07-14", "2023-08-01", "2023-09-15", "2023-11-20"])]
d = ecrire(EVS9, {"SPY": SPY, "AAA": AAA})
vus, controles = [], []


def garder_memoire(e, ctx):
    vus.append(e["depot"])
    return False


def investir_memoire(jour, ctx):
    lendemain = banc.jour_de_bourse(d.calendrier, jour, 1)
    marche = ctx.evenements_marche("2000-01-01")
    controles.append((jour, max(vus, default=""), lendemain, max((e["depot"] for e in marche), default="")))
    return True


banc.simuler(regle(garder=garder_memoire, investir=investir_memoire), d, debut="2023-07-03")
verifier("Mémoire de garder() : au moment de chaque décision, seulement des dépôts d'AVANT le jour de bourse",
         controles and all(m < l for _, m, l, _ in controles), str([c for c in controles if not c[1] < c[2]][:2]))
verifier("evenements_marche() : seulement les dépôts jusqu'à la veille de la décision",
         all(m <= j for j, _, _, m in controles) and any(m == "2023-11-20" for *_, m in controles))

# 10. Contexte : un dépôt d'avant le début de la période (periode.json) n'est jamais acheté, même si son jour d'achat
#     tombe dans la période ; garder() le voit quand même
d = ecrire([ev("x", "AAA", "2023-07-07"), ev("y", "AAA2", "2023-07-10")], {"SPY": SPY, "AAA": AAA, "AAA2": AAA})
(ICI / "periode.json").write_text(json.dumps({"debut": "2023-07-10", "fin": "2023-12-29"}))
d = banc.Donnees(ICI)
vus = []
t, v, _ = banc.simuler(regle(garder=lambda e, ctx: vus.append(e["id"]) or True, MAX_POSITIONS=2), d)
verifier("Dépôt du contexte (7 juillet, achat prévu le 10, 1er jour de la période) : pas acheté ; celui du 10 : acheté le 11",
         [(x["id"], x["achat"]) for x in t] == [("y", "2023-07-11")] and vus == ["x", "y"], str([(x["id"], x["achat"]) for x in t]))
verifier("Début par défaut = celui de periode.json", v[0][0] == "2023-07-10", v[0][0])

# 11. Statistiques : achats de l'année = transactions fermées + positions encore ouvertes
d = ecrire([ev("a", "AAA", "2023-07-10"), ev("b", "AAA2", "2023-12-20")], {"SPY": SPY, "AAA": AAA, "AAA2": AAA})
t, v, ouvertes = banc.simuler(regle(MAX_POSITIONS=2), d, debut="2023-07-03")
s = banc.statistiques(t, v, d, ouvertes)
an = s["annees"]["2023-2024"]
verifier("Achats de l'année = 1 fermée + 1 encore ouverte", (an["transactions"], an["en_attente"], an["achats"]) == (1, 1, 2), str(an))

# 12. Échecs de livraison : seulement ceux publiés (35 jours civils avant la décision) ; finances : à leur date de dépôt
d = ecrire([ev("a", "AAA", "2023-07-10")], {"SPY": SPY, "AAA": AAA})
d.prix["AAA"] = (d.prix["AAA"][0], d.prix["AAA"][1], d.prix["AAA"][2], list(range(len(d.prix["AAA"][0]))))
vus = banc.Contexte(d, "2023-09-15").echecs("AAA", "2023-07-01")
verifier("Échecs : le plus récent visible le 15 septembre est celui du 11 août (35 jours avant)", vus[-1][0] == "2023-08-11", str(vus[-1]))
d.finances = {"a": {"Assets": [[None, "2023-06-30", 100, "n1", "2023-08-01", "10-Q"],
                               [None, "2023-09-30", 120, "n2", "2023-11-05", "10-Q"]]}}
verifier("Finances : le 1er octobre, seulement le bilan déposé avant (avec sa forme)",
         banc.Contexte(d, "2023-10-01").finances("a") == {"Assets": [[None, "2023-06-30", 100, "10-Q"]]})

# 13. Liquide gardé 10 jours (LIQUIDE_JOURS) : SPY plat à 100 $, AAA et BBB plats à 10 $ ; taille inconnue (1 %)
BBB = [(j, 10.0, "B") for j in JOURS]
d = ecrire([ev("a", "AAA", "2023-07-10"), ev("b", "BBB", "2023-07-19")], {"SPY": SPY, "AAA": AAA[:20] + [(j, 10.0, "A") for j in JOURS[20:]], "BBB": BBB})
d.prix["AAA"] = ([j for j in JOURS], [10.0] * len(JOURS), ["A"] * len(JOURS), [0] * len(JOURS))
journal = {}
t13, v13, _ = banc.simuler(regle(MAX_POSITIONS=1, DUREE=5, ARGENT_QUI_ATTEND="SPY", LIQUIDE_JOURS=10), d, debut="2023-07-03",
                           journal=journal)
p1 = (10000 - 10 - 10) * 0.99                 # achat 1 : 10 $ + 10 $ (SPY vendu), 1 % d'écart
l1 = p1 * 0.99 - 10                           # vente 1 : gardée en liquide (pas de SPY racheté)
p2 = (l1 - 10) * 0.99                         # achat 2 : payé avec le liquide, pas de SPY vendu
l2 = p2 * 0.99 - 10                           # vente 2 : liquide, puis dans SPY 10 jours de bourse plus tard (10 $)
attendu = l2 - 10
verifier("Liquide 10 jours : 2 transactions SPY évitées, au cent près", abs(v13[-1][1] - attendu) < 0.01,
         f"{v13[-1][1]:.4f} contre {attendu:.4f}")
sans = (((10000 - 20) * 0.99 * 0.99 - 20) - 20) * 0.99 * 0.99 - 20
t13b, v13b, _ = banc.simuler(regle(MAX_POSITIONS=1, DUREE=5, ARGENT_QUI_ATTEND="SPY"), d, debut="2023-07-03")
verifier("Sans liquide (par défaut) : 4 transactions SPY, au cent près", abs(v13b[-1][1] - sans) < 0.01,
         f"{v13b[-1][1]:.4f} contre {sans:.4f}")
liq_jour = [x for x in v13 if x[0] == "2023-08-09"][0][1]
verifier("Le liquide ne suit pas le S&P 500 avant d'y aller (valeur constante jusqu'au 10 août)", abs(liq_jour - l2) < 0.01,
         f"{liq_jour:.4f} contre {l2:.4f}")

# 14. Journal des signaux : 1 acheté, 1 place pleine, 1 sans prix ; montant minimal
CCC = [("2023-09-01", 5.0, "C")]
d = ecrire([ev("a", "AAA", "2023-07-10"), ev("b", "AAA2", "2023-07-10"), ev("c", "CCC", "2023-07-10")],
           {"SPY": SPY, "AAA": AAA, "AAA2": AAA, "CCC": CCC})
journal = {}
banc.simuler(regle(MAX_POSITIONS=1), d, debut="2023-07-03", journal=journal)
verifier("Journal : 3 signaux, 1 achat, 1 place pleine, 1 sans prix",
         (journal["signaux"], journal["achats"], journal["places_pleines"], journal["sans_prix"]) == (3, 1, 1, 1), str(journal))
journal = {}
t14, _, _ = banc.simuler(regle(MAX_POSITIONS=1, MONTANT_MIN=20000), d, debut="2023-07-03", journal=journal)
verifier("MONTANT_MIN : une position plus petite n'est pas achetée", not t14 and journal["montant_trop_petit"] >= 1, str(journal))

print(f"\n{sum(ok)}/{len(ok)} vérifications réussies")
sys.exit(0 if all(ok) else 1)
