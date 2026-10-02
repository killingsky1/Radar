// Radar : l'app iPhone. Elle lit les fichiers préparés par le robot (data/app/*.json).
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";

const VERSION = "0.2.0";

// ---------- Constantes ----------

const CATEGORIES = {
  compagnies: { label: "Compagnies", icone: "immeuble" },
  baleines: { label: "Gros joueurs", icone: "tarte" },
  politiciens: { label: "Politiciens", icone: "capitole" },
  militaire: { label: "Militaire", icone: "bouclier" },
  gouvernement: { label: "Gouvernement", icone: "document" },
  canada: { label: "Canada", icone: "erable" },
};

const BADGES = {
  confirme: { label: "Confirmé", icone: "double", texte: "Deux sources officielles disent la même chose." },
  officiel: { label: "Officiel", icone: "bouclier-ok", texte: "Une source officielle, tous les contrôles réussis." },
  a_verifier: { label: "À vérifier", icone: "alerte", texte: "Au moins un contrôle raté. Jamais suggérée." },
};

const CONTROLES = {
  source_connue: "Source connue et active",
  source_officielle: "Source officielle",
  champs_requis: "Informations complètes",
  empreinte: "Empreinte du document",
  domaine_officiel: "Lien vers un site officiel",
  dates_coherentes: "Dates cohérentes",
  montant_coherent: "Montant cohérent",
  symboles_valides: "Symboles boursiers valides",
  confirmations_valides: "Confirmations valides",
};

const STATUTS = {
  ok: { label: "OK", couleur: "vert" },
  en_retard: { label: "En retard", couleur: "jaune" },
  en_panne: { label: "En panne", couleur: "rouge" },
  en_pause: { label: "En pause", couleur: "bleu" },
  a_venir: { label: "À venir", couleur: "gris" },
  ecartee: { label: "Laissée de côté", pluriel: "Laissées de côté", couleur: "gris" },
};

const ACCENTS = { bleu: "#4F8CFF", vert: "#2BD9A0", violet: "#9B7BFF", orange: "#FF8A3D" };
const MONTANTS_MIN = [
  [0, "Tous"],
  [1e5, "100 k$"],
  [1e6, "1 M$"],
  [1e7, "10 M$"],
];
const SYMBOLE_RE = /^[A-Z0-9]{1,6}([.-][A-Z0-9]{1,3})?$/;

const REGLAGES_DEFAUT = {
  theme: "sombre",
  taille: "normale",
  accent: "bleu",
  categories: Object.fromEntries(Object.keys(CATEGORIES).map((k) => [k, true])),
  seulementConfirme: false,
  montrerAVerifier: false,
  montantMin: 0,
  tri: "recent",
};

// ---------- Icônes ----------

const ICONES = {
  accueil: <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" />,
  fil: <path d="M4 6h16M4 12h16M4 18h10" />,
  etoile: <path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z" />,
  reglages: (
    <>
      <path d="M4 6h9M17 6h3M4 12h3M11 12h9M4 18h11M19 18h1" />
      <circle cx="15" cy="6" r="2" />
      <circle cx="9" cy="12" r="2" />
      <circle cx="17" cy="18" r="2" />
    </>
  ),
  loupe: (
    <>
      <circle cx="11" cy="11" r="7" />
      <path d="m20 20-3.5-3.5" />
    </>
  ),
  x: <path d="M6 6l12 12M18 6 6 18" />,
  "chevron-d": <path d="m9 6 6 6-6 6" />,
  "chevron-g": <path d="m15 5-7 7 7 7" />,
  externe: <path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />,
  partager: <path d="M12 3v12M8 7l4-4 4 4M5 12v7a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-7" />,
  rafraichir: <path d="M20 12a8 8 0 1 1-2.3-5.6M20 4v5h-5" />,
  "bouclier-ok": (
    <>
      <path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z" />
      <path d="m8.5 12 2.5 2.5 4.5-5" />
    </>
  ),
  double: <path d="m2.5 12.5 4 4L15 8M10.5 15.5l1 1L20 8" />,
  alerte: <path d="M12 4 2.8 19.5h18.4zM12 10v4M12 16.8v.2" />,
  immeuble: <path d="M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16M15 9h4a1 1 0 0 1 1 1v11M3 21h18M8 8h3M8 12h3M8 16h3" />,
  tarte: (
    <>
      <path d="M12 3a9 9 0 1 0 9 9h-9z" />
      <path d="M15 3.5A9 9 0 0 1 20.5 9H15z" />
    </>
  ),
  capitole: <path d="M3 21h18M5 21v-8M9.5 21v-8M14.5 21v-8M19 21v-8M3 10h18L12 4z" />,
  bouclier: (
    <>
      <path d="M12 3 4 6v6c0 4.5 3.4 8.3 8 9 4.6-.7 8-4.5 8-9V6z" />
      <path d="m8.5 10.5 3.5-2 3.5 2M8.5 14.5l3.5-2 3.5 2" />
    </>
  ),
  document: (
    <>
      <path d="M7 3h8l4 4v13a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
      <path d="M14 3v5h5M9 13h6M9 17h4" />
    </>
  ),
  erable: (
    <path d="M12 2.5l1.4 3.1 1.8-.9-.6 4.2 2.7-1.8.6 2.2 2.6-.4-1.1 2.9 1.6.8-4.4 3.4.6 1.8-4.4-.6v4.3h-1.6v-4.3l-4.4.6.6-1.8L3 12.6l1.6-.8-1.1-2.9 2.6.4.6-2.2 2.7 1.8-.6-4.2 1.8.9z" />
  ),
  antenne: (
    <>
      <path d="M5.6 18.4a9 9 0 0 1 0-12.8M18.4 5.6a9 9 0 0 1 0 12.8M8.8 15.2a4.5 4.5 0 0 1 0-6.4M15.2 8.8a4.5 4.5 0 0 1 0 6.4" />
      <circle cx="12" cy="12" r="1.3" />
    </>
  ),
  eclair: <path d="M13 2 4 14h7l-1 8 9-12h-7z" />,
  info: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 11v5M12 7.8v.2" />
    </>
  ),
  installer: (
    <>
      <rect x="6" y="2.5" width="12" height="19" rx="2.5" />
      <path d="M12 7v7M9 11l3 3 3-3" />
    </>
  ),
  corbeille: <path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" />,
  plus: <path d="M12 5v14M5 12h14" />,
  radar: (
    <>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="12" r="4.5" />
      <path d="M12 12 18.4 5.6" />
    </>
  ),
};

function Icone({ nom, taille = 22, rempli = false, epaisseur = 1.8, className }) {
  return (
    <svg
      className={className}
      width={taille}
      height={taille}
      viewBox="0 0 24 24"
      fill={rempli ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={rempli ? 0 : epaisseur}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {ICONES[nom] || ICONES.info}
    </svg>
  );
}

function IconeCategorie({ code, taille = 20 }) {
  const c = CATEGORIES[code];
  return (
    <span className={`pastille cat-${code}`}>
      <Icone nom={c?.icone || "info"} taille={taille} rempli={c?.icone === "erable"} />
    </span>
  );
}

// ---------- Outils ----------

function lireJSON(cle, defaut) {
  try {
    const v = localStorage.getItem(cle);
    return v ? JSON.parse(v) : defaut;
  } catch {
    return defaut;
  }
}

function ecrireJSON(cle, valeur) {
  try {
    localStorage.setItem(cle, JSON.stringify(valeur));
  } catch {
    /* navigation privée : on ignore */
  }
}

function useStockage(cle, defaut) {
  const [valeur, setValeur] = useState(() => lireJSON(cle, defaut));
  const changer = useCallback(
    (v) => {
      setValeur(v);
      ecrireJSON(cle, v);
    },
    [cle],
  );
  return [valeur, changer];
}

function majuscule(texte) {
  return texte ? texte.charAt(0).toUpperCase() + texte.slice(1) : texte;
}

function ilYa(iso) {
  if (!iso) return "jamais";
  const minutes = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (minutes < 1) return "à l'instant";
  if (minutes < 60) return `il y a ${minutes} min`;
  const heures = Math.round(minutes / 60);
  if (heures < 48) return `il y a ${heures} h`;
  return `il y a ${Math.round(heures / 24)} j`;
}

function jourLocal(d = new Date()) {
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}

function libelleJour(jour) {
  if (jour === jourLocal()) return "Aujourd'hui";
  if (jour === jourLocal(new Date(Date.now() - 864e5))) return "Hier";
  return majuscule(new Date(`${jour}T12:00:00`).toLocaleDateString("fr-CA", { weekday: "long", day: "numeric", month: "long" }));
}

function dateLongue(jour) {
  if (!jour) return "";
  return new Date(`${jour}T12:00:00`).toLocaleDateString("fr-CA", { day: "numeric", month: "long", year: "numeric" });
}

// fr-CA écrit déjà « $ US » pour le dollar américain et « $ » pour le canadien. 2 000 000 000 → « 2 G$ US ».
function argent(n, devise) {
  const compact = Math.abs(n) >= 1e6;
  return new Intl.NumberFormat("fr-CA", {
    style: "currency",
    currency: devise || "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: compact ? 2 : 0,
    ...(compact ? { notation: "compact" } : {}),
  }).format(n);
}

function montant(ev) {
  const { amount_min: bas, amount_max: haut, currency } = ev;
  if (bas == null && haut == null) return null;
  if (bas != null && haut != null && bas !== haut) return `${argent(bas, currency)} à ${argent(haut, currency)}`;
  return argent(bas ?? haut, currency);
}

function montantMax(ev) {
  return ev.amount_max ?? ev.amount_min ?? null;
}

// Données vieilles : plus de 30 h un mardi-vendredi, ou plus de 80 h n'importe quand (fin de semaine).
function donneesVieilles(genereA) {
  if (!genereA) return false;
  const heures = (Date.now() - new Date(genereA).getTime()) / 3600000;
  const jour = new Date().getDay();
  return heures > 80 || (jour >= 2 && jour <= 5 && heures > 30);
}

function controlesEnOrdre(checks) {
  const ordre = Object.keys(CONTROLES);
  const rang = (nom) => (ordre.includes(nom) ? ordre.indexOf(nom) : ordre.length);
  return Object.entries(checks || {}).sort(([a], [b]) => rang(a) - rang(b));
}

function enGroupesParJour(liste) {
  const groupes = [];
  for (const ev of liste) {
    const dernier = groupes[groupes.length - 1];
    if (dernier && dernier.jour === ev.published_on) dernier.items.push(ev);
    else groupes.push({ jour: ev.published_on, items: [ev] });
  }
  return groupes;
}

// ---------- Données ----------

const FICHIERS = ["meta", "aujourdhui", "fil", "a_verifier", "sources"];

function useDonnees() {
  const [etat, setEtat] = useState({ chargement: true, erreur: null, donnees: null });
  const charger = useCallback(async () => {
    setEtat((e) => ({ ...e, chargement: true, erreur: null }));
    try {
      const resultats = await Promise.all(
        FICHIERS.map(async (nom) => {
          const r = await fetch(`./data/app/${nom}.json`, { cache: "no-store" });
          if (!r.ok) throw new Error(`${nom}.json : HTTP ${r.status}`);
          return [nom, await r.json()];
        }),
      );
      setEtat({ chargement: false, erreur: null, donnees: Object.fromEntries(resultats) });
    } catch (err) {
      setEtat((e) => ({ ...e, chargement: false, erreur: String(err.message || err) }));
    }
  }, []);
  useEffect(() => {
    charger();
    // Quand on revient dans l'app, on recharge (comme une vraie app).
    const auRetour = () => document.visibilityState === "visible" && charger();
    document.addEventListener("visibilitychange", auRetour);
    return () => document.removeEventListener("visibilitychange", auRetour);
  }, [charger]);
  return { ...etat, charger };
}

function useApparence(reglages) {
  useEffect(() => {
    const sombreSysteme = window.matchMedia?.("(prefers-color-scheme: dark)");
    const appliquer = () => {
      const sombre = reglages.theme === "sombre" || (reglages.theme === "auto" && sombreSysteme?.matches);
      const racine = document.documentElement;
      racine.dataset.theme = sombre ? "sombre" : "clair";
      racine.style.setProperty("--accent", ACCENTS[reglages.accent] || ACCENTS.bleu);
      racine.style.fontSize = reglages.taille === "grande" ? "18px" : "16px";
      document.querySelector('meta[name="theme-color"]')?.setAttribute("content", sombre ? "#07090D" : "#F2F3F7");
    };
    appliquer();
    sombreSysteme?.addEventListener?.("change", appliquer);
    return () => sombreSysteme?.removeEventListener?.("change", appliquer);
  }, [reglages.theme, reglages.accent, reglages.taille]);
}

const Ctx = createContext(null);
const useApp = () => useContext(Ctx);

// Les infos visibles selon les réglages (catégories, confirmées seulement, montant minimum, tri).
function useVisibles({ filtre = "tout", recherche = "" } = {}) {
  const { donnees, reglages } = useApp();
  return useMemo(() => {
    if (!donnees) return [];
    let l = reglages.montrerAVerifier ? [...donnees.fil, ...donnees.a_verifier] : [...donnees.fil];
    l = l.filter((e) => reglages.categories[e.category] !== false);
    if (reglages.seulementConfirme) l = l.filter((e) => e.badge === "confirme");
    if (reglages.montantMin > 0) l = l.filter((e) => montantMax(e) == null || montantMax(e) >= reglages.montantMin);
    if (filtre !== "tout") l = l.filter((e) => e.category === filtre);
    const q = recherche.trim().toLowerCase();
    if (q) {
      l = l.filter((e) => [e.title, ...(e.tickers || []), ...(e.entities || [])].join(" ").toLowerCase().includes(q));
    }
    const recent = (a, b) =>
      b.published_on.localeCompare(a.published_on) || (b.collected_at || "").localeCompare(a.collected_at || "");
    l.sort(reglages.tri === "montant" ? (a, b) => (montantMax(b) ?? -1) - (montantMax(a) ?? -1) || recent(a, b) : recent);
    return l;
  }, [donnees, reglages, filtre, recherche]);
}

// ---------- Morceaux d'interface ----------

function Ecran({ titre, sousTitre, retour, droite, children }) {
  const sentinelle = useRef(null);
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    const el = sentinelle.current;
    if (!el || !("IntersectionObserver" in window)) return undefined;
    const obs = new IntersectionObserver(([e]) => setCompact(!e.isIntersecting), { rootMargin: "-56px 0px 0px 0px" });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return (
    <div className="ecran">
      <div className={compact ? "barre-haut compacte" : "barre-haut"}>
        <div className="barre-cote">
          {retour && (
            <button type="button" className="retour" onClick={retour.action}>
              <Icone nom="chevron-g" taille={22} epaisseur={2.2} />
              {retour.label}
            </button>
          )}
        </div>
        <div className="barre-titre" aria-hidden={!compact}>
          {titre}
        </div>
        <div className="barre-cote droite">{droite}</div>
      </div>
      <header className="grand-titre">
        {sousTitre && <p className="sous-titre">{sousTitre}</p>}
        <h1>{titre}</h1>
      </header>
      <div ref={sentinelle} className="sentinelle" />
      {children}
    </div>
  );
}

function BoutonRond({ icone, label, onClick, tourne }) {
  return (
    <button type="button" className="bouton-rond presse" onClick={onClick} aria-label={label}>
      <Icone nom={icone} taille={20} epaisseur={2} className={tourne ? "tourne" : ""} />
    </button>
  );
}

function Badge({ code, grand }) {
  const b = BADGES[code] || BADGES.a_verifier;
  return (
    <span className={`badge b-${code}${grand ? " grand" : ""}`}>
      <Icone nom={b.icone} taille={grand ? 16 : 14} epaisseur={2.2} />
      {b.label}
    </span>
  );
}

function BadgeIcone({ code }) {
  const b = BADGES[code] || BADGES.a_verifier;
  return (
    <span className={`badge-icone b-${code}`} title={b.label}>
      <Icone nom={b.icone} taille={16} epaisseur={2.2} />
      <span className="cache">{b.label}</span>
    </span>
  );
}

function LigneEvenement({ ev }) {
  const { ouvrirDetail } = useApp();
  const m = montant(ev);
  return (
    <button type="button" className="ligne presse" onClick={() => ouvrirDetail(ev)}>
      <IconeCategorie code={ev.category} />
      <span className="ligne-centre">
        <span className="ligne-titre">{ev.title}</span>
        <span className="ligne-meta">
          {ev.tickers?.slice(0, 3).map((t) => (
            <span key={t} className="symbole">
              {t}
            </span>
          ))}
          {m && <span className="ligne-montant">{m}</span>}
          {!m && !ev.tickers?.length && <span>{CATEGORIES[ev.category]?.label}</span>}
        </span>
      </span>
      <BadgeIcone code={ev.badge} />
    </button>
  );
}

function ListeEvenements({ liste, groupee = true }) {
  if (!groupee) {
    return (
      <div className="carte liste">
        {liste.map((ev) => (
          <LigneEvenement key={ev.id} ev={ev} />
        ))}
      </div>
    );
  }
  return enGroupesParJour(liste).map((g) => (
    <section key={g.jour}>
      <h2 className="section">{libelleJour(g.jour)}</h2>
      <div className="carte liste">
        {g.items.map((ev) => (
          <LigneEvenement key={ev.id} ev={ev} />
        ))}
      </div>
    </section>
  ));
}

function Vide({ icone = "radar", titre, texte }) {
  return (
    <div className="vide">
      <span className="vide-icone">
        <Icone nom={icone} taille={30} />
      </span>
      <p className="vide-titre">{titre}</p>
      <p className="vide-texte">{texte}</p>
    </div>
  );
}

function Interrupteur({ actif, onChange, label }) {
  return (
    <button type="button" role="switch" aria-checked={actif} aria-label={label} className={actif ? "inter actif" : "inter"} onClick={() => onChange(!actif)}>
      <span />
    </button>
  );
}

function Segments({ valeur, options, onChange, label }) {
  return (
    <div className="segments" role="radiogroup" aria-label={label}>
      {options.map(([v, texte]) => (
        <button key={String(v)} type="button" role="radio" aria-checked={valeur === v} className={valeur === v ? "segment actif" : "segment"} onClick={() => onChange(v)}>
          {texte}
        </button>
      ))}
    </div>
  );
}

function Groupe({ titre, pied, children }) {
  return (
    <section className="groupe">
      {titre && <h2 className="section">{titre}</h2>}
      <div className="carte liste">{children}</div>
      {pied && <p className="groupe-pied">{pied}</p>}
    </section>
  );
}

function Rangee({ icone, couleur, label, bloc, children }) {
  return (
    <div className={bloc ? "rangee bloc" : "rangee"}>
      <div className="rangee-gauche">
        {icone && (
          <span className={`pastille petite fond-${couleur || "accent"}`}>
            <Icone nom={icone} taille={17} rempli={icone === "erable"} epaisseur={2} />
          </span>
        )}
        <span className="rangee-label">{label}</span>
      </div>
      <div className="rangee-droite">{children}</div>
    </div>
  );
}

function RangeeLien({ icone, couleur, label, valeur, onClick, danger }) {
  return (
    <button type="button" className={danger ? "rangee lien-rangee presse danger" : "rangee lien-rangee presse"} onClick={onClick}>
      <div className="rangee-gauche">
        {icone && (
          <span className={`pastille petite fond-${couleur || "accent"}`}>
            <Icone nom={icone} taille={17} epaisseur={2} />
          </span>
        )}
        <span className="rangee-label">{label}</span>
      </div>
      <div className="rangee-droite">
        {valeur != null && <span className="rangee-valeur">{valeur}</span>}
        {!danger && <Icone nom="chevron-d" taille={18} epaisseur={2.2} className="chevron" />}
      </div>
    </button>
  );
}

function RadarAnime() {
  return (
    <div className="radar-anime" aria-hidden="true">
      <span className="radar-point p1" />
      <span className="radar-point p2" />
      <span className="radar-point p3" />
    </div>
  );
}

function Feuille({ titre, fermer, children }) {
  const [visible, setVisible] = useState(false);
  const fermerAnime = useCallback(() => {
    setVisible(false);
    setTimeout(fermer, 260);
  }, [fermer]);
  useEffect(() => {
    const id = requestAnimationFrame(() => setVisible(true));
    const echap = (e) => e.key === "Escape" && fermerAnime();
    window.addEventListener("keydown", echap);
    document.body.classList.add("bloque");
    return () => {
      cancelAnimationFrame(id);
      window.removeEventListener("keydown", echap);
      document.body.classList.remove("bloque");
    };
  }, [fermerAnime]);
  return (
    <div className={visible ? "feuille-fond ouvert" : "feuille-fond"} onClick={fermerAnime}>
      <div className="feuille" role="dialog" aria-modal="true" aria-label={titre} onClick={(e) => e.stopPropagation()}>
        <div className="poignee" />
        <button type="button" className="feuille-fermer presse" onClick={fermerAnime} aria-label="Fermer">
          <Icone nom="x" taille={18} epaisseur={2.4} />
        </button>
        {children}
      </div>
    </div>
  );
}

function FeuilleDetail({ ev, fermer }) {
  const { noms, favoris, basculerFavori } = useApp();
  const [copie, setCopie] = useState(false);
  const m = montant(ev);
  const rates = Object.values(ev.checks || {}).filter((ok) => !ok).length;
  const partager = async () => {
    try {
      if (navigator.share) await navigator.share({ title: ev.title, text: ev.title, url: ev.official_url });
      else {
        await navigator.clipboard.writeText(ev.official_url);
        setCopie(true);
      }
    } catch {
      /* partage annulé */
    }
  };
  return (
    <Feuille titre={ev.title} fermer={fermer}>
      <div className="detail-haut">
        <IconeCategorie code={ev.category} taille={18} />
        <span>{CATEGORIES[ev.category]?.label}</span>
        <span className="point-sep">·</span>
        <span>{dateLongue(ev.published_on)}</span>
      </div>
      <h2 className="detail-titre">{ev.title}</h2>
      <div className="detail-badges">
        <Badge code={ev.badge} grand />
      </div>
      {m && <p className="detail-montant">{m}</p>}

      {ev.tickers?.length > 0 && (
        <div className="detail-symboles">
          {ev.tickers.map((t) => {
            const suivi = favoris.includes(t);
            return (
              <button key={t} type="button" className={suivi ? "symbole-grand suivi presse" : "symbole-grand presse"} onClick={() => basculerFavori(t)} aria-pressed={suivi}>
                <Icone nom="etoile" taille={16} rempli={suivi} epaisseur={2} />
                {t}
              </button>
            );
          })}
        </div>
      )}
      {ev.entities?.length > 0 && <p className="detail-entites">{ev.entities.join(" · ")}</p>}
      {ev.notes?.map((n) => (
        <p key={n} className="detail-note">
          <Icone nom="alerte" taille={16} epaisseur={2.2} /> {n}
        </p>
      ))}

      <div className="detail-actions">
        <a className="bouton-principal presse" href={ev.official_url} target="_blank" rel="noopener noreferrer">
          <Icone nom="externe" taille={18} epaisseur={2.2} />
          Document officiel
        </a>
        <button type="button" className="bouton-second presse" onClick={partager} aria-label="Partager">
          <Icone nom="partager" taille={18} epaisseur={2.2} />
          {copie ? "Lien copié" : "Partager"}
        </button>
      </div>

      <h3 className="section">{rates ? `${rates} contrôle(s) raté(s)` : "Tous les contrôles réussis"}</h3>
      <div className="carte liste controles">
        {controlesEnOrdre(ev.checks).map(([nom, ok]) => (
          <div key={nom} className={ok ? "controle ok" : "controle rate"}>
            <Icone nom={ok ? "double" : "x"} taille={16} epaisseur={2.4} />
            {CONTROLES[nom] || nom.replaceAll("_", " ")}
          </div>
        ))}
        {ev.confirmations?.map((c) => (
          <a key={c.official_url} className="controle ok" href={c.official_url} target="_blank" rel="noopener noreferrer">
            <Icone nom="bouclier-ok" taille={16} epaisseur={2.2} />
            Confirmé par {noms[c.source] || c.source}
            <Icone nom="externe" taille={14} epaisseur={2.2} />
          </a>
        ))}
      </div>
      <p className="detail-pied">
        Lu {ilYa(ev.collected_at)} · n° officiel {ev.official_id}
        <br />
        Empreinte {ev.sha256?.slice(0, 16)}…
      </p>
    </Feuille>
  );
}

function FeuilleInstaller({ fermer }) {
  const installee = window.navigator.standalone || window.matchMedia?.("(display-mode: standalone)").matches;
  return (
    <Feuille titre="Installer Radar" fermer={fermer}>
      <h2 className="detail-titre">Installer sur l'iPhone</h2>
      {installee ? (
        <p className="detail-entites">Radar est déjà installé sur ton écran d'accueil.</p>
      ) : (
        <ol className="etapes">
          <li>
            <span className="etape-num">1</span>Ouvre Radar dans <strong>Safari</strong>.
          </li>
          <li>
            <span className="etape-num">2</span>Touche <strong>Partager</strong>
            <span className="icone-inline">
              <Icone nom="partager" taille={16} epaisseur={2.2} />
            </span>
            en bas de l'écran.
          </li>
          <li>
            <span className="etape-num">3</span>Choisis <strong>Sur l'écran d'accueil</strong>.
          </li>
          <li>
            <span className="etape-num">4</span>Touche <strong>Ajouter</strong>. Radar s'ouvre ensuite comme une vraie app, en plein écran.
          </li>
        </ol>
      )}
    </Feuille>
  );
}

// ---------- Écrans ----------

function Accueil({ pousser, allerAuFil }) {
  const { donnees, charger, chargement } = useApp();
  const { meta, aujourdhui } = donnees;
  const visibles = useVisibles();
  const nouvelles = visibles.filter((e) => Date.now() - new Date(e.collected_at).getTime() < 864e5).length;
  const confirmees = visibles.filter((e) => e.badge === "confirme").length;
  const parCategorie = useMemo(() => {
    const n = {};
    for (const e of visibles) n[e.category] = (n[e.category] || 0) + 1;
    return n;
  }, [visibles]);
  const top = aujourdhui?.top || [];
  const pourcentage = meta.sources_total ? Math.round((meta.sources_branchees / meta.sources_total) * 100) : 0;
  const date = majuscule(new Date().toLocaleDateString("fr-CA", { weekday: "long", day: "numeric", month: "long" }));

  return (
    <Ecran titre="Radar" sousTitre={date} droite={<BoutonRond icone="rafraichir" label="Actualiser" onClick={charger} tourne={chargement} />}>
      <EtatDonnees />

      {top.length === 0 ? (
        <div className="heros">
          <RadarAnime />
          <div className="heros-texte">
            <p className="heros-titre">Pas encore de suggestions</p>
            <p className="heros-sous">Le score arrive à la phase 5. En attendant, le fil montre tout ce que le robot lit.</p>
            <div className="mini-barre">
              <div style={{ width: `${Math.max(pourcentage, 3)}%` }} />
            </div>
            <p className="heros-pied">
              {meta.sources_branchees} sur {meta.sources_total} sources · phase {meta.phase}
            </p>
          </div>
        </div>
      ) : (
        <>
          <h2 className="section">À regarder aujourd'hui</h2>
          <ListeEvenements liste={top} groupee={false} />
        </>
      )}

      <div className="tuiles">
        <button type="button" className="tuile presse" onClick={() => allerAuFil("tout")}>
          <Icone nom="eclair" taille={20} epaisseur={2} className="t-accent" />
          <span className="tuile-valeur">{nouvelles}</span>
          <span className="tuile-label">Nouvelles (24 h)</span>
        </button>
        <button type="button" className="tuile presse" onClick={() => allerAuFil("tout")}>
          <Icone nom="double" taille={20} epaisseur={2.2} className="t-vert" />
          <span className="tuile-valeur">{confirmees}</span>
          <span className="tuile-label">Confirmées</span>
        </button>
        <button type="button" className="tuile presse" onClick={() => pousser("a_verifier")}>
          <Icone nom="alerte" taille={20} epaisseur={2} className="t-jaune" />
          <span className="tuile-valeur">{donnees.a_verifier.length}</span>
          <span className="tuile-label">À vérifier</span>
        </button>
        <button type="button" className="tuile presse" onClick={() => pousser("sources")}>
          <Icone nom="antenne" taille={20} epaisseur={2} className="t-bleu" />
          <span className="tuile-valeur">
            {meta.sources_branchees}
            <small>/{meta.sources_total}</small>
          </span>
          <span className="tuile-label">Sources actives</span>
        </button>
      </div>

      <h2 className="section">Catégories</h2>
      <div className="grille-cat">
        {Object.entries(CATEGORIES).map(([k, c]) => (
          <button key={k} type="button" className="cat presse" onClick={() => allerAuFil(k)}>
            <IconeCategorie code={k} />
            <span className="cat-label">{c.label}</span>
            <span className="cat-nombre">{parCategorie[k] || 0}</span>
          </button>
        ))}
      </div>

      <div className="section-ligne">
        <h2 className="section">Dernières infos</h2>
        {visibles.length > 0 && (
          <button type="button" className="lien" onClick={() => allerAuFil("tout")}>
            Tout voir
          </button>
        )}
      </div>
      {visibles.length === 0 ? (
        <div className="carte">
          <Vide titre="Rien pour l'instant" texte="Les premières infos arrivent avec la phase 1 (SEC)." />
        </div>
      ) : (
        <ListeEvenements liste={visibles.slice(0, 5)} groupee={false} />
      )}
      <p className="avertissement">Projet personnel · Pas des conseils financiers</p>
    </Ecran>
  );
}

function EtatDonnees() {
  const { donnees } = useApp();
  const genere = donnees.meta.genere_a;
  if (typeof navigator !== "undefined" && navigator.onLine === false) {
    return <p className="etat gris">Hors ligne · données gardées {ilYa(genere)}</p>;
  }
  if (donneesVieilles(genere)) {
    return <p className="etat jaune">Données vieilles · le robot n'a pas roulé depuis {ilYa(genere).replace("il y a ", "")}</p>;
  }
  return <p className="etat vert">À jour · {ilYa(genere)}</p>;
}

function Fil({ filtre: filtreChoisi, setFiltre, recherche, setRecherche }) {
  const { reglages } = useApp();
  // Si la catégorie choisie a été cachée dans les réglages, on revient à « Tout ».
  const filtre = filtreChoisi !== "tout" && reglages.categories[filtreChoisi] === false ? "tout" : filtreChoisi;
  const liste = useVisibles({ filtre, recherche });
  const categories = Object.entries(CATEGORIES).filter(([k]) => reglages.categories[k] !== false);
  return (
    <Ecran titre="Fil">
      <div className="recherche">
        <Icone nom="loupe" taille={18} epaisseur={2} />
        <input type="search" placeholder="Compagnie, symbole, personne…" value={recherche} onChange={(e) => setRecherche(e.target.value)} enterKeyHint="search" aria-label="Chercher" />
        {recherche && (
          <button type="button" onClick={() => setRecherche("")} aria-label="Effacer">
            <Icone nom="x" taille={16} epaisseur={2.4} />
          </button>
        )}
      </div>
      <div className="puces" role="tablist" aria-label="Catégories">
        {[["tout", "Tout"], ...categories.map(([k, c]) => [k, c.label])].map(([k, label]) => (
          <button key={k} type="button" role="tab" aria-selected={filtre === k} className={filtre === k ? "puce actif" : "puce"} onClick={() => setFiltre(k)}>
            {label}
          </button>
        ))}
      </div>
      {liste.length === 0 ? (
        <Vide
          icone={recherche ? "loupe" : "radar"}
          titre={recherche ? "Aucun résultat" : "Rien pour l'instant"}
          texte={recherche ? "Essaie un autre mot ou un symbole (ex. LMT)." : "Les premières infos arrivent avec la phase 1 (SEC)."}
        />
      ) : (
        <ListeEvenements liste={liste} groupee={reglages.tri === "recent"} />
      )}
    </Ecran>
  );
}

function Favoris() {
  const { donnees, favoris, basculerFavori } = useApp();
  const [saisie, setSaisie] = useState("");
  const symbole = saisie.trim().toUpperCase();
  const valide = SYMBOLE_RE.test(symbole) && !favoris.includes(symbole);
  const ajouter = (e) => {
    e.preventDefault();
    if (!valide) return;
    basculerFavori(symbole);
    setSaisie("");
  };
  const liste = donnees.fil.filter((e) => e.tickers?.some((t) => favoris.includes(t)));
  return (
    <Ecran titre="Favoris">
      <form className="ajout" onSubmit={ajouter}>
        <input value={saisie} onChange={(e) => setSaisie(e.target.value)} placeholder="Symbole, ex. LMT" autoCapitalize="characters" autoCorrect="off" spellCheck={false} aria-label="Symbole à suivre" />
        <button type="submit" className="bouton-principal presse" disabled={!valide}>
          <Icone nom="plus" taille={18} epaisseur={2.4} />
          Ajouter
        </button>
      </form>
      {favoris.length > 0 && (
        <div className="favoris">
          {favoris.map((t) => (
            <span key={t} className="favori">
              <Icone nom="etoile" taille={14} rempli />
              {t}
              <button type="button" onClick={() => basculerFavori(t)} aria-label={`Retirer ${t}`}>
                <Icone nom="x" taille={14} epaisseur={2.6} />
              </button>
            </span>
          ))}
        </div>
      )}
      {favoris.length === 0 ? (
        <Vide icone="etoile" titre="Aucun favori" texte="Ajoute un symbole, ou touche l'étoile d'une compagnie dans une info." />
      ) : liste.length === 0 ? (
        <Vide icone="etoile" titre="Rien sur tes favoris" texte="Dès que le robot lit une info sur une de ces compagnies, elle apparaît ici." />
      ) : (
        <ListeEvenements liste={liste} />
      )}
    </Ecran>
  );
}

function Reglages({ pousser, ouvrirInstaller }) {
  const { donnees, reglages: r, setReglages } = useApp();
  const maj = (champ, valeur) => setReglages({ ...r, [champ]: valeur });
  const { meta } = donnees;
  const reinitialiser = () => {
    if (window.confirm("Remettre tous les réglages par défaut ?")) setReglages(REGLAGES_DEFAUT);
  };
  return (
    <Ecran titre="Réglages">
      <Groupe titre="Affichage">
        <Rangee label="Thème" bloc>
          <Segments label="Thème" valeur={r.theme} onChange={(v) => maj("theme", v)} options={[["sombre", "Sombre"], ["clair", "Clair"], ["auto", "Auto"]]} />
        </Rangee>
        <Rangee label="Taille du texte" bloc>
          <Segments label="Taille du texte" valeur={r.taille} onChange={(v) => maj("taille", v)} options={[["normale", "Normale"], ["grande", "Grande"]]} />
        </Rangee>
        <Rangee label="Couleur">
          <div className="couleurs" role="radiogroup" aria-label="Couleur">
            {Object.entries(ACCENTS).map(([nom, hex]) => (
              <button key={nom} type="button" role="radio" aria-checked={r.accent === nom} aria-label={nom} className={r.accent === nom ? "couleur actif" : "couleur"} style={{ background: hex }} onClick={() => maj("accent", nom)} />
            ))}
          </div>
        </Rangee>
      </Groupe>

      <Groupe titre="Fil" pied="Les infos « À vérifier » ont raté au moins un contrôle. Elles ne sont jamais suggérées.">
        <Rangee label="Seulement les confirmées">
          <Interrupteur label="Seulement les confirmées" actif={r.seulementConfirme} onChange={(v) => maj("seulementConfirme", v)} />
        </Rangee>
        <Rangee label="Montrer les « À vérifier »">
          <Interrupteur label="Montrer les infos à vérifier" actif={r.montrerAVerifier} onChange={(v) => maj("montrerAVerifier", v)} />
        </Rangee>
        <Rangee label="Montant minimum" bloc>
          <Segments label="Montant minimum" valeur={r.montantMin} onChange={(v) => maj("montantMin", v)} options={MONTANTS_MIN} />
        </Rangee>
        <Rangee label="Trier par" bloc>
          <Segments label="Trier par" valeur={r.tri} onChange={(v) => maj("tri", v)} options={[["recent", "Plus récent"], ["montant", "Plus gros montant"]]} />
        </Rangee>
      </Groupe>

      <Groupe titre="Catégories">
        {Object.entries(CATEGORIES).map(([k, c]) => (
          <Rangee key={k} icone={c.icone} couleur={k} label={c.label}>
            <Interrupteur label={c.label} actif={r.categories[k] !== false} onChange={(v) => maj("categories", { ...r.categories, [k]: v })} />
          </Rangee>
        ))}
      </Groupe>

      <Groupe titre="Fiabilité">
        <RangeeLien icone="antenne" couleur="bleu" label="État des sources" valeur={`${meta.sources_branchees}/${meta.sources_total}`} onClick={() => pousser("sources")} />
        <RangeeLien icone="alerte" couleur="jaune" label="À vérifier" valeur={donnees.a_verifier.length} onClick={() => pousser("a_verifier")} />
        <RangeeLien icone="bouclier-ok" couleur="vert" label="Comment c'est vérifié" onClick={() => pousser("verification")} />
      </Groupe>

      <Groupe titre="App">
        <RangeeLien icone="installer" couleur="accent" label="Installer sur l'iPhone" onClick={ouvrirInstaller} />
        <RangeeLien icone="corbeille" label="Réinitialiser les réglages" onClick={reinitialiser} danger />
      </Groupe>

      <p className="avertissement">
        Radar {VERSION} · données {ilYa(meta.genere_a)}
        <br />
        Projet personnel · Pas des conseils financiers
      </p>
    </Ecran>
  );
}

function EcranSources({ retour }) {
  const { donnees } = useApp();
  const sources = donnees.sources;
  const compte = {};
  for (const s of sources) compte[s.statut] = (compte[s.statut] || 0) + 1;
  return (
    <Ecran titre="Sources" retour={retour}>
      <div className="resume">
        {Object.keys(STATUTS)
          .filter((s) => compte[s])
          .map((s) => (
            <span key={s} className={`pilule ${STATUTS[s].couleur}`}>
              <span className={`point ${STATUTS[s].couleur}`} />
              {STATUTS[s].pluriel || STATUTS[s].label} · {compte[s]}
            </span>
          ))}
      </div>
      {Object.entries(CATEGORIES).map(([cat, c]) => {
        const groupe = sources.filter((s) => s.categorie === cat);
        if (!groupe.length) return null;
        return (
          <section key={cat}>
            <h2 className="section">{c.label}</h2>
            <div className="carte liste">
              {groupe.map((s) => (
                <a key={s.id} className={s.statut === "ecartee" ? "source ecartee presse" : "source presse"} href={s.site} target="_blank" rel="noopener noreferrer">
                  <span className={`point ${STATUTS[s.statut]?.couleur || "gris"}`} />
                  <span className="source-texte">
                    <span className="source-nom">
                      {s.nom}
                      {!s.officielle && <span className="mini-pilule">non officielle</span>}
                    </span>
                    <span className="source-etat">
                      {s.libelle}
                      {s.dernier_succes ? ` · lue ${ilYa(s.dernier_succes)}` : ""}
                      {s.explication ? ` · ${s.explication}` : ""}
                    </span>
                  </span>
                  <Icone nom="externe" taille={16} epaisseur={2} className="chevron" />
                </a>
              ))}
            </div>
          </section>
        );
      })}
    </Ecran>
  );
}

function EcranAVerifier({ retour }) {
  const { donnees } = useApp();
  return (
    <Ecran titre="À vérifier" retour={retour}>
      <p className="explication">Ces infos ont raté au moins un contrôle automatique. Elles n'entrent jamais dans les suggestions.</p>
      {donnees.a_verifier.length === 0 ? (
        <Vide icone="bouclier-ok" titre="Rien à vérifier" texte="Tout ce que le robot a lu a passé les contrôles." />
      ) : (
        <ListeEvenements liste={donnees.a_verifier} />
      )}
    </Ecran>
  );
}

function EcranVerification({ retour }) {
  return (
    <Ecran titre="Vérification" retour={retour}>
      <p className="explication">Le robot lit seulement des sources officielles. Chaque info passe des contrôles automatiques avant d'être montrée. Rien plutôt que faux.</p>
      <Groupe titre="Les badges">
        {Object.entries(BADGES).map(([code, b]) => (
          <div key={code} className="rangee bloc">
            <Badge code={code} grand />
            <span className="rangee-texte">{b.texte}</span>
          </div>
        ))}
      </Groupe>
      <Groupe titre="Les contrôles" pied="Chaque source ajoute aussi ses propres contrôles (ex. formulaire 4 : seul le code P est un vrai achat).">
        {Object.values(CONTROLES).map((texte) => (
          <div key={texte} className="controle ok">
            <Icone nom="double" taille={16} epaisseur={2.4} />
            {texte}
          </div>
        ))}
      </Groupe>
      <Groupe titre="Le robot">
        <div className="rangee bloc">
          <span className="rangee-texte">Il roule 5 fois par jour de semaine. Les tests passent avant chaque passage : s'ils échouent, rien n'est publié. Chaque info garde le lien, le numéro officiel et l'empreinte du document original.</span>
        </div>
      </Groupe>
    </Ecran>
  );
}

// ---------- App ----------

const ONGLETS = [
  { id: "accueil", label: "Accueil", icone: "accueil" },
  { id: "fil", label: "Fil", icone: "fil" },
  { id: "favoris", label: "Favoris", icone: "etoile" },
  { id: "reglages", label: "Réglages", icone: "reglages" },
];
const PAGES = { sources: EcranSources, a_verifier: EcranAVerifier, verification: EcranVerification };
const TITRES_ONGLETS = { accueil: "Radar", fil: "Fil", favoris: "Favoris", reglages: "Réglages" };

function Squelette() {
  return (
    <div className="ecran">
      <header className="grand-titre">
        <h1>Radar</h1>
      </header>
      <div className="squelette heros-squelette" />
      <div className="tuiles">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="squelette tuile-squelette" />
        ))}
      </div>
    </div>
  );
}

function App() {
  const { chargement, erreur, donnees, charger } = useDonnees();
  const [reglagesStockes, setReglages] = useStockage("radar-reglages", REGLAGES_DEFAUT);
  const reglages = useMemo(() => ({ ...REGLAGES_DEFAUT, ...reglagesStockes, categories: { ...REGLAGES_DEFAUT.categories, ...reglagesStockes?.categories } }), [reglagesStockes]);
  const [favoris, setFavoris] = useStockage("radar-favoris", []);
  const [onglet, setOnglet] = useState(() => lireJSON("radar-onglet", "accueil"));
  const [pile, setPile] = useState([]);
  // Le fil se souvient du filtre et de la recherche quand on change d'onglet.
  const [filtreFil, setFiltreFil] = useState("tout");
  const [rechercheFil, setRechercheFil] = useState("");
  const [detail, setDetail] = useState(null);
  const [installer, setInstaller] = useState(false);
  useApparence(reglages);

  const choisirOnglet = (id) => {
    setOnglet(id);
    ecrireJSON("radar-onglet", id);
    setPile([]);
    window.scrollTo(0, 0);
  };
  const pousser = (page) => {
    setPile((p) => [...p, page]);
    window.scrollTo(0, 0);
  };
  const revenir = () => {
    setPile((p) => p.slice(0, -1));
    window.scrollTo(0, 0);
  };
  const allerAuFil = (filtre = "tout") => {
    setFiltreFil(filtre);
    setRechercheFil("");
    choisirOnglet("fil");
  };
  const basculerFavori = (t) => setFavoris(favoris.includes(t) ? favoris.filter((x) => x !== t) : [...favoris, t]);
  const noms = useMemo(() => Object.fromEntries((donnees?.sources || []).map((s) => [s.id, s.nom])), [donnees]);

  const valeur = { donnees, chargement, charger, reglages, setReglages, favoris, basculerFavori, noms, ouvrirDetail: setDetail };
  const page = pile[pile.length - 1];
  const Page = page ? PAGES[page] : null;
  const retour = { label: pile.length > 1 ? "Retour" : TITRES_ONGLETS[onglet], action: revenir };

  let contenu;
  if (!donnees && erreur) {
    contenu = (
      <div className="ecran">
        <header className="grand-titre">
          <h1>Radar</h1>
        </header>
        <div className="carte">
          <Vide icone="alerte" titre="Impossible de charger les données" texte={erreur} />
          <button type="button" className="bouton-principal presse plein" onClick={charger}>
            Réessayer
          </button>
        </div>
      </div>
    );
  } else if (!donnees) {
    contenu = <Squelette />;
  } else if (Page) {
    contenu = <Page key={page} retour={retour} />;
  } else if (onglet === "fil") {
    contenu = <Fil filtre={filtreFil} setFiltre={setFiltreFil} recherche={rechercheFil} setRecherche={setRechercheFil} />;
  } else if (onglet === "favoris") {
    contenu = <Favoris />;
  } else if (onglet === "reglages") {
    contenu = <Reglages pousser={pousser} ouvrirInstaller={() => setInstaller(true)} />;
  } else {
    contenu = <Accueil pousser={pousser} allerAuFil={allerAuFil} />;
  }

  return (
    <Ctx.Provider value={valeur}>
      <style>{CSS}</style>
      <main className="app">{contenu}</main>
      <nav className="onglets" aria-label="Navigation">
        {ONGLETS.map((o) => (
          <button key={o.id} type="button" className={onglet === o.id ? "onglet actif" : "onglet"} onClick={() => choisirOnglet(o.id)} aria-current={onglet === o.id ? "page" : undefined}>
            <Icone nom={o.icone} taille={25} rempli={o.id === "favoris" && onglet === o.id} epaisseur={onglet === o.id ? 2.1 : 1.8} />
            <span>{o.label}</span>
          </button>
        ))}
      </nav>
      {detail && <FeuilleDetail ev={detail} fermer={() => setDetail(null)} />}
      {installer && <FeuilleInstaller fermer={() => setInstaller(false)} />}
    </Ctx.Provider>
  );
}

// ---------- Style ----------

const CSS = `
:root { --accent: #4F8CFF; --rayon: 18px; }
:root, [data-theme="sombre"] {
  --fond: #07090D; --fond-2: #0F121A; --carte: #12161F; --carte-2: #1A1F2B; --ligne: rgba(255,255,255,.07);
  --texte: #F3F5F9; --texte-2: #A1A9B8; --texte-3: #6B7385;
  --vert: #2BD9A0; --jaune: #F5B544; --rouge: #FF5C6C; --bleu: #4F8CFF; --gris: #5D6577; --violet: #A98BFF; --cyan: #29C5F6; --olive: #9BD45A;
  --barre: rgba(12,15,21,.92); --ombre: 0 12px 40px rgba(0,0,0,.5); --segment: #2A3142; --inter-off: #2B3142;
  color-scheme: dark;
}
[data-theme="clair"] {
  --fond: #F2F3F7; --fond-2: #FFFFFF; --carte: #FFFFFF; --carte-2: #EEF0F5; --ligne: rgba(15,23,42,.08);
  --texte: #0B1220; --texte-2: #586274; --texte-3: #8D95A5;
  --vert: #0E9F74; --jaune: #B97509; --rouge: #E5484D; --bleu: #2F6BEA; --gris: #A3AAB8; --violet: #7A5AF0; --cyan: #0A93C4; --olive: #5A9618;
  --barre: rgba(255,255,255,.92); --ombre: 0 12px 40px rgba(15,23,42,.14); --segment: #FFFFFF; --inter-off: #E1E4EA;
  color-scheme: light;
}
* { box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
html, body { margin: 0; background: var(--fond); color: var(--texte); }
body { font: 1rem/1.4 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, sans-serif;
  -webkit-font-smoothing: antialiased; -webkit-text-size-adjust: 100%; overscroll-behavior-y: none; }
body.bloque { overflow: hidden; }
a { color: var(--accent); text-decoration: none; }
button { font: inherit; color: inherit; background: none; border: none; padding: 0; cursor: pointer; }
input { font: inherit; color: var(--texte); }
.cache { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); }
.presse { transition: transform .14s ease, opacity .14s ease; }
.presse:active { transform: scale(.97); opacity: .8; }

.app { max-width: 680px; margin: 0 auto; padding: 0 16px calc(env(safe-area-inset-bottom) + 96px); }
.ecran { animation: entree .28s ease both; }
@keyframes entree { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: none; } }

/* En-tête : grand titre qui se replie en petite barre floue en défilant (comme iOS) */
.barre-haut { position: sticky; top: 0; z-index: 20; margin: 0 -16px; padding: env(safe-area-inset-top) 8px 0;
  height: calc(52px + env(safe-area-inset-top)); display: grid; grid-template-columns: 1fr auto 1fr; align-items: center;
  border-bottom: 1px solid transparent; transition: background .2s, border-color .2s; }
.barre-haut.compacte { background: var(--barre); -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px); border-bottom-color: var(--ligne); }
.barre-titre { font-weight: 650; font-size: 1.0625rem; opacity: 0; transition: opacity .2s; }
.barre-haut.compacte .barre-titre { opacity: 1; }
.barre-cote { display: flex; align-items: center; min-width: 0; }
.barre-cote.droite { justify-content: flex-end; padding-right: 8px; }
.retour { display: inline-flex; align-items: center; gap: 2px; color: var(--accent); font-size: 1.0625rem; padding: 8px 6px; }
.grand-titre { padding: 0 4px 6px; margin-top: -8px; }
.grand-titre h1 { margin: 0; font-size: 2.125rem; font-weight: 800; letter-spacing: -.025em; line-height: 1.15; }
.sous-titre { margin: 0 0 2px; color: var(--texte-2); font-size: .8125rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; }
.sentinelle { height: 1px; }
.bouton-rond { width: 38px; height: 38px; border-radius: 19px; display: inline-flex; align-items: center; justify-content: center;
  background: var(--carte-2); color: var(--accent); }
.tourne { animation: tourne 0.9s linear infinite; }
@keyframes tourne { to { transform: rotate(360deg); } }

.etat { display: inline-flex; align-items: center; gap: 8px; margin: 2px 4px 14px; font-size: .875rem; color: var(--texte-2); }
.etat::before { content: ""; width: 8px; height: 8px; border-radius: 4px; background: var(--gris); }
.etat.vert::before { background: var(--vert); box-shadow: 0 0 0 4px color-mix(in srgb, var(--vert) 22%, transparent); }
.etat.jaune { color: var(--jaune); } .etat.jaune::before { background: var(--jaune); }

.section { font-size: .8125rem; font-weight: 600; text-transform: uppercase; letter-spacing: .06em; color: var(--texte-2); margin: 26px 6px 8px; }
.section-ligne { display: flex; align-items: baseline; justify-content: space-between; }
.section-ligne .lien { margin-right: 6px; }
.lien { color: var(--accent); font-size: .9375rem; font-weight: 500; }
.carte { background: var(--carte); border: 1px solid var(--ligne); border-radius: var(--rayon); }
.carte > .vide { padding: 28px 16px; }
.liste { overflow: hidden; }

/* Héros */
.heros { display: flex; gap: 16px; align-items: center; padding: 18px; border-radius: 22px; border: 1px solid var(--ligne);
  background: radial-gradient(120% 140% at 100% 0%, color-mix(in srgb, var(--accent) 24%, transparent), transparent 55%),
    radial-gradient(90% 120% at 0% 100%, color-mix(in srgb, var(--vert) 14%, transparent), transparent 60%), var(--carte); }
.heros-texte { min-width: 0; }
.heros-titre { margin: 0; font-size: 1.1875rem; font-weight: 700; letter-spacing: -.01em; }
.heros-sous { margin: 4px 0 12px; color: var(--texte-2); font-size: .875rem; }
.heros-pied { margin: 6px 0 0; color: var(--texte-3); font-size: .75rem; font-weight: 500; }
.mini-barre { height: 6px; border-radius: 3px; background: var(--carte-2); overflow: hidden; }
.mini-barre div { height: 100%; border-radius: 3px; background: linear-gradient(90deg, var(--accent), var(--vert)); }
.radar-anime { position: relative; flex: none; width: 92px; height: 92px; border-radius: 50%;
  border: 1px solid color-mix(in srgb, var(--vert) 45%, transparent);
  background: radial-gradient(circle, color-mix(in srgb, var(--vert) 85%, white) 0 3px, transparent 4px),
    radial-gradient(circle, transparent 0 31%, color-mix(in srgb, var(--vert) 30%, transparent) 32% 33%, transparent 34% 64%, color-mix(in srgb, var(--vert) 30%, transparent) 65% 66%, transparent 67%); overflow: hidden; }
.radar-anime::after { content: ""; position: absolute; inset: 0; border-radius: 50%;
  background: conic-gradient(from 0deg, color-mix(in srgb, var(--vert) 55%, transparent), transparent 28%); animation: tourne 3.2s linear infinite; }
.radar-point { position: absolute; width: 6px; height: 6px; border-radius: 3px; background: var(--vert); box-shadow: 0 0 10px var(--vert); animation: clignote 3.2s ease-in-out infinite; }
.radar-point.p1 { top: 22%; left: 62%; } .radar-point.p2 { top: 64%; left: 26%; animation-delay: 1.1s; } .radar-point.p3 { top: 58%; left: 72%; animation-delay: 2.1s; background: var(--accent); box-shadow: 0 0 10px var(--accent); }
@keyframes clignote { 0%, 100% { opacity: .15; } 40% { opacity: 1; } }

/* Tuiles */
.tuiles { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 12px; }
.tuile { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: 14px; text-align: left;
  background: var(--carte); border: 1px solid var(--ligne); border-radius: var(--rayon); }
.tuile-valeur { font-size: 1.75rem; font-weight: 750; letter-spacing: -.02em; line-height: 1; font-variant-numeric: tabular-nums; }
.tuile-valeur small { font-size: 1rem; color: var(--texte-3); font-weight: 600; }
.tuile-label { font-size: .8125rem; color: var(--texte-2); font-weight: 500; }
.t-accent { color: var(--accent); } .t-vert { color: var(--vert); } .t-jaune { color: var(--jaune); } .t-bleu { color: var(--bleu); }

/* Catégories */
.grille-cat { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.cat { position: relative; display: flex; flex-direction: column; align-items: flex-start; gap: 10px; padding: 12px; text-align: left;
  background: var(--carte); border: 1px solid var(--ligne); border-radius: var(--rayon); min-width: 0; }
.cat-label { font-size: .8125rem; font-weight: 600; line-height: 1.2; }
.cat-nombre { position: absolute; top: 12px; right: 12px; color: var(--texte-3); font-size: .875rem; font-weight: 650; font-variant-numeric: tabular-nums; }

.pastille { flex: none; width: 36px; height: 36px; border-radius: 11px; display: inline-flex; align-items: center; justify-content: center; }
.pastille.petite { width: 30px; height: 30px; border-radius: 9px; color: #fff; }
.cat-compagnies { color: var(--bleu); background: color-mix(in srgb, var(--bleu) 16%, transparent); }
.cat-baleines { color: var(--cyan); background: color-mix(in srgb, var(--cyan) 16%, transparent); }
.cat-politiciens { color: var(--violet); background: color-mix(in srgb, var(--violet) 16%, transparent); }
.cat-militaire { color: var(--olive); background: color-mix(in srgb, var(--olive) 16%, transparent); }
.cat-gouvernement { color: var(--jaune); background: color-mix(in srgb, var(--jaune) 16%, transparent); }
.cat-canada { color: var(--rouge); background: color-mix(in srgb, var(--rouge) 16%, transparent); }
.fond-accent { background: var(--accent); } .fond-bleu { background: var(--bleu); } .fond-vert { background: var(--vert); }
.fond-jaune { background: var(--jaune); } .fond-compagnies { background: var(--bleu); } .fond-baleines { background: var(--cyan); }
.fond-politiciens { background: var(--violet); } .fond-militaire { background: var(--olive); } .fond-gouvernement { background: var(--jaune); }
.fond-canada { background: var(--rouge); }

/* Lignes d'infos */
.ligne { width: 100%; display: flex; align-items: center; gap: 12px; padding: 12px 14px; text-align: left; position: relative; }
.ligne + .ligne::before, .rangee + .rangee::before, .controle + .controle::before, .source + .source::before {
  content: ""; position: absolute; top: 0; right: 0; left: 62px; border-top: 1px solid var(--ligne); }
.rangee + .rangee::before, .controle + .controle::before { left: 16px; }
.ligne-centre { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 5px; }
.ligne-titre { font-size: .9375rem; font-weight: 600; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.ligne-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; color: var(--texte-2); font-size: .8125rem; }
.ligne-montant { font-weight: 600; color: var(--texte); font-variant-numeric: tabular-nums; }
.symbole { font: 650 .75rem/1 ui-monospace, "SF Mono", Menlo, monospace; letter-spacing: .02em; padding: 4px 6px; border-radius: 6px;
  background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent); }
.badge-icone { flex: none; width: 28px; height: 28px; border-radius: 14px; display: inline-flex; align-items: center; justify-content: center; }
.b-confirme { color: var(--vert); background: color-mix(in srgb, var(--vert) 15%, transparent); }
.b-officiel { color: var(--bleu); background: color-mix(in srgb, var(--bleu) 15%, transparent); }
.b-a_verifier { color: var(--jaune); background: color-mix(in srgb, var(--jaune) 15%, transparent); }
.badge { display: inline-flex; align-items: center; gap: 5px; padding: 4px 9px; border-radius: 999px; font-size: .75rem; font-weight: 700; }
.badge.grand { font-size: .875rem; padding: 6px 12px; }

/* Vide */
.vide { text-align: center; padding: 36px 20px; }
.vide-icone { display: inline-flex; width: 60px; height: 60px; border-radius: 30px; align-items: center; justify-content: center;
  color: var(--accent); background: color-mix(in srgb, var(--accent) 14%, transparent); margin-bottom: 10px; }
.vide-titre { margin: 0; font-weight: 700; font-size: 1.0625rem; }
.vide-texte { margin: 4px 0 0; color: var(--texte-2); font-size: .875rem; }
.avertissement { text-align: center; color: var(--texte-3); font-size: .75rem; margin: 28px 0 0; line-height: 1.6; }
.explication { color: var(--texte-2); font-size: .9375rem; margin: 4px 6px 4px; }

/* Recherche, puces, favoris */
.recherche { display: flex; align-items: center; gap: 8px; height: 42px; padding: 0 12px; margin: 4px 0 12px; border-radius: 12px;
  background: var(--carte-2); color: var(--texte-3); }
.recherche input { flex: 1; min-width: 0; border: none; outline: none; background: none; font-size: 1rem; }
.recherche input::placeholder, .ajout input::placeholder { color: var(--texte-3); text-transform: none; }
.recherche input::-webkit-search-cancel-button { display: none; }
.puces { display: flex; gap: 8px; overflow-x: auto; margin: 0 -16px; padding: 0 16px 4px; scrollbar-width: none; }
.puces::-webkit-scrollbar { display: none; }
.puce { flex: none; padding: 8px 14px; border-radius: 999px; font-size: .875rem; font-weight: 600; background: var(--carte-2); color: var(--texte-2); }
.puce.actif { background: var(--texte); color: var(--fond); }
.ajout { display: flex; gap: 8px; margin: 4px 0 12px; }
.ajout input { flex: 1; min-width: 0; height: 46px; padding: 0 14px; border-radius: 12px; border: 1px solid var(--ligne); background: var(--carte);
  font-size: 1rem; text-transform: uppercase; outline: none; }
.ajout input:focus { border-color: var(--accent); }
.favoris { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 4px; }
.favori { display: inline-flex; align-items: center; gap: 6px; padding: 6px 6px 6px 10px; border-radius: 999px; font: 650 .875rem ui-monospace, "SF Mono", Menlo, monospace;
  background: color-mix(in srgb, var(--jaune) 16%, transparent); color: var(--jaune); }
.favori button { width: 22px; height: 22px; border-radius: 11px; display: inline-flex; align-items: center; justify-content: center; background: color-mix(in srgb, var(--jaune) 22%, transparent); }

/* Boutons */
.bouton-principal { display: inline-flex; align-items: center; justify-content: center; gap: 8px; height: 46px; padding: 0 18px; border-radius: 13px;
  background: var(--accent); color: #fff; font-weight: 650; font-size: 1rem; }
.bouton-principal:disabled { opacity: .4; }
.bouton-principal.plein { width: calc(100% - 32px); margin: 0 16px 16px; }
.bouton-second { display: inline-flex; align-items: center; justify-content: center; gap: 8px; height: 46px; padding: 0 16px; border-radius: 13px;
  background: var(--carte-2); color: var(--texte); font-weight: 600; }

/* Réglages */
.groupe-pied { color: var(--texte-3); font-size: .8125rem; margin: 8px 16px 0; }
.rangee { position: relative; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 11px 16px; min-height: 52px; width: 100%; text-align: left; }
.rangee.bloc { flex-direction: column; align-items: stretch; gap: 10px; }
.rangee.bloc .rangee-droite, .rangee.bloc .segments { width: 100%; }
.rangee-gauche { display: flex; align-items: center; gap: 12px; min-width: 0; }
.rangee-label { font-size: 1rem; }
.rangee-droite { display: flex; align-items: center; gap: 6px; color: var(--texte-3); }
.rangee-valeur { color: var(--texte-2); font-size: .9375rem; }
.rangee-texte { color: var(--texte-2); font-size: .9375rem; }
.lien-rangee.danger .rangee-label { color: var(--rouge); }
.chevron { color: var(--texte-3); flex: none; }
.inter { position: relative; flex: none; width: 51px; height: 31px; border-radius: 16px; background: var(--inter-off); transition: background .2s; }
.inter span { position: absolute; top: 2px; left: 2px; width: 27px; height: 27px; border-radius: 14px; background: #fff; box-shadow: 0 2px 6px rgba(0,0,0,.3); transition: transform .22s cubic-bezier(.3,.7,.3,1); }
.inter.actif { background: var(--vert); }
.inter.actif span { transform: translateX(20px); }
.segments { display: flex; padding: 3px; border-radius: 11px; background: var(--carte-2); }
.segment { flex: 1; padding: 7px 6px; border-radius: 9px; font-size: .875rem; font-weight: 600; color: var(--texte-2); transition: background .18s, color .18s; white-space: nowrap; }
.segment.actif { background: var(--segment); color: var(--texte); box-shadow: 0 1px 4px rgba(0,0,0,.25); }
.couleurs { display: flex; gap: 10px; }
.couleur { width: 28px; height: 28px; border-radius: 14px; box-shadow: inset 0 0 0 1px rgba(255,255,255,.2); }
.couleur.actif { box-shadow: 0 0 0 2px var(--fond), 0 0 0 4px var(--texte); }

/* Sources */
.resume { display: flex; flex-wrap: wrap; gap: 8px; margin: 4px 2px 0; }
.pilule { display: inline-flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 999px; font-size: .8125rem; font-weight: 600; background: var(--carte-2); color: var(--texte-2); }
.point { flex: none; width: 9px; height: 9px; border-radius: 5px; background: var(--gris); }
.point.vert { background: var(--vert); } .point.jaune { background: var(--jaune); } .point.rouge { background: var(--rouge); } .point.bleu { background: var(--bleu); }
.source { position: relative; display: flex; align-items: center; gap: 12px; padding: 12px 16px; color: var(--texte); }
.source + .source::before { left: 37px; }
.source.ecartee { opacity: .55; }
.source-texte { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.source-nom { font-size: .9375rem; font-weight: 550; }
.source-etat { font-size: .8125rem; color: var(--texte-2); }
.mini-pilule { display: inline-block; margin-left: 6px; padding: 1px 7px; border-radius: 999px; font-size: .6875rem; font-weight: 600; background: var(--carte-2); color: var(--texte-2); vertical-align: 1px; }

/* Feuille (glisse du bas) */
.feuille-fond { position: fixed; inset: 0; z-index: 50; background: rgba(0,0,0,0); transition: background .26s ease; display: flex; align-items: flex-end; justify-content: center; }
.feuille-fond.ouvert { background: rgba(0,0,0,.55); }
.feuille { position: relative; width: 100%; max-width: 680px; max-height: 90vh; overflow-y: auto; -webkit-overflow-scrolling: touch;
  background: var(--fond-2); border-radius: 24px 24px 0 0; padding: 10px 20px calc(env(safe-area-inset-bottom) + 24px);
  transform: translateY(100%); transition: transform .3s cubic-bezier(.2,.8,.2,1); box-shadow: var(--ombre); }
.feuille-fond.ouvert .feuille { transform: none; }
.poignee { width: 38px; height: 5px; border-radius: 3px; background: var(--texte-3); opacity: .5; margin: 0 auto 10px; }
.feuille-fermer { position: absolute; top: 14px; right: 14px; width: 32px; height: 32px; border-radius: 16px; display: inline-flex; align-items: center; justify-content: center; background: var(--carte-2); color: var(--texte-2); }
.detail-haut { display: flex; align-items: center; gap: 8px; color: var(--texte-2); font-size: .875rem; font-weight: 500; padding-right: 40px; }
.detail-haut .pastille { width: 30px; height: 30px; border-radius: 9px; }
.point-sep { color: var(--texte-3); }
.detail-titre { font-size: 1.375rem; font-weight: 750; letter-spacing: -.015em; line-height: 1.25; margin: 14px 0 10px; }
.detail-badges { display: flex; gap: 8px; }
.detail-montant { font-size: 2rem; font-weight: 800; letter-spacing: -.02em; margin: 14px 0 0; font-variant-numeric: tabular-nums; }
.detail-symboles { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.symbole-grand { display: inline-flex; align-items: center; gap: 6px; padding: 8px 12px; border-radius: 12px; font: 700 .9375rem ui-monospace, "SF Mono", Menlo, monospace;
  background: var(--carte-2); color: var(--texte); }
.symbole-grand.suivi { background: color-mix(in srgb, var(--jaune) 18%, transparent); color: var(--jaune); }
.detail-entites { color: var(--texte-2); margin: 12px 0 0; font-size: .9375rem; }
.detail-note { display: flex; gap: 8px; align-items: flex-start; margin: 12px 0 0; padding: 10px 12px; border-radius: 12px; font-size: .875rem;
  background: color-mix(in srgb, var(--jaune) 14%, transparent); color: var(--jaune); }
.detail-actions { display: grid; grid-template-columns: 1fr auto; gap: 10px; margin-top: 20px; }
.detail-pied { color: var(--texte-3); font-size: .75rem; margin: 14px 4px 0; line-height: 1.6; word-break: break-all; }
.controle { position: relative; display: flex; align-items: center; gap: 10px; padding: 11px 16px; font-size: .9375rem; color: var(--texte); }
.controle svg:first-child { flex: none; }
.controle.ok svg:first-child { color: var(--vert); }
.controle.rate { color: var(--rouge); font-weight: 600; }
.etapes { list-style: none; padding: 0; margin: 6px 0 0; }
.etapes li { display: flex; align-items: center; gap: 12px; padding: 10px 0; font-size: 1rem; flex-wrap: wrap; }
.etape-num { flex: none; width: 28px; height: 28px; border-radius: 14px; display: inline-flex; align-items: center; justify-content: center; background: var(--accent); color: #fff; font-weight: 700; font-size: .875rem; }
.icone-inline { display: inline-flex; color: var(--accent); }

/* Barre d'onglets floue */
.onglets { position: fixed; z-index: 30; left: 0; right: 0; bottom: 0; display: flex; justify-content: center;
  padding: 6px 8px calc(env(safe-area-inset-bottom) + 4px); background: var(--barre);
  -webkit-backdrop-filter: saturate(180%) blur(20px); backdrop-filter: saturate(180%) blur(20px); border-top: 1px solid var(--ligne); }
.onglet { flex: 1; max-width: 140px; display: flex; flex-direction: column; align-items: center; gap: 3px; padding: 4px 0;
  color: var(--texte-3); font-size: .65625rem; font-weight: 600; min-height: 50px; transition: color .15s; }
.onglet.actif { color: var(--accent); }

/* Chargement */
.squelette { border-radius: var(--rayon); background: linear-gradient(90deg, var(--carte) 0%, var(--carte-2) 50%, var(--carte) 100%); background-size: 200% 100%; animation: brille 1.2s ease-in-out infinite; }
.heros-squelette { height: 130px; margin-top: 12px; border-radius: 22px; }
.tuile-squelette { height: 96px; }
@keyframes brille { from { background-position: 100% 0; } to { background-position: -100% 0; } }

@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }
`;

createRoot(document.getElementById("root")).render(<App />);

if ("serviceWorker" in navigator && location.protocol === "https:") {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
