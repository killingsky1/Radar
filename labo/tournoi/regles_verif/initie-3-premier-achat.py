"""initie-3-premier-achat : premier achat de l'initié dans la compagnie depuis 2 ans (programmation du VÉRIFICATEUR).

Texte pré-enregistré (regles_preenregistrees.json) : achat P d'actions ordinaires ; roles contient dirigeant ou
administrateur (pas un actionnaire de 10 % seul) ; routinier = non ; plan_10b5_1 différent de oui ; montant ≥ 25 000 $ ;
valeur_m entre 100 et 2 000 M$. HISTORIQUE : aucun achat (P) ni vente (S) en bourse par cet initié dans cette compagnie
pendant les 730 jours civils avant le jour_premier_achat de ce dépôt ; un tout premier achat compte aussi. Pas d'action
déjà en portefeuille. Le même jour : le plus gros montant d'abord. Entrée, sortie, taille : comme initie-1 (126 jours de
bourse, 5 positions de 20 %, SPY).
"""
from datetime import date, timedelta

ID = "initie-3-premier-achat"
IMPOSSIBLE = None

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat P d'actions ordinaires » = un événement « achat » du jeu (code P, titres non dérivés). Le champ « titres » "
    "n'est pas filtré : il n'est pas dans les champs de la règle.",
    "roles contient « dirigeant » ou « administrateur » (un actionnaire de 10 % seul ou « autre » seul est exclu).",
    "Plusieurs déclarants : le formulaire est gardé si UN déclarant est à la fois dirigeant ou administrateur ET n'a eu "
    "aucun achat ni vente dans la compagnie pendant les 730 jours.",
    "routinier = non : e['routinier'] faux. plan_10b5_1 différent de oui : true refusé ; false et vide (null) acceptés.",
    "montant ≥ 25 000 $ et 100 ≤ valeur_m ≤ 2 000 (M$), bornes comprises ; montant ou valeur_m absent = refusé.",
    "Silence : ctx.historique_initie(cik du déclarant) (dépôts faits au plus tard le jour de la décision), lignes de cette "
    "compagnie (même cik que e['cik']), sens « achat » ou « vente ». Une ligne brise le silence si ses dates de "
    "transaction (de son jour_premier à son jour_dernier) touchent la fenêtre [jour_premier de l'achat − 730 jours ; "
    "jour_premier de l'achat[ (730 jours civils avant, le jour_premier lui-même exclu).",
    "Dates de transaction absentes d'une ligne passée : sa date de dépôt sert de date. jour_premier absent de l'achat "
    "actuel : sa date de dépôt sert de jour_premier_achat.",
    "Le formulaire actuel ne se compte pas lui-même (ses achats commencent au jour_premier, hors fenêtre) ; mais une vente "
    "du même formulaire, ou un autre formulaire, avec une transaction avant le jour_premier dans la fenêtre, brise le "
    "silence. Aucun historique = tout premier achat = accepté.",
    "Priorité le même jour : le plus gros montant. Égalité : ordre du banc (dépôt, numéro).",
    "Entrée : JOURS_ENTREE = 1 ; TOLERANCE_ENTREE = 5 (sans prix, 5 jours de bourse de plus, sinon le signal tombe).",
    "Sortie : DUREE = 126 jours de bourse après le jour d'achat réel ; TOLERANCE_SORTIE = 10 (puis dernier prix connu).",
    "Taille : MAX_POSITIONS = 5 (20 %) ; ARGENT_QUI_ATTEND = « SPY » ; LIQUIDE_JOURS = 0 ; "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 0. Places pleines : signal laissé tomber. Déjà en portefeuille : pas acheté.",
    "Banc, différent du texte : demi-écart achat-vente selon la valeur en bourse, à l'achat et à la vente, en plus des "
    "10 $ ; position = 20 % moins 10 $, plus petite s'il manque d'argent (sous MONTANT_MIN = 50 $, défaut du banc : pas "
    "d'achat) ; la priorité classe aussi les signaux qui attendent encore un prix ; rendement enchaîné si le CUSIP change.",
    "Harmonisation (6 oct. 2026, avant tout résultat) : « d'actions ordinaires » est une condition du texte, "
    "appliquée comme dans vitesse-* et gestion-* : au moins un des titres déclarés (champ titres) contient "
    "« common » ou « ordinary », sans tenir compte des majuscules ; seulement pour le formulaire qui donne le "
    "signal (les groupes et l'historique de l'initié ne changent pas).",
]

JOURS_ENTREE = 1
DUREE = 126
MAX_POSITIONS = 5
ARGENT_QUI_ATTEND = "SPY"
TOLERANCE_ENTREE = 5
TOLERANCE_SORTIE = 10
LIQUIDE_JOURS = 0
MONTANT_MIN = 50
UNE_ENTREE_PAR_SYMBOLE_JOURS = 0

SILENCE_JOURS = 730


def _base(e, montant_min):
    """La base commune de la piste : achat P, non routinier, hors plan 10b5-1, montant, taille de la compagnie."""
    if e.get("sens") != "achat":
        return False
    if e.get("routinier"):
        return False
    if e.get("plan_10b5_1") is True:
        return False
    m = e.get("montant")
    if m is None or m < montant_min:
        return False
    v = e.get("valeur_m")
    if v is None or v < 100 or v > 2000:
        return False
    return True


def _dirigeant_ou_administrateur(initie):
    roles = initie.get("roles") or []
    return "dirigeant" in roles or "administrateur" in roles


def _silence(ctx, initie_cik, cie, jour_ref, jours):
    """Vrai si l'initié n'a ni acheté ni vendu en bourse dans la compagnie pendant les `jours` jours civils avant
    `jour_ref` (d'après les dépôts connus le jour de la décision)."""
    debut = (date.fromisoformat(jour_ref) - timedelta(days=jours)).isoformat()
    for r in ctx.historique_initie(initie_cik):
        if r[1] != cie or r[3] not in ("achat", "vente"):
            continue
        premier = r[4] or r[0]
        dernier = r[5] or premier
        if premier < jour_ref and dernier >= debut:
            return False
    return True


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not _base(e, 25_000):
        return False
    jour_ref = e.get("jour_premier") or e["depot"]
    return any(_dirigeant_ou_administrateur(i) and _silence(ctx, i["cik"], e["cik"], jour_ref, SILENCE_JOURS)
               for i in e.get("inities") or []) and _actions_ordinaires(e)


def priorite(e, ctx):
    return float(e.get("montant") or 0.0)
