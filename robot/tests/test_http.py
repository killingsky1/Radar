import pytest

from radar.http import ClientPoli, ErreurSource


class Reponse:
    def __init__(self, code, contenu=b"ok", entetes=None):
        self.status_code = code
        self.content = contenu
        self.headers = entetes or {}


class FausseSession:
    def __init__(self, reponses):
        self.reponses = list(reponses)
        self.appels = []

    def get(self, url, headers, timeout):
        self.appels.append((url, headers))
        r = self.reponses.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class Horloge:
    def __init__(self):
        self.t = 0.0
        self.pauses = []

    def __call__(self):
        return self.t

    def dormir(self, s):
        self.pauses.append(s)
        self.t += s


def client(reponses, contact="mathieu@example.com"):
    h = Horloge()
    session = FausseSession(reponses)
    return ClientPoli(contact, session=session, dormir=h.dormir, horloge=h), session, h


def test_le_robot_s_identifie_dans_chaque_requete():
    c, session, _ = client([Reponse(200)])
    c.get("https://www.federalregister.gov/api/v1/documents.json")
    entetes = session.appels[0][1]
    assert "Radar" in entetes["User-Agent"] and "mathieu@example.com" in entetes["User-Agent"]


def test_sec_refusee_sans_courriel():
    c, session, _ = client([Reponse(200)], contact="")
    with pytest.raises(ErreurSource, match="SEC"):
        c.get("https://www.sec.gov/Archives/edgar/daily-index/")
    assert session.appels == []


def test_reessaie_quand_le_site_est_occupe():
    c, session, h = client([Reponse(503, entetes={"Retry-After": "3"}), Reponse(200, b"donnees")])
    t = c.get("https://www.sec.gov/x")
    assert t.statut == 200 and t.contenu == b"donnees" and len(t.sha256) == 64
    assert len(session.appels) == 2 and 3.0 in h.pauses


def test_page_introuvable_ne_reessaie_pas():
    c, session, _ = client([Reponse(404), Reponse(200)])
    with pytest.raises(ErreurSource, match="404"):
        c.get("https://www.sec.gov/x")
    assert len(session.appels) == 1


def test_coupure_reseau_puis_succes():
    c, session, _ = client([ConnectionError("coupé"), Reponse(200)])
    assert c.get("https://www.war.gov/News/Contracts/").statut == 200
    assert len(session.appels) == 2


def test_abandonne_apres_plusieurs_essais():
    c, session, _ = client([Reponse(500)] * 4)
    with pytest.raises(ErreurSource, match="500"):
        c.get("https://www.sec.gov/x")
    assert len(session.appels) == 4


def test_vitesse_limitee_a_la_sec():
    c, _, h = client([Reponse(200), Reponse(200)])
    c.get("https://www.sec.gov/a")
    c.get("https://data.sec.gov/b")  # même domaine racine : doit attendre son tour
    assert h.pauses and abs(h.pauses[-1] - 0.2) < 1e-9  # 5 requêtes/seconde
