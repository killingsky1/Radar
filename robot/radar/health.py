"""État de santé de chaque source. Principe : rien plutôt que faux."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from .registry import SOURCES

LIBELLES = {
    "a_venir": "À venir",
    "ok": "OK",
    "en_retard": "En retard",
    "en_panne": "En panne",
    "en_pause": "En pause",
    "ecartee": "Laissée de côté",
}


def statut(source_id: str, etat: dict | None, branchee: bool, maintenant: datetime) -> tuple[str, str]:
    """Retourne (code, explication) pour une source."""
    src = SOURCES[source_id]
    if src.ecartee:
        return "ecartee", src.ecartee
    if not branchee:
        return "a_venir", f"Prévue à la phase {src.phase}."
    etat = etat or {}
    if etat.get("pause"):
        return "en_pause", etat.get("raison_pause") or "Mise en pause."

    limite = timedelta(hours=src.attente_heures)
    succes = etat.get("dernier_succes")
    erreur = etat.get("derniere_erreur")
    if succes is None or maintenant - datetime.fromisoformat(succes) > limite:
        if erreur:
            return "en_panne", f"Dernière erreur : {erreur}"
        return "en_retard", "Pas de lecture réussie récemment."

    # La lecture marche, mais la source publie-t-elle encore ? (ex. fermeture du gouvernement)
    contenu = etat.get("dernier_contenu")
    if src.publication_max_jours and contenu:
        silence = (maintenant.date() - date.fromisoformat(contenu)).days
        if silence > src.publication_max_jours:
            return "en_pause", f"Rien de publié depuis {silence} jours (fermeture du gouvernement ?)."

    if erreur:
        return "ok", f"Lecture OK récemment, mais le dernier essai a échoué : {erreur}"
    return "ok", ""
