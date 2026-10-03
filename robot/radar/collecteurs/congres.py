"""Congrès américain : chefs, comités, et suivi de H.R. 7008 (interdiction des transactions des élus) avec ses votes.

Sources officielles (robots.txt vérifié le 3 octobre 2026 : tout est permis) :
- Chambre : membres et comités (Clerk, MemberData.xml), chefs (house.gov/leadership)
- Sénat : un fichier XML par comité (senate.gov), chefs (senate.gov/senators/leadership.htm)
- Projet de loi : govinfo (BILLSTATUS, mis à jour toutes les 4 h) ; votes : Clerk (Chambre) et senate.gov (Sénat)

Les chefs sont les 12 postes de l'étude de Wei et Zhou (2025) : président de la Chambre, chefs de parti à la Chambre
et au Sénat, whips, présidents de conférence ou de caucus (au Sénat, le chef démocrate préside aussi le caucus).
S'il n'y en a pas exactement 12, la source tombe en panne : aucun bonus deviné.

Les chefs et les comités ne sont pas des infos du fil : ils sont gardés dans data/elus/congres.json, le statut officiel
du projet de loi dans data/elus/projet.json et les votes des élus dans data/elus/votes.json. La publication les relie
aux transactions des élus (relier_elus) et les donne à l'app (data/app/elus.json, voir pour_app).
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from ..models import Evenement, empreinte
from ..store import Depot
from ..validate import controle_source

VERSION = "congres-1"
MEMBRES_CHAMBRE = "https://clerk.house.gov/xml/lists/MemberData.xml"
CHEFS_CHAMBRE = "https://www.house.gov/leadership"
CHEFS_SENAT = "https://www.senate.gov/senators/leadership.htm"
COMITES_SENAT = "https://www.senate.gov/committees/index.htm"
COMITE_SENAT = "https://www.senate.gov/general/committee_membership/committee_memberships_{}.xml"
PROJET = "https://www.govinfo.gov/bulkdata/BILLSTATUS/119/hr/BILLSTATUS-119hr7008.xml"
PROJET_NOM = "H.R. 7008 (interdiction des transactions boursières des élus)"

# Les 12 postes de l'étude (titres officiels des deux pages ; « Vice », « Deputy », « Assistant » : pas des chefs)
POSTES = (
    ("speaker", re.compile(r"^Speaker of the House$")),
    # Au Sénat, le chef démocrate préside aussi le caucus : titre officiel « Democratic Leader Chair of the Conference »
    ("chef", re.compile(r"^(Senate )?(Majority|Minority|Democratic|Republican) Leader( Chair of the Conference)?$")),
    ("whip", re.compile(r"^(Majority|Minority|Democratic|Republican) Whip$")),
    ("president_caucus", re.compile(r"^(Republican Conference|Democratic Caucus|Democratic Conference) Chair(man|woman|person)?$"
                                    r"|^Chair of the Conference$")),
)
NOMS_POSTES = {"speaker": "président de la Chambre", "chef": "chef de parti", "whip": "whip (2e rang du parti)",
               "president_caucus": "président de la conférence du parti"}
SUFFIXES = {"JR", "SR", "II", "III", "IV"}


def mots(nom: str) -> list[str]:
    n = unicodedata.normalize("NFKD", html.unescape(nom or "")).encode("ascii", "ignore").decode().upper()
    return [m for m in re.findall(r"[A-Z]+", n) if m not in SUFFIXES]


def poste(titre: str) -> str | None:
    t = " ".join(titre.split())
    return next((code for code, motif in POSTES if motif.match(t)), None)


# ---------- Chambre ----------

def lire_membres_chambre(xml: bytes) -> dict:
    """{circonscription: {nom, nom_famille, bioguide, parti, comites: [{nom, role}]}} (élus en poste seulement)."""
    racine = ET.fromstring(xml)
    noms = {c.get("comcode"): " ".join((c.findtext("committee-fullname") or "").split())
            for c in racine.findall("committees/committee")}
    membres = {}
    for m in racine.findall("members/member"):
        info = m.find("member-info")
        cd = (m.findtext("statedistrict") or "").strip()
        nom = " ".join((info.findtext("official-name") or "").split()) if info is not None else ""
        if not cd or not nom:
            continue  # siège vacant
        comites = [{"nom": noms.get(c.get("comcode"), c.get("comcode")), "role": c.get("leadership")}
                   for c in m.findall("committee-assignments/committee") if c.get("comcode") in noms]
        membres[cd] = {"nom": nom, "nom_famille": (info.findtext("lastname") or "").strip(),
                       "bioguide": (info.findtext("bioguideID") or "").strip(), "parti": info.findtext("party"),
                       "comites": comites}
    return membres


def lire_chefs_chambre(page: str) -> list[dict]:
    """(code du poste, titre officiel, nom) pour les postes de l'étude trouvés sur house.gov/leadership."""
    paires = re.findall(r"<h2>(?:<a[^>]*>)?([^<]+)(?:</a>)?</h2>.*?<h3>Rep\.\s*([^<]+)</h3>", page, re.S)
    paires += re.findall(r"<a[^>]*>([^<]+)</a>\s*<br>\s*Rep\.\s*([^<]+?)\s*<br>", page)
    chefs = []
    for titre, nom in paires:
        code = poste(html.unescape(titre))
        if code:
            chefs.append({"poste": code, "titre": " ".join(html.unescape(titre).split()),
                          "nom": " ".join(html.unescape(nom).split())})
    return chefs


# ---------- Sénat ----------

def codes_comites_senat(page: str) -> list[str]:
    return sorted(set(re.findall(r"committee_memberships_([A-Z]{4})\.htm", page)))


def lire_comite_senat(xml: bytes) -> tuple[str, list[dict]]:
    racine = ET.fromstring(xml)
    c = racine.find("committees")
    nom = " ".join((c.findtext("committee_name") or "").split())
    membres = [{"prenom": (m.findtext("name/first") or "").strip(), "nom_famille": (m.findtext("name/last") or "").strip(),
                "etat": (m.findtext("state") or "").strip(), "parti": (m.findtext("party") or "").strip(),
                "role": (m.findtext("position") or "").strip()} for m in c.findall("members/member")]
    return nom, membres


def cle_senateur(nom_famille: str, etat: str) -> str:
    """Nom de famille et État : deux sénateurs d'un même État n'ont pas le même nom (les prénoms varient d'une liste à
    l'autre, ex. « Charles E. » et « Charles »)."""
    return f"{' '.join(mots(nom_famille))}:{etat}"


def un_seul(candidats: list, prenoms: list[str], prenoms_de) -> list:
    """Plusieurs personnes du même nom de famille : on garde celle dont un prénom commence pareil (Mitch / Mitchell)."""
    if len(candidats) > 1:
        candidats = [c for c in candidats if any(a.startswith(b) or b.startswith(a)
                                                 for a in prenoms for b in mots(prenoms_de(c)))]
    return candidats


def lire_chefs_senat(page: str) -> list[dict]:
    chefs = []
    for bloc in re.split(r'<div style="float:left; width:33%', page)[1:]:
        titres = [" ".join(html.unescape(t).split()) for t in re.findall(r"<i>([^<]+)</i>", bloc)]
        nom = re.search(r"<a [^>]*>([^<,]+),\s*<br>\s*([^<]+)</a>", bloc)
        pe = re.search(r"\(([A-Z])-([A-Z]{2})\)", bloc)
        if not nom or not pe:
            continue
        for titre in titres:
            if code := poste(titre):
                chefs.append({"poste": code, "titre": titre, "nom_famille": nom.group(1).strip(),
                              "prenom": nom.group(2).strip(), "parti": pe.group(1), "etat": pe.group(2)})
                break  # un même chef ne compte qu'une fois (au Sénat, le chef démocrate préside aussi le caucus)
    return chefs


# ---------- Lecteur : chefs et comités ----------

def construire_congres(membres_chambre: dict, chefs_chambre: list[dict], comites_senat: list[tuple[str, list[dict]]],
                       chefs_senat: list[dict]) -> dict:
    senat: dict[str, dict] = {}
    for nom_comite, membres in comites_senat:
        for m in membres:
            s = senat.setdefault(cle_senateur(m["nom_famille"], m["etat"]),
                                 {"nom": f"{m['prenom']} {m['nom_famille']}", "nom_famille": m["nom_famille"],
                                  "prenom": m["prenom"], "etat": m["etat"], "parti": m["parti"], "comites": []})
            s["comites"].append({"nom": nom_comite, "role": None if m["role"] in ("", "Member") else m["role"]})
    chefs = []
    for c in chefs_chambre:  # relier le nom de la page des chefs à la circonscription officielle
        nom = mots(c["nom"])
        cds = un_seul([cd for cd, m in membres_chambre.items() if mots(m["nom_famille"])[-1:] == nom[-1:]], nom[:-1],
                      lambda cd: membres_chambre[cd]["nom"])
        if len(cds) == 1:
            chefs.append({"chambre": "chambre", "cle": f"chambre:{cds[0]}", "poste": c["poste"], "titre": c["titre"],
                          "nom": membres_chambre[cds[0]]["nom"]})
    for c in chefs_senat:
        cle = cle_senateur(c["nom_famille"], c["etat"])
        if cle in senat:
            chefs.append({"chambre": "senat", "cle": f"senat:{cle}", "poste": c["poste"], "titre": c["titre"],
                          "nom": f"{c['prenom']} {c['nom_famille']}"})
    return {"chambre": membres_chambre, "senat": senat, "chefs": chefs}


def verifier_congres(c: dict) -> None:
    """Rien plutôt que faux : une liste incomplète ne remplace jamais la précédente."""
    nb = {"chambre": sum(1 for x in c["chefs"] if x["chambre"] == "chambre"),
          "senat": sum(1 for x in c["chefs"] if x["chambre"] == "senat")}
    if (nb["chambre"], nb["senat"]) != (7, 5):
        raise ValueError(f"chefs trouvés : {nb['chambre']} à la Chambre (7 attendus), {nb['senat']} au Sénat (5 attendus)")
    if len(c["chambre"]) < 400 or len(c["senat"]) < 95:
        raise ValueError(f"listes incomplètes : {len(c['chambre'])} représentants, {len(c['senat'])} sénateurs")


def chemin_congres(donnees) -> Path:
    return Path(donnees) / "elus" / "congres.json"


def chemin_votes(donnees) -> Path:
    return Path(donnees) / "elus" / "votes.json"


def chemin_projet(donnees) -> Path:
    return Path(donnees) / "elus" / "projet.json"


def deja(ctx, source: str) -> set[str]:
    """Numéros déjà enregistrés, même au-delà des 3 derniers mois : un vote ou une étape du projet ne change plus
    (sinon les votes de juillet seraient relus à chaque passage une fois sortis de la fenêtre de 3 mois)."""
    return Depot(ctx.donnees).ids_enregistres({source}, mois_max=24)


def _ecrire(chemin: Path, contenu: dict) -> None:
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(contenu, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def collecter_comites(ctx) -> list[Evenement]:
    """Chefs et comités : une liste de référence (pas d'infos dans le fil)."""
    g = ctx.client.get
    membres = lire_membres_chambre(g(MEMBRES_CHAMBRE).contenu)
    chefs_chambre = lire_chefs_chambre(g(CHEFS_CHAMBRE).contenu.decode("utf-8", "replace"))
    codes = codes_comites_senat(g(COMITES_SENAT).contenu.decode("utf-8", "replace"))
    comites = [lire_comite_senat(g(COMITE_SENAT.format(code)).contenu) for code in codes]
    chefs_senat = lire_chefs_senat(g(CHEFS_SENAT).contenu.decode("utf-8", "replace"))
    c = construire_congres(membres, chefs_chambre, comites, chefs_senat)
    verifier_congres(c)
    _ecrire(chemin_congres(ctx.donnees), {**c, "lu": ctx.maintenant.isoformat(), "version": VERSION})
    return []


# ---------- H.R. 7008 : statut officiel et votes ----------

def lire_projet(xml: bytes) -> dict:
    b = ET.fromstring(xml).find("bill")
    votes = {}
    for v in b.iter("recordedVote"):
        cle = (v.findtext("chamber"), v.findtext("rollNumber"))
        votes[cle] = {"chambre": cle[0], "numero": cle[1], "url": (v.findtext("url") or "").strip(),
                      "date": (v.findtext("date") or "")[:10]}
    return {"numero": f"{b.findtext('type')} {b.findtext('number')}", "congres": b.findtext("congress"),
            "titre": " ".join((b.findtext("title") or "").split()),
            "derniere_action": {"date": b.findtext("latestAction/actionDate"),
                                "texte": " ".join((b.findtext("latestAction/text") or "").split())},
            "votes": sorted(votes.values(), key=lambda v: (v["date"], v["chambre"], int(v["numero"] or 0)))}


def etape_fr(texte: str) -> str:
    """Les étapes officielles les plus courantes, en français ; sinon « nouvelle étape » (le texte officiel suit)."""
    t = texte.lower()
    m = re.search(r"(\d+)\s*-\s*(\d+)", texte)
    compte = f", {m.group(1)} pour, {m.group(2)} contre" if m else ""
    if t.startswith("became public law"):
        return "devenu loi"
    if "cloture" in t and "not invoked" in t:
        return f"bloqué au Sénat (clôture rejetée{compte}, 60 voix requises)"
    if "cloture" in t and "invoked" in t:
        return f"le Sénat met fin au blocage (clôture acceptée{compte})"
    if "passed senate" in t or "passed/agreed to in senate" in t:
        return f"adopté par le Sénat{compte}"
    if "passed/agreed to in house" in t or ("passed" in t and "house" in t):
        return f"adopté par la Chambre{compte}"
    if "presented to president" in t:
        return "envoyé au président"
    if "vetoed" in t:
        return "veto du président"
    return "nouvelle étape au Congrès"


def evenement_projet(p: dict, xml: bytes) -> Evenement | None:
    a = p["derniere_action"]
    if not a["date"] or not a["texte"]:
        return None
    jour = a["date"][:10]
    return Evenement(
        source="hr7008", official_id=f"{jour}:{empreinte(a['texte'].encode())[:12]}", category="politiciens",
        kind="projet_de_loi", title=f"{PROJET_NOM} : {etape_fr(a['texte'])}",
        occurred_on=jour, published_on=jour, official_url=PROJET, sha256=empreinte(xml), parser_version=VERSION,
        notes=[f"Texte officiel : « {a['texte']} »"],
        data={"numero": p["numero"], "congres": p["congres"], "titre_officiel": p["titre"], "action": a,
              "resume": f"Projet de loi « {p['titre']} » : interdirait aux élus du Congrès, à leur conjoint et à leurs "
                        f"enfants à charge d'acheter des actions, et les obligerait à annoncer leurs ventes 7 à 14 jours "
                        f"d'avance."},
    )


def collecter_hr7008(ctx) -> list[Evenement]:
    t = ctx.client.get(PROJET)
    p = lire_projet(t.contenu)
    ctx.cache["hr7008"] = p
    _ecrire(chemin_projet(ctx.donnees), {**p, "lu": ctx.maintenant.isoformat()})
    ev = evenement_projet(p, t.contenu)
    return [ev] if ev and ev.official_id not in deja(ctx, "hr7008") else []


@controle_source("hr7008")
def controles_hr7008(ev: Evenement) -> dict[str, bool]:
    return {
        "projet_suivi": ev.data.get("numero") == "HR 7008" and ev.data.get("congres") == "119",
        "etape_datee": bool(re.fullmatch(r"\d{4}-\d\d-\d\d", ev.data.get("action", {}).get("date") or "")),
    }


def lire_vote_chambre(xml: bytes) -> dict:
    r = ET.fromstring(xml)
    votes = {rv.find("legislator").get("name-id"): (rv.findtext("vote") or "").strip()
             for rv in r.iter("recorded-vote") if rv.find("legislator") is not None}
    jour = datetime.strptime((r.findtext(".//action-date") or "").strip(), "%d-%b-%Y").date().isoformat()
    return {"chambre": "House", "question": (r.findtext(".//vote-question") or "").strip(),
            "resultat": (r.findtext(".//vote-result") or "").strip(), "date": jour,
            "projet": " ".join((r.findtext(".//legis-num") or "").split()),
            "oui": int(r.findtext(".//totals-by-vote/yea-total") or -1),
            "non": int(r.findtext(".//totals-by-vote/nay-total") or -1), "votes": votes}


def lire_vote_senat(xml: bytes) -> dict:
    r = ET.fromstring(xml)
    votes = {cle_senateur(m.findtext("last_name") or "", m.findtext("state") or ""):
             (m.findtext("vote_cast") or "").strip() for m in r.findall("members/member")}
    jour = datetime.strptime(" ".join((r.findtext("vote_date") or "").split(",")[:2]).strip(), "%B %d %Y").date().isoformat()
    return {"chambre": "Senate", "question": " ".join((r.findtext("vote_question_text") or "").split()),
            "resultat": " ".join((r.findtext("vote_result_text") or "").split()), "date": jour,
            "projet": " ".join((r.findtext("document/document_name") or "").split()),
            "oui": int(r.findtext("count/yeas") or -1), "non": int(r.findtext("count/nays") or -1), "votes": votes}


def sujet_fr(question: str) -> tuple[str, str]:
    """(objet du vote avec son article, libellé court) : « contre » une motion de procédure n'est pas « contre » le projet."""
    q = question.lower()
    if "suspend the rules" in q:
        return "le projet de loi en procédure accélérée (2/3 des voix requis)", "adoption accélérée (2/3 des voix requis)"
    if "passage" in q:
        return "le projet de loi", "adoption du projet de loi"
    if "recommit" in q:
        return "la motion de renvoi en comité (procédure)", "motion de renvoi en comité (procédure)"
    if "cloture" in q:
        return "la clôture (60 voix requises pour ouvrir le débat)", "clôture pour ouvrir le débat (60 voix requises)"
    if "motion to proceed" in q:
        return "la motion pour ouvrir le débat", "motion pour ouvrir le débat"
    return f"« {question} »", f"autre vote : « {question} »"


def verbe_fr(resultat: str) -> str | None:
    r = resultat.lower()
    if any(m in r for m in ("rejected", "failed", "not agreed", "not invoked")):
        return "rejette"
    if any(m in r for m in ("passed", "agreed", "invoked")):
        return "adopte"
    return None


VOTES_FR = {"Yea": "pour", "Aye": "pour", "Yes": "pour", "Nay": "contre", "No": "contre",
            "Not Voting": "n'a pas voté", "Present": "présent"}


def phrase_vote(chambre: str, question: str, resultat: str) -> str:
    """Ex. « la Chambre adopte le projet de loi » ; résultat inconnu : le texte officiel, tel quel."""
    qui = "la Chambre" if chambre == "House" else "le Sénat"
    objet = sujet_fr(question)[0]
    verbe = verbe_fr(resultat)
    return f"{qui} {verbe} {objet}" if verbe else f"vote sur {objet} ({qui}) : « {resultat} »"


def evenement_vote(v: dict, info: dict, xml: bytes) -> Evenement:
    quoi = phrase_vote(v["chambre"], v["question"], v["resultat"])
    return Evenement(
        source="votes", official_id=f"{v['chambre'][0]}{info['numero']}-{v['date'][:4]}", category="politiciens",
        kind="vote", title=f"{PROJET_NOM} : {quoi}, {v['oui']} pour, {v['non']} contre",
        occurred_on=v["date"], published_on=v["date"], official_url=info["url"], sha256=empreinte(xml),
        parser_version=VERSION, notes=[f"Question officielle : « {v['question']} » · résultat : « {v['resultat']} »"],
        data={"chambre": v["chambre"], "numero": info["numero"], "question": v["question"], "resultat": v["resultat"],
              "projet": v["projet"], "oui": v["oui"], "non": v["non"],
              "compte_oui": sum(1 for x in v["votes"].values() if x in ("Yea", "Aye", "Yes")),
              "compte_non": sum(1 for x in v["votes"].values() if x in ("Nay", "No"))},
    )


def collecter_votes(ctx) -> list[Evenement]:
    """Les votes enregistrés sur H.R. 7008 (lus une fois) ; le vote de chaque élu est gardé pour l'app."""
    p = ctx.cache.get("hr7008") or lire_projet(ctx.client.get(PROJET).contenu)
    chemin = chemin_votes(ctx.donnees)
    gardes = json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}
    connus = deja(ctx, "votes")
    evs = []
    for info in p["votes"]:
        cle = f"{info['chambre'][0]}{info['numero']}-{info['date'][:4]}"
        if cle in connus and cle in gardes:
            continue
        t = ctx.client.get(info["url"])
        v = (lire_vote_chambre if info["chambre"] == "House" else lire_vote_senat)(t.contenu)
        gardes[cle] = {**{k: v[k] for k in ("chambre", "question", "resultat", "date", "oui", "non", "votes")},
                       "numero": info["numero"], "url": info["url"]}
        if cle not in connus:
            evs.append(evenement_vote(v, info, t.contenu))
    if evs or not chemin.exists():
        _ecrire(chemin, gardes)
    return evs


@controle_source("votes")
def controles_votes(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "vote_du_projet_suivi": d.get("projet", "").replace(".", "").replace(" ", "").upper() == "HR7008",
        "total_recompte": d.get("oui") == d.get("compte_oui") and d.get("non") == d.get("compte_non"),
    }


# ---------- Relier les élus des transactions aux listes officielles ----------

def relier_elus(evenements: list[dict], congres: dict, votes: dict) -> dict:
    """Pour chaque élu des transactions : poste de chef, comités, vote sur H.R. 7008. Rien si le lien n'est pas sûr."""
    chefs = {c["cle"]: c for c in congres.get("chefs", [])}
    senateurs = congres.get("senat", {})
    par_elu = {}
    for e in evenements:
        if e.get("source") not in ("chambre_ptr", "senat_ptr") or not e.get("data", {}).get("elu"):
            continue
        d = e["data"]
        nom = d["elu"]
        if nom in par_elu:
            continue
        cle, fiche = None, None
        if e["source"] == "chambre_ptr":
            m = congres.get("chambre", {}).get(d.get("circonscription") or "")
            if m and mots(m["nom_famille"]) and mots(m["nom_famille"])[-1] in mots(nom):
                cle, fiche = f"chambre:{d['circonscription']}", m
        else:
            mots_elu = mots(nom)
            candidats = un_seul([(k, s) for k, s in senateurs.items() if mots(s["nom_famille"])[-1:] == mots_elu[-1:]],
                                mots_elu[:-1], lambda ks: ks[1]["prenom"])
            if len(candidats) == 1:
                cle, fiche = f"senat:{candidats[0][0]}", candidats[0][1]
        if not cle:
            continue
        votes_elu = []
        for k, v in votes.items():
            chambre = "chambre" if v["chambre"] == "House" else "senat"
            identifiant = fiche.get("bioguide") if chambre == "chambre" else cle.split(":", 1)[1]
            if chambre == cle.split(":")[0] and identifiant in v["votes"]:
                valeur = v["votes"][identifiant]
                votes_elu.append({"vote": valeur, "vote_fr": VOTES_FR.get(valeur, valeur), "question": v["question"],
                                  "sujet": sujet_fr(v["question"])[1], "date": v["date"], "chambre": v["chambre"],
                                  "numero": str(v.get("numero") or re.search(r"\d+", k).group(0))})
        votes_elu.sort(key=lambda x: (x["date"], int(x["numero"])))
        chef = chefs.get(cle)
        par_elu[nom] = {"cle": cle, "nom_officiel": fiche["nom"],
                        "chef": {"poste": NOMS_POSTES[chef["poste"]], "titre": chef["titre"]} if chef else None,
                        "comites": fiche.get("comites", []), "votes_hr7008": votes_elu}
    return par_elu


def cle_chef(ev: dict, par_elu: dict) -> str | None:
    """La clé officielle d'un élu chef du Congrès (sinon None)."""
    info = par_elu.get((ev.get("data") or {}).get("elu") or "")
    return info["cle"] if info and info.get("chef") else None


def _lire(chemin: Path) -> dict:
    return json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {}


def pour_app(donnees, evenements: list[dict]) -> dict:
    """Le fichier de l'app (data/app/elus.json) : chefs, comités et vote de chaque élu des transactions, statut du projet.

    Les listes manquantes (lecteur pas encore passé) donnent des listes vides : jamais de chef deviné.
    """
    congres, votes, projet = _lire(chemin_congres(donnees)), _lire(chemin_votes(donnees)), _lire(chemin_projet(donnees))
    statut = None
    if projet.get("derniere_action", {}).get("texte"):
        a = projet["derniere_action"]
        statut = {"nom": PROJET_NOM, "numero": projet["numero"], "titre": projet["titre"], "date": a["date"],
                  "etape": etape_fr(a["texte"]), "texte": a["texte"], "url": PROJET, "lu": projet.get("lu"),
                  "votes": [{**{k: v.get(k) for k in ("chambre", "numero", "question", "resultat", "date", "oui", "non",
                                                       "url")},
                             "phrase": phrase_vote(v["chambre"], v["question"], v["resultat"])}
                            for v in sorted(votes.values(), key=lambda v: (v["date"], int(v.get("numero") or 0)))]}
    return {
        "par_elu": relier_elus(evenements, congres, votes),
        "chefs": [{"chambre": c["chambre"], "poste": NOMS_POSTES[c["poste"]], "titre": c["titre"], "nom": c["nom"]}
                  for c in congres.get("chefs", [])],
        "listes_lues": congres.get("lu"),
        "projet": statut,
    }
