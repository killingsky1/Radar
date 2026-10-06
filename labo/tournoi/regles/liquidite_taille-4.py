"""liquidite_taille-4 : grandes compagnies (>= 10 G$), achat du PDG ou du chef des finances, garder 12 mois, 4 positions.

Programmée d'après le texte pré-enregistré (labo/tournoi/regles_preenregistrees.json), sans rien corriger :
- filtre : achat en bourse (code P) ; valeur_m >= 10 000 M$ ; le titre du dirigeant contient (sans tenir compte des
  majuscules) « CEO », « Chief Executive », « CFO » ou « Chief Financial » ; montant >= 100 000 $ ; routinier = non ;
  plan_10b5_1 différent de « oui » ; dépôt au plus 4 jours civils après jour_dernier_achat ; aucune autre entrée de
  cette règle sur la même compagnie dans les 180 jours civils avant ;
- entrée : clôture SEC du 1er jour de bourse après le dépôt, ou la 1re des 5 jours de bourse suivants, sinon abandon ;
- sortie : 1re clôture SEC au moins 252 jours de bourse après l'entrée ; titre disparu : dernier prix connu × 0,70
  dans le texte (le banc ne peut pas faire la décote : voir CHOIX) ;
- taille : 4 positions de 25 % ; premier arrivé, premier servi (à égalité, le plus gros montant) ; l'argent qui attend
  est dans SPY.
"""
from datetime import date

ID = "liquidite_taille-4"

CHOIX = [
    "« Aucune autre entrée de cette règle sur le même cik_emetteur dans les 180 jours civils avant » : une entrée = un "
    "ACHAT fait par la règle (le mot « entrée » des règles de cette piste veut dire l'achat). Un signal qui n'a pas été "
    "acheté (places pleines, pas de prix) ne compte pas. Fait par le banc : UNE_ENTREE_PAR_SYMBOLE_JOURS = 180, compté "
    "en jours civils d'une date d'achat à l'autre. Comme une position est gardée au moins 252 jours de bourse (plus de "
    "180 jours civils), cette condition ne bloque jamais un achat en pratique.",
    "Le banc compte par SYMBOLE et non par cik (une seule position par symbole, délai de 180 jours par symbole) : une "
    "compagnie écrite avec deux symboles différents dans ses formulaires (ex. deux catégories d'actions) pourrait être "
    "détenue deux fois (rare).",
    "Titre : au moins un des déclarants du formulaire a un titre qui contient, sans tenir compte des majuscules, « ceo », "
    "« chief executive », « cfo » ou « chief financial » (simple recherche dans le texte du titre : « Former CEO » ou "
    "« Co-CEO » comptent). Aucune autre condition sur les rôles, ni de prix minimum (le texte n'en met pas).",
    "Titre disparu : ce texte ne donne pas de délai. On prend celui que la même piste donne au « titre disparu » "
    "(règles 1 et 3) : aucun prix SEC dans les 60 jours de bourse après la date de sortie (TOLERANCE_SORTIE = 60), "
    "puis le dernier prix connu.",
    "Titre disparu : le banc vend au dernier prix SEC connu SANS la décote × 0,70 (le banc ne permet pas de changer le "
    "prix de vente).",
    "« valeur_m >= 10 000 M$ » ; un champ vide (valeur_m, montant ou jour_dernier) : la condition ne peut pas être "
    "vérifiée, l'événement n'est pas gardé.",
    "plan_10b5_1 : seul true (« oui ») exclut ; false et vide sont acceptés, à toute date.",
    "Délai : (date du dépôt − jour_dernier) <= 4 jours civils ; jour_dernier = dernier jour des achats (code P) du "
    "formulaire.",
    "Sortie : DUREE = 252 (1re clôture SEC à partir du 252e jour de bourse après l'achat).",
    "Places pleines : premier arrivé = date de dépôt la plus ancienne ; à égalité de date de dépôt, le montant le plus "
    "gros d'abord (priorite()) ; encore à égalité : l'ordre du banc (numéro du dépôt). Un signal sans place est ignoré.",
    "Taille : MAX_POSITIONS = 4, soit 25 % de la valeur du portefeuille (positions + SPY) calculée par le banc au début "
    "des achats du jour, après les ventes du jour ; s'il ne reste pas assez d'argent, le banc achète moins (règle du "
    "banc). Frais et écart achat-vente : ceux du banc.",
]

# --- Réglages du banc
JOURS_ENTREE = 1                     # clôture SEC du 1er jour de bourse après le dépôt
TOLERANCE_ENTREE = 5                 # pas de prix : 1re clôture des 5 jours de bourse suivants, sinon abandon
DUREE = 252                          # 1re clôture SEC au moins 252 jours de bourse après l'entrée
TOLERANCE_SORTIE = 60                # titre disparu : délai des règles 1 et 3 de la piste (voir CHOIX)
MAX_POSITIONS = 4                    # 4 positions de 25 %
ARGENT_QUI_ATTEND = "SPY"            # l'argent qui attend est dans SPY
LIQUIDE_JOURS = 0                    # l'argent d'une vente retourne dans SPY tout de suite
UNE_ENTREE_PAR_SYMBOLE_JOURS = 180   # aucune autre entrée (achat) sur la même compagnie dans les 180 jours civils avant

# --- Seuils du texte
SEUIL_VALEUR_MIN = 10_000.0                  # M$
SEUIL_MONTANT = 100_000.0                    # $
SEUIL_DELAI = 4                              # jours civils entre le dernier achat et le dépôt
TITRES = ("ceo", "chief executive", "cfo", "chief financial")


def _jours(a, b):
    """Jours civils de la date a à la date b (AAAA-MM-JJ)."""
    return (date.fromisoformat(b) - date.fromisoformat(a)).days


def garder(e, ctx):
    if e.get("sens") != "achat":
        return False
    v = e.get("valeur_m")
    if v is None or v < SEUIL_VALEUR_MIN:
        return False
    titres = [(i.get("titre") or "").lower() for i in (e.get("inities") or [])]
    if not any(t in titre for titre in titres for t in TITRES):
        return False
    m = e.get("montant")
    if m is None or m < SEUIL_MONTANT:
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    if not e.get("jour_dernier") or not e.get("depot") or _jours(e["jour_dernier"], e["depot"]) > SEUIL_DELAI:
        return False
    return True


def priorite(e, ctx):
    """Premier arrivé, premier servi (dépôt le plus ancien) ; à égalité de date, le plus gros montant. Le banc prend le
    plus haut d'abord : la date compte avant le montant (entier exact, montant en cents)."""
    return -date.fromisoformat(e["depot"]).toordinal() * 10 ** 18 + round((e.get("montant") or 0) * 100)
