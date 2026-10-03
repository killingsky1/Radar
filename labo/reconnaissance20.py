"""Lot 3d, 1er passage : ce que chaque source permet vraiment à NOTRE robot (mêmes règles : robots.txt d'abord, lu avec
notre identification ; 401/403 = interdit ; Crawl-delay respecté, sinon 1,5 s par site ; rien n'est contourné).
Courriel seulement pour la SEC (« Radar projet personnel math-veronneau1@hotmail.com »), ailleurs « Radar projet personnel ».

- Trésor : API Fiscal Data (adjudications, solde de trésorerie quotidien, état mensuel, dette) et TreasuryDirect (TA_WS) ;
- USAspending : API (contrats de 100 M$ et plus, modifiés ou nouveaux), date de mise à jour ;
- Tarifs : USITC (HTS), USTR, CBP (CSMS) : robots.txt et pages de départ ;
- NBIM : placements et exclusions ;
- Participations du gouvernement : recherche plein texte d'EDGAR (efts.sec.gov), Commerce, Énergie ;
- Communiqués : listes RSS des agences de presse ;
- SEC : échecs de livraison (page et dernier fichier) ;
- Yahoo : robots.txt seulement (rien d'autre tant que les conditions d'utilisation ne sont pas lues) ;
- war.gov et gao.gov : robots.txt seulement (toujours bloqués ?).
"""
import json
import re
import time
import urllib.robotparser
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

UA = "Radar projet personnel"
UA_SEC = "Radar projet personnel math-veronneau1@hotmail.com"
SORTIE = Path("labo/resultats-lot3d")
SORTIE.mkdir(parents=True, exist_ok=True)
MAX_GARDE = 6_000_000
MAX_LU = 60_000_000
LIENS = re.compile(r"""href=["']([^"'#]+)["']""", re.I)
INTERESSANTS = re.compile(r"\.(csv|json|xml|pdf|xlsx|atom|rss|zip)\b|rss|feed|api|export|download|terms|conditions"
                          r"|legal|copyright|policy|polic|exclu|holding|investments|press|news|bulletin|fails", re.I)
robots, resultats, dernier = {}, {}, {}
AUJ = date.today()
# Des pages publiques contiennent parfois des clés d'accès (ex. une clé Mapbox dans la page de NBIM) : on ne les garde
# jamais. Elles sont masquées avant tout enregistrement.
CLES = [re.compile(rb"\b(?:pk|sk|tk)\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}"), re.compile(rb"AIza[0-9A-Za-z_-]{35}"),
        re.compile(rb"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
        re.compile(rb"(?i)((?:access_?token|api_?key|apikey|secret|token)[\"']?\s*[:=]\s*[\"']?)[A-Za-z0-9._~+/-]{16,}")]


def masquer(contenu, type_contenu):
    if not re.search(r"html|json|xml|javascript|text", type_contenu or ""):
        return contenu, 0
    n = 0
    for motif in CLES:
        contenu, k = motif.subn(lambda m: (m.group(1) if m.groups() else b"") + b"[cle masquee]", contenu)
        n += k
    return contenu, n


def ua(hote):
    return UA_SEC if hote.endswith("sec.gov") else UA


def entetes(hote):
    return {"User-Agent": ua(hote), "Accept-Encoding": "gzip, deflate"}


def regles(hote):
    if hote not in robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(f"https://{hote}/robots.txt", headers=entetes(hote), timeout=(20, 40), allow_redirects=True)
            robots[hote] = {"statut": r.status_code, "texte": r.text[:6000], "url_finale": r.url}
            if r.status_code in (401, 403) or r.status_code >= 500:
                rp.disallow_all = True
            elif r.status_code >= 400:
                rp.allow_all = True
            else:
                rp.parse(r.text.splitlines())
        except Exception as exc:  # noqa: BLE001
            robots[hote] = {"statut": None, "erreur": str(exc)[:200]}
            rp.disallow_all = True  # robots.txt illisible : on ne touche à rien
        delai = rp.crawl_delay(ua(hote)) if robots[hote].get("statut") == 200 else None
        robots[hote]["delai"] = float(delai) if delai else None
        robots[hote]["rp"] = rp
        dernier[hote] = time.monotonic()
        print("robots.txt", hote, robots[hote].get("statut"), "délai", robots[hote]["delai"], flush=True)
    return robots[hote]["rp"]


def attendre(hote):
    reste = max(1.5, robots[hote]["delai"] or 0) - (time.monotonic() - dernier.get(hote, 0))
    if reste > 0:
        time.sleep(reste)


def requete(url, corps=None):
    """Suit les redirections à la main : chaque nouveau site passe par son robots.txt et son délai."""
    for _ in range(6):
        hote = urlparse(url).hostname
        if not regles(hote).can_fetch(ua(hote), url):
            return None, url
        attendre(hote)
        if corps is None:
            r = requests.get(url, headers=entetes(hote), timeout=(20, 180), stream=True, allow_redirects=False)
        else:
            r = requests.post(url, headers={**entetes(hote), "Content-Type": "application/json"}, data=json.dumps(corps),
                              timeout=(20, 180), stream=True, allow_redirects=False)
        dernier[hote] = time.monotonic()
        if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
            r.close()
            url = urljoin(url, r.headers["location"])
            corps = None
            continue
        return r, url
    raise RuntimeError("trop de redirections")


def visiter(nom, url, corps=None, garde=MAX_GARDE):
    res = {"url": url, "post": corps}
    try:
        r, finale = requete(url, corps)
        res["permis_robots_txt"] = r is not None
        res["url_finale"] = finale
        if r is not None:
            morceaux, taille = [], 0
            for m in r.iter_content(65536):
                taille += len(m)
                if taille - len(m) < garde:
                    morceaux.append(m)
                if taille > MAX_LU:
                    break
            r.close()
            contenu, masquees = masquer(b"".join(morceaux)[:garde], r.headers.get("content-type"))
            res["cles_masquees"] = masquees
            res.update({"statut": r.status_code, "type": r.headers.get("content-type"), "taille": taille,
                        "complet": taille <= garde,
                        "entetes": {k: v for k, v in r.headers.items()
                                    if k.lower() in ("last-modified", "etag", "content-length", "cache-control", "retry-after",
                                                     "x-ratelimit-limit", "x-ratelimit-remaining", "content-encoding",
                                                     "server")},
                        "debut": contenu[:600].decode("utf-8", "replace")})
            (SORTIE / f"{nom}.bin").write_bytes(contenu)
            if "html" in (r.headers.get("content-type") or ""):
                texte = contenu.decode("utf-8", "replace")
                res["liens"] = sorted({urljoin(finale, h) for h in LIENS.findall(texte) if INTERESSANTS.search(h)})[:200]
    except Exception as exc:  # noqa: BLE001
        res["erreur"] = str(exc)[:300]
    resultats[nom] = res
    print(nom, "permis" if res.get("permis_robots_txt") else "INTERDIT/erreur", res.get("statut"), res.get("taille"),
          res.get("type"), res.get("erreur", ""), flush=True)
    return res


# ---------- Trésor ----------
FD = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/"
visiter("fd_adjudications", FD + "v1/accounting/od/auctions_query?sort=-auction_date&page[size]=60")
visiter("fd_adjudications_a_venir", FD + "v1/accounting/od/upcoming_auctions?page[size]=50")
visiter("fd_tresorerie_jour", FD + "v1/accounting/dts/operating_cash_balance?sort=-record_date&page[size]=12")
visiter("fd_etat_mensuel", FD + "v1/accounting/mts/mts_table_1?sort=-record_date&page[size]=40")
visiter("fd_dette", FD + "v2/accounting/od/debt_to_penny?sort=-record_date&page[size]=5")
visiter("fd_site", "https://fiscaldata.treasury.gov/datasets/")
visiter("td_adjugees", "https://www.treasurydirect.gov/TA_WS/securities/auctioned?format=json&days=14")
visiter("td_annoncees", "https://www.treasurydirect.gov/TA_WS/securities/announced?format=json&days=14")

# ---------- USAspending ----------
US = "https://api.usaspending.gov/api/v2/"
CHAMPS = ["Award ID", "Recipient Name", "Award Amount", "Awarding Agency", "Awarding Sub Agency", "Start Date",
          "Description", "generated_internal_id", "Last Modified Date", "Base Obligation Date", "recipient_id"]
for nom, type_date, jours in (("us_modifies_7j", "last_modified_date", 7), ("us_nouveaux_30j", "new_awards_only", 30),
                              ("us_signes_7j", "action_date", 7)):
    visiter(nom, US + "search/spending_by_award/", corps={
        "filters": {"award_type_codes": ["A", "B", "C", "D"],
                    "time_period": [{"start_date": (AUJ - timedelta(days=jours)).isoformat(), "end_date": AUJ.isoformat(),
                                     "date_type": type_date}],
                    "award_amounts": [{"lower_bound": 100_000_000}]},
        "fields": CHAMPS, "sort": "Award Amount", "order": "desc", "limit": 100, "page": 1})
visiter("us_mise_a_jour", US + "awards/last_updated/")
visiter("us_site", "https://www.usaspending.gov/")

# ---------- Tarifs ----------
visiter("hts_accueil", "https://hts.usitc.gov/")
visiter("hts_recherche_9903", "https://hts.usitc.gov/reststop/search?keyword=9903.01.25")
visiter("usitc_nouvelles", "https://www.usitc.gov/press_room/news_release")
visiter("ustr_communiques", "https://ustr.gov/about-us/policy-offices/press-office/press-releases")
visiter("cbp_csms", "https://www.cbp.gov/trade/automated/cargo-systems-messaging-service")
visiter("govdelivery_cbp", "https://content.govdelivery.com/accounts/USDHSCBP/bulletins")

# ---------- NBIM ----------
visiter("nbim_placements", "https://www.nbim.no/en/investments/all-investments/")
visiter("nbim_exclusions", "https://www.nbim.no/en/responsible-investment/ethical-exclusions/exclusion-of-companies/")
visiter("nbim_accueil", "https://www.nbim.no/")

# ---------- Participations du gouvernement ----------
visiter("efts_commerce", "https://efts.sec.gov/LATEST/search-index?q=%22Department%20of%20Commerce%22%20%22warrant%22"
        "&forms=8-K&dateRange=custom&startdt=2025-07-01&enddt=" + AUJ.isoformat())
visiter("commerce_communiques", "https://www.commerce.gov/news/press-releases")
visiter("energie_nouvelles", "https://www.energy.gov/newsroom")

# ---------- Communiqués des compagnies ----------
visiter("globenewswire_rss", "https://www.globenewswire.com/rss/list")
visiter("prnewswire_rss", "https://www.prnewswire.com/rss/")
visiter("newswire_ca_rss", "https://www.newswire.ca/rss/")
visiter("newsfile_accueil", "https://www.newsfilecorp.com/")

# ---------- SEC : échecs de livraison ----------
ftd = visiter("sec_ftd_page", "https://www.sec.gov/data-research/sec-markets-data/fails-deliver-data")
zips = sorted(l for l in ftd.get("liens", []) if l.endswith(".zip"))  # noms datés : le plus récent est le dernier
resultats["sec_ftd_page"]["zips"] = zips[-12:]
if zips:
    visiter("sec_ftd_dernier", zips[-1])

# ---------- robots.txt seulement ----------
for hote in ("finance.yahoo.com", "query1.finance.yahoo.com", "www.war.gov", "www.gao.gov"):
    regles(hote)

(SORTIE / "resultats.json").write_text(json.dumps(
    {"pages": resultats, "robots": {h: {k: v for k, v in r.items() if k != "rp"} for h, r in robots.items()}},
    ensure_ascii=False, indent=1), encoding="utf-8")
print("fini")
