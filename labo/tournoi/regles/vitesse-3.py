"""vitesse-3 : achats en groupe (3 initiés ou plus en 30 jours), garder 10 jours.

Programmée telle qu'écrite dans regles_preenregistrees.json (piste « vitesse »), sans rien corriger ni améliorer.
Les choix faits pour les passages ambigus, et les endroits où le banc fait un peu autrement que le texte, sont dans
CHOIX ci-dessous.
"""
from datetime import date, timedelta

ID = "vitesse-3"

CHOIX = [
    "« Achat code P d'actions ordinaires » : un événement « achat » (code P) dont au moins un des titres déclarés "
    "(champ titres) contient « common » ou « ordinary », sans tenir compte des majuscules (ex. « Common Stock », "
    "« Class A Common Stock », « Ordinary Shares »). Un titre sans ces mots (privilégiées, unités, « Shares » seul, "
    "etc.) est refusé.",
    "« groupe ≥ 2 (au moins 2 AUTRES initiés différents… donc 3 acheteurs ou plus) » : groupe_30j ≥ 3, car le "
    "dictionnaire dit que groupe_30j compte aussi ce formulaire (« celui-ci compris ») ; c'est ce que la note de "
    "testabilité demande dans ce cas. groupe_30j = nombre d'initiés différents (cik) dans les formulaires d'achat de la "
    "compagnie déposés dans les 30 jours civils avant le dépôt et le jour même (tous ceux de ce jour-là). Le groupe "
    "compte tous les formulaires d'achat de la compagnie, quel que soit le titre acheté (comme groupe_30j) ; le filtre "
    "« actions ordinaires » ne vise que le formulaire qui donne le signal.",
    "« Le premier formulaire qui fait atteindre ce seuil » : un formulaire d'achat avec groupe_30j ≥ 3 dont le "
    "formulaire d'achat précédent de la compagnie (ordre du banc : dépôt, puis numéro ; tous les initiés), déposé dans "
    "les 30 jours civils avant (même jour compris), avait un groupe_30j de moins de 3, ou qui n'a aucun achat précédent "
    "dans ces 30 jours. Les formulaires du même jour ont tous le même groupe : seul le premier dans l'ordre du banc "
    "peut être le signal. Si le seuil était déjà atteint au formulaire précédent, ce n'est pas le premier : pas de "
    "signal (voir la comparaison à la fin).",
    "Les conditions « montant ≥ 25 000 $ », « routinier = non », « plan_10b5_1 ≠ oui » et « valeur_m entre 100 et "
    "3 000 M$ » s'appliquent au formulaire qui fait atteindre le seuil. S'il ne les remplit pas, pas de signal, et les "
    "formulaires suivants du même groupe ne le remplacent pas (le seuil était déjà atteint).",
    "Montant inconnu = refusé ; routinier doit être faux ; plan_10b5_1 refusé seulement si « oui » (true), le vide "
    "(null) est accepté ; valeur_m : bornes comprises, inconnue = refusé.",
    "« Au moins un des acheteurs du groupe (en comptant celui-ci) est un dirigeant ou un administrateur » : au moins un "
    "déclarant d'un formulaire d'achat de la compagnie déposé dans les 30 jours civils avant ou le jour même (les "
    "formulaires comptés dans groupe_30j) a le rôle « dirigeant » ou « administrateur ».",
    "« Puis plus aucune entrée sur ce symbole pendant 60 jours civils » : réglage du banc "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 60 (aucun nouvel achat du symbole moins de 60 jours civils après un ACHAT fait ; un "
    "signal pas acheté ne bloque rien).",
    "Entrée : clôture SEC du 1er jour de bourse après le dépôt (JOURS_ENTREE = 1) ; pas de prix ce jour-là = signal "
    "abandonné (TOLERANCE_ENTREE = 0).",
    "Sortie : clôture du 10e jour de bourse après le jour d'achat (DUREE = 10). Pas de prix ce jour-là : le banc vend "
    "au 1er prix SEC des 10 jours de bourse suivants, sinon au dernier prix connu (TOLERANCE_SORTIE = 10, valeur "
    "standard du banc) : c'est ainsi que « la compagnie disparaît » est reconnu ; le texte ne donne pas de limite.",
    "Taille : au plus 2 positions (MAX_POSITIONS = 2). Le banc place la valeur du portefeuille ÷ 2 par position "
    "(5 000 $ au départ), pas exactement 5 000 $ fixes.",
    "Argent qui attend dans SPY (ARGENT_QUI_ATTEND = « SPY », LIQUIDE_JOURS = 0) : 4 transactions de 10 $ par "
    "aller-retour (vendre du SPY, acheter l'action, la vendre, racheter du SPY). Le banc compte aussi, comme pour "
    "toutes les règles, le demi-écart achat-vente selon la valeur en bourse.",
    "Une seule position par symbole et signaux sans place perdus : faits par le banc.",
    "« Priorité au groupe le plus grand, puis au plus gros montant » : priorite = groupe_30j × 10^12 + montant ; à "
    "égalité, l'ordre du banc (dépôt, numéro).",
    "Montant minimal d'une position : MONTANT_MIN = 50 $ (valeur standard du banc, le texte n'en parle pas).",
    "Comparaison testeur/vérificateur (6 oct. 2026), 1) « d'actions ordinaires » est une condition du texte (d'autres "
    "règles, ex. prix_bas-1 ou liquidite_taille-1, ne l'écrivent pas) ; d'où le filtre sur le champ titres ci-dessus. "
    "Le vérificateur ne filtrait pas les titres : corrigé dans sa programmation.",
    "Comparaison testeur/vérificateur (6 oct. 2026), 2) « On prend seulement le premier formulaire qui fait atteindre "
    "ce seuil » : lecture retenue (la plus simple, celle du vérificateur) : UN seul formulaire par groupe, le premier "
    "dans l'ordre où le banc lit les dépôts (dépôt, puis numéro) dont le groupe atteint le seuil alors que l'achat "
    "précédent de la compagnie (déposé dans les 30 jours) ne l'atteignait pas. Le testeur prenait comme « premiers » "
    "tous les formulaires du même jour (le banc achetait alors le plus gros montant, même quand le premier n'avait pas "
    "25 000 $) et redonnait un signal quand un initié sortait de la fenêtre de 30 jours entre deux dépôts du même "
    "groupe : corrigé dans sa programmation.",
]

# Réglages du banc
JOURS_ENTREE = 1
TOLERANCE_ENTREE = 0
DUREE = 10
MAX_POSITIONS = 2
ARGENT_QUI_ATTEND = "SPY"
LIQUIDE_JOURS = 0
UNE_ENTREE_PAR_SYMBOLE_JOURS = 60
TOLERANCE_SORTIE = 10
MONTANT_MIN = 50

# Seuils du texte
SEUIL_GROUPE = 3  # « groupe ≥ 2 AUTRES initiés » ; groupe_30j compte aussi ce formulaire
FENETRE_JOURS = 30
MONTANT_SEUIL = 25_000
VALEUR_MIN, VALEUR_MAX = 100, 3000
ROLES = ("dirigeant", "administrateur")


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def _achats_fenetre(e, ctx):
    """Les formulaires d'achat de la compagnie déposés dans les 30 jours civils avant le dépôt et le jour même."""
    depuis = (date.fromisoformat(e["depot"]) - timedelta(days=FENETRE_JOURS)).isoformat()
    return [x for x in ctx.evenements_avant(e["cik"], depuis) if x["sens"] == "achat"]


def garder(e, ctx):
    if e.get("sens") != "achat" or not e.get("symbole"):
        return False
    if not _actions_ordinaires(e):
        return False
    if (e.get("groupe_30j") or 0) < SEUIL_GROUPE:
        return False
    fenetre = _achats_fenetre(e, ctx)
    # Premier formulaire qui fait atteindre le seuil : l'achat précédent de la compagnie (ordre du banc : dépôt, numéro),
    # déposé dans les 30 jours, avait un groupe sous le seuil (ou il n'y en a pas)
    precedents = [x for x in fenetre if (x["depot"], x["id"]) < (e["depot"], e["id"])]
    if precedents and (precedents[-1].get("groupe_30j") or 0) >= SEUIL_GROUPE:
        return False
    m = e.get("montant")
    if m is None or m < MONTANT_SEUIL:
        return False
    if e.get("routinier") is not False:
        return False
    if e.get("plan_10b5_1") is True:
        return False
    v = e.get("valeur_m")
    if v is None or not (VALEUR_MIN <= v <= VALEUR_MAX):
        return False
    return any(r in ROLES for x in fenetre for i in x.get("inities") or [] for r in i.get("roles") or [])


def priorite(e, ctx):
    return (e.get("groupe_30j") or 0) * 1e12 + (e.get("montant") or 0)
