"""La grande chasse (labo/chasse/PLAN.md, figé avant tout calcul) : les indices de chaque achat de dirigeant, un modèle
réentraîné chaque année avec le passé seulement, jugé sur le banc du tournoi tel quel (labo/tournoi/banc.py).

Rien du futur : les indices d'un achat n'utilisent que ce qui était déposé au plus tard le jour de son formulaire 4
(mêmes règles que le Contexte du banc : prix jusqu'à ce jour, finances et actions à leur date de dépôt, quantités
d'échecs 35 jours après) ; le modèle de l'année qui commence le 1er juillet T n'apprend que des achats dont la vente
(la cible) est finie avant T.

Usage : python labo/chasse/chasse.py --coffre cache/coffre --decouverte cache/decouverte --sortie labo/chasse/resultats
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import re
import sys
import time
from bisect import bisect_left, bisect_right, insort
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "tournoi"))
import banc  # noqa: E402  le banc du tournoi, tel quel

DUREES = (63, 126, 252)
PREMIERE_ANNEE, DERNIERE_ANNEE = 2017, 2025  # années testées : 2017-2018 … 2025-2026
DEBUT_ENTRAINEMENT = "2016-01-01"
FIN_COFFRE = "2023-06-30"
PART_GARDEE = 0.10
MAX_POSITIONS = 10
PARAMS = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200, l2_regularization=1.0,
              random_state=0)
CEO = re.compile(r"\bCEO\b|CHIEF EXECUTIVE|\bPEO\b", re.I)
CFO = re.compile(r"\bCFO\b|CHIEF FINANCIAL|\bPFO\b", re.I)
CHAIR = re.compile(r"(?<!VICE )(?<!VICE-)\bCHAIR", re.I)
PRES = re.compile(r"(?<!VICE )(?<!VICE-)\bPRESIDENT\b", re.I)
COO = re.compile(r"\bCOO\b|CHIEF OPERATING", re.I)
NAN = float("nan")
REVENUS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet")
BILANS = ("Assets", "Liabilities", "StockholdersEquity", "AssetsCurrent", "LiabilitiesCurrent")
EXERCICES = ("NetIncomeLoss", "NetCashProvidedByUsedInOperatingActivities") + REVENUS


def moins(jour, n):
    return (date.fromisoformat(jour) - timedelta(days=n)).isoformat()


def ecart_jours(a, b):
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def num(x):
    return NAN if x is None else float(x)


def div(a, b):
    return a / b if (a is not None and b not in (None, 0) and not math.isnan(a) and not math.isnan(b)) else NAN


def journal(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


# ---------- Les indices ----------


class Series:
    """Les prix d'un jeu (d.prix) avec, pour chaque clôture, l'indice où commence son code de titre (CUSIP)."""

    def __init__(self, d):
        self.d = d
        self.debut_cusip = {}
        for s, (dates, px, cus, q) in d.prix.items():
            deb, k0 = [], 0
            for k in range(len(dates)):
                if k and cus[k] != cus[k - 1]:
                    k0 = k
                deb.append(k0)
            self.debut_cusip[s] = deb

    def prix(self, s, jour, bourse_3m, actions):
        """Les indices de prix d'un symbole au soir du `jour` (rien après) : rendements avant, écart au haut et au bas
        de 12 mois, volatilité, présence dans les fichiers d'échecs, échecs publiés ÷ actions, niveau du prix."""
        f = {k: NAN for k in ("r1m", "r3m", "r6m", "r12m", "haut12", "bas12", "volatilite", "presence3m", "echecs",
                              "prix_log")}
        p = self.d.prix.get(s)
        if not p:
            f["presence3m"] = 0.0
            return f
        dates, px, cus, q = p
        k = bisect_right(dates, jour) - 1
        if k < 0 or ecart_jours(dates[k], jour) > 10:
            f["presence3m"] = 0.0
            return f
        deb = self.debut_cusip[s][k]
        dernier = px[k]
        f["prix_log"] = math.log10(dernier) if dernier > 0 else NAN
        for nom, n in (("r1m", 30), ("r3m", 91), ("r6m", 182), ("r12m", 365)):
            cible = moins(dates[k], n)
            i = bisect_right(dates, cible) - 1
            if i >= deb and ecart_jours(dates[i], cible) <= 15 and px[i] > 0:
                f[nom] = dernier / px[i] - 1
        i12 = max(bisect_left(dates, moins(jour, 365)), deb)
        fen = px[i12:k + 1]
        if len(fen) >= 5 and min(fen) > 0:
            f["haut12"] = dernier / max(fen) - 1
            f["bas12"] = dernier / min(fen) - 1
        i6 = max(bisect_left(dates, moins(jour, 182)), deb)
        lr = []
        for j in range(i6 + 1, k + 1):
            g = ecart_jours(dates[j - 1], dates[j])
            if g > 0 and px[j] > 0 and px[j - 1] > 0:
                lr.append(math.log(px[j] / px[j - 1]) ** 2 / (g * 252 / 365))
        if len(lr) >= 5:
            f["volatilite"] = math.sqrt(sum(lr) / len(lr) * 252)
        i3 = bisect_left(dates, moins(jour, 91))
        f["presence3m"] = (k + 1 - i3) / bourse_3m if bourse_3m else NAN
        a, b = bisect_left(dates, moins(jour, 125)), bisect_right(dates, moins(jour, banc.DELAI_ECHECS))
        if b > a and actions:
            f["echecs"] = sum(q[a:b]) / (b - a) / actions
        return f

    def rendement(self, s, jour, n):
        """Rendement du symbole sur n jours civils jusqu'au `jour` (même code de titre), sinon NaN."""
        p = self.d.prix.get(s)
        if not p:
            return NAN
        dates, px = p[0], p[1]
        k = bisect_right(dates, jour) - 1
        if k < 0:
            return NAN
        i = bisect_right(dates, moins(dates[k], n)) - 1
        if i < self.debut_cusip[s][k] or i < 0 or px[i] <= 0:
            return NAN
        return px[k] / px[i] - 1


class Meteo:
    """Le nombre de formulaires 4 d'achat et de vente de tout le marché, par jour de dépôt (sommes cumulées)."""

    def __init__(self, d):
        par_jour = defaultdict(lambda: [0, 0])
        for e in d.evenements:
            par_jour[e["depot"]][0 if e["sens"] == "achat" else 1] += 1
        self.jours = sorted(par_jour)
        self.cum_a, self.cum_v = [0], [0]
        for j in self.jours:
            self.cum_a.append(self.cum_a[-1] + par_jour[j][0])
            self.cum_v.append(self.cum_v[-1] + par_jour[j][1])

    def part_achats(self, jour, n=30):
        i, j = bisect_left(self.jours, moins(jour, n)), bisect_right(self.jours, jour)
        a, v = self.cum_a[j] - self.cum_a[i], self.cum_v[j] - self.cum_v[i]
        return a / (a + v) if a + v else NAN


class Comptes:
    """Les finances et les actions d'une compagnie, visibles au fil des dépôts (1re version déposée, à sa date)."""

    def __init__(self, d, cik):
        faits = []
        for concept, liste in (d.finances.get(cik) or {}).items():
            for f in liste:
                faits.append((f[4], "f", concept, f[0], f[1], f[2]))
        for concept, liste in (d.actions.get(cik) or {}).items():
            for f in liste:
                faits.append((f[4], "a", concept, f[0], f[1], f[2]))
        self.faits = sorted(faits, key=lambda x: (x[0] or "", x[2], x[4] or ""))
        self.k = 0
        self.bilans = defaultdict(dict)  # concept → {fin : valeur}
        self.exercices = defaultdict(dict)  # concept → {fin : valeur} (durées de 350 à 380 jours)
        self.actions = {}  # fin → nombre (la 1re vue gagne)

    def jusqu_a(self, jour):
        while self.k < len(self.faits) and (self.faits[self.k][0] or "9999") <= jour:
            depose, sorte, concept, debut, fin, valeur = self.faits[self.k]
            self.k += 1
            if valeur is None or fin is None:
                continue
            if sorte == "a":
                self.actions.setdefault(fin, valeur)
            elif debut is None:
                self.bilans[concept].setdefault(fin, valeur)
            elif 350 <= ecart_jours(debut, fin) <= 380:
                self.exercices[concept].setdefault(fin, valeur)

    def dernier(self, table, concept):
        t = table.get(concept)
        if not t:
            return None, None
        fin = max(t)
        return fin, t[fin]

    def indices(self, jour, valeur_m):
        f = {}
        fin_a, actif = self.dernier(self.bilans, "Assets")
        _, passif = self.dernier(self.bilans, "Liabilities")
        _, avoir = self.dernier(self.bilans, "StockholdersEquity")
        _, ac = self.dernier(self.bilans, "AssetsCurrent")
        _, pc = self.dernier(self.bilans, "LiabilitiesCurrent")
        _, bn = self.dernier(self.exercices, "NetIncomeLoss")
        _, cfo = self.dernier(self.exercices, "NetCashProvidedByUsedInOperatingActivities")
        f["roa"] = div(num(bn), num(actif))
        f["dette_actif"] = div(num(passif), num(actif))
        f["liquidite"] = div(num(ac), num(pc))
        f["cfo_actif"] = div(num(cfo), num(actif))
        f["perte"] = NAN if bn is None else float(bn < 0)
        f["valeur_comptable"] = div(num(avoir), num(valeur_m) * 1e6 if valeur_m else None)
        f["age_finances"] = ecart_jours(fin_a, jour) if fin_a else NAN
        croissance = NAN
        for concept in REVENUS:
            t = self.exercices.get(concept)
            if t and len(t) >= 2:
                fins = sorted(t)
                derniere = fins[-1]
                avant = [x for x in fins if 300 <= ecart_jours(x, derniere) <= 430]
                if avant and t[avant[-1]]:
                    croissance = t[derniere] / t[avant[-1]] - 1
                    break
        f["croissance_ventes"] = croissance
        dilution = NAN
        if self.actions:
            fins = sorted(self.actions)
            derniere = fins[-1]
            avant = [x for x in fins if 300 <= ecart_jours(x, derniere) <= 430]
            if avant and self.actions[avant[-1]]:
                dilution = self.actions[derniere] / self.actions[avant[-1]] - 1
        f["emission_actions"] = dilution
        return f


INDICES = None  # l'ordre des colonnes, fixé au 1er achat


def indices_achat(e, ctx, series, meteo, comptes):
    """Les indices d'un achat au soir de son dépôt (voir PLAN.md, « Les indices »)."""
    j = e["depot"]
    titres = " ".join((i.get("titre") or "") for i in e.get("inities") or [])
    roles = {r for i in e.get("inities") or [] for r in (i.get("roles") or [])}
    f = {"pdg": float(bool(CEO.search(titres))), "chef_finances": float(bool(CFO.search(titres))),
         "president_conseil": float(bool(CHAIR.search(titres))), "president": float(bool(PRES.search(titres))),
         "chef_exploitation": float(bool(COO.search(titres))), "administrateur": float("administrateur" in roles),
         "dirigeant": float("dirigeant" in roles), "dix_pourcent": float("actionnaire de 10 %" in roles),
         "declarants": float(len(e.get("inities") or []))}
    montant = e.get("montant")
    f["montant_log"] = math.log10(montant) if montant and montant > 0 else NAN
    part = e.get("part")
    f["part"] = NAN if part is None else min(float(part), 10.0)
    f["nouvelle_position"] = float(bool(e.get("nouvelle_position")))
    f["direct"] = float(bool(e.get("direct")))
    p10 = e.get("plan_10b5_1")
    f["plan_10b5_1"] = NAN if p10 is None else float(bool(p10))
    f["routinier"] = float(bool(e.get("routinier")))
    f["delai_depot"] = ecart_jours(e["jour_dernier"], j) if e.get("jour_dernier") else NAN
    f["etalement"] = ecart_jours(e["jour_premier"], e["jour_dernier"]) if e.get("jour_premier") and e.get("jour_dernier") else NAN
    ca = e.get("cloture_avant")
    f["prime_prix"] = div(num(e.get("prix_moyen")), num(ca[1]) if ca else None) - 1 if ca else NAN
    h = e.get("historique") or {}
    f["achats_avant_initie"] = math.log1p(h["achats_avant"]) if h.get("achats_avant") is not None else NAN
    f["jours_depuis_achat_meme_cie"] = num(h.get("jours_depuis_achat_meme_cie"))
    b = e.get("bilan_initie") or {}
    f["bilan_mesures"] = num(b.get("mesures"))
    f["bilan_ecart"] = num(b.get("ecart_moyen"))
    f["bilan_gagnant"] = num(b.get("part_gagnante"))
    f["groupe_30j"] = num(e.get("groupe_30j"))
    f["achats_90j"] = num(e.get("achats_90j"))
    f["ventes_90j"] = num(e.get("ventes_90j"))
    f["ventes_365j"] = float(sum(1 for x in ctx.evenements_avant(e["cik"], moins(j, 365))
                                 if x["sens"] == "vente" and x["depot"] < j))
    f["13d_90j"] = num(e.get("13d_90j"))
    f["13g_90j"] = num(e.get("13g_90j"))
    vm = e.get("valeur_m")
    f["valeur_log"] = math.log10(vm) if vm and vm > 0 else NAN
    f.update(series.prix(e["symbole"], j, len(ctx.jours_de_bourse(moins(j, 91))), e.get("actions_circulation")))
    comptes.jusqu_a(j)
    f.update(comptes.indices(j, vm))
    f["spy_1m"] = series.rendement("SPY", j, 30)
    f["spy_3m"] = series.rendement("SPY", j, 91)
    f["petites_moins_grandes_3m"] = series.rendement("IWM", j, 91) - f["spy_3m"]
    f["meteo_initiés"] = meteo.part_achats(j)
    return f


# ---------- La cible : le rendement net contre le S&P 500, comme le banc ----------


def resultat(d, e, h):
    """(jour de la vente, rendement net − S&P 500) d'un achat gardé `h` jours de bourse, avec les règles du banc :
    achat à la clôture du 1er jour de bourse après le dépôt (3 de plus au plus), vente au jour prévu (10 de plus au
    plus, sinon la dernière clôture connue), demi-écart à l'achat et à la vente. None : pas de prix ou pas encore fini."""
    cal, s = d.calendrier, e["symbole"]
    entree = None
    for k in range(1, banc.TOLERANCE_ENTREE + 2):
        jk = banc.jour_de_bourse(cal, e["depot"], k)
        if jk is None:
            return None
        entree = banc.prix_au(d, s, jk)
        if entree:
            break
    if not entree:
        return None
    prevue = banc.jour_de_bourse(cal, entree[0], h)
    limite = banc.jour_de_bourse(cal, prevue, banc.TOLERANCE_SORTIE) if prevue else None
    if limite is None:
        return None
    sortie, jk = None, prevue
    while jk and jk <= limite:
        sortie = banc.prix_au(d, s, jk)
        if sortie:
            break
        jk = banc.jour_de_bourse(cal, jk, 1)
    sortie = sortie or banc._dernier(d, s, limite)
    if not sortie or sortie[0] < entree[0]:
        return None
    r = banc.rendement_enchaine(d, s, entree, sortie)
    spy = d.prix["SPY"]
    spy_au = lambda j_: spy[1][bisect_right(spy[0], j_) - 1]  # noqa: E731
    m = spy_au(sortie[0]) / spy_au(entree[0]) - 1
    de = banc.demi_ecart(e.get("valeur_m"))
    return sortie[0], (1 + r) * (1 - de) ** 2 - 1 - m


# ---------- Le jeu : indices et cibles de tous les achats ----------


def achats_du_jeu(d, debut, fin):
    return [e for e in d.evenements if e["sens"] == "achat" and e.get("symbole") and debut <= e["depot"] <= fin]


def construire(d, achats, lignes, completer=None):
    """Ajoute à `lignes` (id → {indices, cibles}) les achats ; `completer` : ids dont seules les cibles manquantes sont
    calculées avec ce jeu (achats de la fin du coffre-fort, vendus dans la période de la découverte)."""
    global INDICES
    series, meteo = Series(d), Meteo(d)
    comptes = {}
    n = 0
    for e in sorted(achats, key=lambda x: (x["cik"], x["depot"], x["id"])):
        if completer is not None:
            ligne = lignes.get(e["id"])
            if ligne is None or e["id"] not in completer:
                continue
            for h in DUREES:
                if ligne["cibles"].get(h) is None:
                    ligne["cibles"][h] = resultat(d, e, h)
            continue
        ctx = banc.Contexte(d, e["depot"])
        c = comptes.get(e["cik"])
        if c is None:
            c = comptes[e["cik"]] = Comptes(d, e["cik"])
        f = indices_achat(e, ctx, series, meteo, c)
        if INDICES is None:
            INDICES = list(f)
        lignes[e["id"]] = {"depot": e["depot"], "mois": e["depot"][:7], "symbole": e["symbole"],
                           "x": [f[k] for k in INDICES], "cibles": {h: resultat(d, e, h) for h in DUREES}}
        n += 1
        if n % 20000 == 0:
            journal(f"  {n} achats")
    return n


# ---------- Le modèle, année par année ----------


def rangs_par_mois(ids, lignes, h):
    """Le rang (0 à 1) du rendement net de chaque achat parmi les achats du même mois de dépôt (ceux de la liste)."""
    par_mois = defaultdict(list)
    for i in ids:
        par_mois[lignes[i]["mois"]].append(i)
    y = {}
    for m, l in par_mois.items():
        l = sorted(l, key=lambda i: lignes[i]["cibles"][h][1])
        n = len(l)
        for r, i in enumerate(l):
            y[i] = (r + 0.5) / n
    return y


def annee(t):
    return f"{t}-07-01", f"{t + 1}-06-30", f"{t}-{t + 1}"


def predire(lignes, h, minimum):
    """Les scores des achats de chaque année testée (modèle entraîné avec les années d'avant), les seuils (10 % les plus
    hauts des scores de l'entraînement) et des mesures pour comprendre."""
    scores, seuils, mesures = {}, {}, {}
    for t in range(PREMIERE_ANNEE, DERNIERE_ANNEE + 1):
        debut, fin, nom = annee(t)
        appris = [i for i, l in lignes.items() if DEBUT_ENTRAINEMENT <= l["depot"] < debut
                  and l["cibles"].get(h) is not None and l["cibles"][h][0] < debut]
        testes = [i for i, l in lignes.items() if debut <= l["depot"] <= fin]
        if len(appris) < minimum or not testes:
            mesures[nom] = {"appris": len(appris), "testes": len(testes), "saute": True}
            continue
        y = rangs_par_mois(appris, lignes, h)
        X = np.array([lignes[i]["x"] for i in appris], dtype=float)
        # une colonne sans aucune valeur dans l'entraînement n'apprend rien (et sklearn 1.9.1 plante dessus) : retirée
        pleines = ~np.all(np.isnan(X), axis=0)
        modele = HistGradientBoostingRegressor(**PARAMS).fit(X[:, pleines], np.array([y[i] for i in appris]))
        seuil = float(np.quantile(modele.predict(X[:, pleines]), 1 - PART_GARDEE))
        p = modele.predict(np.array([lignes[i]["x"] for i in testes], dtype=float)[:, pleines])
        for i, v in zip(testes, p):
            scores[i] = float(v)
        seuils[nom] = seuil
        # pour comprendre : achats déjà vendus (cible connue) de l'année testée
        connus = [(scores[i], lignes[i]["cibles"][h][1]) for i in testes if lignes[i]["cibles"].get(h) is not None]
        m = {"appris": len(appris), "testes": len(testes), "seuil": round(seuil, 4),
             "gardes": int(sum(1 for i in testes if scores[i] >= seuil)),
             "indices_vides": [k for k, v in zip(INDICES, pleines) if not v]}
        if len(connus) >= 30:
            sc = np.array([c[0] for c in connus])
            ex = np.array([c[1] for c in connus])
            haut = ex[sc >= seuil]
            m.update({"connus": len(connus), "net_moyen_tous": round(float(ex.mean()), 4),
                      "net_median_tous": round(float(np.median(ex)), 4),
                      "net_moyen_gardes": round(float(haut.mean()), 4) if len(haut) else None,
                      "net_median_gardes": round(float(np.median(haut)), 4) if len(haut) else None,
                      "part_gagnante_gardes": round(float((haut > 0).mean()), 4) if len(haut) else None,
                      "correlation_rang": round(float(np.corrcoef(np.argsort(np.argsort(sc)),
                                                                  np.argsort(np.argsort(ex)))[0, 1]), 4)})
        mesures[nom] = m
        journal(f"  durée {h}, {nom} : {m}")
    return scores, seuils, mesures


# ---------- Le jugement : le banc du tournoi ----------


class Regle:
    ID = "chasse"
    ARGENT_QUI_ATTEND = "SPY"

    def __init__(self, scores, seuils, h):
        self.scores, self.seuils, self.DUREE, self.MAX_POSITIONS = scores, seuils, h, MAX_POSITIONS

    def garder(self, e, ctx):
        sc = self.scores.get(e["id"])
        return e["sens"] == "achat" and sc is not None and sc >= self.seuils.get(banc.annee_de(e["depot"]), 9e9)

    def priorite(self, e, ctx):
        return self.scores.get(e["id"], 0.0)


def ecarts_mensuels(valeur_jour, d):
    spy = d.prix["SPY"]

    def spy_au(j):
        return spy[1][bisect_right(spy[0], j) - 1]

    fins = {}
    for j, v in valeur_jour:
        fins[j[:7]] = (j, v)
    points = ([valeur_jour[0]] if valeur_jour else []) + [fins[m] for m in sorted(fins)]
    if len(points) > 1 and points[1][0] == points[0][0]:
        points.pop(0)
    return [(b[1] / a[1] - 1) - (spy_au(b[0]) / spy_au(a[0]) - 1) for a, b in zip(points, points[1:])]


def juger(d, scores, seuils, h, debut, fin):
    j_ = {}
    transactions, valeur_jour, ouvertes = banc.simuler(Regle(scores, seuils, h), d, debut=debut, fin_prix=fin, journal=j_)
    s = banc.statistiques(transactions, valeur_jour, d, ouvertes)
    return s, ecarts_mensuels(valeur_jour, d), j_, len(transactions)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--coffre", required=True)
    a.add_argument("--decouverte", required=True)
    a.add_argument("--sortie", required=True)
    a.add_argument("--minimum", type=int, default=2000, help="achats appris au minimum pour tester une année")
    x = a.parse_args()
    sortie = Path(x.sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    lignes = {}
    journal("coffre-fort : chargement")
    d = banc.Donnees(x.coffre)
    fin_c = d.periode.get("fin", FIN_COFFRE)
    journal(f"coffre-fort : {len(d.evenements)} formulaires, prix de SPY {d.prix['SPY'][0][0]} → {d.prix['SPY'][0][-1]}")
    n = construire(d, achats_du_jeu(d, DEBUT_ENTRAINEMENT, fin_c), lignes)
    journal(f"coffre-fort : {n} achats")
    del d
    gc.collect()
    journal("découverte : chargement")
    d = banc.Donnees(x.decouverte)
    debut_d = d.periode.get("debut", "2023-07-01")
    journal(f"découverte : {len(d.evenements)} formulaires, prix de SPY {d.prix['SPY'][0][0]} → {d.prix['SPY'][0][-1]}")
    manquants = {i for i, l in lignes.items() if any(l["cibles"].get(h) is None for h in DUREES)}
    construire(d, achats_du_jeu(d, "0000-00-00", fin_c), lignes, completer=manquants)
    journal(f"coffre-fort : {len(manquants)} achats sans toutes leurs cibles, encore sans après la découverte : "
            f"{sum(1 for i in manquants if any(lignes[i]['cibles'].get(h) is None for h in DUREES))}")
    n = construire(d, achats_du_jeu(d, debut_d, d.periode.get("fin", "2026-06-30")), lignes)
    journal(f"découverte : {n} achats ; en tout {len(lignes)} achats, {len(INDICES)} indices")
    couverture = {k: round(float(np.mean([not math.isnan(l['x'][i]) for l in lignes.values()])), 3)
                  for i, k in enumerate(INDICES)}
    cibles = {h: sum(1 for l in lignes.values() if l["cibles"].get(h) is not None) for h in DUREES}
    resultats = {"plan": "labo/chasse/PLAN.md", "achats": len(lignes), "indices": INDICES, "couverture": couverture,
                 "cibles_connues": cibles, "durees": {}}
    predictions = {}
    for h in DUREES:
        journal(f"durée {h} : modèles année par année")
        predictions[h] = predire(lignes, h, x.minimum)
    journal("découverte : le banc")
    jugements = {h: {"decouverte": juger(d, predictions[h][0], predictions[h][1], h, debut_d,
                                         f"{DERNIERE_ANNEE + 1}-06-30")} for h in DUREES}
    del d
    gc.collect()
    journal("coffre-fort : le banc")
    d = banc.Donnees(x.coffre)
    for h in DUREES:
        jugements[h]["coffre"] = juger(d, predictions[h][0], predictions[h][1], h, f"{PREMIERE_ANNEE}-07-01", fin_c)
    for h in DUREES:
        (sc, mc, jc, nc), (sd_, md, jd, nd) = jugements[h]["coffre"], jugements[h]["decouverte"]
        annees = {**sc["annees"], **sd_["annees"]}
        gagnees = sum(1 for v in annees.values() if v.get("portefeuille") is not None and v.get("spy_garde") is not None
                      and v["portefeuille"] > v["spy_garde"])
        tot = (1 + (sc["total"]["portefeuille"] or 0)) * (1 + (sd_["total"]["portefeuille"] or 0)) - 1
        spy = (1 + (sc["total"]["spy_garde"] or 0)) * (1 + (sd_["total"]["spy_garde"] or 0)) - 1
        e = mc + md
        moy = sum(e) / len(e) if e else None
        sdv = math.sqrt(sum((v - moy) ** 2 for v in e) / (len(e) - 1)) if len(e) > 2 else None
        t = moy / (sdv / math.sqrt(len(e))) if sdv else None
        reussi = tot > spy and gagnees >= 6 and t is not None and t >= 2.4
        resultats["durees"][h] = {
            "neuf_ans": {"portefeuille": round(tot, 4), "spy_garde": round(spy, 4), "annees_gagnees": gagnees,
                         "annees": len(annees), "mois": len(e), "ecart_mensuel_moyen": round(moy, 5) if moy else None,
                         "t_mensuel": round(t, 2) if t else None, "reussi": reussi},
            "par_annee": {k: {c: v.get(c) for c in ("transactions", "portefeuille", "spy_garde", "ecart_moyen",
                                                     "ecart_median", "bat_le_marche", "t")} for k, v in sorted(annees.items())},
            "coffre": sc["total"], "decouverte": sd_["total"], "signaux": {"coffre": jc, "decouverte": jd},
            "transactions": {"coffre": nc, "decouverte": nd}, "mesures": predictions[h][2]}
        journal(f"durée {h} : {resultats['durees'][h]['neuf_ans']}")
    (sortie / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({h: v["neuf_ans"] for h, v in resultats["durees"].items()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
