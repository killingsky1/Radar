"""Transactions boursières des élus du Congrès américain (loi STOCK Act) : Sénat et Chambre des représentants.

- Sénat : site officiel efdsearch.senate.gov. Il faut accepter ses conditions (usage non commercial) avant
  de chercher ; les rapports électroniques sont des tableaux web.
- Chambre : index officiel annuel (2026FD.zip) + un PDF par rapport. Le PDF est lu colonne par colonne
  grâce à la position de chaque mot sur la page (pas de devinette).

On garde seulement les actions et options cotées avec un symbole. Les rapports papier (numérisés) et les
amendements (souvent de vieux rapports corrigés) sont laissés de côté : rien plutôt que faux ou en double.
Une info = un élu, un rapport, un symbole, achat ou vente (les petites transactions sont additionnées).

Loi : 5 U.S.C. § 13107 interdit l'usage commercial de ces rapports (sauf les médias). Radar est personnel.
Formats vérifiés sur 59 vrais rapports de la Chambre et 42 du Sénat (septembre-octobre 2026).
"""

from __future__ import annotations

import html
import io
import json
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from ..models import Evenement, empreinte
from ..validate import controle_source

VERSION = "elus-1"
JOURS_EN_ARRIERE = 21
RETARD_LEGAL_JOURS = 45  # STOCK Act : au plus tard 45 jours après la transaction
PLAGES = {  # montants officiels (formulaires du Congrès)
    "$1,001 - $15,000": (1_001, 15_000),
    "$15,001 - $50,000": (15_001, 50_000),
    "$50,001 - $100,000": (50_001, 100_000),
    "$100,001 - $250,000": (100_001, 250_000),
    "$250,001 - $500,000": (250_001, 500_000),
    "$500,001 - $1,000,000": (500_001, 1_000_000),
    "$1,000,001 - $5,000,000": (1_000_001, 5_000_000),
    "$5,000,001 - $25,000,000": (5_000_001, 25_000_000),
    "$25,000,001 - $50,000,000": (25_000_001, 50_000_000),
    "Over $50,000,000": (50_000_001, None),
    "Spouse/DC Over $1,000,000": (1_000_001, None),
    "Over $1,000,000": (1_000_001, None),
}
PROPRIETAIRES = {  # code officiel -> libellé
    "": "l'élu·e", "Self": "l'élu·e", "SP": "conjoint·e", "Spouse": "conjoint·e",
    "JT": "compte conjoint", "Joint": "compte conjoint", "DC": "enfant à charge", "Child": "enfant à charge",
}
DATE_US = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")


def iso_us(texte: str | None) -> str | None:
    m = DATE_US.fullmatch((texte or "").strip())
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(1)), int(m.group(2))).isoformat()
    except ValueError:
        return None


def plage(texte: str) -> tuple[int, int | None] | None:
    return PLAGES.get(" ".join((texte or "").replace("$ ", "$").split()))


def argent(n: float) -> str:
    return f"{n:,.0f}".replace(",", " ") + " $"


@dataclass
class Transaction:
    proprietaire: str  # code officiel (SP, JT, DC, Spouse…) ; vide = l'élu·e
    actif: str
    symbole: str | None
    sorte: str  # action | option
    sens: str  # P (achat) | S (vente) | E (échange)
    partielle: bool
    date: str | None
    montant: str
    option: str | None = None  # call | put
    details: dict = field(default_factory=dict)


@dataclass
class Rapport:
    chambre: str  # senat | chambre
    numero: str
    nom: str
    circonscription: str | None
    depose: str  # AAAA-MM-JJ
    url: str
    sha256: str
    transactions: list[Transaction]
    complet: bool = True  # toutes les lignes du document ont été comprises
    verifs: dict = field(default_factory=dict)  # recoupements entre l'index et le document


# ---------- Regroupement en infos ----------


def evenements(rapport: Rapport, syms) -> list[Evenement]:
    groupes: dict[tuple, list[Transaction]] = {}
    for t in rapport.transactions:
        if t.sens not in ("P", "S") or not t.symbole:
            continue
        groupes.setdefault((t.symbole, t.sens, t.sorte, t.option), []).append(t)
    evs = []
    qui = f"{rapport.nom} ({'Sénat' if rapport.chambre == 'senat' else 'Chambre'}"
    qui += f", {rapport.circonscription})" if rapport.circonscription else ")"
    for (symbole, sens, sorte, option), ts in sorted(groupes.items(), key=lambda g: (g[0][0], g[0][1], g[0][2], g[0][3] or "")):
        plages = [plage(t.montant) for t in ts]
        bas = sum(p[0] for p in plages if p) if all(plages) else None
        haut = None if not all(plages) or any(p[1] is None for p in plages) else sum(p[1] for p in plages)
        verbe = "achète" if sens == "P" else "vend"
        quoi = symbole if sorte == "action" else f"des options {'d’achat (call)' if option == 'call' else 'de vente (put)' if option == 'put' else ''} sur {symbole}".replace("  ", " ")
        combien = f" ({len(ts)} transactions)" if len(ts) > 1 else ""
        montant_txt = ""
        if bas is not None:
            montant_txt = f" : {argent(bas)} à {argent(haut)}" if haut is not None else f" : plus de {argent(bas - 1)}"
        proprios = sorted({PROPRIETAIRES.get(t.proprietaire, t.proprietaire) for t in ts})
        pour = "" if proprios == ["l'élu·e"] else f" — {', '.join(proprios)}"
        dates = sorted(t.date for t in ts if t.date)
        if sorte == "action":
            direction = 1 if sens == "P" else -1
        else:
            direction = {("P", "call"): 1, ("P", "put"): -1}.get((sens, option), 0)
        cote = syms.par_symbole(symbole)
        if cote is None:
            continue  # pas une action cotée au Nasdaq, au NYSE ou au CBOE (FNB, fonds, hors cote) : laissé de côté
        notes = []
        if dates and (date.fromisoformat(rapport.depose) - date.fromisoformat(dates[0])).days > RETARD_LEGAL_JOURS:
            notes.append(f"Déclaré en retard : plus de {RETARD_LEGAL_JOURS} jours après la transaction (limite de la loi STOCK Act).")
        evs.append(Evenement(
            source="senat_ptr" if rapport.chambre == "senat" else "chambre_ptr",
            official_id=f"{rapport.numero}:{symbole}:{sens}{'' if sorte == 'action' else ':' + (option or 'option')}",
            category="politiciens", kind=f"{'achat' if sens == 'P' else 'vente'}_elu" + ("" if sorte == "action" else "_option"),
            title=f"{qui} {verbe} {quoi}{combien}{montant_txt}{pour}",
            occurred_on=dates[0] if dates else rapport.depose, published_on=rapport.depose,
            official_url=rapport.url, sha256=rapport.sha256, parser_version=VERSION,
            tickers=[symbole], entities=[rapport.nom, cote["name"]],
            amount_min=float(bas) if bas is not None else None, amount_max=float(haut) if haut is not None else None,
            direction=direction, notes=notes,
            data={
                "chambre": rapport.chambre, "rapport": rapport.numero, "elu": rapport.nom,
                "circonscription": rapport.circonscription, "lecture_complete": rapport.complet,
                "recoupements": rapport.verifs, "nom_sec": cote["name"],
                "transactions": [{"proprietaire": t.proprietaire, "actif": t.actif, "date": t.date, "montant": t.montant,
                                  "partielle": t.partielle, **t.details} for t in ts],
            },
        ))
    return evs


MOTS_VIDES = {"THE", "INC", "CORP", "CO", "COMPANY", "CORPORATION", "HOLDINGS", "GROUP", "PLC", "LTD", "CLASS"}


def nom_coherent(actif: str, nom_sec: str | None) -> bool:
    """Les 2 premiers mots importants du nom officiel SEC doivent se retrouver dans le nom écrit par l'élu
    (attrape les erreurs de symbole et les symboles réutilisés par une autre compagnie).
    Ex. « JPMORGAN CHASE & CO » et « JP Morgan Chase & Co. Common Stock » : oui.
    « GENERAL MILLS INC » et « General Motors Company » : non."""
    if not nom_sec:
        return False
    colle = re.sub(r"[^A-Z0-9]", "", actif.upper())
    officiel = re.sub(r"\s*/.*$", "", nom_sec.upper())  # « DANAHER CORP /DE/ » : l'État d'incorporation ne compte pas
    mots = [m for m in re.sub(r"[^A-Z0-9 ]", " ", officiel.replace("&", " ")).split() if m not in MOTS_VIDES]
    return bool(mots) and all(m in colle for m in mots[:2])


def _controles(ev: Evenement) -> dict[str, bool]:
    ts = ev.data.get("transactions") or []
    return {
        "lecture_complete": bool(ev.data.get("lecture_complete")),
        "recoupements_index_document": all((ev.data.get("recoupements") or {"aucun": False}).values()),
        "montants_officiels": bool(ts) and all(plage(t["montant"]) for t in ts),
        "dates_transactions_valides": bool(ts) and all(t["date"] and t["date"] <= ev.published_on for t in ts),
        "symbole_cote_sec": bool(ev.data.get("nom_sec")),
        "nom_coherent_avec_symbole": bool(ts) and all(nom_coherent(t["actif"], ev.data.get("nom_sec")) for t in ts),
    }


@controle_source("senat_ptr")
def controles_senat(ev: Evenement) -> dict[str, bool]:
    return _controles(ev)


@controle_source("chambre_ptr")
def controles_chambre(ev: Evenement) -> dict[str, bool]:
    return _controles(ev)


# ---------- Mémoire des rapports déjà lus (y compris ceux sans action) ----------


def _lus(ctx) -> tuple[Path, dict]:
    chemin = Path(ctx.donnees) / "elus" / "rapports_lus.json"
    return chemin, (json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {})


def _noter_lus(ctx, cle: str, numeros: list[str]) -> None:
    chemin, lus = _lus(ctx)
    lus[cle] = (lus.get(cle, []) + [n for n in numeros if n not in lus.get(cle, [])])[-1000:]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(lus, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _symboles(ctx):
    """Liste officielle de la SEC : sans elle, impossible de valider un symbole -> la source attend le prochain passage."""
    from .sec import symboles

    try:
        return symboles(ctx)
    except Exception as exc:
        raise RuntimeError(f"liste officielle des symboles (SEC) indisponible : {exc}") from exc


# ---------- Sénat ----------

SENAT = "https://efdsearch.senate.gov"


def _cellules(rangee: str) -> list[str]:
    return [" ".join(html.unescape(re.sub(r"<[^>]+>", " ", c)).split()) for c in re.findall(r"<td[^>]*>(.*?)</td>", rangee, re.S)]


def lire_page_senat(page: str, numero: str, url: str, sha: str, depose_index: str | None) -> Rapport:
    entete = re.search(r'<h2 class="filedReport">\s*(.*?)\s*</h2>', page, re.S)  # « The Honorable X (X, Y) »
    nom = re.search(r"^(?:(?:The Honorable|Mr\.|Mrs\.|Ms\.|Miss|Dr\.)\s+)?([^(]+?)\s*\(",
                    " ".join(html.unescape(entete.group(1)).split())) if entete else None
    depose = re.search(r"Filed\s+(\d{1,2}/\d{1,2}/\d{4})", page)
    corps = page[page.find("<tbody"):page.find("</tbody>")] if "<tbody" in page else ""
    transactions, complet = [], bool(corps)
    for rangee in re.findall(r"<tr[^>]*>(.*?)</tr>", corps, re.S):
        c = _cellules(rangee)
        if len(c) < 8:
            complet = False
            continue
        _, quand, proprio, symbole, actif, sorte_off, sens_off, montant = c[:8]
        sens = {"Purchase": "P", "Sale (Full)": "S", "Sale (Partial)": "S", "Exchange": "E"}.get(sens_off)
        if sens is None or plage(montant) is None or iso_us(quand) is None:
            complet = False
        if sorte_off not in ("Stock", "Stock Option"):
            continue
        option = None
        if sorte_off == "Stock Option":
            m = re.search(r"Option Type:\s*(Call|Put)", actif, re.I)
            option = m.group(1).lower() if m else None
        symbole = None if symbole in ("", "--") else symbole.upper().replace(".", "-")
        transactions.append(Transaction(
            proprietaire=proprio, actif=actif, symbole=symbole, sorte="action" if sorte_off == "Stock" else "option",
            sens=sens or "?", partielle=sens_off == "Sale (Partial)", date=iso_us(quand), montant=montant, option=option,
            details={"type_officiel": sens_off, "commentaire": c[8] if len(c) > 8 and c[8] != "--" else None},
        ))
    depose_iso = iso_us(depose.group(1)) if depose else None
    return Rapport(
        chambre="senat", numero=numero, nom=" ".join(nom.group(1).split()) if nom else "?", circonscription=None,
        depose=depose_iso or depose_index or "", url=url, sha256=sha, transactions=transactions, complet=complet,
        verifs={"date_de_depot": bool(depose_iso) and depose_iso == depose_index, "nom_lu": bool(nom)},
    )


def collecter_senat(ctx) -> list[Evenement]:
    c = ctx.client
    accueil = c.get(f"{SENAT}/search/home/").contenu.decode("utf-8", "replace")
    jeton = re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', accueil)
    if not jeton:
        raise RuntimeError("page d'accueil du Sénat inattendue (pas de formulaire de conditions)")
    # Accepter les conditions d'utilisation (usage non commercial), comme le ferait une personne.
    c.post(f"{SENAT}/search/home/", {"prohibition_agreement": "1", "csrfmiddlewaretoken": jeton.group(1)},
           entetes={"Referer": f"{SENAT}/search/home/"})
    debut = (ctx.maintenant.date() - timedelta(days=JOURS_EN_ARRIERE)).strftime("%m/%d/%Y 00:00:00")
    rep = c.post(f"{SENAT}/search/report/data/", {
        "start": "0", "length": "100", "report_types": "[11]", "filer_types": "[]",
        "submitted_start_date": debut, "submitted_end_date": "", "candidate_state": "", "senator_state": "",
        "office_id": "", "first_name": "", "last_name": "",
    }, entetes={"X-CSRFToken": c.cookie("csrftoken") or "", "Referer": f"{SENAT}/search/"})
    lignes = json.loads(rep.contenu).get("data")
    if lignes is None:
        raise RuntimeError("réponse de recherche du Sénat inattendue")
    _, lus = _lus(ctx)
    deja = set(lus.get("senat", []))
    syms = _symboles(ctx)
    evs, lus_maintenant = [], []
    for ligne in lignes:
        if len(ligne) < 5 or "(Senator)" not in str(ligne[2]):
            continue
        lien = re.search(r'href="(/search/view/ptr/([0-9a-f-]{36})/)"', str(ligne[3]))
        if not lien or "Amendment" in str(ligne[3]):
            continue  # papier (numérisé) ou amendement : laissé de côté
        numero = lien.group(2)
        if numero in deja:
            continue
        url = SENAT + lien.group(1)
        t = c.get(url)
        rapport = lire_page_senat(t.contenu.decode("utf-8", "replace"), numero, url, t.sha256, iso_us(str(ligne[4])))
        evs.extend(evenements(rapport, syms))
        lus_maintenant.append(numero)
    _noter_lus(ctx, "senat", lus_maintenant)
    return evs


# ---------- Chambre des représentants ----------

CHAMBRE = "https://disclosures-clerk.house.gov/public_disc"
COLONNES = ("id", "proprietaire", "actif", "type", "date", "avis", "montant", "gains")
SUITE_ENTETE = {"Type", "Date", "Gains", ">", "$200?"}  # 2e et 3e lignes de l'entête du tableau


def lire_index_chambre(zip_octets: bytes, annee: int) -> list[dict]:
    with zipfile.ZipFile(io.BytesIO(zip_octets)) as z:
        x = z.read(f"{annee}FD.xml").decode("utf-8", "replace")
    rapports = []
    for m in re.findall(r"<Member>(.*?)</Member>", x, re.S):
        champ = {k: (re.search(rf"<{k}>(.*?)</{k}>", m, re.S) or [None, ""])[1].strip()
                 for k in ("Prefix", "Last", "First", "Suffix", "FilingType", "StateDst", "Year", "FilingDate", "DocID")}
        if champ["FilingType"] == "P" and champ["DocID"].isdigit():
            rapports.append(champ)
    return rapports


def _lignes_de_mots(mots: list[dict]) -> list[list[dict]]:
    lignes: list[list[dict]] = []
    for m in sorted(mots, key=lambda m: (round(m["top"]), m["x0"])):
        if lignes and abs(lignes[-1][0]["top"] - m["top"]) < 3:
            lignes[-1].append(m)
        else:
            lignes.append([m])
    return [sorted(l, key=lambda m: m["x0"]) for l in lignes]


def lire_pdf_chambre(pdf: bytes) -> tuple[dict, list[dict], bool]:
    """Lit un rapport PDF de la Chambre colonne par colonne. Retourne (entête, transactions, lecture_complete)."""
    import pdfplumber

    entete, transactions, bornes = {}, [], None
    courante, etat, etiquettes, fin, etiquettes_statut = None, None, 0, False, 0
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        for page in doc.pages:
            lignes = _lignes_de_mots(page.extract_words())
            debut = 0
            for i, l in enumerate(lignes):  # l'entête du tableau donne la position de chaque colonne
                textes = [m["text"] for m in l]
                if "Owner" in textes and "Asset" in textes and "Notification" in textes:
                    x = {m["text"]: m["x0"] for m in reversed(l)}
                    dates = [m["x0"] for m in l if m["text"] == "Date"]
                    bornes = [x["Owner"], x["Asset"], x["Transaction"], dates[0], x["Notification"], x["Amount"], x["Cap."]]
                    debut = i + 1
                    while debut < len(lignes) and {m["text"] for m in lignes[debut]} <= SUITE_ENTETE:
                        debut += 1
                    break
            for l in lignes[:debut]:
                texte = " ".join(m["text"] for m in l)
                for cle, motif in (("numero", r"Filing ID #(\d+)"), ("nom", r"^Name:\s*(.+)$"),
                                   ("circonscription", r"^State/District:\s*(\S+)")):
                    mm = re.search(motif, texte)
                    if mm and cle not in entete:
                        entete[cle] = mm.group(1).strip()
            if bornes is None or fin:
                continue
            for l in lignes[debut:]:
                cellules = {c: [] for c in COLONNES}
                for m in l:
                    col = sum(1 for b in bornes if m["x0"] >= b - 3)
                    cellules[COLONNES[col]].append(m["text"])
                c = {k: " ".join(v) for k, v in cellules.items()}
                if c["id"].startswith("*") or "asset type abbreviations" in " ".join(m["text"] for m in l):
                    fin = True
                    break
                if DATE_US.fullmatch(c["date"]) and DATE_US.fullmatch(c["avis"]):
                    courante = {"proprietaire": c["proprietaire"], "actif": [c["actif"]], "type": c["type"],
                                "date": c["date"], "avis": c["avis"], "montant": [c["montant"]], "etiquettes": {}}
                    transactions.append(courante)
                    etat = "actif"
                    continue
                if courante is None:
                    continue
                if "\x00" in c["actif"]:  # étiquette (STATUT, DÉTENU PAR, DESCRIPTION…) : lettres masquées dans le PDF
                    mots = c["actif"].split()
                    cle, reste = "", []
                    for j, mot in enumerate(mots):
                        if mot == ":" or "\x00" in mot:
                            cle += mot[0] if mot != ":" else ""
                            if mot.endswith(":"):
                                reste = mots[j + 1:]
                                break
                    courante["etiquettes"][cle] = " ".join(reste)
                    etat = cle
                    if cle == "FS":
                        etiquettes_statut += 1
                    continue
                if etat == "actif":
                    courante["actif"].append(c["actif"])
                    courante["montant"].append(c["montant"])
                elif etat:
                    courante["etiquettes"][etat] = (courante["etiquettes"][etat] + " " + c["actif"]).strip()
    for t in transactions:
        t["actif"] = " ".join(x for x in t["actif"] if x)
        t["montant"] = " ".join(x for x in t["montant"] if x)
    # Chaque transaction du formulaire a exactement une ligne « statut » : sinon, une ligne a été mal comprise.
    complet = bool(transactions) and etiquettes_statut == len(transactions)
    return entete, transactions, complet


def rapport_chambre(info: dict, pdf: bytes, url: str) -> Rapport | None:
    entete, brutes, complet = lire_pdf_chambre(pdf)
    if not entete and not brutes:
        return None  # PDF numérisé (rapport papier) : aucune lettre lisible
    transactions = []
    for b in brutes:
        actif = b["actif"]
        code = re.findall(r"\[([A-Z0-9]{2})\]", actif)
        symbole = re.findall(r"\(([A-Z][A-Z0-9.]{0,6})\)", actif)
        sens = {"P": "P", "S": "S", "S (partial)": "S", "E": "E"}.get(b["type"])
        if sens is None or plage(b["montant"]) is None or iso_us(b["date"]) is None:
            complet = False
        sorte = {"ST": "action", "OP": "option"}.get(code[-1] if code else "")
        if sorte is None:
            continue
        desc = b["etiquettes"].get("D", "")
        option = None
        if sorte == "option":
            option = "call" if re.search(r"\bcall", desc, re.I) else "put" if re.search(r"\bput", desc, re.I) else None
        transactions.append(Transaction(
            proprietaire=b["proprietaire"], actif=actif, symbole=symbole[-1].replace(".", "-") if symbole else None,
            sorte=sorte, sens=sens or "?", partielle=b["type"] == "S (partial)", date=iso_us(b["date"]),
            montant=b["montant"], option=option,
            details={"type_officiel": b["type"], "avis": iso_us(b["avis"]), "description": desc or None},
        ))
    nom_index = " ".join(x for x in (info["First"], info["Last"], info["Suffix"]) if x)
    return Rapport(
        chambre="chambre", numero=info["DocID"], nom=" ".join(x for x in (info["First"], info["Last"]) if x),
        circonscription=info["StateDst"] or None, depose=iso_us(info["FilingDate"]) or "", url=url,
        sha256=empreinte(pdf), transactions=transactions, complet=complet,
        verifs={
            "numero": entete.get("numero") == info["DocID"],
            "nom": bool(info["Last"]) and info["Last"].lower() in (entete.get("nom") or "").lower(),
            "circonscription": entete.get("circonscription") == info["StateDst"],
        } | ({} if nom_index else {"nom_index": False}),
    )


def collecter_chambre(ctx) -> list[Evenement]:
    aujourd_hui = ctx.maintenant.date()
    depuis = (aujourd_hui - timedelta(days=JOURS_EN_ARRIERE)).isoformat()
    infos = []
    for annee in sorted({aujourd_hui.year, (aujourd_hui - timedelta(days=JOURS_EN_ARRIERE)).year}):
        z = ctx.client.get(f"{CHAMBRE}/financial-pdfs/{annee}FD.zip").contenu
        infos += [i for i in lire_index_chambre(z, annee) if (iso_us(i["FilingDate"]) or "") >= depuis]
    _, lus = _lus(ctx)
    deja = set(lus.get("chambre", []))
    syms = _symboles(ctx)
    evs, lus_maintenant, illisibles = [], [], 0
    for info in sorted(infos, key=lambda i: (iso_us(i["FilingDate"]), i["DocID"])):
        if info["DocID"] in deja:
            continue
        url = f"{CHAMBRE}/ptr-pdfs/{info['Year']}/{info['DocID']}.pdf"
        try:
            pdf = ctx.client.get(url).contenu
            rapport = rapport_chambre(info, pdf, url)
        except Exception:  # noqa: BLE001 - un PDF bizarre ne doit pas tout arrêter
            illisibles += 1
            continue
        if rapport is not None:
            evs.extend(evenements(rapport, syms))
        lus_maintenant.append(info["DocID"])
    if illisibles > max(3, len(infos) * 0.1):
        raise RuntimeError(f"{illisibles} rapports illisibles sur {len(infos)}")
    _noter_lus(ctx, "chambre", lus_maintenant)
    return evs
