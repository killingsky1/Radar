"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) des infos du Congrès publiées dans l'app.

Relit elle-même les pages officielles (robots.txt vérifié pour chaque site, 1 requête par seconde au plus,
« Radar projet personnel ») et compare à data/app/elus.json et data/elus/congres.json :
- les 12 chefs : chaque nom suit son titre sur la page officielle des chefs (Chambre, Sénat), bon État ou circonscription ;
- H.R. 7008 : la dernière étape officielle (govinfo) et la liste des votes = celles publiées ;
- chaque vote : les totaux recomptés un par un dans le fichier officiel = ceux publiés ;
- chaque élu des transactions : ses comités et son rôle (Chambre : MemberData ; Sénat : un fichier par comité),
  chef ou non, et chacun de ses votes.
"""
import html
import json
import re
import sys
import time
import unicodedata
import urllib.request
import urllib.robotparser
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

racine = Path(sys.argv[1])
ELUS = json.loads((racine / "app" / "elus.json").read_text(encoding="utf-8"))
CONGRES = json.loads((racine / "elus" / "congres.json").read_text(encoding="utf-8"))
UA = "Radar projet personnel"
ROBOTS, DERNIER = {}, [0.0]
ecarts, lignes = [], []


def dire(t):
    print(t)
    lignes.append(t)


def lire(url):
    site = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
    if site not in ROBOTS:
        rp = urllib.robotparser.RobotFileParser(site + "/robots.txt")
        rp.read()  # 404 : tout est permis ; 401/403 : rien n'est permis
        ROBOTS[site] = rp
    if not ROBOTS[site].can_fetch(UA, url):
        raise SystemExit(f"robots.txt ne permet pas {url}")
    attente = 1.0 - (time.monotonic() - DERNIER[0])
    if attente > 0:
        time.sleep(attente)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=60) as r:
        contenu = r.read()
    DERNIER[0] = time.monotonic()
    return contenu


def norm(t):
    """Majuscules sans accents ni balises, espaces simples."""
    t = re.sub(r"<script.*?</script>|<style.*?</style>", " ", t, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return " ".join(unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().upper().split())


def mots(nom):
    return [m for m in re.findall(r"[A-Z]+", norm(nom)) if m not in {"JR", "SR", "II", "III", "IV"}]


# ---------- 1. Les chefs ----------
chefs = CONGRES.get("chefs", [])
page_chambre = norm(lire("https://www.house.gov/leadership").decode("utf-8", "replace"))
page_senat = norm(lire("https://www.senate.gov/senators/leadership.htm").decode("utf-8", "replace"))
membres_xml = ET.fromstring(lire("https://clerk.house.gov/xml/lists/MemberData.xml"))
noms_comites_chambre = {c.get("comcode"): " ".join((c.findtext("committee-fullname") or "").split())
                        for c in membres_xml.findall("committees/committee")}
CHAMBRE = {}
for m in membres_xml.findall("members/member"):
    cd, info = (m.findtext("statedistrict") or "").strip(), m.find("member-info")
    if cd and info is not None and (info.findtext("official-name") or "").strip():
        CHAMBRE[cd] = {"nom": " ".join(info.findtext("official-name").split()), "famille": info.findtext("lastname") or "",
                       "bioguide": (info.findtext("bioguideID") or "").strip(),
                       "comites": {(noms_comites_chambre[c.get("comcode")], c.get("leadership"))
                                   for c in m.findall("committee-assignments/committee")
                                   if c.get("comcode") in noms_comites_chambre}}

GENRES = {"chambre": {"speaker": 1, "chef": 2, "whip": 2, "conference": 2}, "senat": {"speaker": 0, "chef": 2, "whip": 2,
                                                                                      "conference": 1}}
compte = {"chambre": {k: 0 for k in GENRES["chambre"]}, "senat": {k: 0 for k in GENRES["senat"]}}
for c in chefs:
    t = c["titre"]
    genre = ("speaker" if t == "Speaker of the House" else "whip" if t.endswith(" Whip")
             else "chef" if re.search(r"(Majority|Minority|Democratic|Republican) Leader", t)
             else "conference" if re.search(r"(Conference|Caucus) Chair", t) else None)
    if genre is None:
        ecarts.append(f"chef {c['nom']} : titre « {t} » hors des 12 postes de l'étude")
        continue
    compte[c["chambre"]][genre] += 1
    titre, famille = re.escape(norm(t)), mots(c["nom"])[-1]
    if c["chambre"] == "chambre":
        cd = c["cle"].split(":")[1]
        ok_page = re.search(titre + r" REP\. (?:[A-Z.'-]+ ){0,3}" + famille + r"\b", page_chambre)
        ok_id = cd in CHAMBRE and mots(CHAMBRE[cd]["famille"])[-1] == famille
    else:
        etat = c["cle"].split(":")[2]
        ok_page = re.search(titre + r" " + famille + r", [^()]*\([A-Z]-" + etat + r"\)", page_senat)
        ok_id = True
    if not (ok_page and ok_id):
        ecarts.append(f"chef {c['nom']} ({t}, {c['cle']}) : pas trouvé ainsi sur la page officielle")
dire(f"Chefs publiés : {len(chefs)} · par genre : {compte}")
if compte != GENRES:
    ecarts.append(f"chefs par genre {compte} ≠ attendu {GENRES} (au Sénat, le chef démocrate préside aussi le caucus)")

# ---------- 2. H.R. 7008 et ses votes ----------
p = ELUS.get("projet") or {}
bill = ET.fromstring(lire("https://www.govinfo.gov/bulkdata/BILLSTATUS/119/hr/BILLSTATUS-119hr7008.xml")).find("bill")
officiel = (bill.findtext("latestAction/actionDate"), " ".join((bill.findtext("latestAction/text") or "").split()))
dire(f"Dernière étape officielle : {officiel[0]} « {officiel[1]} »")
if (p.get("date"), p.get("texte")) != officiel:
    ecarts.append(f"étape publiée {p.get('date')} « {p.get('texte')} » ≠ officielle")
votes_officiels = sorted({(v.findtext("chamber"), v.findtext("rollNumber"), (v.findtext("url") or "").strip())
                          for v in bill.iter("recordedVote")}, key=lambda v: (v[0], int(v[1])))
publies = sorted(((v["chambre"], v["numero"], v["url"]) for v in p.get("votes", [])), key=lambda v: (v[0], int(v[1])))
if publies != votes_officiels:
    ecarts.append(f"votes publiés {publies} ≠ officiels {votes_officiels}")
FICHIERS_VOTES = {}
for chambre, numero, url in votes_officiels:
    r = ET.fromstring(lire(url))
    if chambre == "House":
        un_par_un = {rv.find("legislator").get("name-id"): (rv.findtext("vote") or "").strip() for rv in r.iter("recorded-vote")}
        totaux = (int(r.findtext(".//totals-by-vote/yea-total")), int(r.findtext(".//totals-by-vote/nay-total")))
    else:
        un_par_un = {(" ".join(mots(m.findtext("last_name"))), (m.findtext("state") or "").strip()):
                     (m.findtext("vote_cast") or "").strip() for m in r.findall("members/member")}
        totaux = (int(r.findtext("count/yeas")), int(r.findtext("count/nays")))
    FICHIERS_VOTES[(chambre, numero)] = un_par_un
    recompte = (sum(1 for v in un_par_un.values() if v in ("Yea", "Aye", "Yes")),
                sum(1 for v in un_par_un.values() if v in ("Nay", "No")))
    pub = next((v for v in p.get("votes", []) if (v["chambre"], v["numero"]) == (chambre, numero)), {})
    dire(f"Vote {chambre} {numero} : officiel {totaux[0]} pour / {totaux[1]} contre · recompté {recompte[0]}/{recompte[1]}"
         f" · publié {pub.get('oui')}/{pub.get('non')}")
    if not (totaux == recompte == (pub.get("oui"), pub.get("non"))):
        ecarts.append(f"vote {chambre} {numero} : totaux différents")

# ---------- 3. Les élus des transactions ----------
code_comites = sorted(set(re.findall(r"committee_memberships_([A-Z]{4})\.htm",
                                     lire("https://www.senate.gov/committees/index.htm").decode("utf-8", "replace"))))
SENAT = {}
for code in code_comites:
    c = ET.fromstring(lire(f"https://www.senate.gov/general/committee_membership/committee_memberships_{code}.xml"))
    nom = " ".join((c.findtext("committees/committee_name") or "").split())
    for m in c.findall("committees/members/member"):
        role = (m.findtext("position") or "").strip()
        SENAT.setdefault((" ".join(mots(m.findtext("name/last"))), (m.findtext("state") or "").strip()), set()).add(
            (nom, None if role in ("", "Member") else role))
dire(f"Listes officielles relues : {len(CHAMBRE)} représentants, {len(SENAT)} sénateurs, {len(code_comites)} comités du Sénat")

cles_chefs = {c["cle"] for c in chefs}
for nom_rapport, info in sorted(ELUS.get("par_elu", {}).items()):
    cle = info["cle"]
    if cle.startswith("chambre:"):
        m = CHAMBRE.get(cle.split(":")[1])
        if not m or mots(m["famille"])[-1] not in mots(nom_rapport):
            ecarts.append(f"{nom_rapport} : {cle} ne correspond pas à la liste officielle")
            continue
        comites, ident, chambre = m["comites"], m["bioguide"], "House"
    else:
        famille, etat = cle.split(":")[1], cle.split(":")[2]
        comites, ident, chambre = SENAT.get((famille, etat), set()), (famille, etat), "Senate"
        if mots(nom_rapport)[-1:] != famille.split()[-1:]:
            ecarts.append(f"{nom_rapport} : nom de famille différent de {cle}")
    if {(c["nom"], c["role"]) for c in info["comites"]} != comites:
        ecarts.append(f"{nom_rapport} : comités publiés ≠ officiels")
    if bool(info["chef"]) != (cle in cles_chefs):
        ecarts.append(f"{nom_rapport} : chef publié {info['chef']} alors que {cle} chef = {cle in cles_chefs}")
    attendus = {(ch, n): votes[ident] for (ch, n), votes in FICHIERS_VOTES.items() if ch == chambre and ident in votes}
    publies = {(v["chambre"], v["numero"]): v["vote"] for v in info["votes_hr7008"]}
    if publies != attendus:
        ecarts.append(f"{nom_rapport} : votes publiés {publies} ≠ officiels {attendus}")
    dire(f"{nom_rapport} → {cle} · {len(info['comites'])} comité(s) · chef : {'oui' if info['chef'] else 'non'} · votes : "
         + ", ".join(f"{ch} {n} {v}" for (ch, n), v in sorted(publies.items())))

dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART : chefs, comités, étape et votes = pages officielles relues.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
(Path(sys.argv[2]) if len(sys.argv) > 2 else Path("congres.txt")).write_text("\n".join(lignes) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
