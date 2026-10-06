"""liquidite_taille-3 : petites compagnies de qualité (100-500 M$), achat qui grossit vraiment la part de l'initié,
garder 12 mois, 5 positions.

Programmée d'après le texte pré-enregistré (labo/tournoi/regles_preenregistrees.json), sans rien corriger :
- filtre : achat en bourse (code P) ; valeur_m de 100 à 500 M$ ; prix_moyen >= 5 $ ; montant >= 25 000 $ ;
  part_ajoutee >= 10 % ; roles contient « dirigeant » ou « administrateur » ; routinier = non ; plan_10b5_1 différent de
  « oui » ; dépôt au plus 4 jours civils après jour_dernier_achat ; qualité d'après le dernier rapport ANNUEL XBRL dont
  l'exercice s'est terminé au moins 120 jours civils avant la date d'entrée : flux de trésorerie d'exploitation > 0 ET
  capitaux propres > 0 ; aucune autre entrée de cette règle sur la même compagnie dans les 180 jours civils avant ;
- entrée : clôture SEC du 1er jour de bourse après le dépôt, sinon la 1re des 5 jours de bourse suivants, sinon abandon ;
- sortie : 1re clôture SEC au moins 252 jours de bourse après l'entrée, sans prolongation ; aucun prix SEC dans les 60
  jours de bourse après cette date : dernier prix connu × 0,70 dans le texte (le banc ne peut pas faire la décote :
  voir CHOIX) ;
- taille : 5 positions de 20 % ; places pleines : signal ignoré (premier arrivé, premier servi ; à égalité, la plus
  grande part_ajoutee) ; l'argent qui attend est dans SPY.
"""
from datetime import date, timedelta

ID = "liquidite_taille-3"

CHOIX = [
    "« Aucune autre entrée de cette règle sur le même cik_emetteur dans les 180 jours civils avant » : une entrée = un "
    "ACHAT fait par la règle (le texte appelle « entrée » l'achat : « date d'entrée »). Un signal qui n'a pas été acheté "
    "(places pleines, pas de prix) ne compte pas. Fait par le banc : UNE_ENTREE_PAR_SYMBOLE_JOURS = 180, compté en jours "
    "civils d'une date d'achat à l'autre. Comme une position est gardée au moins 252 jours de bourse (plus de 180 jours "
    "civils), cette condition ne bloque jamais un achat en pratique.",
    "Le banc compte par SYMBOLE et non par cik (une seule position par symbole, délai de 180 jours par symbole) : une "
    "compagnie écrite avec deux symboles différents dans ses formulaires pourrait être détenue deux fois (rare).",
    "« Date d'entrée » du filtre qualité : garder() décide le soir du dépôt et ne peut pas connaître la vraie date "
    "d'achat (elle dépend des prix SEC des jours suivants). On prend l'entrée prévue : le 1er jour de semaine (lundi à "
    "vendredi) après la date du dépôt ; les congés de la bourse ne sont pas comptés (la règle ne voit pas le calendrier "
    "futur).",
    "Dernier rapport ANNUEL : l'exercice (durée de 350 à 380 jours, comme dans le dictionnaire) le plus récent du flux "
    "de trésorerie d'exploitation (NetCashProvidedByUsedInOperatingActivities) dont la fin est au moins 120 jours civils "
    "avant l'entrée prévue ; parmi les chiffres déjà déposés le jour du dépôt (le banc ne montre que ceux-là : les 120 "
    "jours du texte sont gardés EN PLUS de ce garde-fou). Le type de formulaire (10-K, 10-K/A...) n'est pas regardé : la "
    "durée de l'exercice suffit.",
    "Capitaux propres : StockholdersEquity au bilan à la MÊME date de fin que cet exercice. Si ce chiffre manque, "
    "l'événement n'est pas gardé (on ne prend pas un autre bilan). S'il n'y a aucun flux annuel assez ancien : pas gardé.",
    "Qualité : les deux chiffres strictement positifs (flux > 0 et capitaux propres > 0).",
    "part_ajoutee = le champ part (actions achetées ÷ actions détenues avant) : part >= 0,10. Part vide (détenues avant "
    "= 0 ou inconnues) : pas gardé.",
    "« Entre 100 M$ et 500 M$ » : bornes comprises (100 <= valeur_m <= 500).",
    "roles : au moins un des déclarants du formulaire a le rôle « dirigeant » ou « administrateur ».",
    "Un champ vide (valeur_m, prix_moyen, montant ou jour_dernier) : la condition ne peut pas être vérifiée, "
    "l'événement n'est pas gardé.",
    "plan_10b5_1 : seul true (« oui ») exclut ; false et vide sont acceptés, à toute date.",
    "Délai : (date du dépôt − jour_dernier) <= 4 jours civils ; jour_dernier = dernier jour des achats (code P) du "
    "formulaire.",
    "Sortie : DUREE = 252 (1re clôture SEC à partir du 252e jour de bourse après l'achat), TOLERANCE_SORTIE = 60.",
    "Titre disparu : le banc vend au dernier prix SEC connu SANS la décote × 0,70 (le banc ne permet pas de changer le "
    "prix de vente).",
    "Places pleines : premier arrivé = date de dépôt la plus ancienne ; à égalité de date de dépôt, la plus grande "
    "part_ajoutee d'abord (priorite()) ; encore à égalité : l'ordre du banc (numéro du dépôt).",
    "Taille : MAX_POSITIONS = 5, soit 20 % de la valeur du portefeuille (positions + SPY) calculée par le banc au début "
    "des achats du jour, après les ventes du jour ; s'il ne reste pas assez d'argent, le banc achète moins (règle du "
    "banc). Frais et écart achat-vente : ceux du banc.",
]

# --- Réglages du banc
JOURS_ENTREE = 1                     # clôture SEC du 1er jour de bourse après le dépôt
TOLERANCE_ENTREE = 5                 # pas de prix : 1re clôture des 5 jours de bourse suivants, sinon abandon
DUREE = 252                          # 1re clôture SEC au moins 252 jours de bourse après l'entrée, sans prolongation
TOLERANCE_SORTIE = 60                # titre disparu : aucun prix SEC dans les 60 jours de bourse après cette date
MAX_POSITIONS = 5                    # 5 positions de 20 %
ARGENT_QUI_ATTEND = "SPY"            # l'argent qui attend est dans SPY, comme dans la règle 1
LIQUIDE_JOURS = 0                    # l'argent d'une vente retourne dans SPY tout de suite
UNE_ENTREE_PAR_SYMBOLE_JOURS = 180   # aucune autre entrée (achat) sur la même compagnie dans les 180 jours civils avant

# --- Seuils du texte
SEUIL_VALEUR_MIN, SEUIL_VALEUR_MAX = 100.0, 500.0   # M$
SEUIL_PRIX = 5.0                                     # $
SEUIL_MONTANT = 25_000.0                             # $
SEUIL_PART = 0.10                                    # 10 %
SEUIL_DELAI = 4                                      # jours civils entre le dernier achat et le dépôt
RECUL_RAPPORT = 120                                  # jours civils entre la fin de l'exercice et la date d'entrée
ROLES = ("dirigeant", "administrateur")
FLUX = "NetCashProvidedByUsedInOperatingActivities"
CAPITAUX = "StockholdersEquity"


def _jours(a, b):
    """Jours civils de la date a à la date b (AAAA-MM-JJ)."""
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def _entree_prevue(depot):
    """Le 1er jour de semaine après le dépôt (l'achat prévu : 1er jour de bourse après le dépôt, congés inconnus)."""
    j = date.fromisoformat(depot) + timedelta(days=1)
    while j.weekday() >= 5:
        j += timedelta(days=1)
    return j


def _qualite(e, ctx):
    """Dernier rapport annuel dont l'exercice a fini au moins 120 jours civils avant l'entrée prévue : flux de trésorerie
    d'exploitation > 0 et capitaux propres > 0 (seulement les chiffres déjà déposés : ctx.finances)."""
    limite = (_entree_prevue(e["depot"]) - timedelta(days=RECUL_RAPPORT)).isoformat()
    faits = ctx.finances(e["cik"])
    exercices = [f for f in faits.get(FLUX, [])
                 if f[0] and f[1] and 350 <= _jours(f[0], f[1]) <= 380 and f[1] <= limite]
    if not exercices:
        return False
    fin, flux = exercices[-1][1], exercices[-1][2]   # trié par fin : le dernier = l'exercice le plus récent
    capitaux = [f[2] for f in faits.get(CAPITAUX, []) if f[0] is None and f[1] == fin]
    if not capitaux or flux is None or capitaux[-1] is None:
        return False
    return flux > 0 and capitaux[-1] > 0


def garder(e, ctx):
    if e.get("sens") != "achat":
        return False
    v = e.get("valeur_m")
    if v is None or not (SEUIL_VALEUR_MIN <= v <= SEUIL_VALEUR_MAX):
        return False
    p = e.get("prix_moyen")
    if p is None or p < SEUIL_PRIX:
        return False
    m = e.get("montant")
    if m is None or m < SEUIL_MONTANT:
        return False
    part = e.get("part")
    if part is None or part < SEUIL_PART:
        return False
    roles = {r for i in (e.get("inities") or []) for r in (i.get("roles") or [])}
    if not any(r in roles for r in ROLES):
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    if not e.get("jour_dernier") or not e.get("depot") or _jours(e["jour_dernier"], e["depot"]) > SEUIL_DELAI:
        return False
    return _qualite(e, ctx)


def priorite(e, ctx):
    """Premier arrivé, premier servi (dépôt le plus ancien) ; à égalité de date, la plus grande part_ajoutee. Le banc
    prend le plus haut d'abord : la date compte avant la part (entier exact, part en millionièmes)."""
    return -date.fromisoformat(e["depot"]).toordinal() * 10 ** 18 + round((e.get("part") or 0) * 10 ** 6)
