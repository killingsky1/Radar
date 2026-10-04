"""Essais hors ligne de labo/acces.py (aucun réseau : urlopen est imité)."""
import http.client
import importlib
import io
import os
import subprocess
import tempfile
import sys
import textwrap
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

LABO = Path(__file__).resolve().parent
sys.path.insert(0, str(LABO))


def charger(**env):
    for k in ("LABO_PANNE", "LABO_ATTENTES"):
        os.environ.pop(k, None)
    os.environ.update(env)
    import acces
    return importlib.reload(acces)


class Faux:
    """Une suite de comportements, un par appel : bytes = réponse, int = code HTTP, Exception = erreur réseau."""
    def __init__(self, *suite):
        self.suite, self.appels = list(suite), 0

    def __call__(self, requete, timeout=None):
        self.appels += 1
        x = self.suite.pop(0)
        url = requete.full_url if hasattr(requete, "full_url") else requete
        if isinstance(x, int):
            raise urllib.error.HTTPError(url, x, "x", Message(), io.BytesIO(b""))
        if isinstance(x, Exception):
            raise x
        corps = x

        class R:
            headers, status = Message(), 200
            def geturl(self): return url
            def read(self, *_):
                if corps == b"COUPE":
                    raise http.client.IncompleteRead(b"par", 10)
                return corps
            def __enter__(self): return self
            def __exit__(self, *_): return False
        return R()


def essai(nom, f):
    try:
        f()
        print("OK    ", nom)
    except AssertionError as exc:
        print("ÉCHEC ", nom, exc)
        global echecs
        echecs += 1


echecs = 0
URL = "https://api.usaspending.gov/robots.txt"


def t1():
    a = charger(); dodos = []; a.dormir = dodos.append
    urllib.request.urlopen = Faux(http.client.RemoteDisconnected("x"), http.client.RemoteDisconnected("x"), b"ok")
    assert a.ouvrir(urllib.request.Request(URL)).read() == b"ok" and dodos == [15.0, 60.0], dodos
essai("connexion coupée 2 fois puis réponse : 2 nouveaux essais (15 s, 60 s), puis lu", t1)


def t2():
    a = charger(); dodos = []; a.dormir = dodos.append
    f = Faux(*[http.client.RemoteDisconnected("x")] * 3)
    urllib.request.urlopen = f
    try:
        a.ouvrir(urllib.request.Request(URL)); assert False, "pas d'exception"
    except a.NonVerifiable as exc:
        assert "ne répond pas après 3 essais" in str(exc) and "RemoteDisconnected" in str(exc), exc
    assert f.appels == 3 and dodos == [15.0, 60.0]
    try:
        a.ouvrir(urllib.request.Request("https://api.usaspending.gov/api/v2/x")); assert False
    except a.NonVerifiable:
        pass
    assert f.appels == 3, "site en panne : plus aucune requête"
essai("toujours coupée : non vérifiable après 3 essais, puis plus aucune requête vers ce site", t2)


def t3():
    a = charger(); dodos = []; a.dormir = dodos.append
    f = Faux(403); urllib.request.urlopen = f
    try:
        a.ouvrir(urllib.request.Request(URL)); assert False
    except a.NonVerifiable as exc:
        assert "refuse" in str(exc) and "403" in str(exc)
    assert f.appels == 1 and dodos == [], "un refus n'est jamais réessayé"
essai("refus 403 : non vérifiable tout de suite, sans nouvel essai", t3)


def t4():
    a = charger(); a.dormir = lambda s: None
    urllib.request.urlopen = Faux(404)
    try:
        a.ouvrir(urllib.request.Request(URL)); assert False
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
    assert "api.usaspending.gov" not in a.EN_PANNE
essai("404 (pas de robots.txt) : passe tel quel, comme avant (tout est permis)", t4)


def t5():
    a = charger(); dodos = []; a.dormir = dodos.append
    urllib.request.urlopen = Faux(503, b"ok")
    assert a.ouvrir(urllib.request.Request(URL)).read() == b"ok" and dodos == [15.0]
essai("erreur 503 puis réponse : réessayé une fois après 15 s", t5)


def t6():
    a = charger(); dodos = []; a.dormir = dodos.append
    urllib.request.urlopen = Faux(b"COUPE", b"complet")
    assert a.ouvrir(urllib.request.Request(URL)).read() == b"complet" and dodos == [15.0]
essai("coupure au milieu du téléchargement : réessayé", t6)


def t7():
    a = charger(LABO_PANNE="api.usaspending.gov", LABO_ATTENTES="0,0"); a.dormir = lambda s: None
    f = Faux(b"sec"); urllib.request.urlopen = f
    try:
        a.ouvrir(urllib.request.Request(URL)); assert False
    except a.NonVerifiable:
        pass
    assert f.appels == 0, "panne simulée : aucun appel réseau"
    assert a.ouvrir(urllib.request.Request("https://www.sec.gov/x")).read() == b"sec" and f.appels == 1
essai("LABO_PANNE : seul le site nommé est en panne simulée, sans réseau ; les autres sont lus", t7)


def t8():
    a = charger()
    with a.section("USAspending"):
        raise a.NonVerifiable("api.usaspending.gov : le site ne répond pas")
    assert a.NON_VERIFIABLES == [("USAspending", "api.usaspending.gov : le site ne répond pas")]
    assert a.verdict([]) == "VERDICT : OK, sauf NON VÉRIFIABLE : USAspending"
    assert a.lignes_non_verifiables() == ["NON VÉRIFIABLE : USAspending : api.usaspending.gov : le site ne répond pas"]
    assert a.verdict(["un écart"]) == "VERDICT : PROBLÈME"
    try:
        with a.section("x"):
            raise ValueError("bogue")
        assert False
    except ValueError:
        pass
    b = charger()
    assert b.verdict([]) == "VERDICT : OK"
essai("section : un site en panne n'arrête que sa partie ; verdicts OK / OK sauf / PROBLÈME", t8)


def lancer(code):
    sortie = Path(tempfile.gettempdir()) / "essai_acces_sortie.txt"
    sortie.unlink(missing_ok=True)
    script = textwrap.dedent(f"""
        import sys; sys.path.insert(0, {str(LABO)!r})
        from pathlib import Path
        import acces
        lignes = ["- partie 1 vérifiée : OK"]
        acces.installer(lignes, Path({str(sortie)!r}))
        {code}
    """)
    r = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    return r.returncode, sortie.read_text(encoding="utf-8") if sortie.exists() else None


def t9():
    code, texte = lancer('raise acces.NonVerifiable("www.sec.gov : le site ne répond pas après 3 essais")')
    assert code == 0 and texte.splitlines()[0] == "- partie 1 vérifiée : OK", (code, texte)
    assert texte.strip().endswith("VERDICT : NON VÉRIFIABLE (arrêt : www.sec.gov : le site ne répond pas après 3 essais ; ce qui précède a été vérifié)"), texte
essai("arrêt sur un site en panne : fichier écrit (ce qui a été vérifié + NON VÉRIFIABLE), code 0", t9)


def t10():
    code, texte = lancer('raise ValueError("bogue du labo")')
    assert code == 1 and texte.strip().endswith("VERDICT : PROBLÈME (vérification arrêtée : ValueError: bogue du labo)"), (code, texte)
essai("autre arrêt (bogue) : fichier écrit avec PROBLÈME, code 1 (pour qu'on regarde)", t10)

print(f"\n{10 - echecs}/10 réussis")
sys.exit(1 if echecs else 0)
