"""Chasse B — tout le marché (labo/chasse2/PLAN.md) : chaque fin de mois, les 1 000 plus grosses compagnies reçoivent un
score d'un modèle qui apprend seulement du passé (toutes les sources de la SEC à la fois) ; on garde les 10 meilleures.
Usage : python labo/chasse2/chasse_b.py --base cache2/base --sortie labo/chasse2/resultats_b
"""
from __future__ import annotations

import argparse
import json
import math
import re
import time
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

import chasse_c
import commun as c

PARAMS = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200, l2_regularization=1.0,
              random_state=0)
UNIVERS = 1000
PRIX_MIN = 5.0
POSITIONS = 10
TOL_MOIS = 5      # jours de bourse : clôture d'une fin de mois
TOL_ENTREE = 3    # jours de bourse : achat au 1er jour après la fin du mois (comme le banc du tournoi)
ACTIONS_JOURS = 400
MIN_SPY = 100.0   # argent qui attend : mis dans SPY seulement à partir de 100 $
REVENUS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet")
NAN = float("nan")
T0 = time.time()


def journal(t):
    print(f"[{(time.time() - T0) / 60:5.1f} min] {t}", flush=True)


def jour_moins(j, jours):
    return c.entier((date.fromisoformat(c.iso(j)) - timedelta(days=jours)).isoformat())


# ---------- Les compagnies : symbole → compagnie, actions, finances, initiés, 13D/13G ----------

class Carte:
    """Symbole d'un prix → compagnie (CIK) au mois m : la compagnie qui a écrit ce symbole le plus de fois dans ses
    formulaires 4 des 24 mois jusqu'à m."""

    def __init__(self, base):
        self.par_mois = defaultdict(list)  # mois (AAAAMM) → [(symbole, cik, nombre)]
        for cik, s, m, n in c.lire_jsonl(Path(base) / "symboles_f4.jsonl.gz"):
            self.par_mois[int(m.replace("-", ""))].append((s, cik, n))
        self.cache = {}

    def au(self, m):
        """{symbole : cik} pour le mois m (AAAAMM)."""
        if m in self.cache:
            return self.cache[m]
        a, mo = divmod(m, 100)
        compte = defaultdict(Counter)
        for k in range(24):
            mm = (a * 12 + mo - 1 - k)
            for s, cik, n in self.par_mois.get((mm // 12) * 100 + mm % 12 + 1, ()):
                compte[s][cik] += n
        self.cache[m] = {s: cc.most_common(1)[0][0] for s, cc in compte.items()}
        return self.cache[m]


class Serie:
    """Faits d'un concept triés par date de dépôt ; pour un jour j : ceux déposés au plus tard j (un préfixe), et le
    meilleur du préfixe (la fin de période la plus récente) en O(log n)."""

    def __init__(self, faits):  # faits : [(déposé, fin, valeur)]
        self.x = sorted(faits)
        self.depots = [f[0] for f in self.x]
        self.meilleur, m = [], None
        for f in self.x:
            if m is None or f[1] >= m[1]:
                m = f
            self.meilleur.append(m)

    def au(self, j):
        i = bisect_right(self.depots, j) - 1
        return self.meilleur[i] if i >= 0 else None

    def avant(self, j, fin_min, fin_max):
        """Parmi les faits déposés au plus tard j : la valeur dont la fin est dans [fin_min, fin_max] (la plus récente)."""
        i = bisect_right(self.depots, j)
        meilleur = None
        for f in self.x[:i]:
            if fin_min <= f[1] <= fin_max and (meilleur is None or f[1] > meilleur[1]):
                meilleur = f
        return meilleur


class Compagnie:
    """Les faits d'une compagnie, utilisables à partir de leur date de dépôt."""

    def __init__(self, faits):
        actions = [(c.entier(f), c.entier(e), float(v)) for e, v, f in faits.get("actions") or []
                   if e and v and f and float(v) > 0]
        actions += [(c.entier(x[4]), c.entier(x[1]), float(x[2]))
                    for x in (faits.get("finances") or {}).get("CommonStockSharesOutstanding", [])
                    if x[1] and x[2] and x[4] and float(x[2]) > 0]
        self.actions = Serie(actions)
        self.fins_actions = sorted((f[1], f[0], f[2]) for f in actions)  # (fin, déposé, valeur)
        fi = faits.get("finances") or {}
        self.ex, self.bi = {}, {}
        for concept, liste in fi.items():
            ex = [(c.entier(x[4]), c.entier(x[1]), float(x[2])) for x in liste if x[0] and x[1] and x[2] is not None and x[4]]
            bi = [(c.entier(x[4]), c.entier(x[1]), float(x[2])) for x in liste if not x[0] and x[1] and x[2] is not None
                  and x[4]]
            if ex:
                self.ex[concept] = Serie(ex)
            if bi:
                self.bi[concept] = Serie(bi)

    def nb_actions(self, j):
        """Les actions en circulation déposées au plus tard j, fin de période dans les 400 jours : la plus récente."""
        f = self.actions.au(j)
        return f[2] if f and f[1] >= jour_moins(j, ACTIONS_JOURS) else None

    def actions_autour(self, avant, jour):
        """Pour confirmer un fractionnement : (dernières actions avant, premières après), déposées dans les 400 jours."""
        limite = c.entier((date.fromisoformat(c.iso(jour)) + timedelta(days=ACTIONS_JOURS)).isoformat())
        av = [x for x in self.fins_actions if x[0] <= avant and x[1] <= limite]
        ap = [x for x in self.fins_actions if x[0] >= jour and x[1] <= limite]
        return (av[-1][2] if av else None), (ap[0][2] if ap else None)

    def _valeur(self, series, concepts, j, il_y_a, fenetre):
        for concept in concepts:
            serie = series.get(concept)
            dernier = serie.au(j) if serie else None
            if not dernier:
                continue
            if il_y_a == 0:
                return dernier[2]
            fin = date.fromisoformat(c.iso(dernier[1]))
            x = serie.avant(j, c.entier((fin - timedelta(days=fenetre[1])).isoformat()),
                            c.entier((fin - timedelta(days=fenetre[0])).isoformat()))
            return x[2] if x else None
        return None

    def exercice(self, concepts, j, il_y_a=0):
        """Valeur du dernier exercice (350 à 380 jours) déposé au plus tard j ; il_y_a=1 : l'exercice d'avant."""
        return self._valeur(self.ex, concepts, j, il_y_a, (330, 400))

    def bilan(self, concept, j, il_y_a=0):
        """Dernière valeur de bilan déposée au plus tard j ; il_y_a=1 : celle d'environ un an avant."""
        return self._valeur(self.bi, [concept], j, il_y_a, (320, 410))


def charger_compagnies(base):
    return {x["cik"]: Compagnie(x) for x in c.lire_jsonl(Path(base) / "faits.jsonl.gz")}


def charger_inities(base):
    """{cik : [(jour, achat?, montant, pdg ou chef des finances)]} triés."""
    par = defaultdict(list)
    for r in c.lire_jsonl(Path(base) / "inities.jsonl.gz"):
        par[r[1]].append((c.entier(r[0]), r[3] == "achat", r[4] or 0.0, bool(r[7] or r[8])))
    for v in par.values():
        v.sort()
    return par


def charger_treize(base):
    par = defaultdict(lambda: ([], []))
    for j, forme, ciks in c.lire_jsonl(Path(base) / "treize.jsonl.gz"):
        for cik in ciks:
            par[cik][0 if forme.startswith("13D") else 1].append(c.entier(j))
    for a, b in par.values():
        a.sort()
        b.sort()
    return par


def compter(liste, debut, fin):
    return bisect_right(liste, fin) - bisect_right(liste, debut)


# ---------- Les indices d'une compagnie à une fin de mois ----------

def ratio(a, b):
    return a / b if a is not None and b not in (None, 0) else NAN


def indices(px, s, cie, ini, treize, fins, k, valeur, spy_ctx, meteo_j):
    m = fins[k]
    f = {}

    def rend(a, b):
        x, y = px.dernier(s, a, TOL_MOIS), px.dernier(s, b, TOL_MOIS)
        return px.rendement(s, x[0], y[0]) if x and y and y[0] > x[0] else NAN
    f["r1"] = rend(fins[k - 1], m) if k >= 1 else NAN
    f["r3"] = rend(fins[k - 3], m) if k >= 3 else NAN
    f["r6"] = rend(fins[k - 6], m) if k >= 6 else NAN
    f["r12_1"] = rend(fins[k - 12], fins[k - 1]) if k >= 12 else NAN
    d, aj = px.d[s], px.ajustes(s)
    fin_i = int(np.searchsorted(d, m, "right"))
    i = int(np.searchsorted(d, px.cal[max(px.rang(m) - 63, 0)], "left"))
    if fin_i - i >= 16:
        rangs = np.searchsorted(px.cal_np, d[i:fin_i])
        ecarts = np.maximum(np.diff(rangs), 1)
        rs = np.log(aj[i + 1:fin_i] / aj[i:fin_i - 1]) / np.sqrt(ecarts)
        f["vol63"] = float(np.std(rs))
    else:
        f["vol63"] = NAN
    i = int(np.searchsorted(d, px.cal[max(px.rang(m) - 252, 0)], "left"))
    f["ecart_haut12"] = float(aj[fin_i - 1] / aj[i:fin_i].max() - 1) if fin_i - i >= 20 else NAN
    f["valeur_log"] = math.log10(valeur)
    eq = cie.bilan("StockholdersEquity", m)
    ni, cfo = cie.exercice(["NetIncomeLoss"], m), cie.exercice(["NetCashProvidedByUsedInOperatingActivities"], m)
    ventes, gp = cie.exercice(REVENUS, m), cie.exercice(["GrossProfit"], m)
    actif, passif = cie.bilan("Assets", m), cie.bilan("Liabilities", m)
    f["bm"], f["ep"], f["sp"], f["cfp"] = ratio(eq, valeur), ratio(ni, valeur), ratio(ventes, valeur), ratio(cfo, valeur)
    f["roa"], f["gpa"] = ratio(ni, actif), ratio(gp, actif)
    f["accruals"] = ratio(ni - cfo, actif) if ni is not None and cfo is not None else NAN
    f["dette_actif"] = ratio(passif, actif)
    f["liquidite"] = ratio(cie.bilan("AssetsCurrent", m), cie.bilan("LiabilitiesCurrent", m))
    v1 = cie.exercice(REVENUS, m, 1)
    f["croissance_ventes"] = ratio(ventes, v1) - 1 if ventes is not None and v1 else NAN
    a1 = cie.bilan("Assets", m, 1)
    f["croissance_actif"] = ratio(actif, a1) - 1 if actif is not None and a1 else NAN
    n0, n1 = cie.nb_actions(m), cie.nb_actions(jour_moins(m, 365))
    f["variation_actions"] = n0 / n1 - 1 if n0 and n1 else NAN
    evs = ini or []
    jours = [e[0] for e in evs]
    a90, a365, a180 = jour_moins(m, 90), jour_moins(m, 365), jour_moins(m, 180)
    lo90, lo365, lo180, hi = bisect_right(jours, a90), bisect_right(jours, a365), bisect_right(jours, a180), \
        bisect_right(jours, m)
    f["ins_achats_90"] = float(sum(1 for e in evs[lo90:hi] if e[1]))
    f["ins_ventes_90"] = float(sum(1 for e in evs[lo90:hi] if not e[1]))
    f["ins_achats_365"] = float(sum(1 for e in evs[lo365:hi] if e[1]))
    f["ins_ventes_365"] = float(sum(1 for e in evs[lo365:hi] if not e[1]))
    f["pdg_cfo_achat_180"] = float(any(e[1] and e[3] for e in evs[lo180:hi]))
    f["achats_sur_valeur_365"] = sum(e[2] for e in evs[lo365:hi] if e[1]) / valeur
    t13 = treize or ([], [])
    f["treize_d_365"] = float(compter(t13[0], a365, m))
    f["treize_g_365"] = float(compter(t13[1], a365, m))
    i21 = int(np.searchsorted(d, px.cal[max(px.rang(m) - 21, 0)], "left"))
    qs = px.q[s][i21:fin_i]
    qs = qs[qs >= 0]
    f["echecs_21"] = float(qs.sum() / 21) / n0 if n0 and len(qs) else NAN
    f.update(spy_ctx)
    f["meteo"] = meteo_j if meteo_j is not None else NAN
    return f


# ---------- La base mensuelle ----------

def construire(px, carte, cies, inis, treize, meteo, fins, debut, fin):
    """Lignes (fin de mois, symbole, cik, valeur, indices, cible) des 1 000 plus grosses compagnies de chaque mois."""
    lignes, noms = [], None
    retenus = Counter()

    def spy_r(a, b):
        x, y = px.dernier("SPY", a, TOL_MOIS), px.dernier("SPY", b, TOL_MOIS)
        return px.rendement("SPY", x[0], y[0]) if x and y else NAN
    for k, m in enumerate(fins):
        if not (debut <= m <= fin) or k < 1:
            continue
        carte_m = carte.au(m // 100)
        candidats = []
        for s, cik in carte_m.items():
            if s not in px.d or cik not in cies:
                continue
            x = px.dernier(s, m, TOL_MOIS)
            if not x or x[1] < PRIX_MIN:
                continue
            n = cies[cik].nb_actions(m)
            if not n:
                continue
            candidats.append((x[1] * n / 1e6, s, cik))
        candidats.sort(reverse=True)
        univers = candidats[:UNIVERS]
        retenus[m] = len(univers)
        spy_ctx = {"spy_1m": spy_r(fins[k - 1], m), "spy_3m": spy_r(fins[k - 3], m) if k >= 3 else NAN}
        iwm = px.dernier("IWM", fins[k - 3], TOL_MOIS) if k >= 3 else None
        iwm2 = px.dernier("IWM", m, TOL_MOIS)
        spy_ctx["iwm_moins_spy_3m"] = (px.rendement("IWM", iwm[0], iwm2[0]) - spy_ctx["spy_3m"]) if iwm and iwm2 else NAN
        meteo_j = meteo.get(c.iso(m))
        suivant = fins[k + 1] if k + 1 < len(fins) else None
        for valeur_m, s, cik in univers:
            f = indices(px, s, cies[cik], inis.get(cik), treize.get(cik), fins, k, valeur_m * 1e6, spy_ctx, meteo_j)
            if noms is None:
                noms = list(f)
            cible = None
            if suivant is not None:
                x = px.dernier(s, m, TOL_MOIS)
                y = px.dernier(s, suivant, 10**6)  # une compagnie qui disparaît : sa dernière clôture
                sx, sy = px.dernier("SPY", m, TOL_MOIS), px.dernier("SPY", suivant, TOL_MOIS)
                if x and y and y[0] > x[0] and sx and sy:
                    cible = px.rendement(s, x[0], y[0]) - px.rendement("SPY", sx[0], sy[0])
            lignes.append({"m": m, "s": s, "cik": cik, "valeur_m": valeur_m, "x": [f[n] for n in noms], "cible": cible})
        if m % 10000 // 100 == 12:
            journal(f"  base : {m // 10000} fait ({len(lignes):,} lignes)")
    return lignes, noms, retenus


def rangs_mois(lignes, ids):
    par = defaultdict(list)
    for i in ids:
        par[lignes[i]["m"]].append(i)
    y = {}
    for l in par.values():
        l.sort(key=lambda i: lignes[i]["cible"])
        for r, i in enumerate(l):
            y[i] = (r + 0.5) / len(l)
    return y


def predire(lignes, fins):
    """Score de chaque ligne des mois de décision de chaque année jugée (modèle appris sur les mois dont la cible est
    connue avant le 1er juillet de l'année)."""
    scores, mesures = {}, {}
    suivant = {a: b for a, b in zip(fins, fins[1:])}
    for an in range(c.PREMIERE_ANNEE, c.DERNIERE_ANNEE + 1):
        juin = max(m for m in fins if m // 100 == an * 100 + 6)
        mai_suivant = max(m for m in fins if m // 100 == (an + 1) * 100 + 5)
        appris = [i for i, l in enumerate(lignes) if l["cible"] is not None and suivant.get(l["m"], 10**9) <= juin]
        testes = [i for i, l in enumerate(lignes) if juin <= l["m"] <= mai_suivant]
        nom = f"{an}-{an + 1}"
        y = rangs_mois(lignes, appris)
        X = np.array([lignes[i]["x"] for i in appris], dtype=float)
        pleines = ~np.all(np.isnan(X), axis=0)
        modele = HistGradientBoostingRegressor(**PARAMS).fit(X[:, pleines], np.array([y[i] for i in appris]))
        p = modele.predict(np.array([lignes[i]["x"] for i in testes], dtype=float)[:, pleines])
        for i, v in zip(testes, p):
            scores[i] = float(v)
        connus = [i for i in testes if lignes[i]["cible"] is not None]
        m = {"appris": len(appris), "testes": len(testes), "indices_vides": int((~pleines).sum())}
        if len(connus) > 100:
            sc = np.array([scores[i] for i in connus])
            ex = np.array([lignes[i]["cible"] for i in connus])
            m["correlation_rang"] = round(float(np.corrcoef(np.argsort(np.argsort(sc)), np.argsort(np.argsort(ex)))[0, 1]), 4)
            par_mois = defaultdict(list)
            for i in connus:
                par_mois[lignes[i]["m"]].append(i)
            top, tous = [], []
            for l in par_mois.values():
                l.sort(key=lambda i: -scores[i])
                top += [lignes[i]["cible"] for i in l[:POSITIONS]]
                tous += [lignes[i]["cible"] for i in l]
            m["ecart_moyen_10_meilleurs"] = round(float(np.mean(top)), 5)
            m["ecart_moyen_univers"] = round(float(np.mean(tous)), 5)
        mesures[nom] = m
        journal(f"  {nom} : {m}")
    return scores, mesures


# ---------- Le portefeuille ----------

def simuler(px, lignes, scores, fins, frais):
    """Chaque fin de mois de décision : les 10 meilleurs scores ; au 1er jour de bourse après (3 jours de plus au plus) :
    vendre ce qui n'y est plus, acheter ce qui entre (part égale), garder le reste ; l'argent qui attend dans SPY."""
    par_mois = defaultdict(list)
    for i, v in scores.items():
        par_mois[lignes[i]["m"]].append((v, lignes[i]["s"], lignes[i]["valeur_m"]))
    decisions = sorted(par_mois)
    jours = [j for j in px.cal if c.entier(c.DEBUT) <= j <= c.entier(c.FIN)]
    spy_px = {}
    dernier = None
    spy_d = dict((j, px.corrige("SPY", i)) for i, j in enumerate(px.d["SPY"]))
    for j in px.cal:
        dernier = spy_d.get(j, dernier)
        spy_px[j] = dernier
    tenus = {}  # symbole → [parts (prix corrigés), valeur en bourse M$]
    argent, spy_parts = c.CAPITAL, 0.0
    valeurs, journal_ordres = [], Counter()
    a_faire = {}
    for m in decisions:
        r = bisect_right(px.cal, m)
        if r < len(px.cal):
            a_faire[px.cal[r]] = m

    def prix_de(s, j):
        x = px.dernier(s, j, 10**6)
        return px.corrige(s, bisect_left(px.d[s], x[0])) if x else None

    for j in jours:
        if j in a_faire:
            m = a_faire[j]
            cible = [x for x in sorted(par_mois[m], reverse=True)[:POSITIONS]]
            voulus = {s: v for _, s, v in cible}
            for s in list(tenus):  # vendre ce qui sort (ou ce qui n'a plus de prix depuis 10 jours : sa dernière clôture)
                if s not in voulus:
                    x = px.premier(s, j, TOL_ENTREE) or px.dernier(s, j, 10**6)
                    p = px.corrige(s, bisect_left(px.d[s], x[0]))
                    montant = tenus[s][0] * p
                    argent += montant - c.cout(montant, tenus[s][1], frais)
                    del tenus[s]
                    journal_ordres["ventes"] += 1
            if spy_parts and spy_px[j]:  # tout l'argent qui attend revient pour les achats
                montant = spy_parts * spy_px[j]
                argent += montant - c.cout(montant, 1e9, frais)
                spy_parts = 0.0
            total = argent + sum(t[0] * (prix_de(s, j) or 0) for s, t in tenus.items())
            nouveaux = [s for s in voulus if s not in tenus]
            part = total / POSITIONS
            for s in nouveaux:
                x = px.premier(s, j, TOL_ENTREE)
                if not x or argent < 50:
                    journal_ordres["sans prix ou sans argent"] += 1
                    continue
                montant = min(part, argent)
                p = px.corrige(s, bisect_left(px.d[s], x[0]))
                tenus[s] = [(montant - c.cout(montant, voulus[s], frais)) / p, voulus[s]]
                argent -= montant
                journal_ordres["achats"] += 1
            if argent >= MIN_SPY and spy_px[j]:
                spy_parts = (argent - c.cout(argent, 1e9, frais)) / spy_px[j]
                argent = 0.0
        valeur = argent + spy_parts * (spy_px[j] or 0) + sum(t[0] * (prix_de(s, j) or 0) for s, t in tenus.items())
        valeurs.append((j, valeur))
    return valeurs, {j: spy_px[j] for j in jours}, dict(journal_ordres)


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--base", required=True)
    a.add_argument("--sortie", required=True)
    x = a.parse_args()
    journal("chargement")
    px = c.Prix(x.base)
    carte, cies = Carte(x.base), charger_compagnies(x.base)
    inis, treize = charger_inities(x.base), charger_treize(x.base)
    meteo = chasse_c.meteo(x.base)
    journal(f"prix : {len(px.d):,} symboles · compagnies avec faits : {len(cies):,} · initiés : {len(inis):,}")
    # Fractionnements (labo/chasse2/PLAN.md) : confirmés par les actions en circulation de la compagnie du symbole
    fins = px.fins_de_mois(px.cal[0], px.cal[-1])
    fract = []

    def confirmer(s, avant, jour, n):
        cik = carte.au(jour // 100).get(s)
        if cik is None or cik not in cies:
            return False
        av, ap = cies[cik].actions_autour(avant, jour)
        return bool(av and ap) and abs((ap / av) / n - 1) <= 0.20
    for s in list(px.d):
        if s in ("SPY", "IWM", "SSO"):
            fract += px.corriger(s, c.confirmer_fonds(px)) if s != "SPY" else px.corriger(s)
        else:
            fract += px.corriger(s, confirmer)
    journal(f"fractionnements confirmés : {len(fract):,}")
    lignes, noms, retenus = construire(px, carte, cies, inis, treize, meteo, fins, fins[1], c.entier(c.FIN))
    journal(f"base mensuelle : {len(lignes):,} lignes, {len(noms)} indices ; univers par mois : min {min(retenus.values())}, "
            f"max {max(retenus.values())}")
    scores, mesures = predire(lignes, fins)
    resultats = {"plan": "labo/chasse2/PLAN.md (chasse B)", "indices": noms, "lignes": len(lignes),
                 "univers_min_max": [min(retenus.values()), max(retenus.values())], "fractionnements": len(fract),
                 "exemples_fractionnements": fract[:40], "mesures": mesures, "prix_retires": px.retires}
    for nom, frais in c.FRAIS.items():
        valeurs, spy, ordres = simuler(px, lignes, scores, fins, frais)
        j = c.juger(valeurs, spy)
        resultats[nom] = {**j, "ordres": ordres}
        journal(f"chasse B, frais {nom} : {json.dumps({k: j[k] for k in ('total', 'examen_2012_2017', 'annees_gagnees', 't_mensuel', 'reussi')}, ensure_ascii=False)}")
    Path(x.sortie).mkdir(parents=True, exist_ok=True)
    (Path(x.sortie) / "resultats.json").write_text(json.dumps(resultats, ensure_ascii=False, indent=1) + "\n",
                                                   encoding="utf-8")


if __name__ == "__main__":
    main()
