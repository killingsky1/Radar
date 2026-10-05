"""Lecteurs SEC : formulaire 4 (dirigeants), 8-K (événements majeurs), 13D/13G (plus de 5 %).

Tout part de l'index officiel des dépôts d'une journée (master.AAAAMMJJ.idx) : une liste complète, publiée par la SEC.
Les symboles viennent de la liste officielle de la SEC (company_tickers_exchange.json) :
on garde seulement les compagnies cotées au Nasdaq, au NYSE ou au CBOE (pas les fonds communs ni le hors-cote).

Formats vérifiés sur de vrais documents du 1er octobre 2026 (formulaire 4 : schéma X0609 ; 13D : X0202).
"""

from __future__ import annotations

import html
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from ..models import Evenement, empreinte
from ..store import Depot
from ..validate import controle_source, jours_ouvrables

VERSION = "sec-7"  # à augmenter quand un lecteur change : les infos sont relues et mises à jour
ARCHIVES = "https://www.sec.gov/Archives"
BOURSES_GARDEES = {"Nasdaq", "NYSE", "CBOE"}
SEUIL_ACHAT = 25_000  # $ US : sous ce montant, un achat est du bruit
SEUIL_VENTE = 1_000_000  # $ US : seules les grosses ventes comptent
JOURS_OUVRABLES_EN_ARRIERE = 3  # jours ouvrables rattrapés si des passages ont été manqués
FORMES_13 = {"SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G"}
# Au-dessus de ce prix par action, c'est presque toujours une erreur de frappe dans le document
# (ex. le prix total écrit dans la case « prix par action »). Exception : les rares actions qui valent vraiment autant.
PRIX_MAX = 2_000
PRIX_MIN = 0.10  # sous 10 cents l'action, une vente de 1 M$ et plus au Nasdaq ou au NYSE est presque toujours une erreur
PRIX_ELEVES = {"BRK-A", "NVR", "BKNG", "AZO", "SEB", "FCNCA", "MKL", "WTM", "FICO", "TPL"}
VALEUR_MAX = 5_000_000_000  # une seule déclaration de plus de 5 G$ : à vérifier
# Note du déposant qui dit que la transaction ne s'est pas faite en bourse : émission (entrée en bourse, placement)
# ou transaction négociée en privé. Seules les notes rattachées à la transaction elle-même comptent (pas celles sur
# les actions détenues après ni sur la forme de détention).
HORS_BOURSE = re.compile(r"initial public offering|\bIPO\b|public offering|private placement|privately negotiated|"
                         r"not effected on (?:a|any) (?:national )?securities exchange|registered direct offering|"
                         r"directed share program", re.I)
PARTIES_TRANSACTION = ("securityTitle", "transactionDate", "transactionCoding", "transactionAmounts")
# Note du déposant qui dit que l'achat est automatique : réinvestissement de dividendes, régime d'achat d'actions des
# employés. Ce n'est pas une décision d'acheter (ex. Simon Property, 1er oct. 2026 : 7 administrateurs).
AUTOMATIQUE = re.compile(r"reinvest\w*\s+(?:of\s+)?(?:the\s+)?dividends?|dividends?\s+reinvest\w*|"
                         r"employee stock purchase plan", re.I)
SOUS_EVALUE = re.compile(r"undervalu", re.I)  # « undervalued », « undervaluation » (point 4 d'un 13D)

ITEMS_8K = {  # description officielle EDGAR (début) -> (item, libellé, direction)
    "entry into a material definitive agreement": ("1.01", "contrat important signé", 0),
    "termination of a material definitive agreement": ("1.02", "contrat important résilié", -1),
    "bankruptcy or receivership": ("1.03", "faillite ou mise sous séquestre", -1),
    "material cybersecurity incidents": ("1.05", "cyberattaque importante", -1),
    "completion of acquisition or disposition of assets": ("2.01", "acquisition ou vente d'actifs complétée", 0),
    "costs associated with exit or disposal activities": ("2.05", "restructuration (fermetures, mises à pied)", -1),
    "material impairments": ("2.06", "dépréciation importante d'actifs", -1),
    "notice of delisting or failure to satisfy": ("3.01", "avis de retrait de la bourse", -1),
    "changes in registrant's certifying accountant": ("4.01", "changement de vérificateur comptable", -1),
    "non-reliance on previously issued financial statements": ("4.02", "états financiers passés à ne plus croire", -1),
    "changes in control of registrant": ("5.01", "changement de contrôle", 0),
}


# ---------- Outils communs ----------


@dataclass
class DepotSec:
    acc: str  # numéro officiel, ex. 0001822293-26-000002
    forme: str
    depose: str  # AAAA-MM-JJ
    fichier: str  # edgar/data/…/acc.txt
    filers: list[tuple[str, str]] = field(default_factory=list)  # (cik, nom)

    def dossier(self, cik: str) -> str:
        return f"{ARCHIVES}/edgar/data/{int(cik)}/{self.acc.replace('-', '')}"

    def page_officielle(self, cik: str) -> str:
        return f"{self.dossier(cik)}/{self.acc}-index.htm"


def lire_index(texte: str) -> dict[str, DepotSec]:
    """master.idx -> {numéro: DepotSec}. Un dépôt apparaît une fois par déposant (ex. dirigeant + compagnie)."""
    depots: dict[str, DepotSec] = {}
    for ligne in texte.splitlines():
        morceaux = ligne.split("|")
        if len(morceaux) != 5 or not morceaux[0].strip().isdigit():
            continue
        cik, nom, forme, depose, fichier = (m.strip() for m in morceaux)
        depose = depose.replace("-", "")  # index du jour : 20260813 ; index du trimestre : 2026-08-13
        acc = fichier.rsplit("/", 1)[-1].removesuffix(".txt")
        d = depots.setdefault(acc, DepotSec(acc, forme, f"{depose[:4]}-{depose[4:6]}-{depose[6:8]}", fichier))
        d.filers.append((cik, nom))
    return depots


class Symboles:
    """Liste officielle de la SEC : CIK -> symboles cotés en bourse."""

    def __init__(self, donnees: dict):
        champs = donnees["fields"]
        self.par_cik: dict[int, list[dict]] = {}
        for ligne in donnees["data"]:
            r = dict(zip(champs, ligne))
            self.par_cik.setdefault(int(r["cik"]), []).append(r)

    def cote(self, cik: str | int) -> dict | None:
        """Le symbole de l'action ordinaire cotée au Nasdaq, au NYSE ou au CBOE, sinon None.

        Une compagnie peut avoir plusieurs symboles (ex. GME et GME-WT, des bons de souscription) :
        on préfère celui sans suffixe.
        """
        cotes = [r for r in self.par_cik.get(int(cik), []) if r["exchange"] in BOURSES_GARDEES]
        return next((r for r in cotes if "-" not in r["ticker"]), cotes[0] if cotes else None)

    def tous(self, cik: str | int) -> list[str]:
        return [r["ticker"] for r in self.par_cik.get(int(cik), [])]

    def par_symbole(self, symbole: str) -> dict | None:
        """La ligne officielle d'un symbole coté au Nasdaq, au NYSE ou au CBOE (ex. « BRK-B »), sinon None."""
        if not hasattr(self, "_par_symbole"):
            self._par_symbole = {r["ticker"]: r for rs in self.par_cik.values() for r in rs
                                 if r["exchange"] in BOURSES_GARDEES}
        return self._par_symbole.get(normaliser_symbole(symbole))

    def par_nom(self, nom: str | None) -> dict | None:
        """La compagnie cotée dont le nom officiel est EXACTEMENT ce nom (formes juridiques et ponctuation à part).

        Rien si le nom est ambigu ou absent : une filiale (« Takeda Pharmaceuticals America ») n'est pas
        rattachée à sa mère cotée, et une abréviation (« IONIS PHARMS ») n'est pas devinée.
        """
        if not hasattr(self, "_par_nom"):
            self._par_nom: dict[str, set[int]] = {}
            for cik, rs in self.par_cik.items():
                for r in rs:
                    if r["exchange"] in BOURSES_GARDEES and r.get("name"):
                        self._par_nom.setdefault(nom_normalise(r["name"]), set()).add(cik)
        n = nom_normalise(nom or "")
        ciks = self._par_nom.get(n, set()) if n else set()
        return self.cote(next(iter(ciks))) if len(ciks) == 1 else None


def normaliser_symbole(s: str | None) -> str:
    return (s or "").strip().upper().replace(".", "-")


FORMES_JURIDIQUES = {"INC", "INCORPORATED", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "LIMITED", "LTEE", "PLC",
                     "LLC", "LP", "LLP", "AG", "SA", "NV", "SE", "AB", "ASA", "SPA", "BV", "ULC"}


def nom_normalise(nom: str) -> str:
    """« Eli Lilly and Company » et « ELI LILLY & Co » -> « ELI LILLY AND » : pour comparer des noms officiels."""
    n = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode().upper().replace("&", " AND ")
    n = re.sub(r"[/\\]\s*[A-Z]{2,4}[/\\]?\s*$", " ", n)  # suffixes de la SEC : « /DE/ », « /CAN/ », « \DE »
    mots = re.findall(r"[A-Z0-9]+", n)
    while mots and (mots[-1] in FORMES_JURIDIQUES or len(mots[-1]) == 1):  # « L.L.C. », « S.A. »
        mots.pop()
    if mots and mots[0] == "THE":
        mots.pop(0)
    return " ".join(mots)


def entete(texte: str) -> dict[str, str]:
    """Quelques champs de l'en-tête officiel (SGML) d'un dépôt."""
    champs = {}
    for cle, motif in {
        "acc": r"ACCESSION NUMBER:\s*([\d-]+)",
        "type": r"CONFORMED SUBMISSION TYPE:\s*(\S[^\n]*)",
        "depose": r"FILED AS OF DATE:\s*(\d{8})",
        "periode": r"CONFORMED PERIOD OF REPORT:\s*(\d{8})",
        "accepte": r"<ACCEPTANCE-DATETIME>\s*(\d{14})",
    }.items():
        m = re.search(motif, texte)
        if m:
            champs[cle] = m.group(1).strip()
    return champs


def iso(aaaammjj: str | None) -> str | None:
    return f"{aaaammjj[:4]}-{aaaammjj[4:6]}-{aaaammjj[6:8]}" if aaaammjj and len(aaaammjj) == 8 else None


def xml_du_depot(texte: str) -> ET.Element:
    """Le document XML principal du dépôt, sans les espaces de noms (plus simple à lire)."""
    m = re.search(r"<XML>\s*(.*?)\s*</XML>", texte, re.S)
    if not m:
        raise ValueError("aucun document XML dans le dépôt")
    racine = ET.fromstring(m.group(1).strip())
    for el in racine.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return racine


def oui(valeur: str | None) -> bool:
    return (valeur or "").strip().lower() in ("1", "true")


def nombre(valeur: str | None) -> float | None:
    try:
        return float((valeur or "").replace(",", "").strip())
    except ValueError:
        return None


MOIS_FR = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre",
           "novembre", "décembre")


def date_fr(iso_jour: str) -> str:
    d = date.fromisoformat(iso_jour)
    return f"{'1er' if d.day == 1 else d.day} {MOIS_FR[d.month - 1]} {d.year}"


def nombre_fr(n: float) -> str:
    return f"{n:,.0f}".replace(",", " ")


# ---------- Index du jour, partagé par les trois lecteurs ----------


def jours_a_lire(maintenant: datetime, deja: set[str]) -> list[date]:
    """Les derniers jours ouvrables (avant aujourd'hui) pas encore lus."""
    jours, d, ouvrables = [], maintenant.date(), 0
    while ouvrables < JOURS_OUVRABLES_EN_ARRIERE:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            ouvrables += 1
            if d.isoformat() not in deja:
                jours.append(d)
    return sorted(jours)


def index_du_jour(ctx, jour: date) -> tuple[dict[str, DepotSec] | None, str | None]:
    cache = ctx.cache.setdefault("sec_index", {})
    if jour not in cache:
        url = f"{ARCHIVES}/edgar/daily-index/{jour.year}/QTR{(jour.month - 1) // 3 + 1}/master.{jour:%Y%m%d}.idx"
        try:
            t = ctx.client.get(url)
            cache[jour] = (lire_index(t.contenu.decode("latin-1")), t.sha256)
        except Exception as exc:  # index pas encore publié (ou jour férié) : on réessaiera au prochain passage
            if "403" in str(exc) or "404" in str(exc):
                cache[jour] = (None, None)
            else:
                raise
    return cache[jour]


def symboles(ctx) -> Symboles:
    if "sec_symboles" not in ctx.cache:
        t = ctx.client.get("https://www.sec.gov/files/company_tickers_exchange.json")
        ctx.cache["sec_symboles"] = Symboles(json.loads(t.contenu))
    return ctx.cache["sec_symboles"]


def jours_lus(ctx) -> tuple[Path, dict]:
    chemin = Path(ctx.donnees) / "sec" / "jours_lus.json"
    return chemin, (json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {})


def lire_journees(ctx, source: str, formes: set[str], lire_un) -> list[Evenement]:
    """Pour chaque journée pas encore lue : lit chaque dépôt des formes voulues avec `lire_un`.

    Un document illisible est sauté (rien plutôt que faux), mais s'il y en a trop, la source tombe en panne.
    """
    symboles(ctx)  # si la SEC nous bloque, ça plante ici (source en panne) au lieu de passer inaperçu
    chemin, lus = jours_lus(ctx)
    deja = set(lus.get(source, []))
    tous: list[Evenement] = []
    for jour in jours_a_lire(ctx.maintenant, deja):
        depots, _ = index_du_jour(ctx, jour)
        if depots is None:
            continue
        choisis = [d for d in depots.values() if d.forme in formes]
        illisibles = 0
        for d in choisis:
            try:
                tous.extend(lire_un(ctx, d))
            except Exception:  # noqa: BLE001 - un document bizarre ne doit pas tout arrêter
                illisibles += 1
        if choisis and illisibles > max(3, len(choisis) * 0.05):
            raise RuntimeError(f"{illisibles} documents illisibles sur {len(choisis)} le {jour}")
        deja.add(jour.isoformat())
    lus[source] = sorted(deja)[-30:]
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(lus, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return tous


# ---------- Formulaire 4 : achats et ventes des dirigeants ----------


def lire_form4(texte: str) -> dict:
    racine = xml_du_depot(texte)
    if racine.tag != "ownershipDocument":
        raise ValueError(f"document inattendu : {racine.tag}")
    proprietaires = []
    for p in racine.findall("reportingOwner"):
        rel = p.find("reportingOwnerRelationship")
        proprietaires.append({
            "cik": p.findtext("reportingOwnerId/rptOwnerCik"),
            "nom": (p.findtext("reportingOwnerId/rptOwnerName") or "").strip(),
            "administrateur": oui(rel.findtext("isDirector")) if rel is not None else False,
            "dirigeant": oui(rel.findtext("isOfficer")) if rel is not None else False,
            "dix_pourcent": oui(rel.findtext("isTenPercentOwner")) if rel is not None else False,
            "titre": ((rel.findtext("officerTitle") if rel is not None else "") or "").strip(),
        })
    notes = {n.get("id"): " ".join((n.text or "").split()) for n in racine.findall("footnotes/footnote")}
    transactions = []
    for tr in racine.findall("nonDerivativeTable/nonDerivativeTransaction"):
        ids = sorted({f.get("id") for partie in PARTIES_TRANSACTION for el in tr.findall(partie) for f in el.iter("footnoteId")})
        hors_bourse = next((notes[i][:300] for i in ids if HORS_BOURSE.search(notes.get(i, ""))), None)
        automatique = next((notes[i][:300] for i in ids if AUTOMATIQUE.search(notes.get(i, ""))), None)
        transactions.append({
            "code": (tr.findtext("transactionCoding/transactionCode") or "").strip(),
            "date": (tr.findtext("transactionDate/value") or "").strip()[:10],
            "actions": nombre(tr.findtext("transactionAmounts/transactionShares/value")),
            "prix": nombre(tr.findtext("transactionAmounts/transactionPricePerShare/value")),
            "acquis_cede": (tr.findtext("transactionAmounts/transactionAcquiredDisposedCode/value") or "").strip(),
            "apres": nombre(tr.findtext("postTransactionAmounts/sharesOwnedFollowingTransaction/value")),
            "hors_bourse": hors_bourse,
            "automatique": automatique,
        })
    return {
        "type": racine.findtext("documentType"),
        "cik_emetteur": (racine.findtext("issuer/issuerCik") or "").strip(),
        "nom_emetteur": (racine.findtext("issuer/issuerName") or "").strip(),
        "symbole_declare": (racine.findtext("issuer/issuerTradingSymbol") or "").strip(),
        "plan_10b5_1": oui(racine.findtext("aff10b5One")),
        "proprietaires": proprietaires,
        "transactions": transactions,
    }


def role(p: dict) -> str:
    if p["dirigeant"] and p["titre"]:
        return p["titre"]
    if p["dirigeant"]:
        return "dirigeant"
    if p["administrateur"]:
        return "administrateur"
    if p["dix_pourcent"]:
        return "actionnaire de 10 %"
    return "initié"


def evenements_form4(texte: str, sha: str, depot: DepotSec, syms: Symboles) -> list[Evenement]:
    f = lire_form4(texte)
    h = entete(texte)
    cote = syms.cote(f["cik_emetteur"])
    if cote is None:  # fonds commun, hors-cote ou compagnie inconnue : pas une action cotée
        return []
    publie = iso(h.get("depose")) or depot.depose
    noms = [p["nom"] for p in f["proprietaires"]]
    roles = sorted({role(p) for p in f["proprietaires"]})
    evenements = []
    for code, verbe, seuil, direction in (("P", "achète", SEUIL_ACHAT, 1), ("S", "vend", SEUIL_VENTE, -1)):
        lignes = [t for t in f["transactions"] if t["code"] == code]
        if not lignes:
            continue
        valeur = sum((t["actions"] or 0) * (t["prix"] or 0) for t in lignes)
        actions = sum(t["actions"] or 0 for t in lignes)
        if valeur < seuil:
            continue
        dates = sorted(t["date"] for t in lignes if t["date"])
        notes = []
        retard = jours_ouvrables(date.fromisoformat(dates[0]), date.fromisoformat(publie)) if dates else 0
        if retard > 2:
            notes.append(f"Déclaré en retard : {retard} jours ouvrables après la transaction (limite légale : 2).")
        if code == "S" and f["plan_10b5_1"]:
            notes.append("Vente prévue d'avance (plan 10b5-1) : moins révélatrice qu'une vente décidée sur le moment.")
        hors_bourse = next((t["hors_bourse"] for t in lignes if t.get("hors_bourse")), None)
        if hors_bourse:
            extrait = hors_bourse if len(hors_bourse) <= 160 else hors_bourse[:159] + "…"
            notes.append(f"Note du déposant : transaction lors d'une émission ou hors bourse (« {extrait} »).")
        automatique = next((t["automatique"] for t in lignes if t.get("automatique")), None)
        if automatique:
            extrait = automatique if len(automatique) <= 160 else automatique[:159] + "…"
            notes.append(f"Note du déposant : achat automatique (réinvestissement de dividendes ou régime d'achat des "
                         f"employés) (« {extrait} »).")
        titre = f"{' et '.join(noms)} ({', '.join(roles)}) {verbe} {nombre_fr(actions)} actions de {cote['name']}"
        evenements.append(Evenement(
            source="sec_form4", official_id=f"{depot.acc}:{code}", category="compagnies",
            kind="achat_initie" if code == "P" else "vente_initie", title=titre,
            occurred_on=dates[0] if dates else publie, published_on=publie,
            official_url=depot.page_officielle(f["cik_emetteur"]), sha256=sha, parser_version=VERSION,
            tickers=[cote["ticker"]], entities=noms + [cote["name"]],
            amount_min=round(valeur, 2), amount_max=round(valeur, 2), direction=direction, notes=notes,
            data={
                "cik_emetteur": f["cik_emetteur"], "bourse": cote["exchange"], "symbole_declare": f["symbole_declare"],
                "symboles_sec": syms.tous(f["cik_emetteur"]), "actions": actions,
                "prix_moyen": round(valeur / actions, 4) if actions else None, "plan_10b5_1": f["plan_10b5_1"],
                "roles": roles, "transactions": lignes, "hors_bourse": hors_bourse, "automatique": automatique,
                # Lot L : pour reconnaître les initiés routiniers (même numéro CIK que dans les jeux de données)
                "proprietaires_cik": [str(int(p["cik"])) for p in f["proprietaires"] if (p["cik"] or "").strip().isdigit()],
            },
        ))
    return evenements


@controle_source("sec_form4")
def controles_form4(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    code = "P" if ev.kind == "achat_initie" else "S"
    lignes = d.get("transactions", [])
    declare = normaliser_symbole(d.get("symbole_declare"))
    recalcule = sum(t["actions"] * t["prix"] for t in lignes if t["actions"] and t["prix"])
    return {
        "code_achat_ou_vente_reel": bool(lignes) and all(
            t["code"] == code and t["acquis_cede"] == ("A" if code == "P" else "D") for t in lignes),
        "prix_et_actions_positifs": bool(lignes) and all((t["actions"] or 0) > 0 and (t["prix"] or 0) > 0 for t in lignes),
        # Le symbole écrit par le déclarant doit correspondre à la liste officielle de la SEC (s'il en a écrit un).
        "symbole_conforme_sec": not declare or declare in {normaliser_symbole(s) for s in d.get("symboles_sec", [])},
        "montant_recalcule": abs(recalcule - (ev.amount_max or 0)) <= max(1.0, 0.005 * recalcule),
        "prix_plausible": all((t["prix"] or 0) <= (1_000_000 if ev.tickers[:1] and ev.tickers[0] in PRIX_ELEVES else PRIX_MAX)
                              for t in lignes),
        "montant_plausible": (ev.amount_max or 0) <= VALEUR_MAX,
        "dates_transaction_valides": all(t["date"] and t["date"] <= ev.published_on for t in lignes),
    }


def lire_un_form4(ctx, depot: DepotSec) -> list[Evenement]:
    t = ctx.client.get(f"{ARCHIVES}/{depot.fichier}")
    return evenements_form4(t.contenu.decode("utf-8", "replace"), t.sha256, depot, symboles(ctx))


def collecter_form4(ctx) -> list[Evenement]:
    return lire_journees(ctx, "sec_form4", {"4"}, lire_un_form4)


# ---------- 8-K : événements majeurs ----------


def lire_8k(entete_html: str) -> dict:
    texte = html.unescape(entete_html)
    items = []
    for desc in re.findall(r"ITEM INFORMATION:\s*([^\n<]+)", texte):
        bas = desc.strip().lower()
        for prefixe, (item, libelle, direction) in ITEMS_8K.items():
            if bas.startswith(prefixe):
                items.append({"item": item, "libelle": libelle, "direction": direction, "officiel": desc.strip()})
    filers = re.findall(r"COMPANY CONFORMED NAME:\s*([^\n]+)\n\s*CENTRAL INDEX KEY:\s*(\d+)", texte)
    return {**entete(texte), "items": items, "filers": [(cik, nom.strip()) for nom, cik in filers]}


def evenements_8k(entete_html: str, sha: str, depot: DepotSec, syms: Symboles) -> list[Evenement]:
    f = lire_8k(entete_html)
    if not f["items"]:
        return []
    cik, cote = next(((c, syms.cote(c)) for c, _ in f["filers"] if syms.cote(c)), (None, None))
    if cote is None:
        return []
    publie = iso(f.get("depose")) or depot.depose
    return [Evenement(
        source="sec_8k", official_id=depot.acc, category="compagnies", kind="evenement_8k",
        title=f"{cote['name']} : {' + '.join(i['libelle'] for i in f['items'])}",
        occurred_on=min(iso(f.get("periode")) or publie, publie), published_on=publie,
        official_url=depot.page_officielle(cik), sha256=sha, parser_version=VERSION,
        tickers=[cote["ticker"]], entities=[cote["name"]],
        direction=-1 if any(i["direction"] < 0 for i in f["items"]) else 0,
        data={"cik": cik, "bourse": cote["exchange"], "items": f["items"], "type": f.get("type")},
    )]


@controle_source("sec_8k")
def controles_8k(ev: Evenement) -> dict[str, bool]:
    items = ev.data.get("items", [])
    return {
        "items_officiels_reconnus": bool(items) and all(i["item"] in {v[0] for v in ITEMS_8K.values()} for i in items),
        "type_8k": ev.data.get("type") == "8-K",
    }


def empreinte_entete(entete_html: str) -> str:
    """Empreinte de l'en-tête officiel du dépôt (<SEC-HEADER>…</SEC-HEADER>), espaces normalisés.

    Mesuré le 3 octobre 2026 : pour 9 dépôts, les octets de la page « -index-headers.html » ne correspondaient
    plus à ceux lus par le robot la veille, alors que les faits étaient identiques et que la SEC donne une date de
    modification antérieure. Cause inconnue (la copie lue n'avait pas été gardée). L'empreinte porte donc sur
    l'en-tête officiel lui-même, pas sur la page qui l'entoure.
    """
    m = re.search(r"<SEC-HEADER>.*?</SEC-HEADER>", entete_html, re.S)
    return empreinte(" ".join((m.group(0) if m else entete_html).split()).encode("utf-8"))


def lire_un_8k(ctx, depot: DepotSec) -> list[Evenement]:
    cik = depot.filers[0][0]
    t = ctx.client.get(f"{depot.dossier(cik)}/{depot.acc}-index-headers.html")
    texte = t.contenu.decode("utf-8", "replace")
    ctx.cache.setdefault("entetes_8k", {})[depot.acc] = texte  # réutilisé par les participations (pas de 2e lecture)
    return evenements_8k(texte, empreinte_entete(texte), depot, symboles(ctx))


def collecter_8k(ctx) -> list[Evenement]:
    return lire_journees(ctx, "sec_8k", {"8-K"}, lire_un_8k)


# ---------- 13D / 13G : un gros joueur dépasse 5 % ----------


def lire_13dg(texte: str) -> dict:
    racine = xml_du_depot(texte)
    if racine.tag != "edgarSubmission":
        raise ValueError(f"document inattendu : {racine.tag}")
    type_depot = (racine.findtext("headerData/submissionType") or "").strip()
    entete_xml = racine.find("formData/coverPageHeader")
    if type_depot.startswith("SCHEDULE 13D"):
        emetteur = entete_xml.find("issuerInfo")
        cik = emetteur.findtext("issuerCIK")
        nom = emetteur.findtext("issuerName")
        date_evt = entete_xml.findtext("dateOfEvent")
        noeuds = racine.findall("formData/reportingPersons/reportingPersonInfo")
        personnes = [(p.findtext("reportingPersonName"), nombre(p.findtext("percentOfClass")),
                      nombre(p.findtext("aggregateAmountOwned"))) for p in noeuds]
        item4 = racine.find("formData/items1To7/item4")  # « Purpose of Transaction » : le but écrit par le déclarant
        but = " ".join(" ".join(item4.itertext()).split()) if item4 is not None else None
    else:
        cik = entete_xml.findtext("issuerInfo/issuerCik") or entete_xml.findtext(".//issuerCik")
        nom = entete_xml.findtext("issuerInfo/issuerName") or entete_xml.findtext(".//issuerName")
        date_evt = entete_xml.findtext("eventDateRequiresFilingThisStatement")
        noeuds = racine.findall("formData/coverPageHeaderReportingPersonDetails")
        personnes = [(p.findtext("reportingPersonName"), nombre(p.findtext("classPercent")),
                      nombre(p.findtext("reportingPersonBeneficiallyOwnedAggregateNumberOfShares"))) for p in noeuds]
        but = None
    personnes = [p for p in personnes if p[0]]
    # Type officiel de chaque déclarant (IA = gestionnaire de placements, IN = individu, CO = compagnie…)
    types = sorted({(t.text or "").strip() for n in noeuds for t in n.findall("typeOfReportingPerson")} - {""})
    if not personnes:
        raise ValueError("aucune personne déclarante")
    # Plusieurs personnes d'un même groupe déclarent souvent les mêmes actions : on garde le plus gros pourcentage.
    principale = max(personnes, key=lambda p: p[1] or 0)
    mois, jour, annee = (date_evt or "//").strip().split("/")
    return {
        "type": type_depot, "cik_emetteur": (cik or "").strip(), "nom_emetteur": (nom or "").strip(),
        "date_evenement": f"{annee}-{mois}-{jour}" if annee else None,
        "declarant": principale[0].strip(), "pourcentage": principale[1], "actions": principale[2],
        "nb_personnes": len(personnes), "types_declarants": types, "amendement": entete_xml.findtext("amendmentNo"),
        # Le déclarant écrit-il que l'action est sous-évaluée ? (None : pas de point 4 dans le document)
        "but_sous_evalue": None if but is None else bool(SOUS_EVALUE.search(but)),
        "extrait_but": (re.search(r"[^.]*undervalu[^.]*\.?", but, re.I) or [but[:300]])[0].strip()[:300] if but else None,
        "cik_sujet_entete": (re.search(r"SUBJECT COMPANY:.*?CENTRAL INDEX KEY:\s*(\d+)", texte, re.S) or [None, None])[1],
    }


def evenements_13dg(texte: str, sha: str, depot: DepotSec, syms: Symboles) -> list[Evenement]:
    f = lire_13dg(texte)
    cote = syms.cote(f["cik_emetteur"])
    if cote is None:
        return []
    h = entete(texte)
    publie = iso(h.get("depose")) or depot.depose
    actif = f["type"].startswith("SCHEDULE 13D")
    pct = f["pourcentage"]
    pct_txt = f"{pct:.2f}".rstrip("0").rstrip(".").replace(".", ",") if pct is not None else "?"
    precision = "13D, intentions actives" if actif else "13G, placement passif"
    if f["type"].endswith("/A"):
        precision += f", mise à jour n° {f['amendement']}" if f["amendement"] else ", mise à jour"
    sortie = f["type"].endswith("/A") and pct is not None and pct < 5
    if sortie:  # une mise à jour sous 5 % : le gros joueur a vendu
        titre = f"{f['declarant']} passe sous 5 % de {cote['name']} : il en détient maintenant {pct_txt} % ({precision})"
    else:
        titre = f"{f['declarant']} détient {pct_txt} % de {cote['name']} ({precision})"
    return [Evenement(
        source="sec_13dg", official_id=depot.acc, category="baleines", kind="sous_5_pourcent" if sortie else "plus_5_pourcent",
        title=titre,
        occurred_on=min(f["date_evenement"] or publie, publie), published_on=publie,
        official_url=depot.page_officielle(f["cik_emetteur"]), sha256=sha, parser_version=VERSION,
        tickers=[cote["ticker"]], entities=[f["declarant"], cote["name"]],
        direction=-1 if sortie else (1 if f["type"] == "SCHEDULE 13D" else 0),
        data={**f, "bourse": cote["exchange"]},
    )]


@controle_source("sec_13dg")
def controles_13dg(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "pourcentage_valide": d.get("pourcentage") is not None and 0 <= d["pourcentage"] <= 100,
        "emetteur_coherent": d.get("cik_sujet_entete") is None
        or int(d["cik_sujet_entete"]) == int(d.get("cik_emetteur") or 0),
    }


def lire_un_13dg(ctx, depot: DepotSec) -> list[Evenement]:
    t = ctx.client.get(f"{ARCHIVES}/{depot.fichier}")
    return evenements_13dg(t.contenu.decode("utf-8", "replace"), t.sha256, depot, symboles(ctx))


def collecter_13dg(ctx) -> list[Evenement]:
    return lire_journees(ctx, "sec_13dg", FORMES_13, lire_un_13dg)


# ---------- Formulaire 144 : un dirigeant annonce qu'il va vendre ----------

RELATIONS_144 = {"officer": "dirigeant", "director": "administrateur", "10% stockholder": "actionnaire de 10 %",
                 "10% owner": "actionnaire de 10 %", "affiliate": "affilié", "other": "autre", "investor": "investisseur",
                 "former officer": "ancien dirigeant", "former director": "ancien administrateur",
                 "member of immediate family of any of the foregoing": "famille"}
SEUIL_144_PLAN = 25_000_000  # vente prévue d'avance (plan 10b5-1) : seulement les très grosses
# Une vente décidée librement (sans plan automatique) en dit plus : on la garde dès 1 M$ (SEUIL_VENTE).


def lire_144(texte: str) -> dict:
    racine = xml_du_depot(texte)
    if racine.tag != "edgarSubmission" or (racine.findtext("headerData/submissionType") or "").strip() != "144":
        raise ValueError("document inattendu (pas un formulaire 144)")
    f = racine.find("formData")
    info = f.find("issuerInfo")
    lignes = []
    for t in f.findall("securitiesInformation"):
        mdy = (t.findtext("approxSaleDate") or "").strip().split("/")
        lignes.append({
            "classe": (t.findtext("securitiesClassTitle") or "").strip(),
            "actions": nombre(t.findtext("noOfUnitsSold")), "valeur": nombre(t.findtext("aggregateMarketValue")),
            "en_circulation": nombre(t.findtext("noOfUnitsOutstanding")),
            "date_prevue": f"{mdy[2]}-{mdy[0]}-{mdy[1]}" if len(mdy) == 3 else None,
            "bourse": (t.findtext("securitiesExchangeName") or "").strip(),
        })
    avis = (f.findtext("noticeSignature/noticeDate") or "").strip().split("/")
    return {
        "cik_emetteur": (info.findtext("issuerCik") or "").strip(), "nom_emetteur": (info.findtext("issuerName") or "").strip(),
        "vendeur": (info.findtext("nameOfPersonForWhoseAccountTheSecuritiesAreToBeSold") or "").strip(),
        # Certains déclarants écrivent « Officer, Director » dans une seule case : on sépare.
        "relations": [x.strip() for r in info.findall("relationshipsToIssuer/relationshipToIssuer")
                      for x in (r.text or "").split(",") if x.strip()],
        "lignes": lignes,
        "plan_10b5_1": [(d.text or "").strip() for d in f.findall("noticeSignature/planAdoptionDates/planAdoptionDate")],
        "date_avis": f"{avis[2]}-{avis[0]}-{avis[1]}" if len(avis) == 3 else None,
    }


def evenements_144(texte: str, sha: str, depot: DepotSec, syms: Symboles) -> list[Evenement]:
    f = lire_144(texte)
    cote = syms.cote(f["cik_emetteur"])
    if cote is None or not f["lignes"]:
        return []
    actions = sum(l["actions"] or 0 for l in f["lignes"])
    valeur = sum(l["valeur"] or 0 for l in f["lignes"])
    if valeur < (SEUIL_144_PLAN if f["plan_10b5_1"] else SEUIL_VENTE):
        return []
    publie = iso(entete(texte).get("depose")) or depot.depose
    relations = ", ".join(dict.fromkeys(RELATIONS_144.get(r.lower(), r) for r in f["relations"])) or "initié"
    notes = (["Vente prévue d'avance dans un plan automatique (règle 10b5-1)."] if f["plan_10b5_1"]
             else ["Vente décidée librement (pas dans un plan automatique)."])
    dates = sorted(l["date_prevue"] for l in f["lignes"] if l["date_prevue"])
    if dates:
        notes.append(f"Date de vente prévue : {date_fr(dates[0])}.")
    return [Evenement(
        source="sec_form144", official_id=depot.acc, category="compagnies", kind="intention_vente",
        title=f"{f['vendeur']} ({relations}) prévoit vendre {nombre_fr(actions)} actions de {cote['name']}",
        occurred_on=min(f["date_avis"] or publie, publie), published_on=publie,
        official_url=depot.page_officielle(f["cik_emetteur"]), sha256=sha, parser_version=VERSION,
        tickers=[cote["ticker"]], entities=[f["vendeur"], cote["name"]], amount_min=valeur, amount_max=valeur,
        direction=-1, notes=notes, data={**f, "actions": actions, "bourse": cote["exchange"]},
    )]


@controle_source("sec_form144")
def controles_144(ev: Evenement) -> dict[str, bool]:
    lignes = ev.data.get("lignes") or []
    actions = ev.data.get("actions") or 0
    prix = (ev.amount_max or 0) / actions if actions else None
    eleve = any(t in PRIX_ELEVES for t in ev.tickers)
    return {
        "actions_et_valeur_positives": bool(lignes) and all((l["actions"] or 0) > 0 and (l["valeur"] or 0) > 0 for l in lignes),
        # Entre 0,10 $ et 2 000 $ l'action (ex. réel : « 158 milliards d'actions de Barclays » = 0,03 $ l'action)
        "prix_implicite_plausible": prix is not None and prix >= PRIX_MIN and (eleve or prix <= PRIX_MAX),
        "montant_plausible": (ev.amount_max or 0) <= VALEUR_MAX,
        # On ne peut pas vendre plus d'actions qu'il n'en existe (chiffre écrit dans le formulaire lui-même)
        "actions_sous_le_total_en_circulation": bool(lignes) and all(
            l.get("en_circulation") and (l["actions"] or 0) <= l["en_circulation"] for l in lignes),
    }


def lire_un_144(ctx, depot: DepotSec) -> list[Evenement]:
    t = ctx.client.get(f"{ARCHIVES}/{depot.fichier}")
    return evenements_144(t.contenu.decode("utf-8", "replace"), t.sha256, depot, symboles(ctx))


def collecter_144(ctx) -> list[Evenement]:
    return lire_journees(ctx, "sec_form144", {"144"}, lire_un_144)


# ---------- Offres d'achat de compagnies entières et retraits de la bourse ----------

FORMES_OFFRES = {  # forme officielle -> (sorte, libellé)
    "SC TO-T": ("offre_achat", "Offre publique d'achat"),
    "SC TO-C": ("offre_annoncee", "Offre d'achat annoncée"),
    "SC 13E3": ("privatisation", "Projet de privatisation (règle 13e-3)"),
}
JOURS_SANS_DOUBLON = 90


def lire_entete_offre(entete_html: str) -> dict:
    texte = html.unescape(entete_html)
    sujet = re.search(r"SUBJECT COMPANY:.*?COMPANY CONFORMED NAME:\s*([^\n<]+).*?CENTRAL INDEX KEY:\s*(\d+)", texte, re.S)
    deposants = re.findall(r"FILED BY:.*?COMPANY CONFORMED NAME:\s*([^\n<]+).*?CENTRAL INDEX KEY:\s*(\d+)", texte, re.S)
    return {
        **entete(texte), "cible": sujet.group(1).strip() if sujet else None, "cik_cible": sujet.group(2) if sujet else None,
        "deposants": [(cik, nom.strip()) for nom, cik in deposants],
    }


def evenements_offre(entete_html: str, sha: str, depot: DepotSec, syms: Symboles, vus: set) -> list[Evenement]:
    f = lire_entete_offre(entete_html)
    forme = (f.get("type") or depot.forme).strip()
    if depot.forme in FORMES_OFFRES:
        forme = depot.forme  # une même déclaration peut servir à 2 formes (ex. TO-I + 13E3) : on garde celle de l'index
    if forme not in FORMES_OFFRES or not f["cik_cible"]:
        return []
    cote = syms.cote(f["cik_cible"])
    if cote is None:
        return []  # la compagnie visée n'est pas cotée au Nasdaq, au NYSE ou au CBOE
    sorte, libelle = FORMES_OFFRES[forme]
    acheteurs = [(c, n) for c, n in f["deposants"] if int(c) != int(f["cik_cible"])]
    if sorte != "privatisation" and not acheteurs:
        return []  # la compagnie qui rachète ses propres actions : pas une offre d'un autre acheteur
    # Une privatisation est déclarée par la compagnie ET par ses acheteurs : une seule info par compagnie.
    cle = f"{int(f['cik_cible'])}:{sorte}" + ("" if sorte == "privatisation"
                                             else ":" + ",".join(sorted(str(int(c)) for c, _ in acheteurs)))
    if sorte != "offre_achat" and cle in vus:
        return []  # même annonce déjà publiée (une offre donne souvent plusieurs communications)
    vus.add(cle)
    publie = iso(f.get("depose")) or depot.depose
    tickers = [cote["ticker"]]
    for c, _ in acheteurs:
        autre = syms.cote(c)
        if autre and autre["ticker"] not in tickers:
            tickers.append(autre["ticker"])
    noms = " et ".join(n for _, n in acheteurs) or None
    if sorte == "privatisation":
        titre = f"{libelle} : {cote['name']}" + (f" (déposé par {noms})" if noms else "")
    else:
        titre = f"{libelle} : {noms} vise les actions de {cote['name']}"
    return [Evenement(
        source="sec_offres", official_id=depot.acc, category="compagnies", kind=sorte, title=titre,
        occurred_on=publie, published_on=publie, official_url=depot.page_officielle(f["cik_cible"]), sha256=sha,
        parser_version=VERSION, tickers=tickers, entities=[n for _, n in acheteurs] + [cote["name"]], direction=1,
        data={"forme": forme, "cible": f["cible"], "cik_cible": f["cik_cible"], "acheteurs": acheteurs,
              "cle": cle, "bourse": cote["exchange"]},
    )]


@controle_source("sec_offres")
def controles_offres(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    return {
        "forme_reconnue": d.get("forme") in FORMES_OFFRES,
        "acheteur_different_de_la_cible": ev.kind == "privatisation"
        or bool(d.get("acheteurs")) and all(int(c) != int(d.get("cik_cible") or 0) for c, _ in d["acheteurs"]),
    }


def _offres_vues(ctx) -> set:
    """Annonces déjà publiées depuis 90 jours (clé : compagnie visée, sorte, acheteurs)."""
    if "sec_offres_vues" not in ctx.cache:
        limite = (ctx.maintenant.date() - timedelta(days=JOURS_SANS_DOUBLON)).isoformat()
        depot = Depot(ctx.donnees)
        ctx.cache["sec_offres_vues"] = {d["data"].get("cle") for dossier in ("evenements", "a_verifier")
                                        for d in depot.lire(dossier)
                                        if d["source"] == "sec_offres" and d["published_on"] >= limite}
    return ctx.cache["sec_offres_vues"]


def lire_une_offre(ctx, depot: DepotSec) -> list[Evenement]:
    cik = depot.filers[0][0]
    t = ctx.client.get(f"{depot.dossier(cik)}/{depot.acc}-index-headers.html")
    texte = t.contenu.decode("utf-8", "replace")
    return evenements_offre(texte, empreinte_entete(texte), depot, symboles(ctx), _offres_vues(ctx))


def collecter_offres(ctx) -> list[Evenement]:
    return lire_journees(ctx, "sec_offres", set(FORMES_OFFRES), lire_une_offre)
