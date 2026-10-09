"""Chasse 2 : ce qui est commun aux chasses (base, prix, frais, jugement), selon labo/chasse2/PLAN.md."""
from __future__ import annotations

import gzip
import json
import math
import sys
from bisect import bisect_left, bisect_right
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "tournoi"))
import banc  # noqa: E402  le banc du tournoi : frais (demi_ecart, FRAIS)

PREMIERE_ANNEE, DERNIERE_ANNEE = 2012, 2025  # années jugées : juillet T à juin T+1, 2012-2013 à 2025-2026
EXAMEN = (2012, 2016)  # 2012-2013 à 2016-2017 : jamais vues
DEBUT, FIN = f"{PREMIERE_ANNEE}-07-01", f"{DERNIERE_ANNEE + 1}-06-30"
FRAIS = {"10 $": banc.FRAIS, "0 $": 0.0}
CAPITAL = 10_000.0
T_MIN = 2.4


def iso(x):
    x = str(x)
    return f"{x[:4]}-{x[4:6]}-{x[6:8]}"


def entier(j):
    return int(j.replace("-", ""))


def annee(j):
    """« 2012-2013 » pour un jour de juillet 2012 à juin 2013 (AAAA-MM-JJ ou AAAAMMJJ)."""
    return banc.annee_de(iso(j) if isinstance(j, int) else j)


def lire_jsonl(chemin):
    with gzip.open(chemin, "rt", encoding="utf-8") as f:
        for ligne in f:
            yield json.loads(ligne)


class Prix:
    """Clôtures de la SEC par symbole (base de la chasse 2) ; dates en entiers AAAAMMJJ, tableaux numpy (mémoire)."""

    def __init__(self, base, symboles=None):
        base = Path(base)
        self.cal = [int(x) for x in json.loads((base / "calendrier.json").read_text())]
        self.cal_np = np.array(self.cal, dtype=np.int64)
        self.pos = {j: i for i, j in enumerate(self.cal)}
        self.d, self.p, self.q, self.c, self.f, self.aj = {}, {}, {}, {}, {}, {}
        for x in lire_jsonl(base / "prix.jsonl.gz"):
            if symboles is not None and x["s"] not in symboles:
                continue
            s = x["s"]
            self.d[s] = np.array(x["d"], dtype=np.int64)
            self.p[s] = np.array(x["p"], dtype=np.float64)
            self.q[s] = np.array(x["q"], dtype=np.int64)
            self.c[s] = [sys.intern(v) for v in x["c"]]

    def rang(self, j):
        """Position du dernier jour de bourse ≤ j dans le calendrier."""
        return int(np.searchsorted(self.cal_np, j, "right")) - 1

    def indice(self, s, j):
        """Indice de la clôture du jour j (une clôture de s)."""
        return int(np.searchsorted(self.d[s], j, "left"))

    def dernier(self, s, j, tol):
        """Dernière clôture au plus tard le jour j, à tol jours de bourse au plus : (jour, prix, cusip) ou None."""
        d = self.d.get(s)
        if d is None or not len(d):
            return None
        i = int(np.searchsorted(d, j, "right")) - 1
        if i < 0 or self.rang(j) - self.rang(int(d[i])) > tol:
            return None
        return int(d[i]), float(self.p[s][i]), self.c[s][i]

    def premier(self, s, j, tol):
        """Première clôture au plus tôt le jour j, à tol jours de bourse au plus."""
        d = self.d.get(s)
        if d is None or not len(d):
            return None
        i = int(np.searchsorted(d, j, "left"))
        if i >= len(d) or self.rang(int(d[i])) - self.rang(j) > tol:
            return None
        return int(d[i]), float(self.p[s][i]), self.c[s][i]

    def corriger(self, s, confirmer=None):
        """Facteurs cumulés de s (prix corrigé = prix × facteur). Changement de code du titre : rendement nul ce jour-là
        (comme le banc du tournoi). Même code, rapport de prix à 5 % près de 1/N ou de N (N entier de 2 à 50) :
        fractionnement (ou regroupement) si confirmer(s, jour d'avant, jour, n) le confirme, n = facteur des actions
        (N ou 1/N) ; le rendement est alors corrigé (labo/chasse2/PLAN.md). Renvoie les fractionnements retenus."""
        d, p, cu = self.d[s], self.p[s], self.c[s]
        m = np.ones(len(d))
        trouves = []
        if len(d) > 1:
            r = p[1:] / p[:-1]
            change = np.array([cu[a] != cu[a - 1] for a in range(1, len(d))], dtype=bool)
            m[1:][change] = (p[:-1] / p[1:])[change]
            if confirmer is not None:
                for a in np.nonzero(~change & ((r < 0.53) | (r > 1.9)))[0] + 1:
                    n = facteur(float(r[a - 1]))
                    if n and confirmer(s, int(d[a - 1]), int(d[a]), n):
                        m[a] = n
                        trouves.append([s, int(d[a]), round(n, 4)])
        self.f[s] = np.cumprod(m)
        self.aj[s] = p * self.f[s]
        return trouves

    def ajustes(self, s):
        """Les prix corrigés de s (tableau numpy)."""
        if s not in self.aj:
            self.corriger(s)
        return self.aj[s]

    def corrige(self, s, i):
        """Le prix corrigé de s à l'indice i."""
        return float(self.ajustes(s)[i])

    def rendement(self, s, a, b):
        """Rendement de la clôture du jour a à celle du jour b (deux clôtures de s), prix corrigés (codes du titre
        enchaînés, fractionnements confirmés)."""
        aj = self.ajustes(s)
        return float(aj[self.indice(s, b)] / aj[self.indice(s, a)]) - 1

    def fins_de_mois(self, debut, fin):
        """Le dernier jour de bourse de chaque mois, de debut à fin (entiers)."""
        sortie = {}
        for j in self.cal:
            if debut <= j <= fin:
                sortie[j // 100] = j
        return [sortie[m] for m in sorted(sortie)]


def facteur(r):
    """Rapport de prix r à 5 % près de 1/N (fractionnement : n = N) ou de N (regroupement : n = 1/N), N de 2 à 50 ;
    sinon None."""
    if r <= 0:
        return None
    if r < 1:
        n = round(1 / r)
        return float(n) if 2 <= n <= 50 and abs(r * n - 1) <= 0.05 else None
    n = round(r)
    return 1 / n if 2 <= n <= 50 and abs(r / n - 1) <= 0.05 else None


def confirmer_fonds(px):
    """Pour un fonds coté (pas d'actions en circulation déposées) : confirmé si SPY a bougé de moins de 5 % entre les
    deux clôtures."""
    def confirmer(s, avant, jour, n):
        a, b = px.dernier("SPY", avant, 5), px.dernier("SPY", jour, 5)
        return bool(a and b) and abs(b[1] / a[1] - 1) < 0.05
    return confirmer


def cout(montant, valeur_m, frais):
    """Frais d'une transaction : commission + demi-écart achat-vente du banc du tournoi selon la valeur en bourse (M$)."""
    return frais + montant * banc.demi_ecart(valeur_m)


def juger(valeurs, spy, paris_par_annee=None):
    """valeurs : [(jour, valeur du portefeuille)] chaque jour de bourse ; spy : {jour : clôture de SPY}.
    Écarts MENSUELS contre SPY (fin de mois à fin de mois), années de juillet à juin, total, examen 2012-2017, et le
    critère du plan. paris_par_annee (chasse C) : {année : True si un pari a été fait} ; sans : toutes les années."""
    jours = [j for j, _ in valeurs]
    val = dict(valeurs)

    def spy_au(j):
        k = max(x for x in spy if x <= j) if j not in spy else j
        return spy[k]

    fins = {}
    for j in jours:
        fins[j // 100] = j
    points = [jours[0]] + [fins[m] for m in sorted(fins)]
    if len(points) > 1 and points[1] == points[0]:
        points.pop(0)
    ecarts = [(val[b] / val[a] - 1) - (spy_au(b) / spy_au(a) - 1) for a, b in zip(points, points[1:])]
    n = len(ecarts)
    moy = sum(ecarts) / n if n else 0.0
    sd = math.sqrt(sum((e - moy) ** 2 for e in ecarts) / (n - 1)) if n > 2 else 0.0
    t = moy / (sd / math.sqrt(n)) if sd > 0 else 0.0

    def periode(a, b):
        dans = [j for j in jours if a <= j <= b]
        if len(dans) < 2:
            return None
        avant = [j for j in jours if j < a]
        j0 = avant[-1] if avant else dans[0]
        return {"portefeuille": round(val[dans[-1]] / val[j0] - 1, 4),
                "spy": round(spy_au(dans[-1]) / spy_au(j0) - 1, 4)}

    par_annee = {}
    for an in range(PREMIERE_ANNEE, DERNIERE_ANNEE + 1):
        x = periode(an * 10000 + 701, (an + 1) * 10000 + 630)
        if x:
            par_annee[f"{an}-{an + 1}"] = x
    total = periode(jours[0], jours[-1])
    examen = periode(EXAMEN[0] * 10000 + 701, (EXAMEN[1] + 1) * 10000 + 630)
    gagnees = [a for a, x in par_annee.items() if x["portefeuille"] > x["spy"]]
    if paris_par_annee is None:
        annees_ok = len(gagnees) >= 9
        detail_annees = f"{len(gagnees)} sur {len(par_annee)}"
    else:
        avec = [a for a in par_annee if paris_par_annee.get(a)]
        sans = [a for a in par_annee if not paris_par_annee.get(a)]
        g = [a for a in avec if a in gagnees]
        p_sans = math.prod(1 + par_annee[a]["portefeuille"] for a in sans)
        s_sans = math.prod(1 + par_annee[a]["spy"] for a in sans)
        annees_ok = bool(avec) and 3 * len(g) >= 2 * len(avec) and p_sans >= s_sans - 1e-9
        detail_annees = f"{len(g)} sur {len(avec)} années avec un pari ; autres années : {p_sans - 1:+.4f} contre SPY {s_sans - 1:+.4f}"
    criteres = {"bat_spy_au_total": total["portefeuille"] > total["spy"], "annees": annees_ok,
                "t_mensuel": t >= T_MIN, "examen_2012_2017": bool(examen) and examen["portefeuille"] > examen["spy"]}
    return {"total": total, "examen_2012_2017": examen, "annees_gagnees": detail_annees, "mois": n,
            "ecart_mensuel_moyen": round(moy, 5), "t_mensuel": round(t, 2), "criteres": criteres,
            "reussi": all(criteres.values()), "par_annee": par_annee}
