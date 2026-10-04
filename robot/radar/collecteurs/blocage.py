"""Fins de blocage après une entrée en bourse (SEC, prospectus final 424B4).

Après une entrée en bourse, les dirigeants et les anciens actionnaires s'engagent à ne pas vendre pendant une période
(souvent 180 jours) comptée à partir de la date du prospectus. Radar publie la fin prévue SEULEMENT si tout est écrit
clairement dans le prospectus officiel (sinon rien) :
- une vraie entrée en bourse (« This is an initial public offering » ou « Prior to this offering, there has been no
  public market ») ; pas une compagnie de chèque en blanc (SPAC), pas une inscription directe, pas une compagnie dont
  les actions se négocient déjà ailleurs (ex. SK hynix, cotée en Corée) ;
- la date du prospectus écrite dans le document : sur la couverture (« The date of this prospectus is … »,
  « Prospectus dated … ») ou dans la phrase des 25 jours (« Through and including … (25 days after the date of this
  prospectus) ») ; une seule date, au plus 2 jours ouvrables avant le dépôt à la SEC ;
- une seule durée dans les phrases du blocage (« lock-up »), comptée à partir de la date du prospectus ;
- aucune clause de levée anticipée (selon le cours, après les résultats, par tranches).
La fin = date du prospectus + la durée (ex. 180 jours après le 30 juillet 2026 = 26 janvier 2027, inclus). C'est une date
PRÉVUE : les banques qui ont mené l'entrée en bourse peuvent lever le blocage plus tôt.

Mesuré au labo le 4 octobre 2026 : 114 prospectus 424B4 de juillet à septembre 2026, dont 25 vraies entrées en bourse ;
12 passent la règle (11 de 180 jours, 1 de 90 jours). 0 point dans la note : les études (Field et Hanka 2001 ; Brav et
Gompers 2003) trouvent −1,2 à −1,5 % sur 3 jours autour de la fin du blocage, sur des données de 1988 à 1997, et Radar
n'a rien trouvé de solide depuis 2015.

Rattrapage, une seule fois : les prospectus d'avril à septembre 2026 (index trimestriels officiels de la SEC), pour les
fins de blocage d'octobre 2026 à mars 2027. Ensuite, les 424B4 de chaque jour (index quotidien, comme les autres
lecteurs de la SEC). Une nouvelle compagnie dont le symbole n'est pas encore dans la liste officielle de la SEC est
gardée en attente (au plus 20 jours) : on la publie quand son symbole apparaît.
"""

from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from ..models import Evenement
from ..validate import controle_source
from .gazette import details
from .sec import ARCHIVES, DepotSec, date_fr, lire_index, lire_journees, symboles

VERSION = "blocage-1"
DEBUT_RATTRAPAGE = date(2026, 4, 1)
MAX_PAR_PASSAGE = 320  # prospectus lus au plus par passage pendant le rattrapage (2e trimestre : 170, 3e : 114)
JOURS_ATTENTE_SYMBOLE = 20
DEBUT = 40_000  # caractères du début du prospectus (couverture et résumé) pour reconnaître une entrée en bourse
COUVERTURE = 120_000
ECART_MAX_OUVRABLES = 2  # Règle 424(b) : dépôt au plus tard le 2e jour ouvrable après la fixation du prix

MOIS = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}"
IPO = re.compile(r"this is (?:an|the|our) initial public offering|prior to this offering,? there (?:has|have) been no "
                 r"(?:established )?public market", re.I)
EXCLUSIONS = {
    "compagnie de chèque en blanc (SPAC)": re.compile(r"blank check company|special purpose acquisition", re.I),
    "inscription directe": re.compile(r"direct listing", re.I),
    # Au présent seulement : « until our Ordinary Shares are listed on a national securities exchange » (RUI Holdings,
    # une vraie entrée en bourse) parle du futur
    "actions déjà négociées ailleurs": re.compile(
        r"(?<!until )(?<!once )(?<!when )(?<!after )(?<!if )(?<!before )\b(?:our|its)\s+(?:common|ordinary)\s+(?:shares|"
        r"stock)\s+(?:are|is)\s+(?:currently\s+)?(?:listed|traded|quoted)\s+on\b|last reported (?:sale|sales|closing|"
        r"trading) price of (?:our|the|its)\s+(?:common|ordinary)", re.I),
}
COUV = re.compile(r"(?:The date of this prospectus is|Prospectus dated)\s+(" + MOIS + ")")
# « Through and including … (the 25th day after the date of this prospectus) » : preuve directe. « … after the commencement
# of this offering » : le début de l'offre n'est pas forcément la date du prospectus, donc seulement une confirmation.
J25 = re.compile(r"Through and including (" + MOIS + r")\s*\((?:the )?25(?:th)? days? after the (date of this "
                 r"prospectus|commencement of this offering)\)?", re.I)
SOMMAIRE = re.compile(r"table of contents", re.I)
N = r"(?:[a-z][a-z -]*\((\d{2,3})\)|(\d{2,3}))"
DUREE = re.compile(N + r"[ -]days? (?:after|from|following) the date of (?:this|the final) prospectus", re.I)
DUREE_PERIODE = re.compile(N + r"-day (?:lock-?up|restricted) period", re.I)
BLOCAGE = re.compile(r"lock-?up|restricted period", re.I)
PAS_LE_BLOCAGE = re.compile(r"Rule 144|Rule 701|effective date of the registration|25 days|underwriter(?:s'|'s)? "
                            r"warrants|FINRA Rule 5110", re.I)
ANTICIPEE = re.compile(
    r"(?:closing|last reported sale) price[^.]{0,250}(?:exceed|at least|greater than|equal to or greater)[^.]{0,150}"
    r"(?:initial public )?offering price"
    r"|(?:release|announcement) of (?:our |its )?(?:earnings|quarterly|financial results)[^.]{0,200}(?:lock-?up|"
    r"restricted period)"
    r"|(?:lock-?up|restricted period)[^.]{0,200}(?:release|announcement) of (?:our |its )?(?:earnings|quarterly|"
    r"financial results)"
    r"|early release|released early|earlier of[^.]{0,200}(?:lock-?up|restricted period|trading day)"
    r"|(?:lock-?up|restricted period)[^.]{0,200}\b\d{1,3}(?:\.\d+)?\s?(?:%|percent) of[^.]{0,120}(?:will be |shall be |"
    r"are |be )?released", re.I)
INITIES = re.compile(r"directors|officers|holders|shareholders|stockholders", re.I)
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


# ---------- Lecture du prospectus ----------


def decoder(contenu: bytes) -> str:
    """Les dépôts sont en UTF-8 ou en Windows-1252 (guillemets « courbes ») : jamais de caractères abîmés."""
    try:
        return contenu.decode("utf-8")
    except UnicodeDecodeError:
        return contenu.decode("cp1252", "replace")


def document_424b4(txt: str) -> str | None:
    """Le document 424B4 du dépôt complet (.txt), sans les pièces jointes ni les images."""
    for m in re.finditer(r"<DOCUMENT>\s*<TYPE>([^\n<]+)(.*?)</DOCUMENT>", txt, re.S):
        if m.group(1).strip().upper().startswith("424B4"):
            t = re.search(r"<TEXT>(.*?)</TEXT>", m.group(2), re.S)
            return t.group(1) if t else m.group(2)
    return None


def texte_doc(brut: str) -> str:
    """Texte lisible : un espace entre les blocs, rien pour une balise dans une ligne (« 202<span>6</span> » = 2026)."""
    t = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>|<!--.*?-->", " ", brut)
    t = re.sub(r"(?i)<\s*/?\s*(?:br|p|div|li|tr|td|th|table|h\d|center)\b[^>]*>", " ", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return " ".join(t.replace("\xa0", " ").replace("​", " ").split())


def jour(s: str) -> date:
    return datetime.strptime(" ".join(s.split()), "%B %d, %Y").date()


def jours_ouvrables(a: date, b: date) -> int:
    """Jours de semaine après `a` jusqu'à `b` inclus (les jours fériés comptent : c'est plus strict)."""
    n, j = 0, a
    while j < b:
        j += timedelta(days=1)
        n += j.weekday() < 5
    return n


def date_bas_de_couverture(texte: str) -> str | None:
    """La date qui termine la couverture, sous le nom des banques (« … LifeSci Capital September 24, 2026 »)."""
    liens = [m.start() for m in SOMMAIRE.finditer(texte[:COUVERTURE])][:2]
    if len(liens) < 2 or liens[0] > 200:
        return None
    m = re.search(r"(" + MOIS + r")\.?\s*$", texte[liens[0]:liens[1]])
    return m.group(1) if m else None


def phrases(texte: str) -> list[str]:
    """Coupe après « . » ou « ; », aussi quand un guillemet ou une parenthèse suit (« …Agreement.” Lock-Up … »)."""
    return re.split(r"(?<=[.;])\s+|(?<=[.;][”\"’)])\s+", texte)


def valeur_phrase(s: str) -> int:
    """La phrase montrée : l'engagement des dirigeants et des actionnaires (« have agreed … for a period of 180 days »),
    pas celle du programme d'actions réservées (Jersey Mike's) ni un résumé ; à égalité, la première."""
    return (2 * bool(INITIES.search(s)) + bool(re.search(r"agreed|agreements?", s, re.I))
            + bool(re.search(r"for a period of|during the period", s, re.I)) - 3 * bool(re.search(r"directed share", s, re.I)))


def couper(phrase: str, maximum: int = 700) -> str:
    if len(phrase) <= maximum:
        return phrase
    return phrase[:maximum].rsplit(" ", 1)[0] + " …"


def extrait(phrase: str, maximum: int = 700) -> str:
    """La phrase du prospectus, mot pour mot. Trop longue : le début, « … », puis le passage où se trouve la durée
    (Jersey Mike's : « 180 days » vient après une longue liste de ce qui est interdit)."""
    m = next(iter([*DUREE.finditer(phrase), *DUREE_PERIODE.finditer(phrase)]), None)
    if len(phrase) <= maximum or m is None or m.end() + 120 <= maximum:
        return couper(phrase, maximum)
    tete = phrase[:300].rsplit(" ", 1)[0]
    a = phrase.rfind(" ", 0, max(0, m.start() - 200)) + 1
    if a <= len(tete):
        return couper(phrase, m.end() + 120)
    fin = phrase.find(" ", m.end() + 120)
    return f"{tete} … {phrase[a:fin]} …" if fin != -1 else f"{tete} … {phrase[a:]}"


def analyser(texte: str, depose: date) -> dict:
    """Ce que dit le prospectus, et les raisons de NE PAS publier (liste vide = publiable)."""
    debut = texte[:DEBUT]
    r: dict = {"entree_en_bourse": bool(IPO.search(debut)),
               "exclusions": [nom for nom, motif in EXCLUSIONS.items() if motif.search(debut)]}
    preuves = [{"sorte": "couverture", "date": jour(m.group(1)).isoformat(), "phrase": m.group(0), "directe": True}
               for m in COUV.finditer(texte[:COUVERTURE])]
    bas = date_bas_de_couverture(texte)
    if bas:
        preuves.append({"sorte": "bas de la couverture", "date": jour(bas).isoformat(), "phrase": bas, "directe": True})
    preuves += [{"sorte": "25 jours", "date": (jour(m.group(1)) - timedelta(days=25)).isoformat(), "phrase": m.group(0),
                 "directe": m.group(2).lower().startswith("date")} for m in J25.finditer(texte)]
    uniques, vues = [], set()
    for p in preuves:
        if (p["sorte"], p["date"]) not in vues:
            vues.add((p["sorte"], p["date"]))
            uniques.append(p)
    r["preuves_date"] = uniques
    dates = sorted({p["date"] for p in uniques})
    durees, candidates = set(), []
    for s in phrases(texte):
        if not BLOCAGE.search(s) or PAS_LE_BLOCAGE.search(s):
            continue
        trouve = {int(m.group(1) or m.group(2)) for m in (*DUREE.finditer(s), *DUREE_PERIODE.finditer(s))}
        if trouve:
            durees |= trouve
            candidates.append(s)
    r["durees"] = sorted(durees)
    anticipee = ANTICIPEE.search(texte)
    r["levee_anticipee"] = bool(anticipee)
    if anticipee:
        r["phrase_levee_anticipee"] = couper(texte[max(0, anticipee.start() - 200):anticipee.end() + 200], 900)
    raisons = []
    if not r["entree_en_bourse"]:
        raisons.append("pas une entrée en bourse")
    raisons += [f"exclu : {e}" for e in r["exclusions"]]
    if len(dates) != 1 or not any(p["directe"] for p in uniques):
        raisons.append("dates du prospectus différentes" if len(dates) > 1 else "date du prospectus absente")
    else:
        d0 = date.fromisoformat(dates[0])
        r["date_prospectus"] = dates[0]
        r["ecart_ouvrables"] = jours_ouvrables(d0, depose) if d0 <= depose else None
        if r["ecart_ouvrables"] is None or r["ecart_ouvrables"] > ECART_MAX_OUVRABLES:
            raisons.append("date du prospectus trop loin du dépôt à la SEC")
    if len(durees) != 1:
        raisons.append("aucune durée de blocage" if not durees else "plusieurs durées de blocage")
    if r["levee_anticipee"]:
        raisons.append("levée anticipée mentionnée")
    r["raisons"] = raisons
    if not raisons:
        n = next(iter(durees))
        r["duree_jours"] = n
        r["fin_blocage"] = (date.fromisoformat(r["date_prospectus"]) + timedelta(days=n)).isoformat()
        r["phrase_blocage"] = extrait(max(candidates, key=valeur_phrase))
    return r


# ---------- Info publiée ----------


def jour_fr(iso_jour: str) -> str:
    return f"{JOURS_FR[date.fromisoformat(iso_jour).weekday()]} {date_fr(iso_jour)}"


def titre(nom: str, r: dict) -> str:
    return (f"{nom} : fin prévue du blocage de {r['duree_jours']} jours le {date_fr(r['fin_blocage'])} "
            f"(entrée en bourse, prospectus du {date_fr(r['date_prospectus'])})")


def evenement(depot: DepotSec, cik: str, nom: str, cote: dict, r: dict, sha: str) -> Evenement:
    preuves = " ; ".join(f"« {p['phrase']} »" for p in r["preuves_date"])
    d = {"cik": cik, "bourse": cote["exchange"], "date_prospectus": r["date_prospectus"], "duree_jours": r["duree_jours"],
         "fin_blocage": r["fin_blocage"], "preuves_date": r["preuves_date"], "phrase_blocage": r["phrase_blocage"],
         "entree_en_bourse": r["entree_en_bourse"], "levee_anticipee": r["levee_anticipee"],
         "ecart_ouvrables": r["ecart_ouvrables"],
         "details": details(("Compagnie", nom), ("Date du prospectus", date_fr(r["date_prospectus"])),
                            ("Durée du blocage", f"{r['duree_jours']} jours"),
                            ("Fin prévue du blocage", f"{jour_fr(r['fin_blocage'])} (inclus)"),
                            ("Phrase du prospectus", r["phrase_blocage"]), ("Date du prospectus prouvée par", preuves))}
    return Evenement(
        source="sec_blocage", official_id=depot.acc, category="compagnies", kind="fin_blocage", title=titre(nom, r),
        occurred_on=r["date_prospectus"], published_on=depot.depose, official_url=depot.page_officielle(cik), sha256=sha,
        parser_version=VERSION, tickers=[cote["ticker"]], entities=[nom], direction=0, data=d,
        notes=["Date prévue par le prospectus : les banques qui ont mené l'entrée en bourse peuvent lever le blocage plus "
               "tôt, en tout ou en partie. Information seulement : 0 point dans la note."])


@controle_source("sec_blocage")
def controles(ev: Evenement) -> dict[str, bool]:
    d = ev.data
    preuves = d.get("preuves_date") or []
    try:
        fin_ok = (date.fromisoformat(d["date_prospectus"]) + timedelta(days=d["duree_jours"])).isoformat() == d["fin_blocage"]
    except (KeyError, TypeError, ValueError):
        fin_ok = False
    return {
        "entree_en_bourse": d.get("entree_en_bourse") is True,
        "date_du_prospectus_prouvee": bool(preuves) and all(p.get("date") == d.get("date_prospectus") for p in preuves),
        "une_seule_duree": isinstance(d.get("duree_jours"), int) and 30 <= d["duree_jours"] <= 400
                           and str(d["duree_jours"]) in (d.get("phrase_blocage") or ""),
        "fin_calculee": fin_ok,
        "sans_levee_anticipee": d.get("levee_anticipee") is False,
        "compagnie_cotee": bool(ev.tickers),
    }


# ---------- Lecture des dépôts ----------


def etat(ctx) -> tuple[Path, dict]:
    chemin = Path(ctx.donnees) / "sec" / "blocage.json"
    return chemin, (json.loads(chemin.read_text(encoding="utf-8")) if chemin.exists() else {})


def lire_depot(ctx, depot: DepotSec, attente: dict) -> list[Evenement]:
    """Un 424B4 : rien s'il ne passe pas la règle ; en attente si la compagnie n'a pas encore de symbole officiel."""
    t = ctx.client.get(f"{ARCHIVES}/{depot.fichier}")
    doc = document_424b4(decoder(t.contenu))
    if doc is None:
        return []
    r = analyser(texte_doc(doc), date.fromisoformat(depot.depose))
    if r["raisons"]:
        return []
    cik, nom = depot.filers[0]
    cote = symboles(ctx).cote(cik)
    if cote is None:
        attente[depot.acc] = {"cik": cik, "nom": nom, "depose": depot.depose, "fichier": depot.fichier}
        return []
    attente.pop(depot.acc, None)
    return [evenement(depot, cik, cote.get("name") or nom, cote, r, t.sha256)]


def trimestres(debut: date, avant: date) -> list[tuple[int, int]]:
    """(année, trimestre) de `debut` jusqu'au trimestre qui précède `avant` (son index trimestriel est complet)."""
    t, fin = (debut.year, (debut.month - 1) // 3 + 1), (avant.year, (avant.month - 1) // 3 + 1)
    out = []
    while t < fin:
        out.append(t)
        t = (t[0] + (t[1] == 4), t[1] % 4 + 1)
    return out


def rattrapage(ctx, e: dict, attente: dict) -> list[Evenement]:
    """Les 424B4 des trimestres complets depuis avril 2026, une seule fois (au plus MAX_PAR_PASSAGE par passage)."""
    finis, lus, tous = set(e.get("trimestres_finis", [])), set(e.get("lus", [])), []
    budget = MAX_PAR_PASSAGE
    for annee, tri in trimestres(DEBUT_RATTRAPAGE, ctx.maintenant.date()):
        cle = f"{annee}T{tri}"
        if cle in finis:
            continue
        index = ctx.client.get(f"{ARCHIVES}/edgar/full-index/{annee}/QTR{tri}/master.idx")
        depots = [d for d in lire_index(index.contenu.decode("latin-1")).values()
                  if d.forme == "424B4" and d.depose >= DEBUT_RATTRAPAGE.isoformat()]
        reste = [d for d in depots if d.acc not in lus][:budget]
        illisibles = 0
        for d in reste:
            try:
                tous.extend(lire_depot(ctx, d, attente))
            except Exception:  # noqa: BLE001 - comme pour les jours : un document bizarre est sauté (rien plutôt que faux)
                illisibles += 1
            lus.add(d.acc)
        if illisibles > max(3, len(reste) * 0.05):  # trop de pannes : la source tombe, tout sera relu au prochain passage
            raise RuntimeError(f"{illisibles} prospectus illisibles sur {len(reste)} ({cle})")
        budget -= len(reste)
        if all(d.acc in lus for d in depots):
            finis.add(cle)
        if budget == 0:
            break
    e["trimestres_finis"], e["lus"] = sorted(finis), sorted(lus)
    return tous


def en_attente(ctx, attente: dict) -> list[Evenement]:
    """Nouvelles compagnies sans symbole officiel au moment du dépôt : publiées dès que le symbole apparaît."""
    tous = []
    for acc, a in list(attente.items()):
        if (ctx.maintenant.date() - date.fromisoformat(a["depose"])).days > JOURS_ATTENTE_SYMBOLE:
            del attente[acc]
            continue
        if symboles(ctx).cote(a["cik"]) is not None:
            try:
                tous.extend(lire_depot(ctx, DepotSec(acc, "424B4", a["depose"], a["fichier"], [(a["cik"], a["nom"])]),
                                       attente))
            except Exception:  # noqa: BLE001 - reste en attente : on réessaiera au prochain passage
                pass
    return tous


def collecter(ctx) -> list[Evenement]:
    chemin, e = etat(ctx)
    attente = e.setdefault("en_attente", {})
    tous = rattrapage(ctx, e, attente)
    vus = set(e["lus"])  # déjà lus par le rattrapage (ex. le dernier jour d'un trimestre) : pas de 2e lecture
    tous += en_attente(ctx, attente)
    tous += lire_journees(ctx, "sec_blocage", {"424B4"},
                          lambda c, d: [] if d.acc in vus else lire_depot(c, d, attente))
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(e, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    return tous
