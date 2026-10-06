"""groupes-4 — 13D et achat d'un dirigeant ou administrateur sur la même compagnie à 90 jours ou moins d'écart,
garder 6 mois.

Programmé tel qu'écrit dans labo/tournoi/regles_preenregistrees.json (piste « groupes »).
Signal sur une compagnie quand les DEUX sont vrais, avec 90 jours civils ou moins entre les deux dates de dépôt (dans
un sens ou dans l'autre) : (A) un 13D initial ; (B) un formulaire 4 d'achat en bourse d'un dirigeant ou administrateur,
d'au moins 25 000 $, routinier = non, plan_10b5_1 = non ou vide. En plus : valeur en bourse >= 100 M$ à la date de
décision (la plus récente des deux dates de dépôt) ; pas d'autre signal groupes-4 sur la compagnie dans les 365 jours
avant ; 13G ignorés.
Entrée : clôture SEC du 1er jour de bourse après le dépôt du plus récent des deux, sinon la 1re des 5 jours de bourse
suivants. Sortie : 126e jour de bourse après l'achat. 10 places de 10 % ; le même jour, le plus gros montant d'achat
d'initié d'abord ; argent qui attend dans SPY.

LIMITE DU BANC : il n'achète qu'au lendemain d'un formulaire 4. Quand le 13D est le plus récent des deux, l'entrée au
lendemain du 13D n'est possible que si un formulaire 4 de la même compagnie est déposé le jour même (voir CHOIX).
"""
from datetime import date, timedelta

ID = "groupes-4"

CHOIX = [
    "(A) 13D initial = forme « 13D » des dépôts 13D/13G de la compagnie (ctx.depots_13). Le jeu sépare l'original (SC 13D, "
    "SCHEDULE 13D) de la modification (« 13D/A ») : la solution « à défaut » du texte (1er 13D sans autre 13D dans les "
    "365 jours) ne sert donc pas. 13D/A, 13G et 13G/A ignorés. « Sur la compagnie » = les 13D que le jeu attribue à ce "
    "cik (le jeu compte aussi, rarement, une compagnie cotée qui est elle-même le déposant).",
    "[REMPLACÉ le 6 oct. 2026 : voir « Harmonisation » à la fin de CHOIX] (B) Achat : formulaire sens = achat (code P ; le champ titres n'est pas filtré, le texte ne donne pas de liste de "
    "titres), au moins un déclarant « dirigeant » ou « administrateur », montant >= 25 000 $ (absent = écarté), champ "
    "routinier faux (vrai si un des déclarants est routinier ; sans historique, le jeu met faux), plan_10b5_1 différent "
    "de vrai (faux et vide passent, quelle que soit la date).",
    "Paire : un 13D initial et un achat (B) de la même compagnie (cik ; un achat sans symbole lisible compte aussi), "
    "déposés à 90 jours civils ou moins l'un de l'autre, dans un sens ou dans l'autre (le même jour compris). Date de "
    "décision J = la plus récente des deux dates de dépôt ; tout ce qui sert à décider est déposé au plus tard le jour J.",
    "Valeur en bourse à la date J : la valeur_m du dernier formulaire 4 de la compagnie (achat ou vente, ordre du banc) "
    "déposé de J-30 à J qui en a une (quand l'achat (B) est déposé le jour J, c'est la valeur_m des formulaires de ce "
    "jour) ; à défaut, « comme dans groupes-3 » : actions_circulation du dernier formulaire 4 qui en a (fait XBRL déjà "
    "déposé) × dernière clôture SEC connue au plus tard J, sans limite d'âge. La règle « fin de période d'au moins 45 "
    "jours » n'est pas appliquée : le jeu donne les actions XBRL d'après leur date de dépôt (pas leur fin de période), "
    "et un fait déjà déposé ne vient pas du futur. Valeur inconnue : pas de signal.",
    "365 jours : un signal = une date de décision J qui remplit tout, sans autre signal sur la même compagnie (cik) du "
    "jour J-365 au jour J-1 ; calculé de proche en proche depuis le début des données ; au plus un signal par date.",
    "LIMITE DU BANC, cas « achat d'initié puis 13D » (le 13D est le plus récent des deux) : le banc n'achète qu'au "
    "lendemain d'un formulaire 4. L'achat prévu au 1er jour de bourse après le 13D n'est donc possible que si un "
    "formulaire 4 de la même compagnie (achat ou vente, avec symbole) est déposé le jour même du 13D : ce formulaire "
    "« porte » alors le signal (même jour d'entrée que le texte). Sans un tel formulaire, le signal est perdu (pas "
    "acheté), mais il compte quand même pour la règle des 365 jours, comme dans le texte. Le cas « 13D puis achat » "
    "(l'achat est le plus récent) est complet.",
    "Porteur : le signal d'une date J est gardé sur le PREMIER achat (B) avec symbole déposé le jour J (cas 1 : c'est le "
    "formulaire 4 de la paire, le plus récent des deux) ; s'il n'y en a pas (cas 2 seul, ou achats B sans symbole), sur "
    "le PREMIER formulaire 4 (avec symbole) de la compagnie déposé le jour J, dans l'ordre de lecture du banc (date, puis "
    "numéro) ; les autres dépôts du jour ne sont pas gardés (un seul achat par signal). Le banc achète le symbole de ce "
    "formulaire.",
    "Priorité : le plus gros montant parmi les achats (B) des paires de cette date de décision. Le banc classe ainsi tous "
    "les signaux achetables ce jour-là (ceux du jour et ceux qui attendent encore un prix).",
    "Entrée (banc) : clôture SEC du 1er jour de bourse après le dépôt du porteur, c'est-à-dire après la date de décision "
    "(JOURS_ENTREE = 1) ; sans prix ce jour-là, le banc réessaie les 5 jours de bourse suivants (TOLERANCE_ENTREE = 5), "
    "sinon pas d'achat.",
    "Sortie (banc) : clôture du 126e jour de bourse après le jour d'achat (DUREE = 126) ; sans prix ce jour-là, 1re "
    "clôture des 10 jours de bourse suivants, sinon la dernière clôture connue (TOLERANCE_SORTIE = 10, défaut du banc : "
    "le texte ne dit pas après combien de jours la compagnie a « disparu »).",
    "Taille (banc) : MAX_POSITIONS = 10, chaque achat = valeur du portefeuille ÷ 10 (frais compris) ; places pleines : "
    "signal ignoré ; une position de moins de 50 $ n'est pas achetée (MONTANT_MIN du banc, laissé par défaut).",
    "Une seule position par compagnie : le banc l'applique par symbole (garder ne voit pas le portefeuille).",
    "Argent qui attend : SPY, 10 $ par transaction SPY. Le banc ajoute aussi, pour toutes les règles, le demi-écart "
    "achat-vente selon la valeur en bourse.",
    "CONCILIATION avec le vérificateur (6 octobre 2026, selon le texte ; mêmes choix dans les deux fichiers) : "
    "(a) porteur : quand un achat (B) est déposé le jour J, c'est LUI qui porte le signal (le texte : le formulaire 4 de "
    "la paire est le plus récent des deux), même si un autre formulaire 4 de la compagnie est lu avant lui ce jour-là ; "
    "corrigé ici (avant : le 1er formulaire 4 du jour, même une vente). (b) valeur en bourse : la valeur_m la plus "
    "récente des formulaires 4 déposés de J-30 à J, sinon, « à défaut » comme le dit le texte, la valeur calculée comme "
    "dans groupes-3 (actions XBRL déjà déposées du dernier formulaire 4 avec symbole qui en a × dernière clôture SEC "
    "connue au plus tard J) ; le vérificateur, qui n'avait pas ce calcul, est corrigé. (c) priorité : le plus gros "
    "montant parmi TOUS les achats (B) des paires du jour (« le plus gros montant d'achat d'initié ») ; le vérificateur, "
    "qui prenait le montant du porteur dans le cas 1, est corrigé.",
    "Harmonisation (6 oct. 2026, avant tout résultat) : « d'actions ordinaires » est une condition du texte, "
    "appliquée comme dans vitesse-* et gestion-* : au moins un des titres déclarés (champ titres) contient "
    "« common » ou « ordinary », sans tenir compte des majuscules ; seulement pour le formulaire qui donne le "
    "signal (les groupes et l'historique de l'initié ne changent pas).",
]

JOURS_ENTREE = 1
TOLERANCE_ENTREE = 5
DUREE = 126
TOLERANCE_SORTIE = 10
MAX_POSITIONS = 10
ARGENT_QUI_ATTEND = "SPY"

_ECART_MAX = 90             # jours civils entre le 13D initial et l'achat (B)
_MIN_MONTANT = 25_000       # $
_VALEUR_MIN_M = 100         # M$
_FENETRE_VALEUR_M = 30      # jours civils : valeur_m d'un formulaire 4 des 30 derniers jours (comme groupes-3)
_SANS_NOUVEAU_SIGNAL = 365  # jours civils

# Cache de calculs (permis) : (cik, date de décision) → signal ? Ne dépend que des dépôts faits au plus tard ce jour-là.
_statut_de = {}


def _jours_avant(jour, n):
    return (date.fromisoformat(jour) - timedelta(days=n)).isoformat()


def _dirigeant_ou_admin(x):
    return any("dirigeant" in (i.get("roles") or []) or "administrateur" in (i.get("roles") or [])
               for i in x.get("inities") or [])


def _achat_b(x):
    """(B) : achat d'un dirigeant ou administrateur, >= 25 000 $, non routinier, sans plan 10b5-1."""
    return (x.get("sens") == "achat" and _dirigeant_ou_admin(x) and (x.get("montant") or 0) >= _MIN_MONTANT
            and x.get("routinier") is False and x.get("plan_10b5_1") is not True)


def _decisions(evs, treize, jusqu_a):
    """{date de décision : [achats (B) des paires dont c'est la date]}, pour les dates au plus tard `jusqu_a`.
    `evs` : dépôts de la compagnie triés (date, numéro) ; `treize` : [(date, forme)] des 13D/13G de la compagnie."""
    achats = [x for x in evs if x["depot"] <= jusqu_a and _achat_b(x)]
    d13 = sorted({j for j, f in treize if f == "13D" and j <= jusqu_a})
    sortie = {}
    for x in achats:  # l'achat est le plus récent des deux (ou le même jour) : un 13D initial déposé de J-90 à J
        bas = _jours_avant(x["depot"], _ECART_MAX)
        if any(bas <= j <= x["depot"] for j in d13):
            sortie.setdefault(x["depot"], []).append(x)
    for j in d13:  # le 13D est le plus récent des deux (ou le même jour) : un achat (B) déposé de J-90 à J
        bas = _jours_avant(j, _ECART_MAX)
        paires = [x for x in achats if bas <= x["depot"] <= j]
        if paires:
            sortie.setdefault(j, []).extend(paires)
    return sortie


def _valeur(evs, jour, ctx):
    """Valeur en bourse (M$) à la date de décision : valeur_m du dernier formulaire 4 de la compagnie déposé de J-30 à J
    qui en a une ; à défaut, actions_circulation du dernier formulaire 4 qui en a × dernière clôture SEC connue."""
    bas = _jours_avant(jour, _FENETRE_VALEUR_M)
    v, a = None, None
    for x in evs:
        if x["depot"] > jour:
            break
        if x.get("valeur_m") is not None and x["depot"] >= bas:
            v = x["valeur_m"]
        if x.get("actions_circulation") and x.get("symbole"):
            a = x
    if v is not None:
        return v
    if a is None:
        return None
    c = ctx.cloture(a["symbole"], jour, tolerance_jours=10 ** 6)
    return a["actions_circulation"] * c[1] / 1e6 if c else None


def _signaux(cik, ctx):
    """{date de signal : plus gros montant d'achat (B)} de la compagnie jusqu'au jour de ctx, de proche en proche (règle
    des 365 jours), y compris les signaux que le banc ne peut pas acheter (sans porteur)."""
    evs = ctx.evenements_avant(cik, "0000-00-00")  # triés (date de dépôt, numéro), jusqu'au jour de décision
    decisions = _decisions(evs, ctx.depots_13(cik, "0000-00-00"), ctx.jour)
    dernier, sortie = None, {}
    for j in sorted(decisions):
        s = _statut_de.get((cik, j))
        if s is None:
            v = _valeur(evs, j, ctx)
            s = (v is not None and v >= _VALEUR_MIN_M
                 and (dernier is None or dernier < _jours_avant(j, _SANS_NOUVEAU_SIGNAL)))
            _statut_de[(cik, j)] = s
        if s:
            dernier = j
            sortie[j] = max(x.get("montant") or 0.0 for x in decisions[j])
    return sortie


def _actions_ordinaires(e):
    return any("common" in (t or "").lower() or "ordinary" in (t or "").lower() for t in e.get("titres") or [])


def garder(e, ctx):
    t, cik = e["depot"], e["cik"]
    # Dans les deux cas, il faut un 13D initial de la compagnie déposé de J-90 à J (tri rapide).
    if not any(f == "13D" for _, f in ctx.depots_13(cik, _jours_avant(t, _ECART_MAX))):
        return False
    # Porteur du signal du jour J : le 1er achat (B) avec symbole déposé ce jour-là (cas 1 : c'est le formulaire 4 de la
    # paire) ; à défaut, le 1er formulaire 4 (avec symbole) de la compagnie déposé ce jour-là (ordre du banc).
    du_jour = [x for x in ctx.evenements_avant(cik, t) if x.get("symbole")]
    porteur = next((x for x in du_jour if _achat_b(x)), du_jour[0] if du_jour else None)
    if porteur is None or porteur["id"] != e["id"]:
        return False
    # « D'actions ordinaires » : vérifié si le formulaire gardé est un achat (porteur du cas 2 : parfois une vente)
    return t in _signaux(cik, ctx) and (e.get("sens") != "achat" or _actions_ordinaires(e))


def priorite(e, ctx):
    """Le plus gros montant d'achat d'initié (B) des paires de cette date de décision."""
    return _signaux(e["cik"], ctx).get(e["depot"], 0.0)
