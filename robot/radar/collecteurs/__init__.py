"""Un lecteur (collecteur) par source. Chaque phase en ajoute.

Un collecteur reçoit le contexte (client web, date) et retourne une liste d'Evenement.
S'il lève une exception, seule sa source tombe « en panne » ; les autres continuent.
"""

from __future__ import annotations

from collections.abc import Callable

from ..models import Evenement

Collecteur = Callable[["object"], list[Evenement]]

from . import banques, canada, cftc, congres, elus, fda, fonds13f, maison_blanche, registre, regulateurs, sec  # noqa: E402

# L'ordre compte : les lecteurs SEC chargent la liste officielle des symboles, réutilisée ensuite.
COLLECTEURS: dict[str, Collecteur] = {
    "sec_form4": sec.collecter_form4,
    "sec_form144": sec.collecter_144,
    "sec_8k": sec.collecter_8k,
    "sec_13dg": sec.collecter_13dg,
    "sec_13f": fonds13f.collecter,
    "sec_offres": sec.collecter_offres,
    "sec_poursuites": regulateurs.collecter_sec_poursuites,
    "cftc_cot": cftc.collecter,
    "maison_blanche": maison_blanche.collecter,
    "fda": fda.collecter,
    "nhtsa": regulateurs.collecter_nhtsa,
    "doj_antitrust": regulateurs.collecter_doj,
    "sanctions_us": regulateurs.collecter_ofac,
    "ftc_fusions": regulateurs.collecter_ftc,
    "fed": banques.collecter_fed,
    "banque_canada": banques.collecter_bdc,
    "registre_federal": registre.collecter_registre,
    "ventes_armes": registre.collecter_ventes_armes,
    "senat_ptr": elus.collecter_senat,
    "chambre_ptr": elus.collecter_chambre,
    "comites": congres.collecter_comites,
    "hr7008": congres.collecter_hr7008,  # avant « votes » : les votes viennent du statut du projet de loi
    "votes": congres.collecter_votes,
    "nouvelles_defense_ca": canada.collecter_defense,
    "nouvelles_eco_ca": canada.collecter_economie,
}
