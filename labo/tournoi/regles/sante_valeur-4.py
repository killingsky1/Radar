"""sante_valeur-4 : S&P 500 par défaut + quelques paris rares sur le trio strict (cœur-satellites), garde de 12 mois
(règle pré-enregistrée, piste « sante_valeur »).

Texte (labo/tournoi/regles_preenregistrees.json), en bref :
- Filtre : formulaire 4 avec achat en bourse (code P) où (a) roles contient administrateur OU dirigeant ; (b) routinier
  = non ; (c) plan_10b5_1 = non (ou vide) ; (d) montant ≥ 100 000 $ ; (e) valeur_m ≥ 100 M$ ; (f) capitaux propres > 0
  et B/M ≥ 0,70 ; (g) F7 ≥ 6 sur 7 (défini dans sante_valeur-1) ; (h) bénéfice net_t > 0 et flux d'exploitation_t > 0 ;
  (i) passif ÷ actif ≤ 0,70 ; (j) compagnie pas déjà en portefeuille. Si un élément du F7 ne peut pas être calculé,
  l'événement est écarté.
- Paramètres : délais comptables, B/M et F7 exactement comme dans sante_valeur-1 (annuel ≥ 120 jours, trimestriel ≥ 60
  jours après la fin de période). F7 de sante_valeur-1 : 1) bénéfice net_t ÷ actif_t > 0 ; 2) flux d'exploitation_t
  > 0 ; 3) BN_t/actif_t > BN_t-1/actif_t-1 ; 4) flux d'exploitation_t > BN_t ; 5) passif_t/actif_t <
  passif_t-1/actif_t-1 ; 6) actions en circulation_t ≤ 1,02 × actions_t-1 ; 7) revenus_t/actif_t >
  revenus_t-1/actif_t-1 ; exercice t = dernier exercice annuel connu, t-1 = l'exercice dont la fin tombe 330 à 400
  jours avant celle de t ; capitaux propres du B/M : la période connue la plus récente.
- Entrée : clôture du 1er jour de bourse après le dépôt ; sans prix SEC, 1re clôture SEC dans les 5 jours de bourse
  suivants, sinon abandon. Pas de limite mensuelle : on achète chaque événement admissible tant qu'il reste une place,
  dans l'ordre des dates de dépôt (à égalité, le plus gros montant).
- Sortie : 12 mois après l'achat, à la 1re clôture SEC à cette date ou après ; aucune dans les 10 jours de bourse :
  dernière clôture SEC connue ; titre disparu : dernier prix SEC connu. L'argent revient dans SPY le même jour.
- Taille : base 100 % SPY ; au plus 4 satellites en même temps, chacun égal à 15 % de la valeur totale du portefeuille
  au moment de l'achat, payé en vendant du SPY ; au maximum 60 % en actions individuelles, au minimum 40 % dans SPY ;
  quand aucune place n'est libre, les nouveaux événements sont ignorés.

Reprogrammée le 6 octobre 2026 : l'élément 6 du F7 se calcule maintenant avec ctx.actions_par_periode() (actions en
circulation à chaque fin de période, ajoutées au jeu de recherche ce jour-là). La version d'avant était écartée
(IMPOSSIBLE) faute de cette donnée.
"""
import calendar
import math
from datetime import date, timedelta

ID = "sante_valeur-4"
IMPOSSIBLE = None

CHOIX = [
    "Comparaison testeur/vérificateur (6 oct. 2026) : les deux programmes ne donnaient pas les mêmes achats et ventes "
    "sur le faux jeu. Décision selon le texte : ce programme suit le texte et n'est pas changé ; le vérificateur est "
    "corrigé sur 5 points : (1) vente 12 mois civils après l'achat (« à cette date ou après », pas 252 jours de "
    "bourse) ; (2) (j) « compagnie pas déjà en portefeuille » fait partie du filtre (vérifié le soir du dépôt, par "
    "compagnie, avec le portefeuille refait par la règle ; le banc refuse en plus un symbole déjà détenu) ; (3) chiffre "
    "de 350 à 380 jours tiré d'un 10-Q exclu de l'exercice annuel ; (4) t-1 : la fin la plus proche de 365 jours, puis "
    "la plus récente ; (5) le même concept de revenus pour t et t-1. Mêmes décisions que pour sante_valeur-1 et, pour "
    "les points 1 à 3, que pour sante_valeur-2 et 3. Vérifié ensuite identique sur le faux jeu et sur un jeu ciblé "
    "(comparaison/sante_valeur/jeu_sante_valeur-4).",
    "Événement = une ligne « achat » du jeu (code P, titres non dérivés) qui a un symbole (le banc n'achète que "
    "celles-là). Le champ « titres » n'est pas filtré : le texte ne le demande pas.",
    "(a) Rôles : l'événement est gardé si AU MOINS UN déclarant (e['inities']) a « administrateur » ou « dirigeant » "
    "dans roles.",
    "(b) routinier doit valoir false.",
    "(c) plan_10b5_1 : écarté seulement si true ; false et vide (null) acceptés, à toute date (texte : « non (ou "
    "vide) »).",
    "(d) montant ≥ 100 000 $ et (e) valeur_m ≥ 100 M$ : bornes comprises ; champ absent = écarté.",
    "Données comptables (comme sante_valeur-1) = ctx.finances et ctx.actions_par_periode (le banc ne montre un chiffre "
    "qu'à partir de sa vraie date de dépôt) ET, en plus, les délais du texte : un exercice annuel (une durée de 350 à "
    "380 jours, pas tirée d'un 10-Q : un 10-Q peut donner 12 mois glissants, ce n'est pas un exercice) compte si sa fin "
    "date d'au moins 120 jours avant le dépôt ; un chiffre de bilan (à une date : actif, passif, capitaux propres, "
    "actions en circulation) compte si cette date est au moins 60 jours avant le dépôt (bilan d'un 10-Q ou 10-Q/A) ou "
    "au moins 120 jours avant (bilan d'un 10-K ou d'une autre forme).",
    "Exercice t = l'exercice annuel connu dont la fin est la plus récente (tous les concepts en dollars ensemble). "
    "Exercice t-1 = l'exercice annuel dont la fin tombe 330 à 400 jours avant celle de t (s'il y en a plusieurs : le plus "
    "proche de 365 jours, puis le plus récent). Actif, passif et actions en circulation de t et de t-1 (pour le F7) = "
    "les chiffres de bilan datés exactement de la fin de ces exercices.",
    "Concepts : capitaux propres = StockholdersEquity ; actif = Assets ; passif = Liabilities ; bénéfice net = "
    "NetIncomeLoss ; flux d'exploitation = NetCashProvidedByUsedInOperatingActivities ; revenus = Revenues, sinon "
    "RevenueFromContractWithCustomerExcludingAssessedTax, sinon SalesRevenueNet (le même concept pour t et t-1 : le "
    "premier de cette liste qui a les deux années). Rien n'est recalculé (par exemple, passif = actif − capitaux "
    "propres) : un concept absent = condition impossible à vérifier = écarté. Deux chiffres annuels d'un concept avec "
    "la même fin : celui dont le début est le plus récent.",
    "Élément 6 du F7, actions en circulation : CommonStockSharesOutstanding (us-gaap) de ctx.actions_par_periode, le "
    "chiffre du bilan daté de la fin de l'exercice t, et celui daté de la fin de t-1 ; condition actions_t ≤ 1,02 × "
    "actions_t-1 (borne comprise). Pourquoi ce concept : le F7 de sante_valeur-1 compare les actions de l'exercice t et "
    "de l'exercice t-1, et les champs de cette règle disent « XBRL annuel et trimestriel : … actions en circulation, "
    "date de fin de période » ; c'est exactement CommonStockSharesOutstanding (au bilan, à la date de fin de la "
    "période). EntityCommonStockSharesOutstanding (dei) n'est pas pris, même en secours : il est daté de la page "
    "couverture, près du dépôt du rapport, pas de la fin de l'exercice ; le mêler aurait comparé d'autres dates (ce "
    "serait changer la règle). Chiffre absent pour t ou t-1 = élément impossible à calculer = événement écarté (texte). "
    "Pas d'ajustement pour un fractionnement d'actions : le jeu donne la 1re version déposée de chaque chiffre, et un "
    "fractionnement entre t-1 et t compte comme une hausse.",
    "(f) Capitaux propres pour le B/M = le dernier bilan connu de StockholdersEquity (date la plus récente, 10-Q ou "
    "10-K). Capitaux propres > 0 et capitaux propres ÷ (valeur_m × 1 000 000) ≥ 0,70 (borne comprise). Absents = "
    "écarté.",
    "(g) F7 comme sante_valeur-1 : 1 point par condition vraie, il en faut au moins 6. Un élément impossible à calculer "
    "(chiffre absent, actif nul) = événement écarté (texte). Conditions strictes comme écrites (> et <), sauf l'élément "
    "6 (≤). Les deux éléments retirés du score original (liquidité courante, marge brute) ne sont pas ajoutés.",
    "(h) Bénéfice net de t > 0 et flux d'exploitation de t > 0 (exercice t ci-dessus).",
    "(i) Passif ÷ actif ≤ 0,70 (borne comprise) : le texte de cette règle ne dit pas quelle période (il écrit « _t » "
    "seulement en (h)) ; pris comme le B/M de sante_valeur-1 et le même ratio de sante_valeur-3 (« période connue la "
    "plus récente ») : le dernier bilan connu qui a le passif ET l'actif à la même date.",
    "(j) Compagnie déjà en portefeuille : vérifié le soir du dépôt, par compagnie (cik), dans le portefeuille que la "
    "règle recalcule : elle refait jour par jour les achats et ventes du banc pour ses propres signaux (mêmes règles : "
    "prix du jour exact, 5 jours de réessai, 4 places, symbole déjà détenu, ventes avant achats, ordre de priorite()), "
    "avec les seules données connues le soir du dépôt (un cache de calculs du passé, refait si une nouvelle "
    "simulation commence). Le banc refuse aussi, le jour de l'achat, un symbole déjà détenu.",
    "Pas de limite mensuelle : tous les événements admissibles sont gardés ; le banc les achète dans l'ordre de "
    "priorite() (date de dépôt la plus ancienne d'abord, puis le plus gros montant) tant qu'il reste une des 4 places ; "
    "sinon il les ignore (même un signal qui attendait encore son prix).",
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
    "la date des 12 mois (texte : 10 jours de bourse) ; jamais avant la date des 12 mois. Sur le FAUX jeu (calendrier "
    "sans congés, environ 261 jours de bourse par an), le 262e jour tombe sur la date des 12 mois ou le lendemain : "
    "sans prix ce jour-là, la vente se fait tout de suite à la dernière clôture connue.",
    "Titre disparu (rachat, faillite) : vendu au dernier prix SEC connu, comme le texte, mais à la date de sortie "
    "ci-dessus (12 mois, ou le 262e jour de bourse) : savoir plus tôt qu'un titre a disparu demanderait de voir le "
    "futur, et le texte ne fixe aucun délai pour le décider. La position garde sa place jusque-là.",
    "Taille : MAX_POSITIONS = 4 et poids() = 0,6 : chaque achat = valeur du portefeuille ÷ 4 × 0,6 = 15 %. « Au maximum "
    "60 % en actions, au minimum 40 % dans SPY » est lu comme la conséquence de 4 × 15 % au moment des achats, pas "
    "comme une règle de plus (rien n'est vendu si les satellites montent au-delà de 60 %).",
    "Banc (diffère du texte) : la position vaut 15 % de la valeur MOINS les 10 $ de frais ; frais de 10 $ par "
    "transaction (SPY compris) plus un demi-écart achat-vente selon la valeur en bourse, à l'achat et à la vente ; "
    "MONTANT_MIN = 50 (réglage par défaut, le texte n'en parle pas).",
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
MAX_POSITIONS = 4
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0
POIDS = 0.6                 # 4 places × 0,6 = 15 % de la valeur par satellite

# Seuils du texte
ROLES_ADMIS = ("administrateur", "dirigeant")
MONTANT_MINIMUM = 100_000
VALEUR_M_MINIMUM = 100
BM_MINIMUM = 0.70
F7_MINIMUM = 6
PASSIF_SUR_ACTIF_MAXIMUM = 0.70
DELAI_ANNUEL = 120           # jours civils entre la fin d'un exercice et le dépôt
DELAI_TRIMESTRE = 60         # jours civils entre la fin d'un trimestre et le dépôt
DUREE_EXERCICE = (350, 380)  # jours : une durée annuelle dans ctx.finances
ECART_T_MOINS_1 = (330, 400)  # jours entre la fin de t-1 et celle de t
HAUSSE_ACTIONS_MAX = 1.02
REVENUS = ("Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet")
ACTIONS = "CommonStockSharesOutstanding"  # actions en circulation au bilan, à la fin de la période


def poids(e, ctx):
    return POIDS


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
    if IMPOSSIBLE:
        return False
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


# ---------- Le filtre (a) à (i) ----------

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
    cp = _dernier_bilan(bilans, "StockholdersEquity")
    if cp is None or cp <= 0 or cp / (v * 1_000_000) < BM_MINIMUM:
        return False
    f7 = _f7(annuels, bilans)
    if f7 is None or f7 < F7_MINIMUM:
        return False
    t, _ = _exercices(annuels)
    bn = annuels.get("NetIncomeLoss", {}).get(t)
    fe = annuels.get("NetCashProvidedByUsedInOperatingActivities", {}).get(t)
    if bn is None or fe is None or bn <= 0 or fe <= 0:
        return False
    pa = _passif_sur_actif(bilans)
    return pa is not None and pa <= PASSIF_SUR_ACTIF_MAXIMUM


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
    autre : ≥ 120 jours). Les bilans comprennent les actions en circulation (ACTIONS) de ctx.actions_par_periode."""
    j = _d(depot)
    lim_an = (j - timedelta(days=DELAI_ANNUEL)).isoformat()
    lim_tr = (j - timedelta(days=DELAI_TRIMESTRE)).isoformat()
    sources = list(ctx.finances(cik).items())
    actions = ctx.actions_par_periode(cik).get(ACTIONS)
    if actions:
        sources.append((ACTIONS, actions))
    annuels, bilans = {}, {}
    for concept, faits in sources:
        for f in faits:
            debut, fin, valeur, forme = f[0], f[1], f[2], (f[3] if len(f) > 3 else None)
            if valeur is None or not fin:
                continue
            trimestriel = str(forme or "").upper().startswith("10-Q")
            if debut is None:
                if fin <= (lim_tr if trimestriel else lim_an):
                    bilans.setdefault(concept, {})[fin] = valeur
            elif (concept != ACTIONS and not trimestriel and fin <= lim_an
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


def _f7(annuels, bilans):
    """Score F7 (0 à 7), ou None si un élément ne peut pas être calculé."""
    t, t1 = _exercices(annuels)
    if t is None or t1 is None:
        return None
    bn = annuels.get("NetIncomeLoss", {})
    fe = annuels.get("NetCashProvidedByUsedInOperatingActivities", {})
    actif = bilans.get("Assets", {})
    passif = bilans.get("Liabilities", {})
    actions = bilans.get(ACTIONS, {})
    rev = None
    for concept in REVENUS:
        v = annuels.get(concept, {})
        if t in v and t1 in v:
            rev = (v[t], v[t1])
            break
    valeurs = [bn.get(t), bn.get(t1), fe.get(t), actif.get(t), actif.get(t1), passif.get(t), passif.get(t1), rev,
               actions.get(t), actions.get(t1)]
    if any(x is None for x in valeurs) or not actif[t] or not actif[t1]:
        return None
    return sum([
        bn[t] / actif[t] > 0,
        fe[t] > 0,
        bn[t] / actif[t] > bn[t1] / actif[t1],
        fe[t] > bn[t],
        passif[t] / actif[t] < passif[t1] / actif[t1],
        actions[t] <= HAUSSE_ACTIONS_MAX * actions[t1],
        rev[0] / actif[t] > rev[1] / actif[t1],
    ])


# ---------- Le portefeuille refait par la règle (pour « déjà en portefeuille ») ----------
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
                 ombre={"jour": None, "positions": [], "attente": [], "statut": {}, "a_venir": []})
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


def _admissible(e, ctx, c):
    if e["id"] not in c["filtre"]:
        c["filtre"][e["id"]] = _filtre(e, ctx)
    return c["filtre"][e["id"]]


def _decider_le_jour(ctx, c, jour):
    """Décide d'un coup pour tous les achats déposés ce jour-là (ctx.jour == jour) : tous ceux qui passent le filtre
    et dont la compagnie n'est pas déjà en portefeuille."""
    lot = [x for x in ctx.evenements_marche(jour)
           if x["depot"] == jour and x.get("sens") == "achat" and x.get("symbole")]
    detenues = {p["cik"] for p in c["ombre"]["positions"]}
    choisis = [x for x in sorted(lot, key=lambda x: x["id"]) if x["cik"] not in detenues and _admissible(x, ctx, c)]
    ids = {x["id"] for x in choisis}
    for x in lot:
        c["decision"][x["id"]] = x["id"] in ids
    c["ombre"]["a_venir"].extend(choisis)
