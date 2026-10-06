"""sante_valeur-3 : argent réel et bénéfices de qualité, flux de trésorerie élevé par rapport au prix + achat d'initié,
garde de 12 mois (règle pré-enregistrée, piste « sante_valeur »).

Texte (labo/tournoi/regles_preenregistrees.json), en bref :
- Filtre : formulaire 4 avec achat en bourse (code P) où (a) roles contient administrateur OU dirigeant ; (b) routinier
  = non ; (c) plan_10b5_1 = non (ou vide) ; (d) montant ≥ 50 000 $ ; (e) valeur_m ≥ 100 M$ ; (f) exercice t : flux de
  trésorerie d'exploitation_t ÷ (valeur_m × 1 000 000) ≥ 0,10 ; (g) flux d'exploitation_t ≥ bénéfice net_t ;
  (h) bénéfice net_t > 0 ; (i) passif ÷ actif total (période connue la plus récente) ≤ 0,70 ; (j) capitaux propres > 0 ;
  (k) compagnie pas déjà en portefeuille.
- Paramètres : exercice t = dernier exercice annuel dont la fin date d'au moins 120 jours avant le dépôt. Passif, actif
  et capitaux propres : période connue la plus récente (trimestre avec fin ≥ 60 jours avant le dépôt, ou exercice
  annuel).
- Entrée : clôture du 1er jour de bourse après le dépôt ; sans prix SEC, 1re clôture SEC dans les 5 jours de bourse
  suivants, sinon abandon. Au plus 1 nouvel achat par mois civil : le premier événement admissible du mois (à égalité,
  le plus gros montant).
- Sortie : 12 mois après l'achat, à la 1re clôture SEC à cette date ou après ; aucune dans les 10 jours de bourse :
  dernière clôture SEC connue ; titre disparu : dernier prix SEC connu.
- Taille : au plus 6 positions, chacune 1/6 de la valeur totale du portefeuille au moment de l'achat ; au plus 1 achat
  par mois ; argent qui attend dans SPY ; au départ, 100 % SPY.
"""
import calendar
import math
from datetime import date, timedelta

ID = "sante_valeur-3"
IMPOSSIBLE = None

CHOIX = [
    "DÉCISION DE LA COMPARAISON (testeur contre vérificateur) : ce programme suit le texte et n'est pas changé ; le "
    "vérificateur est corrigé sur quatre points : vente 12 mois civils après l'achat (« à cette date ou après », pas "
    "252 jours de bourse) ; (k) « pas déjà en portefeuille » fait partie du filtre (un tel événement ne prend pas la "
    "place du mois) ; la place du mois n'est prise que par un achat (un événement gardé que le banc n'achète pas la "
    "laisse au suivant) ; chiffre de 350 à 380 jours tiré d'un 10-Q exclu de l'exercice annuel.",
    "Événement = une ligne « achat » du jeu (code P, titres non dérivés) qui a un symbole (le banc n'achète que "
    "celles-là). Le champ « titres » n'est pas filtré : le texte ne le demande pas.",
    "(a) Rôles : l'événement est gardé si AU MOINS UN déclarant (e['inities']) a « administrateur » ou « dirigeant » "
    "dans roles.",
    "(b) routinier doit valoir false.",
    "(c) plan_10b5_1 : écarté seulement si true ; false et vide (null) acceptés (texte : « non (ou vide) »).",
    "(d) montant ≥ 50 000 $ et (e) valeur_m ≥ 100 M$ : bornes comprises ; champ absent = écarté.",
    "Données comptables = ctx.finances (le banc ne montre un chiffre qu'à partir de sa vraie date de dépôt) ET, en "
    "plus, les délais du texte : un exercice annuel (une durée de 350 à 380 jours, pas tirée d'un 10-Q : un 10-Q peut "
    "donner 12 mois glissants, ce n'est pas un exercice) compte si sa fin date d'au moins 120 jours avant le dépôt ; "
    "un bilan (chiffre à une date) compte si cette date est au moins 60 jours avant le dépôt (bilan d'un 10-Q ou "
    "10-Q/A) ou au moins 120 jours avant (bilan d'un 10-K ou d'une autre forme).",
    "Exercice t = l'exercice annuel connu dont la fin est la plus récente (tous les concepts ensemble). Flux "
    "d'exploitation = NetCashProvidedByUsedInOperatingActivities ; bénéfice net = NetIncomeLoss, tous deux de "
    "l'exercice t ; un des deux absent pour t = écarté (rien n'est recalculé). Deux chiffres annuels d'un concept avec "
    "la même fin : celui dont le début est le plus récent.",
    "(f) flux_t ÷ (valeur_m × 1 000 000) ≥ 0,10 ; (g) flux_t ≥ bénéfice net_t ; (h) bénéfice net_t > 0 (bornes comme "
    "écrites).",
    "« Période connue la plus récente » pour le bilan : (i) passif (Liabilities) ÷ actif (Assets) pris au dernier bilan "
    "connu qui a LES DEUX chiffres à la même date, ≤ 0,70 (borne comprise) ; (j) capitaux propres (StockholdersEquity) "
    "= le dernier bilan connu de ce concept, > 0. Un concept absent = écarté (le passif n'est pas recalculé à partir "
    "de l'actif et des capitaux propres).",
    "(k) Compagnie déjà en portefeuille : vérifié le soir du dépôt, par compagnie (cik), dans le portefeuille que la "
    "règle recalcule (voir plus bas). Le banc refuse aussi, le jour de l'achat, un symbole déjà détenu.",
    "Un achat par mois civil : le mois est celui du DÉPÔT (« le premier événement admissible du mois ») ; un dépôt du "
    "31 janvier acheté en février prend la place de janvier. La place n'est prise que par un vrai achat : un événement "
    "abandonné faute de prix, ou refusé par le banc (6 places prises, symbole déjà détenu), laisse la place à "
    "l'événement admissible suivant du mois.",
    "Le banc n'a pas de limite par mois : garder() la fait. Pour savoir si un de ses signaux a été acheté, la règle "
    "refait jour par jour les achats et ventes du banc pour ses propres signaux (mêmes règles : prix du jour exact, 5 "
    "jours de réessai, 6 places, symbole déjà détenu, ventes avant achats, ordre de priorite()), avec les seules "
    "données connues le soir du dépôt (un cache de calculs du passé, refait si une nouvelle simulation commence). "
    "Le montant minimal du banc (50 $) n'est pas refait : il ne peut pas manquer avec 1/6 du portefeuille.",
    "Limite du banc : il ne peut pas réserver la place du mois à un signal qui attend encore son prix. Donc, tant qu'un "
    "événement gardé du mois attend son prix (jusqu'à 6 jours de bourse), les autres événements du mois sont écartés, "
    "même si celui qui attend finit abandonné (le texte donnerait alors sa chance au suivant, s'il avait encore un "
    "prix dans ses propres 6 jours). Sinon, deux achats pourraient tomber le même mois.",
    "Même jour de dépôt : les événements admissibles du jour sont classés par montant (le plus gros d'abord, puis le "
    "numéro du dépôt) ; un seul est gardé.",
    "Début de la période : la règle ne peut pas lire periode.json. Elle le déduit du 1er dépôt du jeu (le jeu commence "
    "1 an avant le début, contexte) : 1er dépôt + 365 jours, ramené au 1er du mois. Les dépôts d'avant ne sont jamais "
    "achetés par le banc : garder() les écarte. Hypothèse : le banc est lancé sans --debut (comme juger.py).",
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (1er jour de bourse après le dépôt, puis les 5 jours de bourse "
    "suivants ; sinon abandon).",
    "Sortie : date cible = date d'achat + 12 mois civils (même jour du mois ; 29 février → 28 février). sortir_avant() "
    "dit de vendre dès que le prochain jour de semaine atteint cette date ; le banc vend à la 1re clôture SEC à cette "
    "date ou après. Le calendrier des jours de bourse futurs n'est pas visible : un congé juste avant la date cible peut "
    "retarder la vente d'un jour de bourse.",
    "Sortie sans prix SEC : le banc vend au plus tard au 262e jour de bourse après l'achat (DUREE = 262, "
    "TOLERANCE_SORTIE = 0) : à la clôture de ce jour s'il y en a une, sinon à la dernière clôture connue. Avec environ "
    "250 jours de bourse par an dans le calendrier des fichiers de la SEC, c'est environ 10 à 12 jours de bourse après "
    "la date des 12 mois (texte : 10 jours de bourse) ; jamais avant la date des 12 mois. Titre disparu : dernière "
    "clôture connue, comme le texte. Sur le FAUX jeu (calendrier sans congés, environ 261 jours de bourse par an), "
    "le 262e jour tombe sur la date des 12 mois ou le lendemain : sans prix ce jour-là, la vente se fait tout de "
    "suite à la dernière clôture connue.",
    "Plusieurs signaux qui attendent le même jour (ils viennent de mois différents) : priorite() = date de dépôt la plus "
    "ancienne d'abord, puis le plus gros montant.",
    "Taille : MAX_POSITIONS = 6 (1/6 de la valeur du portefeuille). Banc (diffère du texte) : la position vaut 1/6 de la "
    "valeur MOINS les 10 $ de frais ; frais de 10 $ par transaction (SPY compris) plus un demi-écart achat-vente selon "
    "la valeur en bourse, à l'achat et à la vente ; MONTANT_MIN = 50 (réglage par défaut, le texte n'en parle pas).",
    "Banc (le texte n'en parle pas) : changement de CUSIP pendant la détention = rendement enchaîné ; ventes du jour "
    "avant les achats du jour ; une position encore ouverte à la fin des prix reste ouverte. Argent qui attend dans SPY "
    "(ARGENT_QUI_ATTEND = « SPY », LIQUIDE_JOURS = 0), comme le texte.",
    "Pas de vente anticipée : sortir_avant() ne sert qu'à la vente des 12 mois.",
]

# Réglages du banc
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 262                 # filet : la vente normale (12 mois civils) est faite par sortir_avant()
TOLERANCE_SORTIE = 0
MAX_POSITIONS = 6
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

# Seuils du texte
ROLES_ADMIS = ("administrateur", "dirigeant")
MONTANT_MINIMUM = 50_000
VALEUR_M_MINIMUM = 100
FLUX_SUR_VALEUR_MINIMUM = 0.10
PASSIF_SUR_ACTIF_MAXIMUM = 0.70
UN_ACHAT_PAR_MOIS = True
DELAI_ANNUEL = 120          # jours civils entre la fin d'un exercice et le dépôt
DELAI_TRIMESTRE = 60        # jours civils entre la fin d'un trimestre et le dépôt
DUREE_EXERCICE = (350, 380)  # jours : une durée annuelle dans ctx.finances
ECART_T_MOINS_1 = (330, 400)  # jours entre la fin de t-1 et celle de t (pas utilisé : seulement t ici)


# ---------- Dates ----------

def _d(x):
    return date.fromisoformat(x)


def _plus_12_mois(jour):
    j = _d(jour)
    a, m = j.year + 1, j.month
    return date(a, m, min(j.day, calendar.monthrange(a, m)[1])).isoformat()


def _jour_de_semaine_suivant(jour):
    j = _d(jour) + timedelta(days=1)
    while j.weekday() >= 5:
        j += timedelta(days=1)
    return j.isoformat()


def _vendre_au_prochain_jour(achat, veille):
    """Vendre au jour de bourse qui suit `veille` ? Oui dès que ce jour atteint la date d'achat + 12 mois."""
    return _jour_de_semaine_suivant(veille) >= _plus_12_mois(achat)


# ---------- Fonctions du banc ----------

def sortir_avant(pos, jour, ctx):
    return _vendre_au_prochain_jour(pos["entree"][0], jour)


def priorite(e, ctx):
    """Date de dépôt la plus ancienne d'abord, puis le plus gros montant (le banc trie par -priorite)."""
    return -_d(e["depot"]).toordinal() + math.log10(1 + max(e.get("montant") or 0, 0)) / 16


def garder(e, ctx):
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    c = _cache(e, ctx)
    if e["id"] not in c["decision"]:
        if e["depot"] < c["debut"]:
            c["decision"][e["id"]] = False  # contexte (avant le début) : jamais acheté par le banc
        else:
            _avancer(ctx, c)
            _decider_le_jour(ctx, c, e["depot"])
    return c["decision"].get(e["id"], False)


# ---------- Le filtre (a) à (j) ----------

def _filtre(e, ctx):
    if not any(r in ROLES_ADMIS for i in (e.get("inities") or []) for r in (i.get("roles") or [])):
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    if e.get("montant") is None or e["montant"] < MONTANT_MINIMUM:
        return False
    v = e.get("valeur_m")
    if v is None or v < VALEUR_M_MINIMUM:
        return False
    annuels, bilans = _comptes(ctx, e["cik"], e["depot"])
    t, _ = _exercices(annuels)
    if t is None:
        return False
    fe = annuels.get("NetCashProvidedByUsedInOperatingActivities", {}).get(t)
    bn = annuels.get("NetIncomeLoss", {}).get(t)
    if fe is None or bn is None:
        return False
    if fe / (v * 1_000_000) < FLUX_SUR_VALEUR_MINIMUM or fe < bn or bn <= 0:
        return False
    pa = _passif_sur_actif(bilans)
    if pa is None or pa > PASSIF_SUR_ACTIF_MAXIMUM:
        return False
    cp = _dernier_bilan(bilans, "StockholdersEquity")
    return cp is not None and cp > 0


def _passif_sur_actif(bilans):
    """Passif ÷ actif au dernier bilan connu qui a les deux chiffres à la même date."""
    actif, passif = bilans.get("Assets") or {}, bilans.get("Liabilities") or {}
    dates = set(actif) & set(passif)
    if not dates:
        return None
    f = max(dates)
    return passif[f] / actif[f] if actif[f] else None


def _comptes(ctx, cik, depot):
    """Chiffres « connus » au dépôt selon le texte : {concept: {fin: valeur}} pour les exercices annuels (durée de 350 à
    380 jours, pas tirée d'un 10-Q ; fin ≥ 120 jours avant) et pour les bilans (10-Q : fin ≥ 60 jours avant ; 10-K ou
    autre : ≥ 120 jours)."""
    j = _d(depot)
    lim_an = (j - timedelta(days=DELAI_ANNUEL)).isoformat()
    lim_tr = (j - timedelta(days=DELAI_TRIMESTRE)).isoformat()
    annuels, bilans = {}, {}
    for concept, faits in ctx.finances(cik).items():
        for f in faits:
            debut, fin, valeur, forme = f[0], f[1], f[2], (f[3] if len(f) > 3 else None)
            if valeur is None or not fin:
                continue
            trimestriel = str(forme or "").upper().startswith("10-Q")
            if debut is None:
                if fin <= (lim_tr if trimestriel else lim_an):
                    bilans.setdefault(concept, {})[fin] = valeur
            elif (not trimestriel and fin <= lim_an
                  and DUREE_EXERCICE[0] <= (_d(fin) - _d(debut)).days <= DUREE_EXERCICE[1]):
                annuels.setdefault(concept, {})[fin] = valeur
    return annuels, bilans


def _dernier_bilan(bilans, concept):
    v = bilans.get(concept)
    return v[max(v)] if v else None


def _exercices(annuels):
    """(fin de t, fin de t-1) ; None si absent."""
    fins = sorted({f for v in annuels.values() for f in v})
    if not fins:
        return None, None
    t = fins[-1]
    avant = [f for f in fins if ECART_T_MOINS_1[0] <= (_d(t) - _d(f)).days <= ECART_T_MOINS_1[1]]
    if not avant:
        return t, None
    return t, min(avant, key=lambda f: (abs((_d(t) - _d(f)).days - 365), -_d(f).toordinal()))


# ---------- Le portefeuille refait par la règle (pour « 1 achat par mois » et « déjà en portefeuille ») ----------
# Cache de calculs du passé seulement : ce que le banc a fait de NOS signaux, jour par jour, avec les données connues
# au plus tard le jour de la décision (ctx). Refait de zéro si une nouvelle simulation commence.

_CACHE = {}


def _cache(e, ctx):
    c = _CACHE
    if c and e["depot"] < c["dernier_depot"]:
        c.clear()  # nouvelle simulation (les dépôts arrivent toujours dans l'ordre)
    if not c:
        premier = ctx.evenements_marche("0000-00-00")[0]["depot"]
        c.update(debut=(_d(premier) + timedelta(days=365)).replace(day=1).isoformat(), filtre={}, decision={},
                 gardes_mois={}, ombre={"jour": None, "positions": [], "attente": [], "statut": {}, "a_venir": []})
    c["dernier_depot"] = e["depot"]
    return c


def _prix(ctx, s, jour):
    x = ctx.clotures(s, jour, jour)
    return x[0] if x else None


def _avancer(ctx, c):
    """Refait les jours de bourse du banc jusqu'à aujourd'hui (ctx.jour)."""
    o = c["ombre"]
    depuis = c["debut"] if o["jour"] is None else (_d(o["jour"]) + timedelta(days=1)).isoformat()
    if depuis <= ctx.jour:
        for jour in ctx.jours_de_bourse(depuis):
            _journee(ctx, c, jour)


def _journee(ctx, c, jour):
    """Un jour du banc pour nos signaux : ventes, puis achats (même logique que banc.simuler)."""
    o = c["ombre"]
    veille = o["jour"]
    gardees = []
    for p in o["positions"]:
        p["n"] += 1  # jours de bourse depuis l'achat
        prevue = p["n"] >= DUREE
        plus_tot = (not prevue and veille is not None and jour > p["entree"]
                    and _vendre_au_prochain_jour(p["entree"], veille))
        vendue = (prevue or plus_tot) and _prix(ctx, p["s"], jour) is not None
        if not vendue and prevue and p["n"] >= DUREE + TOLERANCE_SORTIE:
            vendue = True  # dernière clôture connue
        if not vendue:
            gardees.append(p)
    o["positions"] = gardees
    attente = []
    for e, n in o["attente"]:
        if n + 1 <= TOLERANCE_ENTREE:
            attente.append((e, n + 1))
        else:
            o["statut"][e["id"]] = ("perdu", veille, "sans prix")
    k = 0
    while k < len(o["a_venir"]) and o["a_venir"][k]["depot"] < jour:
        attente.append((o["a_venir"][k], 0))
        k += 1
    del o["a_venir"][:k]
    reste = []
    for e, n in sorted(attente, key=lambda x: (-priorite(x[0], None), x[0]["depot"], x[0]["id"])):
        if _prix(ctx, e["symbole"], jour) is None:
            reste.append((e, n))
        elif len(o["positions"]) >= MAX_POSITIONS:
            o["statut"][e["id"]] = ("perdu", jour, "places pleines")
        elif any(p["s"] == e["symbole"] for p in o["positions"]):
            o["statut"][e["id"]] = ("perdu", jour, "déjà en portefeuille")
        else:
            o["positions"].append({"id": e["id"], "s": e["symbole"], "cik": e["cik"], "entree": jour, "n": 0})
            o["statut"][e["id"]] = ("achete", jour, "")
    o["attente"] = reste
    o["jour"] = jour


def _statut(c, id_):
    """« achete », « perdu » (jamais acheté, plus de chance) ou « en_attente », le soir du dernier jour refait."""
    o = c["ombre"]
    if id_ in o["statut"]:
        return o["statut"][id_][0]
    for e, n in o["attente"]:
        if e["id"] == id_:
            return "perdu" if n >= TOLERANCE_ENTREE else "en_attente"
    return "en_attente"  # son 1er jour d'achat n'est pas encore arrivé


def _admissible(e, ctx, c):
    if e["id"] not in c["filtre"]:
        c["filtre"][e["id"]] = _filtre(e, ctx)
    return c["filtre"][e["id"]]


def _decider_le_jour(ctx, c, jour):
    """Décide d'un coup pour tous les achats déposés ce jour-là (ctx.jour == jour)."""
    lot = [x for x in ctx.evenements_marche(jour)
           if x["depot"] == jour and x.get("sens") == "achat" and x.get("symbole")]
    mois = jour[:7]
    libre = not UN_ACHAT_PAR_MOIS or all(_statut(c, i) == "perdu" for i in c["gardes_mois"].get(mois, []))
    detenues = {p["cik"] for p in c["ombre"]["positions"]}
    choisis = []
    if libre:
        for x in sorted(lot, key=lambda x: (-(x.get("montant") or 0), x["id"])):
            if _admissible(x, ctx, c) and x["cik"] not in detenues:
                choisis.append(x)
                if UN_ACHAT_PAR_MOIS:
                    break
    ids = {x["id"] for x in choisis}
    for x in lot:
        c["decision"][x["id"]] = x["id"] in ids
    for x in sorted(choisis, key=lambda x: x["id"]):
        c["gardes_mois"].setdefault(mois, []).append(x["id"])
        c["ombre"]["a_venir"].append(x)
