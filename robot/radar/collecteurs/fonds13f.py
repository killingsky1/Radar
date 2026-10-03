"""SEC 13F : ce que les gros fonds ont acheté ou vendu pendant le trimestre (formulaire 13F-HR).

Chaque fonds de la liste dépose, au plus tard 45 jours après la fin du trimestre, ses positions en actions
américaines. On compare avec le trimestre précédent (même fonds, rapport complet des deux côtés) et on garde
les gros changements : au moins 1 % du portefeuille (250 M$ suffisent pour un très gros fonds) et 10 M$ US.
Le prix réel des transactions n'est pas publié : la valeur est estimée au prix de fin de trimestre déclaré.

Symbole boursier : table officielle CUSIP -> symbole des données « fails-to-deliver » de la SEC, vérifiée
contre la liste officielle des compagnies cotées ; sinon, pas de symbole (rien plutôt que faux).
"""

from __future__ import annotations

import io
import json
import re
import statistics
import xml.etree.ElementTree as ET
import zipfile
from datetime import date

from ..models import Evenement, empreinte
from ..validate import controle_source
from .sec import ARCHIVES, DepotSec, lire_journees, nom_normalise, symboles

VERSION = "fonds13f-1"
PART_MIN = 0.01  # 1 % du portefeuille…
PLAFOND = 250_000_000  # … mais 250 M$ suffisent pour un très gros fonds (Caisse de dépôt : 1 % = 700 M$)
MONTANT_MIN = 10_000_000  # $ US
MAX_PAR_DEPOT = 8
PAGE_FTD = "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data"
FICHIERS_FTD = 6  # 3 mois de données : couvre presque toutes les actions cotées
SUBMISSIONS = "https://data.sec.gov/submissions/CIK{:010d}.json"
# CIK vérifiés dans les index officiels de la SEC (13F-HR déposés du 3 au 14 août 2026) -> nom affiché
FONDS = {
    1067983: "Berkshire Hathaway", 1350694: "Bridgewater Associates", 2026053: "Pershing Square",
    1037389: "Renaissance Technologies", 1423053: "Citadel Advisors", 1029160: "Soros Fund Management",
    1656456: "Appaloosa", 1040273: "Third Point", 1167483: "Tiger Global Management", 1061768: "Baupost Group",
    921669: "Carl C. Icahn", 1697748: "ARK Investment Management", 1536411: "Duquesne Family Office",
    1791786: "Elliott Investment Management", 1135730: "Coatue Management", 1103804: "Viking Global Investors",
    1061165: "Lone Pine Capital", 1166559: "Gates Foundation Trust", 1374170: "Norges Bank (Norvège)",
    898286: "Caisse de dépôt et placement du Québec", 1283718: "Investissements RPC",
    937567: "Ontario Teachers' Pension Plan", 1396318: "Investissements PSP", 1228242: "BCI (Colombie-Britannique)",
    1053321: "OMERS", 1463559: "AIMCo (Alberta)", 1535845: "HOOPP (Ontario)", 915191: "Fairfax Financial",
}
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
        "novembre", "décembre"]


def _nom(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _champ(el: ET.Element, nom: str) -> str:
    for x in el.iter():
        if _nom(x.tag) == nom:
            return (x.text or "").strip()
    return ""


def lire_couverture(xml: bytes) -> dict:
    """Page de couverture officielle (primary_doc.xml) : trimestre, sorte de rapport, modification ou non."""
    racine = ET.fromstring(xml)
    trimestre = _champ(racine, "reportCalendarOrQuarter")  # MM-JJ-AAAA
    m = re.fullmatch(r"(\d\d)-(\d\d)-(\d{4})", trimestre)
    lignes = _champ(racine, "tableEntryTotal")
    return {"trimestre": f"{m.group(3)}-{m.group(1)}-{m.group(2)}" if m else None,
            "sorte": _champ(racine, "reportType").upper(),
            "modification": _champ(racine, "isAmendment").lower() == "true",
            # Positions cachées (traitement confidentiel demandé à la SEC) : la table publique est incomplète.
            "confidentiel": _champ(racine, "isConfidentialOmitted").lower() == "true",
            "lignes_annoncees": int(lignes) if lignes.isdigit() else None,
            "nom": _champ(racine, "name")}


# Seules les actions ordinaires d'une compagnie comptent : pas les actions privilégiées, bons de souscription,
# billets, parts ni les fonds indiciels (ETF), dont les achats ne disent rien sur une compagnie en particulier.
AUTRES_TITRES = re.compile(r"\b(PFD|PREF|PREFERRED|DEP|DEPOSITARY SH|NOTES?|BONDS?|WTS?|WARRANTS?|RIGHTS?|UNITS?|ETF|ETN|"
                           r"DEBT|CONV|DBCV)\b")
FONDS_INDICIELS = re.compile(r"\b(ETF|EXCHANGE TRADED|ISHARES|SPDR|SELECT SECTOR|INDEX FDS?|INDEX FUNDS?|PROSHARES|"
                             r"DIREXION|WISDOMTREE|VANECK|GLOBAL X)\b")


def action_ordinaire(nom: str, classe_titre: str) -> bool:
    return not AUTRES_TITRES.search(classe_titre.upper()) and not FONDS_INDICIELS.search(nom.upper())


def lire_positions(xml: bytes) -> dict:
    """Table officielle des positions -> {cusip: {nom, classe, actions, valeur}} (actions ordinaires seulement).

    Les options (putCall), les obligations (PRN), les actions privilégiées et les fonds indiciels sont mis de
    côté (ils restent dans la valeur totale du portefeuille). Valeurs en dollars ; si le fonds les déclare
    encore en milliers (prix médian sous 1 $), elles sont converties et c'est noté.
    """
    racine = ET.fromstring(xml)
    positions: dict[str, dict] = {}
    total = 0.0
    lignes = 0
    for ligne in racine.iter():
        if _nom(ligne.tag) != "infoTable":
            continue
        lignes += 1
        valeur = float(_champ(ligne, "value") or 0)
        total += valeur
        if _champ(ligne, "putCall") or _champ(ligne, "sshPrnamtType").upper() != "SH":
            continue
        if not action_ordinaire(_champ(ligne, "nameOfIssuer"), _champ(ligne, "titleOfClass")):
            continue
        cusip = _champ(ligne, "cusip").upper()
        p = positions.setdefault(cusip, {"nom": _champ(ligne, "nameOfIssuer"), "classe": _champ(ligne, "titleOfClass"),
                                         "actions": 0, "valeur": 0.0})
        p["actions"] += int(float(_champ(ligne, "sshPrnamt") or 0))
        p["valeur"] += valeur
    prix = [p["valeur"] / p["actions"] for p in positions.values() if p["actions"] > 0]
    en_milliers = bool(prix) and statistics.median(prix) < 1.0
    if en_milliers:
        for p in positions.values():
            p["valeur"] *= 1000
        total *= 1000
    return {"positions": positions, "total": total, "en_milliers": en_milliers, "lignes": lignes}


def comparable(couverture: dict, table: dict) -> bool:
    """Rapport complet, sans positions cachées, et table qui a bien toutes les lignes annoncées sur la couverture.

    Vu le 3 octobre 2026 : Norges Bank, 1er trimestre 2026, « positions confidentielles omises » et 1 seule ligne
    publique sur 1 507 annoncées. Comparer avec ce rapport inventait des « nouvelles positions ».
    """
    return (couverture["sorte"] == "13F HOLDINGS REPORT" and not couverture["confidentiel"]
            and couverture["lignes_annoncees"] == table["lignes"])


def trimestre_precedent(jour: str) -> str:
    a, m = int(jour[:4]), int(jour[5:7])
    a, m = (a - 1, 12) if m == 3 else (a, m - 3)
    fin = {3: 31, 6: 30, 9: 30, 12: 31}[m]
    return f"{a}-{m:02d}-{fin}"


def fractionnement_probable(avant: dict, apres: dict) -> bool:
    """Un fractionnement d'actions (ex. 10 pour 1) multiplie les actions sans que le fonds achète : on l'écarte.

    Signe : le nombre d'actions est multiplié (ou divisé) par un entier k ET le prix par environ k.
    """
    if not (avant["actions"] and apres["actions"] and avant["valeur"] and apres["valeur"]):
        return False
    r_actions = apres["actions"] / avant["actions"]
    r_prix = (avant["valeur"] / avant["actions"]) / (apres["valeur"] / apres["actions"])
    for ratio, inverse in ((r_actions, False), (1 / r_actions, True)):
        k = round(ratio)
        if k >= 2 and abs(ratio - k) / k < 0.02:
            attendu = 1 / k if inverse else k
            if abs(r_prix - attendu) / attendu < 0.25:
                return True
    return False


def mouvements(avant: dict, apres: dict) -> list[dict]:
    """Les gros changements entre deux trimestres, du plus gros au plus petit."""
    total = max(avant["total"], apres["total"])
    trouves = []
    for cusip in set(avant["positions"]) | set(apres["positions"]):
        a = avant["positions"].get(cusip, {"actions": 0, "valeur": 0.0})
        b = apres["positions"].get(cusip, {"actions": 0, "valeur": 0.0})
        if a["actions"] == b["actions"] or fractionnement_probable(a, b):
            continue
        ref = b if b["actions"] else a
        prix = ref["valeur"] / ref["actions"]
        montant = abs(b["actions"] - a["actions"]) * prix
        if montant < max(MONTANT_MIN, min(PART_MIN * total, PLAFOND)):
            continue
        sorte = "nouvelle" if not a["actions"] else "sortie" if not b["actions"] else (
            "hausse" if b["actions"] > a["actions"] else "baisse")
        trouves.append({"cusip": cusip, "nom": ref["nom"], "classe": ref["classe"], "sorte": sorte,
                        "actions_avant": a["actions"], "actions_apres": b["actions"], "valeur_avant": a["valeur"],
                        "valeur_apres": b["valeur"], "prix": prix, "montant": montant, "part": montant / total,
                        "total": total})
    return sorted(trouves, key=lambda m: -m["montant"])[:MAX_PAR_DEPOT]


# ---------- Symboles : table officielle CUSIP -> symbole ----------


def table_cusip(ctx) -> dict[str, tuple[str, str]]:
    if "sec_cusip" not in ctx.cache:
        page = ctx.client.get(PAGE_FTD).contenu.decode("utf-8", "replace")
        fichiers = sorted(set(re.findall(r"/files/data/fails-deliver-data/(cnsfails\d{6}[ab]\.zip)", page)))
        if not fichiers:
            raise RuntimeError("table CUSIP de la SEC introuvable")
        table: dict[str, tuple[str, str]] = {}
        for f in fichiers[-FICHIERS_FTD:]:  # du plus ancien au plus récent : le plus récent l'emporte
            contenu = ctx.client.get(f"https://www.sec.gov/files/data/fails-deliver-data/{f}").contenu
            with zipfile.ZipFile(io.BytesIO(contenu)) as z:
                texte = z.read(z.namelist()[0]).decode("latin-1")
            for ligne in texte.splitlines()[1:]:
                p = ligne.split("|")
                if len(p) >= 5 and len(p[1]) == 9 and p[2]:
                    table[p[1].upper()] = (p[2].strip(), p[4].strip())
        ctx.cache["sec_cusip"] = table
    return ctx.cache["sec_cusip"]


def symbole(cusip: str, emetteur: str, table: dict, syms) -> list[str]:
    trouve = table.get(cusip)
    if not trouve:
        return []
    ligne = syms.par_symbole(trouve[0])
    if not ligne:
        return []  # pas coté au Nasdaq, au NYSE ou au CBOE
    mots = [m for m in nom_normalise(emetteur).split() if len(m) >= 3]
    # Garde-fou : le 1er mot du nom déclaré au 13F doit se retrouver dans le nom officiel ou la description SEC.
    if mots and (mots[0] in nom_normalise(ligne["name"]).split() or mots[0] in nom_normalise(trouve[1]).split()):
        return [ligne["ticker"]]
    return []


# ---------- Événements ----------


def date_fr(jour: str) -> str:
    d = date.fromisoformat(jour)
    return f"{'1er' if d.day == 1 else d.day} {MOIS[d.month - 1]} {d.year}"


def actions_fr(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:,.1f} M d'actions".replace(",", " ").replace(".", ",")
    return f"{n:,.0f} actions".replace(",", " ")


def de(nom: str) -> str:
    return f"d'{nom}" if nom[:1].upper() in "AEIOUYÉÈÊÀÂÎÔÛ" else f"de {nom}"


def classe(titre_officiel: str) -> str:
    """« CAP STK CL A » -> « (classe A) » : distingue deux classes d'actions de la même compagnie."""
    m = re.search(r"\bCL(?:ASS)?\s*([A-C])\b", titre_officiel.upper())
    return f" (classe {m.group(1)})" if m else ""


def titre(fonds: str, m: dict, nom: str, trimestre: str) -> str:
    nom = nom + classe(m.get("classe", ""))
    if m["sorte"] == "nouvelle":
        t = f"{fonds} achète {actions_fr(m['actions_apres'])} {de(nom)} (nouvelle position)"
    elif m["sorte"] == "sortie":
        t = f"{fonds} vend toutes ses actions {de(nom)} ({actions_fr(m['actions_avant'])})"
    else:
        ecart = m["actions_apres"] - m["actions_avant"]
        pct = round(100 * abs(ecart) / m["actions_avant"])
        verbe = "achète" if ecart > 0 else "vend"
        t = f"{fonds} {verbe} {actions_fr(abs(ecart))} {de(nom)} ({'+' if ecart > 0 else '−'}{pct} %)"
    return f"{t}, trimestre au {date_fr(trimestre)}"


def evenements_13f(cik: int, depot: DepotSec, xml_apres: bytes, couv_apres: dict, couv_avant: dict,
                   xml_avant: bytes, acc_avant: str, table: dict, syms) -> list[Evenement]:
    apres, avant = lire_positions(xml_apres), lire_positions(xml_avant)
    if not (comparable(couv_apres, apres) and comparable(couv_avant, avant)):
        return []  # rien plutôt que faux
    fonds = FONDS[cik]
    notes = ["Valeur estimée au prix de fin de trimestre déclaré : le prix réel des transactions n'est pas publié."]
    if apres["en_milliers"] or avant["en_milliers"]:
        notes.append("Le fonds déclare ses valeurs en milliers de dollars : converties en dollars.")
    evs = []
    for m in mouvements(avant, apres):
        tickers = symbole(m["cusip"], m["nom"], table, syms)
        nom = syms.par_symbole(tickers[0])["name"] if tickers else m["nom"]  # nom officiel SEC s'il est sûr
        nom = re.sub(r"\s*[/\\][A-Z]{2,4}/?\s*$", "", nom)  # « BANK OF AMERICA CORP /DE/ » -> sans l'État
        evs.append(Evenement(
            source="sec_13f", official_id=f"{depot.acc}:{m['cusip']}", category="baleines", kind="position_fonds",
            title=titre(fonds, m, nom, couv_apres["trimestre"]), occurred_on=couv_apres["trimestre"],
            published_on=depot.depose, official_url=depot.page_officielle(str(cik)), sha256=empreinte(xml_apres),
            parser_version=VERSION, tickers=tickers, entities=[fonds, nom],
            amount_min=round(m["montant"]), amount_max=round(m["montant"]),
            direction=1 if m["sorte"] in ("nouvelle", "hausse") else -1, notes=list(notes),
            data={**m, "fonds": fonds, "cik_fonds": cik, "trimestre": couv_apres["trimestre"],
                  "trimestre_precedent": couv_avant["trimestre"], "acc_precedent": acc_avant,
                  "sortes_rapports": [couv_avant["sorte"], couv_apres["sorte"]],
                  "positions_cachees": [couv_avant["confidentiel"], couv_apres["confidentiel"]],
                  "lignes": [[couv_avant["lignes_annoncees"], avant["lignes"]], [couv_apres["lignes_annoncees"], apres["lignes"]]]},
        ))
    return evs


@controle_source("sec_13f")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    a, b = d.get("actions_avant", -1), d.get("actions_apres", -1)
    sorte = "nouvelle" if a == 0 else "sortie" if b == 0 else "hausse" if b > a else "baisse"
    return {
        "trimestres_consecutifs": bool(d.get("trimestre")) and d.get("trimestre_precedent") == trimestre_precedent(d["trimestre"]),
        "rapports_complets": d.get("sortes_rapports") == ["13F HOLDINGS REPORT", "13F HOLDINGS REPORT"]
                             and d.get("positions_cachees") == [False, False]
                             and all(a == b for a, b in d.get("lignes") or [[0, 1]]),
        "variation_recalculee": a >= 0 and b >= 0 and a != b and sorte == d.get("sorte")
                                and abs(abs(b - a) * d.get("prix", 0) - d.get("montant", -1)) < 1,
        "prix_plausible": 0.01 <= d.get("prix", 0) <= 1_000_000,
        "part_du_portefeuille_coherente": 0 < d.get("montant", 0) <= d.get("total", 0),
    }


def lire_un_13f(ctx, depot: DepotSec) -> list[Evenement]:
    ciks = [int(c) for c, _ in depot.filers if int(c) in FONDS]
    if not ciks:
        return []  # pas un fonds suivi : aucune requête
    cik = ciks[0]
    dossier = depot.dossier(str(cik))
    fichiers = [f["name"] for f in json.loads(ctx.client.get(f"{dossier}/index.json").contenu)["directory"]["item"]]
    couv_apres = lire_couverture(ctx.client.get(f"{dossier}/primary_doc.xml").contenu)
    if (couv_apres["modification"] or couv_apres["sorte"] != "13F HOLDINGS REPORT" or not couv_apres["trimestre"]
            or couv_apres["confidentiel"]):
        return []  # modification, avis, rapport combiné ou positions cachées : pas comparable
    tables = [f for f in fichiers if f.endswith(".xml") and f != "primary_doc.xml"]
    if len(tables) != 1:
        raise ValueError(f"table des positions introuvable dans {depot.acc} : {fichiers}")
    xml_apres = ctx.client.get(f"{dossier}/{tables[0]}").contenu
    # Le trimestre précédent : le 13F-HR original du même fonds, pour le trimestre juste avant.
    rec = json.loads(ctx.client.get(SUBMISSIONS.format(cik)).contenu)["filings"]["recent"]
    voulu = trimestre_precedent(couv_apres["trimestre"])
    precedents = [acc for forme, acc, rapport in zip(rec["form"], rec["accessionNumber"], rec["reportDate"])
                  if forme == "13F-HR" and rapport == voulu and acc != depot.acc]
    if len(precedents) != 1:
        return []  # aucun (ou plusieurs) rapport du trimestre précédent : pas de comparaison
    acc_avant = precedents[0]
    dossier_avant = f"{ARCHIVES}/edgar/data/{cik}/{acc_avant.replace('-', '')}"
    couv_avant = lire_couverture(ctx.client.get(f"{dossier_avant}/primary_doc.xml").contenu)
    if couv_avant["sorte"] != "13F HOLDINGS REPORT" or couv_avant["trimestre"] != voulu or couv_avant["confidentiel"]:
        return []
    fichiers_avant = [f["name"] for f in
                      json.loads(ctx.client.get(f"{dossier_avant}/index.json").contenu)["directory"]["item"]]
    tables_avant = [f for f in fichiers_avant if f.endswith(".xml") and f != "primary_doc.xml"]
    if len(tables_avant) != 1:
        raise ValueError(f"table des positions introuvable dans {acc_avant}")
    xml_avant = ctx.client.get(f"{dossier_avant}/{tables_avant[0]}").contenu
    # La table des symboles (6 fichiers de la SEC) n'est téléchargée que s'il y a des mouvements à nommer.
    table = table_cusip(ctx) if mouvements(lire_positions(xml_avant), lire_positions(xml_apres)) else {}
    return evenements_13f(cik, depot, xml_apres, couv_apres, couv_avant, xml_avant, acc_avant, table, symboles(ctx))


def collecter(ctx) -> list[Evenement]:
    return lire_journees(ctx, "sec_13f", {"13F-HR"}, lire_un_13f)
