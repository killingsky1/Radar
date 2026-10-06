"""meteo-4 : saison froide, suivre les achats d'initiés de novembre à janvier, revendre fin avril, S&P 500 de mai à
octobre (règle pré-enregistrée, piste « meteo »).

Texte (labo/tournoi/regles_preenregistrees.json) :
- CALENDRIER : nouvelles positions seulement si le jour d'entrée tombe entre le 1er jour de bourse de novembre et le
  dernier jour de bourse de janvier (inclusivement).
- PANIER : achat P ; roles contient administrateur ou dirigeant ; routinier = non ; plan_10b5_1 différent de « oui »
  (vide accepté) ; montant >= 100 000 $ ; valeur_m >= 100 M$ ; on ne possède pas déjà cette compagnie.
- Entrée : clôture SEC du 1er jour de bourse après le dépôt, si ce jour tombe dans la période novembre-janvier ; sans
  prix, 1re clôture SEC des 5 jours de bourse suivants, à condition qu'elle tombe encore dans la période ; sinon on
  laisse passer. Le même jour : plus gros montant d'abord.
- Sortie : toutes les positions vendues à la clôture SEC du dernier jour de bourse d'avril ; sans prix ce jour-là, la
  dernière clôture SEC des 5 jours de bourse avant ; sinon la 1re clôture SEC disponible après ; compagnie disparue :
  dernière clôture connue. De mai à octobre : 100 % SPY.
- Taille : 10 cases de 10 % de la valeur du portefeuille ; pleines : on laisse passer ; le reste dans SPY (10 $ par
  transaction).
"""
from datetime import date, timedelta

ID = "meteo-4"
IMPOSSIBLE = None

CHOIX = [
    # --- Le panier
    "« Achat P » = un événement « achat » du jeu de données (code P, titres non dérivés, en bourse).",
    "Rôles : l'événement est gardé si AU MOINS UN déclarant du formulaire a « administrateur » ou « dirigeant » dans "
    "ses rôles (un formulaire peut avoir plusieurs déclarants). Si tous les déclarants sont seulement actionnaires de "
    "10 % ou « autre », il est refusé.",
    "routinier = non : le champ routinier de l'événement doit valoir false (il vaut true si un des déclarants est "
    "routinier).",
    "plan_10b5_1 différent de « oui » : refusé seulement si true ; false et vide (null) acceptés.",
    "montant >= 100 000 $ et valeur_m >= 100 M$ : bornes comprises ; montant ou valeur_m absent (null) = refusé.",
    "« On ne possède pas déjà cette compagnie » : fait par le banc, qui refuse un SYMBOLE déjà en portefeuille (une "
    "compagnie qui aurait deux symboles, par exemple deux catégories d'actions, pourrait être achetée deux fois).",
    "Plusieurs événements le même jour : priorite = montant (le plus gros d'abord). Égalité : le banc prend le dépôt "
    "le plus ancien, puis le numéro du dépôt. Le banc trie ensemble les signaux du jour et ceux qui attendent encore "
    "un prix.",
    # --- Entrée et période
    "Entrée : JOURS_ENTREE = 1 et TOLERANCE_ENTREE = 5 (le 1er jour de bourse après le dépôt ; sans prix, le 1er prix "
    "des 5 jours de bourse suivants ; sinon abandon).",
    "Période : un achat se fait seulement si le 1er jour de bourse après le dépôt (vérifié dans garder) ET le jour "
    "d'achat lui-même (vérifié dans investir, le jour où le prix est trouvé) sont en novembre, décembre ou janvier. "
    "Un achat prévu fin octobre sans prix, puis trouvé en novembre, est donc laissé ; un achat prévu fin janvier sans "
    "prix, puis trouvé en février, aussi.",
    "Le banc ne montre pas les jours à venir (investir reçoit la veille du jour d'achat ; garder, le jour du dépôt) : "
    "le jour de bourse qui suit est pris comme le jour de semaine suivant (lundi à vendredi). Il n'y a pas de congé de "
    "bourse autour du 1er novembre ni de la fin de janvier, donc le mois trouvé est le bon.",
    # --- Sortie
    "Sortie fin avril (sortir_avant) : chaque position est vendue au dernier jour de bourse d'avril qui suit son achat "
    "(achat en novembre ou décembre : avril de l'année suivante ; en janvier : avril de la même année). Ce jour est "
    "pris comme le dernier jour de semaine d'avril (pas de congé de bourse fin avril). Le banc décide la veille et "
    "vend à la clôture du jour s'il y a un prix ce jour-là.",
    "Pas de prix SEC le dernier jour de bourse d'avril (diffère du texte) : une vente décidée par sortir_avant se "
    "fait seulement à la clôture du jour même dans le banc ; vendre plus tôt, au prix d'un des 5 jours d'avant, "
    "demanderait de savoir d'avance qu'il n'y aura pas de prix le dernier jour d'avril. Le 1er repli du texte "
    "(dernière clôture des 5 jours de bourse avant) n'est donc pas fait : sortir_avant reste vrai et le banc vend à la "
    "1re clôture SEC disponible après (le 2e repli du texte).",
    "DUREE = 150 jours de bourse : seulement un filet, plus long que la plus longue garde possible (du 1er jour de "
    "bourse de novembre au dernier d'avril : au plus 129 jours de bourse après l'achat). Il ne sert que si aucun prix "
    "n'existe entre la fin d'avril et ce 150e jour (compagnie disparue) : avec TOLERANCE_SORTIE = 0, la vente se fait "
    "alors à la dernière clôture connue.",
    "De mai à octobre : aucun nouvel achat (investir faux) ; l'argent attend dans SPY.",
    # --- Taille et banc
    "Taille : MAX_POSITIONS = 10 (10 % chacune) ; ARGENT_QUI_ATTEND = « SPY » ; LIQUIDE_JOURS = 0 (l'argent d'une "
    "vente retourne dans SPY le jour même). Les 10 places prises : le signal est laissé, même s'il attendait un prix.",
    "Banc (diffère du texte) : le 10 % est calculé avec la valeur du portefeuille à la clôture du jour d'achat (après "
    "les ventes du jour), pas à la clôture de la veille ; la position vaut ce 10 % MOINS les 10 $ de frais ; s'il ne "
    "reste pas assez d'argent, il achète avec ce qui reste ; une position de moins de 50 $ n'est pas achetée "
    "(MONTANT_MIN = 50, réglage par défaut du banc).",
    "Banc (diffère du texte) : en plus des 10 $ par transaction (SPY compris), un demi-écart achat-vente selon la "
    "valeur en bourse, à l'achat et à la vente.",
    "Banc (le texte n'en parle pas) : changement de CUSIP pendant la détention = rendement enchaîné ; les ventes du "
    "jour passent avant les achats du jour ; une position encore ouverte à la fin des prix reste ouverte ; "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 0 (un symbole vendu peut être racheté tout de suite).",
    "Comparaison testeur/vérificateur (6 oct. 2026) : 2 écarts, corrigés dans le fichier du VÉRIFICATEUR ; rien ne "
    "change ici. 1) Entrée : ce fichier suit le texte (« 1er jour de bourse après le dépôt, si ce jour tombe dans la "
    "période » ; sans prix, « à condition qu'elle tombe ENCORE dans la période ») ; le vérificateur achetait le "
    "1er novembre 2023 un dépôt du 30 octobre dont le 1er jour (31 octobre) était hors période, sans prix. 2) Sans prix "
    "après la fin d'avril : le texte ne donne aucun délai avant de dire la compagnie disparue ; le vérificateur "
    "abandonnait au 139e jour de bourse après l'entrée, ce fichier au 150e ; on garde le plus long (plus proche de « la "
    "première clôture SEC disponible après »), donc le délai de ce fichier.",
]

# Réglages du banc
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 150  # filet seulement : la vraie vente est fin avril (sortir_avant)
TOLERANCE_SORTIE = 0
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

# Seuils du texte
MONTANT_MINIMUM = 100_000  # $
VALEUR_MINIMUM = 100  # M$
MOIS_ENTREE = (11, 12, 1)  # novembre, décembre, janvier


# ---------- Le panier ----------

def _panier(e):
    if e.get("sens") != "achat":
        return False
    if not any(r in ("administrateur", "dirigeant") for i in (e.get("inities") or []) for r in (i.get("roles") or [])):
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    montant, valeur = e.get("montant"), e.get("valeur_m")
    if montant is None or montant < MONTANT_MINIMUM:
        return False
    if valeur is None or valeur < VALEUR_MINIMUM:
        return False
    return True


# ---------- Le calendrier ----------

def _jour_de_semaine_suivant(jour):
    d = date.fromisoformat(jour) + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.isoformat()


def _dans_la_periode(jour):
    return int(jour[5:7]) in MOIS_ENTREE


def _dernier_jour_d_avril(achat):
    """Le dernier jour de semaine d'avril qui suit un achat (novembre-décembre : l'année suivante)."""
    annee = int(achat[:4]) + (1 if int(achat[5:7]) >= 5 else 0)
    d = date(annee, 4, 30)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d.isoformat()


def garder(e, ctx):
    # le 1er jour de bourse après le dépôt doit tomber en novembre, décembre ou janvier
    return _panier(e) and _dans_la_periode(_jour_de_semaine_suivant(e["depot"]))


def priorite(e, ctx):
    return float(e.get("montant") or 0.0)


def investir(jour, ctx):
    # `jour` = la veille du jour d'achat : le jour d'achat doit tomber en novembre, décembre ou janvier
    return _dans_la_periode(_jour_de_semaine_suivant(jour))


def sortir_avant(pos, jour, ctx):
    # `jour` = la veille : vendre à partir du dernier jour de bourse d'avril (1re clôture disponible)
    return _jour_de_semaine_suivant(jour) >= _dernier_jour_d_avril(pos["entree"][0])
