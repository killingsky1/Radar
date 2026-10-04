"""Règles communes du labo quand un site ne répond pas ou refuse : « non vérifiable », jamais un plantage.

- Aucune réponse (connexion coupée, délai dépassé) ou erreur 5xx du site : 2 nouveaux essais, 15 s puis 60 s plus tard
  (ex. USAspending, 4 oct. 2026 : connexion coupée sans réponse en lisant robots.txt, puis normal au passage suivant).
  Toujours en panne : NonVerifiable.
- Refus (401/403) : NonVerifiable tout de suite, sans nouvel essai. On respecte, comme un robots.txt qui interdit.
- Un site déclaré non vérifiable le reste jusqu'à la fin du script : plus aucune requête vers lui.
- section(nom) : une partie de la vérification qui dépend d'un site ; s'il est en panne, elle est notée « non vérifiable »
  et la suite continue (les parties qui ne dépendent pas de ce site restent vérifiées).
- installer(lignes, sortie) : si le script s'arrête quand même, son fichier est écrit avec ce qui a été vérifié et une
  ligne VERDICT (NON VÉRIFIABLE si un site ne répond pas, PROBLÈME sinon, pour qu'on regarde).
Essais hors ligne : LABO_PANNE (sites séparés par des virgules, ou *) simule une connexion coupée sans toucher au réseau ;
LABO_ATTENTES (ex. « 0,0 ») remplace les attentes entre les essais.
"""
import http.client
import os
import socket
import sys
import time
import traceback
import urllib.error
import urllib.request
from contextlib import contextmanager
from urllib.parse import urlparse

ATTENTES = tuple(float(x) for x in os.environ.get("LABO_ATTENTES", "15,60").split(","))
PANNE = {x.strip() for x in os.environ.get("LABO_PANNE", "").split(",") if x.strip()}
EN_PANNE: dict[str, str] = {}  # site → raison
NON_VERIFIABLES: list[tuple[str, str]] = []  # (partie, raison)
dormir = time.sleep


class NonVerifiable(Exception):
    """Le site ne répond pas (après les essais) ou refuse le robot : rien n'est relu, on le dit."""


class Reponse:
    """La réponse lue en entier pendant l'essai (une coupure au milieu du téléchargement est aussi réessayée)."""

    def __init__(self, r, contenu: bytes):
        self.headers, self.status, self.url, self._contenu = r.headers, r.status, r.geturl(), contenu

    def read(self, *_):
        return self._contenu

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _hote(requete) -> str:
    return urlparse(requete.full_url if hasattr(requete, "full_url") else str(requete)).netloc


def ouvrir(requete, timeout=60):
    """Comme urllib.request.urlopen, mais : nouveaux essais si pas de réponse ou erreur 5xx, puis NonVerifiable ;
    NonVerifiable tout de suite pour un refus (401/403). Les autres réponses (ex. 404) passent telles quelles."""
    hote = _hote(requete)
    if hote in EN_PANNE:
        raise NonVerifiable(f"{hote} : {EN_PANNE[hote]}")
    derniere = ""
    for i in range(len(ATTENTES) + 1):
        if i:
            dormir(ATTENTES[i - 1])
        try:
            if "*" in PANNE or hote in PANNE:
                raise http.client.RemoteDisconnected("Remote end closed connection without response (panne simulée)")
            with urllib.request.urlopen(requete, timeout=timeout) as r:
                return Reponse(r, r.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                EN_PANNE[hote] = f"le site refuse le robot (erreur {exc.code}) : on respecte"
                raise NonVerifiable(f"{hote} : {EN_PANNE[hote]}") from exc
            if exc.code < 500:
                raise
            derniere = f"erreur {exc.code} du site"
        except (urllib.error.URLError, http.client.HTTPException, socket.timeout, TimeoutError, ConnectionError) as exc:
            derniere = f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}"
    EN_PANNE[hote] = f"le site ne répond pas après {len(ATTENTES) + 1} essais ({derniere})"
    raise NonVerifiable(f"{hote} : {EN_PANNE[hote]}")


@contextmanager
def section(nom: str):
    """Une partie qui dépend d'un site : en panne → « non vérifiable », et la suite du script continue."""
    try:
        yield
    except NonVerifiable as exc:
        NON_VERIFIABLES.append((nom, str(exc)))
        print(f"NON VÉRIFIABLE : {nom} : {exc}", flush=True)


def lignes_non_verifiables() -> list[str]:
    return [f"NON VÉRIFIABLE : {nom} : {raison}" for nom, raison in NON_VERIFIABLES]


def verdict(ecarts) -> str:
    """La ligne VERDICT : PROBLÈME s'il y a un écart ; sinon OK, en nommant ce qui n'a pas pu être relu."""
    if ecarts:
        return "VERDICT : PROBLÈME"
    if NON_VERIFIABLES:
        return "VERDICT : OK, sauf NON VÉRIFIABLE : " + " ; ".join(nom for nom, _ in NON_VERIFIABLES)
    return "VERDICT : OK"


def installer(lignes: list, sortie):
    """Si le script s'arrête en cours de route, son fichier est quand même écrit, avec une ligne VERDICT."""
    def crochet(typ, exc, tb):
        if issubclass(typ, NonVerifiable):
            fin = [*lignes_non_verifiables(), f"VERDICT : NON VÉRIFIABLE (arrêt : {exc} ; ce qui précède a été vérifié)"]
            code = 0
        else:
            traceback.print_exception(typ, exc, tb)
            fin = [f"VERDICT : PROBLÈME (vérification arrêtée : {typ.__name__}: {str(exc)[:300]})"]
            code = 1
        for ligne in fin:
            print(ligne, flush=True)
        try:
            sortie.write_text("\n".join([*lignes, *fin]) + "\n", encoding="utf-8")
        finally:
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(code)
    sys.excepthook = crochet
