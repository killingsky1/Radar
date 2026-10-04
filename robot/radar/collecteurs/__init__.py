"""Un lecteur (collecteur) par source. Chaque phase en ajoute.

Un collecteur reçoit le contexte (client web, date) et retourne une liste d'Evenement.
S'il lève une exception, seule sa source tombe « en panne » ; les autres continuent.
"""

from __future__ import annotations

from collections.abc import Callable

from ..models import Evenement

Collecteur = Callable[["object"], list[Evenement]]

from . import (banques, blocage, canada, canada_eco, ccc, cftc, congres, contrats_ca, douane, elus, fda,  # noqa: E402
               fonds13f, gazette, legisinfo, lobbying, maison_blanche, oge, participations, prix_sec, rachats,
               registre, regulateurs, sante, sante_canada, sec, tresor, usaspending)

# L'ordre compte : les lecteurs SEC chargent la liste officielle des symboles, réutilisée ensuite.
COLLECTEURS: dict[str, Collecteur] = {
    "sec_form4": sec.collecter_form4,
    "sec_form144": sec.collecter_144,
    "sec_8k": sec.collecter_8k,
    "sec_13dg": sec.collecter_13dg,
    "sec_13f": fonds13f.collecter,
    "sec_offres": sec.collecter_offres,
    "sec_blocage": blocage.collecter,  # 1re lecture : rattrapage des prospectus d'avril à septembre 2026
    "sec_ftd": prix_sec.collecter,  # prix pour mesurer les résultats de Radar (jamais un signal)
    "sec_rachats_xbrl": rachats.collecter_xbrl,  # rachats faits (rapports annuels) : un seul fichier de l'API de la SEC
    "sec_sante": sante.collecter,  # santé financière (9 critères de Piotroski) : dernier rapport annuel (companyfacts)
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
    "oge_278t": oge.collecter,
    "lobbying": lobbying.collecter,  # lit les listes du score précédent (data/app/aujourdhui.json)
    "nouvelles_defense_ca": canada.collecter_defense,
    "nouvelles_eco_ca": canada.collecter_economie,
    "concurrence_ca": canada_eco.collecter_concurrence,
    "sanctions_ca": canada_eco.collecter_sanctions,
    "statcan": canada_eco.collecter_statcan,
    "gazette_ca": gazette.collecter_reglements,  # les 2 sources de la Gazette se partagent une seule lecture
    "grands_projets_ca": gazette.collecter_projets,
    "legisinfo": legisinfo.collecter,
    "sante_canada": sante_canada.collecter,
    "contrats_ca_10k": contrats_ca.collecter,  # 1re lecture d'un trimestre : silencieuse (voir contrats_ca.py)
    "ccc": ccc.collecter,
    "tresor": tresor.collecter,  # état mensuel : 1re lecture silencieuse (voir tresor.py)
    "tarifs": douane.collecter,
    "usaspending": usaspending.collecter,  # 1re lecture silencieuse (voir usaspending.py)
    "participations_gouv": participations.collecter,  # après sec_8k : réutilise les en-têtes déjà lus
    "sec_rachats": rachats.collecter,  # après participations_gouv : réutilise les documents 8.01 déjà lus
}
