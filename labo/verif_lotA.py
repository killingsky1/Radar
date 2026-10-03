"""Contre-vérification INDÉPENDANTE (n'importe rien du robot) du lot A, sur les fichiers du robot (main), sans internet.
- Doublons de formulaires 4 : regroupement refait ici (même compagnie, même sens, mêmes lignes date/code/actions/prix) ;
  chaque groupe = UNE info montrée, les autres marquées « même transaction » vers elle ; jamais 2 lignes dans le fil ;
  aucune info marquée sans vrai doublon.
- Sites qui refusent le robot : « Refusée par le site » dans l'app si et seulement si 2 refus confirmés dans l'état du
  robot ; dates de l'explication = dates de l'état ; aucun appel au site pendant la pause.
- Participations : aucun titre avec des parenthèses dans des parenthèses.
"""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

racine = Path(sys.argv[1])
SORTIE = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("lotA.txt")
MOIS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre",
        "décembre")
lignes, ecarts = [], []


def dire(t):
    print(t, flush=True)
    lignes.append(t)


def jour_fr(iso):
    d = datetime.fromisoformat(iso).astimezone(ZoneInfo("America/Toronto")).date()
    return f"{'1er' if d.day == 1 else d.day} {MOIS[d.month - 1]} {d.year}"


evs = []
for f in sorted((racine / "evenements").glob("*.jsonl"))[-3:]:
    evs += [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]
fil = json.loads((racine / "app" / "fil.json").read_text(encoding="utf-8"))
ids_fil = {e["id"] for e in fil}

# ---------- Doublons de formulaires 4 ----------
groupes = defaultdict(list)
for e in evs:
    t = (e.get("data") or {}).get("transactions") or []
    if e["source"] == "sec_form4" and e.get("tickers") and t:
        cle = (e["tickers"][0], e["kind"],
               tuple(sorted((x.get("date"), x.get("code"), x.get("actions"), x.get("prix")) for x in t)))
        groupes[cle].append(e)
doubles = [g for g in groupes.values() if len(g) > 1]
avant = len(ecarts)
for g in doubles:
    montres = [e for e in g if not e["data"].get("meme_transaction_que")]
    nom = f"{g[0]['tickers'][0]} ({len(g)} formulaires)"
    if len(montres) != 1:
        ecarts.append(f"doublons {nom} : {len(montres)} infos montrées au lieu d'une")
        continue
    m = montres[0]
    if any(e["data"].get("meme_transaction_que") != m["id"] for e in g if e is not m):
        ecarts.append(f"doublons {nom} : une info ne pointe pas vers celle qui est montrée")
    if len(m["data"].get("aussi_declare_par") or []) != len(g) - 1:
        ecarts.append(f"doublons {nom} : « aussi déclarée par » ne nomme pas les {len(g) - 1} autres")
    if sum(e["id"] in ids_fil for e in g) > 1:
        ecarts.append(f"doublons {nom} : plusieurs lignes dans le fil")
    dire(f"Doublon {nom} : montrée {m['official_id']} « {m['title'][:70]} » · aussi déclarée par "
         f"{len(m['data'].get('aussi_declare_par') or [])}")
ids_doubles = {e["id"] for g in doubles for e in g}
faux = [e["id"] for e in evs if (e.get("data") or {}).get("meme_transaction_que") and e["id"] not in ids_doubles]
if faux:
    ecarts.append(f"{len(faux)} info(s) marquée(s) « même transaction » sans vrai doublon : {faux[:3]}")
dire(f"Doublons de formulaires 4 (3 derniers mois) : {len(doubles)} groupe(s), {sum(len(g) for g in doubles)} "
     f"formulaires ; une seule ligne par groupe : {'OUI' if len(ecarts) == avant else 'NON'}")

# ---------- Sites qui refusent le robot ----------
etat = json.loads((racine / "etat_sources.json").read_text(encoding="utf-8"))
sources = {s["id"]: s for s in json.loads((racine / "app" / "sources.json").read_text(encoding="utf-8"))}
refusees = 0
for sid, s in sources.items():
    e = etat.get(sid) or {}
    r = e.get("refus") or {}
    if (s["statut"] == "refusee") != bool(r.get("confirme")):
        ecarts.append(f"source {sid} : affichée « {s['libelle']} » alors que le refus confirmé = {bool(r.get('confirme'))}")
    elif s["statut"] == "refusee":
        refusees += 1
        if f"depuis le {jour_fr(r['depuis'])}" not in s["explication"] or \
                f"réessaie une fois le {jour_fr(r['prochain_essai'])}" not in s["explication"]:
            ecarts.append(f"source {sid} : dates de l'explication ≠ état du robot")
        if (e.get("derniere_tentative") or "") > r["dernier_refus"]:
            ecarts.append(f"source {sid} : le robot a sollicité le site pendant la pause")
        dire(f"Source {sid} : « {s['libelle']} » · {s['explication']}")
    elif r:
        dire(f"Source {sid} : 1 refus noté le {jour_fr(r['depuis'])} (erreur {r['code']}), pas encore confirmé : "
             f"lue normalement au prochain passage")
dire(f"Sources refusées par leur site : {refusees}")

# ---------- Participations : titres ----------
for e in evs:
    if e["source"] == "participations_gouv":
        double = re.search(r"\([^()]*\(", e["title"])
        if double:
            ecarts.append(f"participation {e['official_id']} : parenthèses dans des parenthèses")
        dire(f"Participation {e['official_id']} : « {e['title']} » · {'ÉCART' if double else 'conforme'}")

dire("\n".join(ecarts) if ecarts else "AUCUN ÉCART.")
dire("VERDICT : " + ("PROBLÈME" if ecarts else "OK"))
SORTIE.write_text("\n".join(lignes) + "\n", encoding="utf-8")
sys.exit(1 if ecarts else 0)
