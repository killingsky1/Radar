"""Tournoi Radar : le banc d'essai, LE MÊME pour toutes les règles.

Une règle = un fichier Python (labo/tournoi/regles/<id>.py) qui définit :
    ID = "vitesse-1"
    def garder(e, ctx) -> bool          # garder cet événement ? (e : une ligne d'evenements.jsonl.gz)
    # facultatif :
    JOURS_ENTREE = 1                    # acheter à la clôture du N-ième jour de bourse APRÈS le dépôt (1 au plus tôt)
    DUREE = 21                          # jours de bourse de détention (sortie à la clôture du jour prévu)
    MAX_POSITIONS = 10                  # positions en même temps (montant = valeur du portefeuille ÷ ce nombre)
    ARGENT_QUI_ATTEND = "SPY"           # "SPY" (l'argent pas investi suit le S&P 500) ou "rien"
    def sortir_avant(pos, jour, ctx) -> bool   # vendre plus tôt (ex. seuil de perte), vu à la clôture du `jour`
    def investir(jour, ctx) -> bool     # « météo » : acheter de nouvelles positions ce jour-là ? (sinon S&P 500)
    def poids(e, ctx) -> float          # part relative d'une position (1 = normale), 0.25 à 4
    def priorite(e, ctx) -> float       # trop de signaux le même jour : le plus haut d'abord (sinon : dépôt, numéro)
    TOLERANCE_ENTREE = 3                # pas de prix le jour prévu : réessayer jusqu'à N jours de bourse (0 = abandon)
    UNE_ENTREE_PAR_SYMBOLE_JOURS = 0    # après un achat, aucun nouvel achat du même symbole pendant N jours civils

`ctx` ne montre QUE ce qui était connu au moment de la décision : toute demande d'une donnée plus récente lève une
erreur (garde-fou contre le futur). `ctx.evenements_marche(depuis)` donne tous les formulaires 4 (toutes compagnies)
déposés depuis une date jusqu'au jour de la décision : pour une « météo » des initiés, sans garder de mémoire.
garder() est appelé dans l'ordre des dépôts, au fil des jours (un dépôt n'est lu que le jour de bourse qui suit) : même
une règle qui se souviendrait des dépôts déjà vus ne pourrait pas voir le futur.
Les données peuvent contenir des dépôts d'avant le début de la période (contexte, 1 an) : jamais achetés ; le début et
la fin de la période sont dans periode.json.
Le banc fait tout le reste, pareil pour tous :
- Achat : clôture de la SEC du N-ième jour de bourse après le dépôt ; pas de prix ce jour-là : jusqu'à 3 jours de bourse
  plus tard, sinon pas acheté (l'argent attend).
- Vente : clôture du jour prévu ; pas de prix : 1re clôture suivante (jusqu'à 10 jours de bourse), sinon la dernière
  connue. Changement de CUSIP (regroupement d'actions) : rendement enchaîné de part et d'autre du changement.
- Frais : 10 $ par transaction + demi-écart achat-vente selon la valeur en bourse (moins de 300 M$ ou inconnue : 1 % ;
  300 M$ à 2 G$ : 0,5 % ; 2 à 10 G$ : 0,2 % ; 10 G$ et plus : 0,05 %), à l'achat ET à la vente. Argent qui attend dans
  SPY : 10 $ de plus par achat (vendre du SPY) et par vente (racheter du SPY), sans écart (SPY est très liquide).
- Comparaison : 10 000 $ dans le S&P 500 (SPY) gardés tout le long, mêmes dates ; et chaque transaction contre SPY aux
  mêmes dates.
- Années de juillet à juin. Une année « pas encore mesurable » si plus de 5 % de ses transactions attendent des prix.

Usage : python labo/tournoi/banc.py <fichier de règle> [--donnees labo/tournoi/donnees] [--sortie rapport.json]
"""
import argparse
import gzip
import importlib.util
import json
import math
import sys
from bisect import bisect_left, bisect_right
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

CAPITAL = 10_000.0
FRAIS = 10.0
TOLERANCE_ENTREE = 3   # jours de bourse
TOLERANCE_SORTIE = 10  # jours de bourse
EN_ATTENTE_MAX = 0.05


def demi_ecart(valeur_m):
    if valeur_m is None or valeur_m < 300:
        return 0.01
    if valeur_m < 2000:
        return 0.005
    if valeur_m < 10000:
        return 0.002
    return 0.0005


class Futur(Exception):
    """Une règle a demandé une donnée qui n'était pas encore connue."""


class Donnees:
    def __init__(self, dossier):
        d = Path(dossier)
        with gzip.open(d / "evenements.jsonl.gz", "rt", encoding="utf-8") as f:
            self.evenements = [json.loads(l) for l in f]
        self.prix = {}
        with gzip.open(d / "prix.jsonl.gz", "rt", encoding="utf-8") as f:
            for l in f:
                x = json.loads(l)
                self.prix[x["s"]] = ([_iso(v) for v in x["d"]], x["p"], x["c"], x["q"])
        self.finances = {}
        if (d / "finances.jsonl.gz").exists():
            with gzip.open(d / "finances.jsonl.gz", "rt", encoding="utf-8") as f:
                for l in f:
                    x = json.loads(l)
                    self.finances[x["cik"]] = x["faits"]
        self.treize = {}
        if (d / "13d13g.jsonl.gz").exists():
            with gzip.open(d / "13d13g.jsonl.gz", "rt", encoding="utf-8") as f:
                for l in f:
                    x = json.loads(l)
                    self.treize[x["cik"]] = sorted(tuple(v) for v in x["depots"])
        self.calendrier = json.loads((d / "calendrier.json").read_text(encoding="utf-8"))
        self.evenements.sort(key=lambda e: (e["depot"], e["id"]))
        self.depots = [e["depot"] for e in self.evenements]
        f = d / "periode.json"
        self.periode = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
        self.par_cie = defaultdict(list)
        for e in self.evenements:
            self.par_cie[e["cik"]].append(e)
        for v in self.par_cie.values():
            v.sort(key=lambda e: (e["depot"], e["id"]))


def _iso(x):
    x = str(x)
    return f"{x[:4]}-{x[4:6]}-{x[6:]}"


class Contexte:
    """Ce qu'une règle peut voir, jusqu'au jour `jusqu_a` compris (clôtures connues le soir de ce jour)."""

    def __init__(self, donnees, jusqu_a):
        self._d, self.jour = donnees, jusqu_a

    def _verifier(self, jour):
        if jour > self.jour:
            raise Futur(f"donnée du {jour} demandée le {self.jour}")

    def clotures(self, symbole, depuis, jusqu_a=None):
        """[(date, prix, cusip)] du symbole entre deux dates (comprises)."""
        jusqu_a = jusqu_a or self.jour
        self._verifier(jusqu_a)
        p = self._d.prix.get(symbole)
        if not p:
            return []
        i, j = bisect_left(p[0], depuis), bisect_right(p[0], jusqu_a)
        return [(p[0][k], p[1][k], p[2][k]) for k in range(i, j)]

    def cloture(self, symbole, jour=None, tolerance_jours=10):
        """La dernière clôture au plus tard `jour` (par défaut : aujourd'hui pour la règle)."""
        jour = jour or self.jour
        self._verifier(jour)
        p = self._d.prix.get(symbole)
        if not p:
            return None
        i = bisect_right(p[0], jour) - 1
        if i < 0 or (date.fromisoformat(jour) - date.fromisoformat(p[0][i])).days > tolerance_jours:
            return None
        return (p[0][i], p[1][i], p[2][i])

    def echecs(self, symbole, depuis):
        """[(date, quantité d'échecs de livraison)] depuis une date."""
        self._verifier(self.jour)
        p = self._d.prix.get(symbole)
        if not p:
            return []
        i, j = bisect_left(p[0], depuis), bisect_right(p[0], self.jour)
        return [(p[0][k], p[3][k]) for k in range(i, j)]

    def finances(self, cik):
        """{concept: [début, fin, valeur]} des exercices annuels UTILISABLES aujourd'hui (le plus récent en dernier)."""
        sortie = {}
        for concept, faits in (self._d.finances.get(cik) or {}).items():
            ok = sorted((f for f in faits if f[4] <= self.jour), key=lambda f: f[1])
            if ok:
                sortie[concept] = [[f[0], f[1], f[2]] for f in ok]
        return sortie

    def depots_13(self, cik, depuis):
        """[(date, forme)] des 13D/13G sur la compagnie depuis une date, jusqu'à aujourd'hui."""
        return [x for x in self._d.treize.get(cik, []) if depuis <= x[0] <= self.jour]

    def evenements_avant(self, cik, depuis):
        """Les formulaires 4 (achats et ventes) sur la compagnie DÉPOSÉS de `depuis` à aujourd'hui."""
        return [e for e in self._d.par_cie.get(cik, []) if depuis <= e["depot"] <= self.jour]

    def evenements_marche(self, depuis):
        """Tous les formulaires 4 (achats et ventes, toutes compagnies) DÉPOSÉS de `depuis` à aujourd'hui."""
        d = self._d
        return d.evenements[bisect_left(d.depots, depuis):bisect_right(d.depots, self.jour)]

    def jours_de_bourse(self, depuis):
        i, j = bisect_left(self._d.calendrier, depuis), bisect_right(self._d.calendrier, self.jour)
        return self._d.calendrier[i:j]


def charger_regle(chemin):
    spec = importlib.util.spec_from_file_location("regle", chemin)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def jour_de_bourse(cal, jour, decalage):
    """Le jour de bourse `decalage` jours après `jour` (1 = le 1er jour de bourse strictement après)."""
    i = bisect_right(cal, jour) + decalage - 1
    return cal[i] if 0 <= i < len(cal) else None


def annee_de(jour):
    a = int(jour[:4])
    return f"{a}-{a + 1}" if int(jour[5:7]) >= 7 else f"{a - 1}-{a}"


def prix_au(d, s, jour):
    """(date, prix, cusip) de la clôture du `jour` exactement, sinon None."""
    p = d.prix.get(s)
    if not p:
        return None
    i = bisect_left(p[0], jour)
    return (p[0][i], p[1][i], p[2][i]) if i < len(p[0]) and p[0][i] == jour else None


def rendement_enchaine(d, s, entree, sortie):
    """Rendement de la clôture d'entrée à celle de sortie ; un changement de CUSIP entre les deux : enchaîné de part
    et d'autre (prix d'avant le changement, puis prix d'après)."""
    p = d.prix[s]
    i, j = bisect_left(p[0], entree[0]), bisect_left(p[0], sortie[0])
    r, base = 1.0, p[1][i]
    for k in range(i + 1, j + 1):
        if p[2][k] != p[2][k - 1]:
            r *= p[1][k - 1] / base
            base = p[1][k]
    return r * p[1][j] / base - 1


def simuler(regle, d, debut=None, fin_prix=None):
    """Le portefeuille, jour de bourse par jour de bourse. Chaque décision n'utilise que ce qui était connu AVANT la
    clôture où l'on achète ou vend : garder() voit le soir du dépôt ; investir() et sortir_avant() voient la veille."""
    cal = d.calendrier
    fin_prix = fin_prix or cal[-1]
    jours_entree = getattr(regle, "JOURS_ENTREE", 1)
    duree = getattr(regle, "DUREE", 21)
    max_pos = getattr(regle, "MAX_POSITIONS", 10)
    attend = getattr(regle, "ARGENT_QUI_ATTEND", "SPY")
    tol_entree = getattr(regle, "TOLERANCE_ENTREE", TOLERANCE_ENTREE)
    pause = getattr(regle, "UNE_ENTREE_PAR_SYMBOLE_JOURS", 0)
    frais_spy = FRAIS if attend == "SPY" else 0.0
    dernier_achat = {}
    if jours_entree < 1:
        raise ValueError("JOURS_ENTREE doit être au moins 1 : l'heure du dépôt est inconnue")
    # 1. Les signaux : chaque événement gardé, le soir de son dépôt ; achat prévu le N-ième jour de bourse après.
    #    Lus au fil des jours : au début d'un jour de bourse, seulement les dépôts faits AVANT ce jour.
    signaux = defaultdict(list)
    a_lire = [e for e in d.evenements if e.get("symbole")]
    lus = 0

    def lire_signaux(avant_le):
        nonlocal lus
        while lus < len(a_lire) and a_lire[lus]["depot"] < avant_le:
            e = a_lire[lus]
            lus += 1
            # garder() voit aussi les dépôts du contexte (avant le début), mais ils ne sont jamais achetés
            if regle.garder(e, Contexte(d, e["depot"])) and e["depot"] >= debut:
                jour = jour_de_bourse(cal, e["depot"], jours_entree)
                if jour:
                    signaux[jour].append(e)
    spy = d.prix["SPY"]

    def spy_au(jour):
        return spy[1][bisect_right(spy[0], jour) - 1]

    debut = debut or d.periode.get("debut") or min(e["depot"] for e in d.evenements)
    jours = [j for j in cal if debut <= j <= fin_prix]
    argent, parts_spy, positions, attente, transactions, valeur_jour = CAPITAL, 0.0, [], [], [], []
    veille = None
    for jour in jours:
        lire_signaux(jour)
        ctx_veille = Contexte(d, veille) if veille else None
        # a) ventes : prévues, ou plus tôt selon la règle (décidé la veille) ; seulement s'il y a un prix CE jour-là,
        #    sinon on réessaie le lendemain ; 10 jours de bourse sans prix après la date prévue : dernière clôture connue
        garder = []
        for pos in positions:
            prevue = jour >= pos["sortie_prevue"]
            plus_tot = (not prevue and ctx_veille is not None and hasattr(regle, "sortir_avant")
                        and jour > pos["entree"][0] and regle.sortir_avant(pos, veille, ctx_veille))
            px = prix_au(d, pos["s"], jour) if (prevue or plus_tot) else None
            if px is None and prevue and jour >= pos["sortie_limite"]:
                px = _dernier(d, pos["s"], jour)
            if px is None:
                garder.append(pos)
                continue
            r = rendement_enchaine(d, pos["s"], pos["entree"], px)
            net = pos["montant"] * (1 + r) * (1 - pos["demi_ecart"]) - FRAIS - frais_spy
            argent += net
            m = spy_au(px[0]) / spy_au(pos["entree"][0]) - 1
            transactions.append({"id": pos["id"], "s": pos["s"], "achat": pos["entree"][0], "vente": px[0],
                                 "jour_vente": jour, "rendement": round(r, 4), "marche": round(m, 4),
                                 "ecart": round(r - m, 4), "net": round(net / pos["cout"] - 1, 4),
                                 "plus_tot": bool(plus_tot), "annee": annee_de(pos["entree"][0])})
        positions = garder
        # b) achats : les signaux du jour et ceux en attente d'un prix (3 jours de bourse au plus)
        if parts_spy:
            argent += parts_spy * spy_au(jour)
            parts_spy = 0.0
        meteo = not hasattr(regle, "investir") or (ctx_veille is not None and regle.investir(veille, ctx_veille))
        attente = [(e, n + 1) for e, n in attente if n + 1 <= tol_entree] + [(e, 0) for e in signaux.get(jour, [])]
        valeur = argent + sum(p["montant"] * (1 + rendement_enchaine(d, p["s"], p["entree"], x))
                              for p in positions if (x := _dernier(d, p["s"], jour)))
        reste = []
        if hasattr(regle, "priorite"):
            ordre = sorted(attente, key=lambda x: (-regle.priorite(x[0], Contexte(d, x[0]["depot"])), x[0]["depot"], x[0]["id"]))
        else:
            ordre = sorted(attente, key=lambda x: (x[0]["depot"], x[0]["id"]))
        for e, n in ordre:
            px = prix_au(d, e["symbole"], jour)
            if px is None:
                reste.append((e, n))
                continue
            if not meteo or len(positions) >= max_pos or any(p["s"] == e["symbole"] for p in positions):
                continue
            if pause and e["symbole"] in dernier_achat and \
                    (date.fromisoformat(jour) - date.fromisoformat(dernier_achat[e["symbole"]])).days < pause:
                continue
            w = min(max(regle.poids(e, Contexte(d, e["depot"])), 0.25), 4.0) if hasattr(regle, "poids") else 1.0
            montant = min(argent - frais_spy, valeur / max_pos * w) - FRAIS
            if montant < 50:
                continue
            ecart = demi_ecart(e.get("valeur_m"))
            argent -= montant + FRAIS + frais_spy
            dernier_achat[e["symbole"]] = jour
            sortie_prevue = jour_de_bourse(cal, jour, duree) or "9999-12-31"
            positions.append({"id": e["id"], "s": e["symbole"], "cik": e["cik"], "entree": px,
                              "montant": montant * (1 - ecart), "cout": montant + FRAIS + frais_spy, "demi_ecart": ecart,
                              "sortie_prevue": sortie_prevue,
                              "sortie_limite": jour_de_bourse(cal, sortie_prevue, TOLERANCE_SORTIE) or "9999-12-31"})
        attente = reste
        if attend == "SPY" and argent > 0:
            parts_spy, argent = argent / spy_au(jour), 0.0
        valeur_jour.append((jour, argent + parts_spy * spy_au(jour) + sum(
            p["montant"] * (1 + rendement_enchaine(d, p["s"], p["entree"], x))
            for p in positions if (x := _dernier(d, p["s"], jour)))))
        veille = jour
    return transactions, valeur_jour, positions


def _dernier(d, s, jour):
    """La dernière clôture connue au plus tard le `jour` (pour la valeur du portefeuille)."""
    p = d.prix.get(s)
    if not p:
        return None
    k = bisect_right(p[0], jour) - 1
    return (p[0][k], p[1][k], p[2][k]) if k >= 0 else None


def statistiques(transactions, valeur_jour, d, positions_ouvertes):
    spy = d.prix["SPY"]

    def spy_au(jour):
        i = bisect_right(spy[0], jour) - 1
        return spy[1][i]

    par_annee = defaultdict(list)
    for t in transactions:
        par_annee[t["annee"]].append(t)
    attente = defaultdict(int)
    for p in positions_ouvertes:
        attente[annee_de(p["entree"][0])] += 1
    annees = {}
    for an in sorted(set(par_annee) | set(attente)):
        ts = par_annee.get(an, [])
        a, b = f"{an[:4]}-07-01", f"{an[5:]}-06-30"
        v = [x for x in valeur_jour if a <= x[0] <= b]
        e = [t["ecart"] for t in ts]
        n = len(e)
        moy = sum(e) / n if n else None
        sd = math.sqrt(sum((x - moy) ** 2 for x in e) / (n - 1)) if n > 2 else None
        annees[an] = {
            "transactions": n, "en_attente": attente.get(an, 0), "achats": n + attente.get(an, 0),
            "mesurable": n > 0 and attente.get(an, 0) <= EN_ATTENTE_MAX * (n + attente.get(an, 0)),
            "ecart_moyen": round(moy, 4) if n else None,
            "ecart_median": round(sorted(e)[n // 2] if n % 2 else (sorted(e)[n // 2 - 1] + sorted(e)[n // 2]) / 2, 4) if n else None,
            "bat_le_marche": round(sum(x > 0 for x in e) / n, 4) if n else None,
            "t": round(moy / (sd / math.sqrt(n)), 2) if sd else None,
            "portefeuille": round(v[-1][1] / v[0][1] - 1, 4) if len(v) > 1 else None,
            "spy_garde": round(spy_au(v[-1][0]) / spy_au(v[0][0]) - 1, 4) if len(v) > 1 else None}
    total = {"portefeuille": round(valeur_jour[-1][1] / CAPITAL - 1, 4) if valeur_jour else None,
             "spy_garde": round(spy_au(valeur_jour[-1][0]) / spy_au(valeur_jour[0][0]) - 1, 4) if valeur_jour else None,
             "pire_baisse": None, "mois": 0, "ecart_mensuel_moyen": None, "t_mensuel": None}
    # Écart mensuel du portefeuille contre SPY (fin de mois à fin de mois) : moyenne et t de Student
    fins = {}
    for j, v in valeur_jour:
        fins[j[:7]] = (j, v)
    mois = sorted(fins)
    ecarts = [(fins[b][1] / fins[a][1] - 1) - (spy_au(fins[b][0]) / spy_au(fins[a][0]) - 1) for a, b in zip(mois, mois[1:])]
    if len(ecarts) > 2:
        moy = sum(ecarts) / len(ecarts)
        sd = math.sqrt(sum((x - moy) ** 2 for x in ecarts) / (len(ecarts) - 1))
        total.update({"mois": len(ecarts), "ecart_mensuel_moyen": round(moy, 5),
                      "t_mensuel": round(moy / (sd / math.sqrt(len(ecarts))), 2) if sd else None})
    if valeur_jour:
        haut, pire = 0.0, 0.0
        for _, x in valeur_jour:
            haut = max(haut, x)
            pire = min(pire, x / haut - 1)
        total["pire_baisse"] = round(pire, 4)
    return {"annees": annees, "total": total}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("regle")
    a.add_argument("--donnees", default="labo/tournoi/donnees")
    a.add_argument("--sortie")
    a.add_argument("--debut", help="1er jour du portefeuille (par défaut : le début de periode.json)")
    x = a.parse_args()
    regle = charger_regle(x.regle)
    d = Donnees(x.donnees)
    transactions, valeur_jour, ouvertes = simuler(regle, d, debut=x.debut)
    r = {"regle": regle.ID, **statistiques(transactions, valeur_jour, d, ouvertes),
         "transactions": len(transactions)}
    texte = json.dumps(r, ensure_ascii=False, indent=1)
    if x.sortie:
        Path(x.sortie).write_text(texte + "\n", encoding="utf-8")
        Path(x.sortie).with_suffix(".transactions.json").write_text(json.dumps(transactions, ensure_ascii=False),
                                                                     encoding="utf-8")
    print(texte)


if __name__ == "__main__":
    main()
