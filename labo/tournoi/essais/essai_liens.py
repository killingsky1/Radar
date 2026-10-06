"""Essai hors ligne de verif_liens.py : de faux sites sur cette machine (127.0.0.1), où la bonne réponse est connue.

Vérifie surtout les règles de politesse : robots.txt (interdit, absent, illisible, refusé), Crawl-delay, redirections
vérifiées avant d'être suivies, aucune requête vers une adresse interdite, agent « Radar projet personnel » sans courriel.
"""
import hashlib
import importlib
import json
import os
import shutil
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ICI = Path(__file__).resolve().parent
TMP = ICI / "tmp_liens"
ok = []


def verifier(nom, condition, detail=""):
    ok.append(bool(condition))
    print(f"{'OK    ' if condition else 'ÉCHEC '} {nom} {detail}")


JOURNAL = []  # (site, chemin, moment, agent)


def serveur(routes):
    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            site = f"127.0.0.1:{self.server.server_port}"
            JOURNAL.append((site, self.path, time.monotonic(), self.headers.get("User-Agent")))
            code, entetes, corps = routes(self.path)
            self.send_response(code)
            for k, v in entetes.items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(corps if isinstance(corps, bytes) else corps.encode())

        def log_message(self, *_):
            pass

    s = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, f"http://127.0.0.1:{s.server_port}"


HTML = {"Content-Type": "text/html; charset=utf-8"}
TEXTE = {"Content-Type": "text/plain"}
PAGE_BROCHET = ('<html><head><meta name="citation_title" content="Information Content of Insider Trades before and '
                'after the Sarbanes-Oxley Act"><title>SSRN</title></head><body>…</body></html>')

# Site B : tout interdit ; site C : pas de robots.txt (404) ; site D : robots.txt refusé (403) ; site E : robots.txt = page web
B, b = serveur(lambda p: (200, TEXTE, "User-agent: *\nDisallow: /\n") if p == "/robots.txt" else (200, HTML, "<title>x</title>"))
C, c = serveur(lambda p: (404, TEXTE, "") if p == "/robots.txt" else
               (200, HTML, "<html><title>Are Insider Trades Informative? | The Review of Financial Studies</title></html>"))
D, d = serveur(lambda p: (403, TEXTE, "refusé"))
E, e = serveur(lambda p: (200, HTML, "<html><title>Just a moment...</title></html>"))


def pdf(texte):
    """Un vrai petit PDF d'une page avec ce texte."""
    contenu = f"BT /F1 12 Tf 72 720 Td ({texte}) Tj ET".encode()
    objets = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
              b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
              b"<< /Length %d >>\nstream\n" % len(contenu) + contenu + b"\nendstream",
              b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    sortie, positions = b"%PDF-1.4\n", []
    for i, o in enumerate(objets, 1):
        positions.append(len(sortie))
        sortie += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(sortie)
    sortie += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objets) + 1) + b"".join(b"%010d 00000 n \n" % q for q in positions)
    return sortie + b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objets) + 1, xref)


PDF = {"Content-Type": "application/pdf"}


def route_a(p):
    if p == "/robots.txt":
        return 200, TEXTE, "User-agent: *\nDisallow: /prive\nCrawl-delay: 1\n"
    return {
        "/etude1": (200, HTML, PAGE_BROCHET),
        "/prive/etude2": (200, HTML, PAGE_BROCHET),
        "/mort": (404, HTML, "introuvable"),
        "/redir": (302, {"Location": f"{b}/page"}, ""),
        "/redir2": (301, {"Location": f"{c}/etude3"}, ""),
        "/generique": (200, HTML, "<html><title>Just a moment...</title><body>Checking your browser</body></html>"),
        "/papier.pdf": (200, PDF, pdf("Are Insider Trades Informative? Josef Lakonishok and Inmoo Lee")),
        "/abime.pdf": (200, PDF, b"%PDF-1.4 abime"),
        "/zhao": (200, HTML, '<html><head><meta name="citation_title" content="Insider Purchases Far Below the 52-Week High: '
                             'Decomposing the Disclosure Reaction in Microcap Equities"></head></html>'),
        "/accueil": (200, HTML, "<html><title>Home</title></html>"),
        "/texte": (200, HTML, "<html><title>Working papers</title><body><h1>Cohen Malloy Pomorski : Decoding Inside "
                              "Information</h1></body></html>"),
    }.get(p, (404, HTML, ""))


A, a = serveur(route_a)

# Faux Crossref : la bonne étude pour Brochet ; un mauvais auteur pour « Fantôme » ; rien de proche pour « Inventé »
CR_ITEMS = {
    "Brochet": [{"DOI": "10.2308/accr.2010.85.2.419", "title": ["Information Content of Insider Trades before and after "
                 "the Sarbanes-Oxley Act"], "author": [{"family": "Brochet"}], "issued": {"date-parts": [[2010]]},
                 "container-title": ["The Accounting Review"]}],
    "Fantôme": [{"DOI": "10.1/x", "title": ["Decoding Inside Information"], "author": [{"family": "Autre"}],
                 "issued": {"date-parts": [[2012]]}}],
    "Inventé": [{"DOI": "10.1/y", "title": ["Something Else Entirely"], "author": [{"family": "Inventé"}]}],
    "Lakonishok": [{"DOI": "10.1093/rfs/14.1.79", "title": ["Are Insider Trades Informative?"],
                    "author": [{"family": "Lakonishok"}, {"family": "Lee"}], "issued": {"date-parts": [[2001]]}}],
    "Cohen": [],
    "Zhao": [],  # comme arXiv : pas dans Crossref
    "Alldredge": [{"DOI": "10.1111/jfir.12172", "title": ["Do insiders cluster trades with colleagues? Evidence from daily insider trading"],
                   "author": [{"family": "Alldredge"}, {"family": "Blank"}], "issued": {"date-parts": [[2019]]},
                   "container-title": ["Journal of Financial Research"]}],
    "Vieux": [{"DOI": "10.1/z", "title": ["Something about clusters"], "author": [{"family": "Vieux"}],
               "issued": {"date-parts": [[2012]]}, "container-title": ["Journal of Financial Research"]}],
    "Mauvaisauteur": [{"DOI": "10.1093/epolic/eiaa012", "title": ["Anticipating the financial crisis: evidence from insider trading in banks"],
                       "author": [{"family": "Akin"}, {"family": "Marín"}, {"family": "Peydró"}], "issued": {"date-parts": [[2020]]}}],
    "Akbas": [{"DOI": "10.1111/jofi.12878", "title": ["Insider Investment Horizon"], "author": [{"family": "Akbas"}],
               "issued": {"date-parts": [[2020]]}, "container-title": ["The Journal of Finance"]}],
}


def route_cr(p):
    if p == "/robots.txt":
        return 200, TEXTE, "User-agent: *\nAllow: /\n"
    q = parse_qs(urlsplit(p).query).get("query.bibliographic", [""])[0]
    items = next((v for k, v in CR_ITEMS.items() if q.startswith(k)), [])
    return 200, {"Content-Type": "application/json"}, json.dumps({"message": {"items": items}})


CR, cr = serveur(route_cr)

REF_BROCHET = ("Brochet, F. (2010). Information Content of Insider Trades before and after the Sarbanes-Oxley Act. "
               "The Accounting Review 85(2), 419-446.")
REF_LAKO = "Lakonishok, J., & Lee, I. (2001). \"Are Insider Trades Informative?\" Review of Financial Studies 14(1), 79-111."
REF_COHEN = "Cohen, L., Malloy, C., & Pomorski, L. (2012). Decoding Inside Information. Journal of Finance 67(3)."
REF_ZHAO = ("Zhao, H. (2026). Insider Purchases Far Below the 52-Week High: Decomposing the Disclosure Reaction in Microcap "
            "Equities. arXiv 2602.06198 (v2, sept. 2026)")
REGLES = {"regles": [
    {"id": "r1", "etudes": [{"reference": REF_BROCHET, "lien": f"{a}/etude1"},
                            {"reference": REF_BROCHET, "lien": f"{a}/prive/etude2"}]},
    {"id": "r2", "etudes": [{"reference": REF_BROCHET, "lien": f"{a}/etude1"},  # la même étude dans 2 règles
                            {"reference": "Inventé, X. (2020). Une étude qui n'existe pas du tout. Revue 1.",
                             "lien": f"{a}/mort"},
                            {"reference": REF_LAKO, "lien": f"{a}/redir2"},
                            {"reference": "Fantôme, Y. (2012). Decoding Inside Information. Journal 1.",
                             "lien": f"{a}/redir"}]},
    {"id": "r3", "etudes": [{"reference": REF_COHEN, "lien": f"{a}/texte"},
                            {"reference": REF_COHEN, "lien": f"{d}/etude"},
                            {"reference": REF_COHEN, "lien": f"{d}/autre"},
                            {"reference": REF_COHEN, "lien": f"{e}/etude"},
                            {"reference": REF_COHEN, "lien": f"{a}/generique"},
                            {"reference": REF_LAKO, "lien": f"{a}/papier.pdf"},
                            {"reference": REF_BROCHET, "lien": f"{a}/abime.pdf"}]},
    {"id": "r4", "etudes": [{"reference": REF_ZHAO, "lien": f"{a}/zhao"},
                            {"reference": "Alldredge et Blank (2019), Journal of Financial Research 42(2)", "lien": ""},
                            {"reference": "Vieux, Z. (2019), Journal of Financial Research 40(1)", "lien": f"{a}/accueil"}]},
    {"id": "r5", "etudes": [{"reference": "Mauvaisauteur, Anticipating the Financial Crisis: Evidence from Insider Trading in "
                                          "Banks (Economic Policy)", "lien": ""},
                            {"reference": "Akbas, Jiang et Koch (2020), Insider Investment Horizon, Journal of Finance 75(3)",
                             "lien": "https://doi.org/10.1111/jofi.12877"}]},
]}

shutil.rmtree(TMP, ignore_errors=True)
TMP.mkdir()
(TMP / "regles.json").write_text(json.dumps(REGLES, ensure_ascii=False))
empreinte = hashlib.sha256((TMP / "regles.json").read_bytes()).hexdigest()
os.environ.update(TOURNOI_REGLES=str(TMP / "regles.json"), TOURNOI_LIENS=str(TMP / "liens"), TOURNOI_CROSSREF=f"{cr}/works",
                  TOURNOI_DELAI="0.2", LABO_ATTENTES="0,0", no_proxy="127.0.0.1,localhost", NO_PROXY="127.0.0.1,localhost")
sys.path.insert(0, str(ICI.parent))
v = importlib.import_module("verif_liens")

# Petites fonctions
verifier("Titre cité : après l'année, jusqu'au point", v.titre_cite(REF_BROCHET) ==
         "Information Content of Insider Trades before and after the Sarbanes-Oxley Act", v.titre_cite(REF_BROCHET))
verifier("Titre cité : entre guillemets, avec son point d'interrogation", v.titre_cite(REF_LAKO) ==
         "Are Insider Trades Informative?", v.titre_cite(REF_LAKO))
verifier("1er auteur : « Cohen, L., Malloy… » → Cohen ; « Lakonishok and Lee (2001) » → Lakonishok ; « Ke, B. » → Ke",
         (v.premier_auteur(REF_COHEN), v.premier_auteur("Lakonishok and Lee (2001). X."), v.premier_auteur("Ke, B. (2003). Y."))
         == ("Cohen", "Lakonishok", "Ke"))
verifier("Comparaison : accents et ponctuation ignorés", v.part("Décodage de l’information", "decodage DE l'information") == 1.0)
verifier("Titre HTML : citation_title avant <title>", v.titre_html(PAGE_BROCHET)[1] == "citation_title")

v.main()
res = json.loads((TMP / "liens" / "verif_liens.json").read_text())
par = {(x["reference"][:8], x["adresse"].rsplit("/", 1)[-1], x["adresse"].split("/")[2]): x for x in res if x["adresse"]}


def r(ref, fin, site=a):
    return par[(ref[:8], fin, site.split("/")[2])]


verifier("Une étude citée par 2 règles = 1 ligne, avec ses 2 règles", r(REF_BROCHET, "etude1")["regles"] == ["r1", "r2"])
verifier("Lien bon : titre de la page (citation_title) = titre cité", r(REF_BROCHET, "etude1")["lien"] == "bon")
verifier("Crossref : bonne étude (titre et 1er auteur) → trouvée", r(REF_BROCHET, "etude1")["crossref"]["etat"] == "trouvee"
         and r(REF_BROCHET, "etude1")["existe"] == "oui (Crossref)")
x = r(REF_BROCHET, "etude2")
verifier("robots.txt interdit /prive : non vérifiable, et AUCUNE requête vers cette adresse",
         x["lien"] == "non_verifiable" and not any(p.startswith("/prive") for _, p, _, _ in JOURNAL), x.get("raison"))
verifier("Lien mort (404)", r("Inventé,", "mort")["lien"] == "mort")
x = r("Inventé,", "mort")
verifier("Étude inventée : pas dans Crossref, lien mort → non confirmée", x["crossref"]["etat"] == "pas_trouvee"
         and x["existe"] == "non confirmée")
x = r(REF_LAKO, "redir2")
verifier("Redirection vers un site sans robots.txt (404 = permis) : suivie, titre lu", x["lien"] == "bon"
         and x["url_finale"].startswith(c), f"{x['lien']} {x.get('url_finale')}")
x = r("Fantôme,", "redir")
verifier("Redirection vers un site qui interdit tout : PAS suivie (aucune requête vers sa page)",
         x["lien"] == "non_verifiable" and not any(s == b.split("/")[2] and p == "/page" for s, p, _, _ in JOURNAL), x.get("raison"))
verifier("Crossref : bon titre mais autre auteur → pas trouvée", x["crossref"]["etat"] == "pas_trouvee"
         and x["existe"] == "non confirmée")
x = r(REF_COHEN, "texte")
verifier("Titre seulement dans le texte de la page → « probable » ; Crossref vide → existe par le lien",
         x["lien"] == "probable" and x["existe"] == "oui (lien)", f"{x['lien']} {x['existe']}")
x, y = r(REF_COHEN, "etude", d), r(REF_COHEN, "autre", d)
verifier("robots.txt refusé (403) : non vérifiable, puis plus aucune requête vers ce site",
         x["lien"] == y["lien"] == "non_verifiable" and [p for s, p, _, _ in JOURNAL if s == d.split("/")[2]] == ["/robots.txt"])
verifier("robots.txt qui est une page web : site non lu", r(REF_COHEN, "etude", e)["lien"] == "non_verifiable"
         and [p for s, p, _, _ in JOURNAL if s == e.split("/")[2]] == ["/robots.txt"])
verifier("Page générique (« Just a moment... ») → autre_page", r(REF_COHEN, "generique")["lien"] == "autre_page")
x = r(REF_LAKO, "papier.pdf")
verifier("PDF : titre lu sur la 1re page → bon", x["lien"] == "bon" and x["source_titre"] == "pdf", f"{x['lien']} {x.get('titre_page')}")
x = r(REF_BROCHET, "abime.pdf")
verifier("PDF abîmé : « pdf illisible », pas de plantage → autre_page", x["lien"] == "autre_page"
         and x["source_titre"].startswith("pdf illisible"), f"{x['lien']} {x.get('source_titre')}")
moments = [t for s, _, t, _ in JOURNAL if s == a.split("/")[2]]
ecarts = [round(t2 - t1, 2) for t1, t2 in zip(moments, moments[1:])]
verifier("Crawl-delay de 1 s respecté sur le site A (TOURNOI_DELAI 0,2 s plus court)", min(ecarts) >= 0.95, str(ecarts))
agents = {u for *_, u in JOURNAL}
verifier("Chaque requête : agent « Radar projet personnel », sans courriel", agents == {"Radar projet personnel"}, str(agents))
verifier("Le fichier des règles n'est pas modifié", hashlib.sha256((TMP / "regles.json").read_bytes()).hexdigest() == empreinte)
resume = (TMP / "liens" / "resume.md").read_text()
verifier("Résumé : 10 études, 17 liens, 4 non confirmées, 2 erreurs de citation, ligne VERDICT « À REGARDER »",
         "- Études différentes : 10 (dans 5 règles), avec 17 liens" in resume and "- Non confirmée : 4" in resume
         and resume.rstrip().endswith("VERDICT : À REGARDER — 4 étude(s) non confirmée(s) (ni Crossref ni un lien), "
                                      "2 erreur(s) de citation") and len(res) == 17, resume.splitlines()[-1])
mal = next(z for z in res if z["reference"].startswith("Mauvaisauteur"))
verifier("Titre exact trouvé avec d'autres auteurs → alerte « auteur cité ≠ auteurs »",
         mal["alertes"] and mal["alertes"][0].startswith("auteur cité ≠ auteurs de l'étude trouvée (Akin"), str(mal["alertes"]))
ak = next(z for z in res if z["reference"].startswith("Akbas"))
verifier("Lien vers un autre DOI que celui de l'étude → alerte (12877 au lieu de 12878)",
         ak["crossref"]["etat"] == "trouvee" and any("10.1111/jofi.12877" in a and "10.1111/jofi.12878" in a for a in ak["alertes"]),
         str(ak["alertes"]))
verifier("Aucune alerte sur les bonnes études (Brochet, Lakonishok)",
         not any(z["alertes"] for z in res if z["reference"] in (REF_BROCHET, REF_LAKO)))
verifier("DOI : même revue, autre numéro → même « tige » ; revue et document de travail → tiges différentes",
         v.tige_doi("10.1111/jofi.12877") == v.tige_doi("10.1111/jofi.12878")
         and v.tige_doi("10.1111/jofi.12365") != v.tige_doi("10.2139/ssrn.2080900")
         and v.tige_doi("10.2469/faj.v53.n5.2116") == v.tige_doi("10.2469/faj.v53.n5.2118"))
sans_auteur = {"reference": "Insider trading patterns during the COVID period, Pacific-Basin Finance Journal (2025)", "adresse": "",
               "crossref": {"etat": "pas_trouvee", "meilleur": {"titre": "Insider trading patterns during the COVID period",
                                                                "auteurs": "Jiang Ma Ma", "annee": 2025, "auteur": False}}}
presse = {"reference": "Bloomberg (2025), Is the Stock Market's 'January Effect' Real? (presse)", "adresse": "",
          "crossref": {"etat": "pas_trouvee", "meilleur": {"titre": "January Effect in EU Stock Market", "auteurs": "Georgiou",
                                                           "annee": 2015, "auteur": False}}}
version_travail = {"reference": "McLean, R. D. et Pontiff, J. (2016), Does Academic Research Destroy Stock Return Predictability?",
                   "adresse": "https://doi.org/10.1111/jofi.12365",
                   "crossref": {"etat": "trouvee", "meilleur": {"titre": "Does Academic Research Destroy Stock Return Predictability?",
                                                                "auteurs": "McLean Pontiff", "annee": 2016, "auteur": True,
                                                                "doi": "10.2139/ssrn.2080900"}}}
verifier("Pas de fausse alerte : référence sans auteur, article de presse au titre court, version document de travail",
         v.alertes(sans_auteur) == [] and v.alertes(presse) == [] and v.alertes(version_travail) == [],
         str([v.alertes(sans_auteur), v.alertes(presse), v.alertes(version_travail)]))
non = sorted((x["reference"][:8], x["adresse"].rsplit("/", 1)[-1]) for x in res if x["existe"] == "non confirmée")
verifier("Non confirmées = l'étude inventée, celle au mauvais auteur, la revue à la mauvaise année, l'auteur mal attribué",
         non == [("Fantôme,", "redir"), ("Inventé,", "mort"), ("Mauvaisa", ""), ("Vieux, Z", "accueil")], str(non))
x = r(REF_ZHAO, "zhao")
verifier("Titre cité suivi d'autre texte (« … Equities. arXiv … ») : le titre exact de la page → bon, existe par le lien",
         x["lien"] == "bon" and x["existe"] == "oui (lien)", f"{x['lien']} {x.get('score_titre')}")
y = next(z for z in res if z["reference"].startswith("Alldredge"))
verifier("Référence sans titre (auteurs, année, revue) : Crossref trouvée par la revue et l'année",
         y["crossref"]["etat"] == "trouvee" and y["existe"] == "oui (Crossref)", str(y["crossref"]))
z = r("Vieux, Z", "accueil")
verifier("Même revue mais pas la même année : pas trouvée ; page « Home » : autre_page",
         z["crossref"]["etat"] == "pas_trouvee" and z["lien"] == "autre_page", f"{z['crossref']['etat']} {z['lien']}")
verifier("L'existence vaut pour la référence : Cohen confirmée par un lien, donc aussi sur ses liens non lus",
         {x["existe"] for x in res if x["reference"] == REF_COHEN} == {"oui (lien)"})
cr_req = [p for s, p, _, _ in JOURNAL if s == cr.split("/")[2] and p != "/robots.txt"]
verifier("Crossref : une seule recherche par référence (10 références)", len(cr_req) == 10, str(len(cr_req)))
for s in (A, B, C, D, E, CR):
    s.shutdown()
shutil.rmtree(TMP, ignore_errors=True)
print(f"\n{sum(ok)}/{len(ok)} vérifications réussies")
sys.exit(0 if all(ok) else 1)
