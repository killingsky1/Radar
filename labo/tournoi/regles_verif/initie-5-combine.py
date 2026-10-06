"""initie-5-combine : PDG ou directeur financier, premier achat depuis 1 an, part ajoutée d'au moins 10 %
(programmation du VÉRIFICATEUR).

Texte pré-enregistré (regles_preenregistrees.json) : achat P d'actions ordinaires ; le titre contient CEO, Chief
Executive, Principal Executive, CFO, Chief Financial ou Principal Financial (sans tenir compte des majuscules) ;
routinier = non ; plan_10b5_1 différent de oui ; montant ≥ 25 000 $ ; part_ajoutee ≥ 0,10 (rempli s'il ne détenait
rien avant) ; valeur_m entre 100 et 2 000 M$ ; aucun achat P ni vente S de cet initié dans cette compagnie pendant les
365 jours civils avant le jour_premier_achat ; pas d'action déjà en portefeuille ; le même jour : directeur financier
d'abord, puis la plus grande part_ajoutee. Entrée, sortie, taille : comme initie-1 (126 jours de bourse, 5 positions de
20 %, SPY).
"""
from datetime import date, timedelta

ID = "initie-5-combine"
IMPOSSIBLE = None

CHOIX = [
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] « Achat P d'actions ordinaires » = un événement « achat » du jeu (code P, titres non dérivés). Le champ « titres » "
    "n'est pas filtré : il n'est pas dans les champs de la règle.",
    "Titre : le texte de e['inities'][i]['titre'] contient, sans tenir compte des majuscules, « ceo », « chief "
    "executive », « principal executive », « cfo », « chief financial » ou « principal financial » (comme initie-1). "
    "Simple recherche de texte, sans autre nettoyage. Le champ « roles » n'est pas vérifié (pas dans le filtre).",
    "Plusieurs déclarants : le formulaire est gardé si UN déclarant a à la fois le titre ET le silence de 365 jours.",
    "routinier = non : e['routinier'] faux. plan_10b5_1 différent de oui : true refusé ; false et vide (null) acceptés.",
    "montant ≥ 25 000 $ et 100 ≤ valeur_m ≤ 2 000 (M$), bornes comprises ; montant ou valeur_m absent = refusé.",
    "part_ajoutee = e['part'] ≥ 0,10 ; ou bien e['nouvelle_position'] vrai (rien détenu avant : rempli, comme le texte). "
    "Détenues avant inconnues (part vide sans nouvelle position) : pas rempli, refusé.",
    "Silence : ctx.historique_initie(cik du déclarant) (dépôts faits au plus tard le jour de la décision), lignes de cette "
    "compagnie (même cik que e['cik']), sens « achat » ou « vente ». Une ligne brise le silence si ses dates de "
    "transaction (de son jour_premier à son jour_dernier) touchent la fenêtre [jour_premier de l'achat − 365 jours ; "
    "jour_premier de l'achat[ (365 jours civils avant, le jour_premier lui-même exclu). Aucun historique = accepté.",
    "Dates de transaction absentes d'une ligne passée : sa date de dépôt sert de date. jour_premier absent de l'achat "
    "actuel : sa date de dépôt sert de jour_premier_achat. Une vente du même formulaire faite avant le jour_premier de "
    "l'achat brise le silence.",
    "Priorité le même jour : directeur financier d'abord (un déclarant retenu dont le titre contient cfo, chief "
    "financial ou principal financial), puis la plus grande part_ajoutee ; une nouvelle position compte comme la plus "
    "grande part (infinie). Calcul : 10^9 si directeur financier, plus 2 × 10^8 pour une nouvelle position, sinon la "
    "part (plafonnée à 10^8 dans ce calcul). Égalité : ordre du banc (dépôt, numéro).",
    "Entrée : JOURS_ENTREE = 1 ; TOLERANCE_ENTREE = 5 (sans prix, 5 jours de bourse de plus, sinon le signal tombe).",
    "Sortie : DUREE = 126 jours de bourse après le jour d'achat réel ; TOLERANCE_SORTIE = 10 (puis dernier prix connu).",
    "Taille : MAX_POSITIONS = 5 (20 %) ; ARGENT_QUI_ATTEND = « SPY » ; LIQUIDE_JOURS = 0 ; "
    "UNE_ENTREE_PAR_SYMBOLE_JOURS = 0. Places pleines : signal laissé tomber. Déjà en portefeuille : pas acheté.",
    "Banc, différent du texte : demi-écart achat-vente selon la valeur en bourse, à l'achat et à la vente, en plus des "
    "10 $ ; position = 20 % moins 10 $, plus petite s'il manque d'argent (sous MONTANT_MIN = 50 $, défaut du banc : pas "
    "d'achat) ; la priorité classe aussi les signaux qui attendent encore un prix ; rendement enchaîné si le CUSIP change.",
    "Comparaison des deux programmations (jeu ciblé, 5 places : le même jour, 7 achats de PDG, parts de 2 à 500 "
    "millions et une nouvelle position ; puis 6 achats de directeurs financiers, 5 parts de 150 à 550 millions et une "
    "nouvelle position) : le testeur donnait 10^8 à une nouvelle position, à égalité avec une part ≥ 10^8 ; le "
    "vérificateur plafonnait la part à 999 999, donc les parts plus grandes étaient à égalité. Le texte : « la plus "
    "grande part_ajoutee », et une nouvelle position (rien avant) compte comme la plus grande (part infinie). Calcul "
    "commun : 10^9 si directeur financier, plus 2 × 10^8 pour une nouvelle position, sinon la part plafonnée à 10^8 "
    "(les deux corrigés). Au-delà de 10^8, deux parts comptent comme égales (ordre du banc).",
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

MOTS_PDG = ("ceo", "chief executive", "principal executive")
MOTS_DFO = ("cfo", "chief financial", "principal financial")
PART_MIN = 0.10
SILENCE_JOURS = 365


def _titre_contient(initie, mots):
    t = (initie.get("titre") or "").lower()
    return any(m in t for m in mots)


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


def _part(e):
    """part_ajoutee pour le filtre et la priorité : 2 × 10^8 pour une nouvelle position (rien avant), None si inconnue."""
    if e.get("part") is not None:
        return min(float(e["part"]), 1e8)
    if e.get("nouvelle_position"):
        return 2e8
    return None


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


def _retenus(e, ctx):
    """Les déclarants qui ont le titre de PDG ou de directeur financier ET le silence de 365 jours."""
    jour_ref = e.get("jour_premier") or e["depot"]
    return [i for i in e.get("inities") or []
            if (_titre_contient(i, MOTS_PDG) or _titre_contient(i, MOTS_DFO))
            and _silence(ctx, i["cik"], e["cik"], jour_ref, SILENCE_JOURS)]


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    if not _base(e, 25_000):
        return False
    p = _part(e)
    if p is None or p < PART_MIN:
        return False
    return bool(_retenus(e, ctx)) and _actions_ordinaires(e)


def priorite(e, ctx):
    dfo = any(_titre_contient(i, MOTS_DFO) for i in _retenus(e, ctx))
    return (1e9 if dfo else 0.0) + (_part(e) or 0.0)
