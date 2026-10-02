// Radar : l'app iPhone. Elle lit les fichiers préparés par le robot (data/app/*.json).
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";

// Nom lisible de chaque source (vient de sources.json)
const NomsSources = createContext({});

const CATEGORIES = {
  compagnies: { label: "Compagnies", icone: "🏢" },
  baleines: { label: "Gros joueurs", icone: "🐋" },
  politiciens: { label: "Politiciens", icone: "🏛️" },
  militaire: { label: "Militaire", icone: "🎖️" },
  gouvernement: { label: "Gouvernement", icone: "📜" },
  canada: { label: "Canada", icone: "🍁" },
};

const BADGES = {
  confirme: { label: "Confirmé", icone: "✅✅", classe: "b-confirme" },
  officiel: { label: "Officiel", icone: "✅", classe: "b-officiel" },
  a_verifier: { label: "À vérifier", icone: "🟡", classe: "b-verifier" },
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

const COULEUR_STATUT = { ok: "vert", en_retard: "jaune", en_panne: "rouge", en_pause: "bleu", a_venir: "gris", ecartee: "gris" };
const ORDRE_STATUTS = ["ok", "en_retard", "en_panne", "en_pause", "a_venir", "ecartee"];
const LIBELLE_STATUT = { ok: "OK", en_retard: "En retard", en_panne: "En panne", en_pause: "En pause", a_venir: "À venir", ecartee: "Laissées de côté" };

const PHASES = [
  "Fondations et validation",
  "Compagnies et gros joueurs (SEC)",
  "Militaire (É.-U. et Canada)",
  "Politiciens",
  "Gouvernement et régulateurs",
  "Score, tableau de score, alertes",
];

const ONGLETS = [
  { id: "aujourdhui", label: "Aujourd'hui", icone: "⭐" },
  { id: "fil", label: "Fil", icone: "📰" },
  { id: "verifier", label: "À vérifier", icone: "🟡" },
  { id: "sources", label: "Sources", icone: "📡" },
];

// ---------- Outils ----------

function lireStockage(cle, defaut) {
  try {
    return localStorage.getItem(cle) ?? defaut;
  } catch {
    return defaut;
  }
}

function ecrireStockage(cle, valeur) {
  try {
    localStorage.setItem(cle, valeur);
  } catch {
    /* navigation privée : on ignore */
  }
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

function dateCourte(jour) {
  if (!jour) return "";
  const d = new Date(`${jour}T12:00:00`);
  return d.toLocaleDateString("fr-CA", { day: "numeric", month: "short", year: "numeric" });
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

// Les contrôles dans un ordre logique : ceux qu'on connaît d'abord, puis ceux propres à la source.
function controlesEnOrdre(checks) {
  const ordre = Object.keys(CONTROLES);
  const rang = (nom) => (ordre.includes(nom) ? ordre.indexOf(nom) : ordre.length);
  return Object.entries(checks || {}).sort(([a], [b]) => rang(a) - rang(b));
}

// Données vieilles : plus de 30 h un mardi-vendredi, ou plus de 80 h n'importe quand (fin de semaine).
function donneesVieilles(genereA) {
  if (!genereA) return false;
  const heures = (Date.now() - new Date(genereA).getTime()) / 3600000;
  const jour = new Date().getDay();
  return heures > 80 || (jour >= 2 && jour <= 5 && heures > 30);
}

// ---------- Chargement ----------

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
  }, [charger]);
  return { ...etat, charger };
}

// ---------- Morceaux ----------

function Badge({ code }) {
  const b = BADGES[code] || BADGES.a_verifier;
  return (
    <span className={`badge ${b.classe}`}>
      {b.icone} {b.label}
    </span>
  );
}

function Categorie({ code }) {
  const c = CATEGORIES[code];
  if (!c) return null;
  return (
    <span className="chip">
      {c.icone} {c.label}
    </span>
  );
}

function CarteEvenement({ ev, controlesOuverts = false }) {
  const noms = useContext(NomsSources);
  const [ouvert, setOuvert] = useState(controlesOuverts);
  const rates = Object.entries(ev.checks || {}).filter(([, ok]) => !ok);
  const m = montant(ev);
  return (
    <article className="carte">
      <div className="ligne-haut">
        <Badge code={ev.badge} />
        <Categorie code={ev.category} />
        <span className="date">{dateCourte(ev.published_on)}</span>
      </div>
      <h3 className="titre">{ev.title}</h3>
      {(ev.tickers?.length > 0 || m) && (
        <div className="ligne-infos">
          {ev.tickers?.map((t) => (
            <span key={t} className="symbole">
              {t}
            </span>
          ))}
          {m && <span className="montant">{m}</span>}
        </div>
      )}
      {ev.entities?.length > 0 && <p className="discret">{ev.entities.join(" · ")}</p>}
      {ev.notes?.map((n) => (
        <p key={n} className="note">
          ⚠️ {n}
        </p>
      ))}
      <div className="actions">
        <a href={ev.official_url} target="_blank" rel="noopener noreferrer">
          Document officiel ↗
        </a>
        <button type="button" className="lien" onClick={() => setOuvert(!ouvert)} aria-expanded={ouvert}>
          {ouvert ? "Cacher les contrôles" : rates.length ? `${rates.length} contrôle(s) raté(s)` : "Pourquoi ce badge ?"}
        </button>
      </div>
      {ouvert && (
        <ul className="controles">
          {controlesEnOrdre(ev.checks).map(([nom, ok]) => (
            <li key={nom} className={ok ? "ok" : "rate"}>
              {ok ? "✓" : "✗"} {CONTROLES[nom] || nom.replaceAll("_", " ")}
            </li>
          ))}
          {ev.confirmations?.map((c) => (
            <li key={c.official_url} className="ok">
              ✓ Confirmé par{" "}
              <a href={c.official_url} target="_blank" rel="noopener noreferrer">
                {noms[c.source] || c.source} ↗
              </a>
            </li>
          ))}
          <li className="discret">Lu {ilYa(ev.collected_at)} · empreinte {ev.sha256?.slice(0, 12)}…</li>
        </ul>
      )}
    </article>
  );
}

function Vide({ titre, texte }) {
  return (
    <div className="vide">
      <p className="vide-titre">{titre}</p>
      <p className="discret">{texte}</p>
    </div>
  );
}

// ---------- Écrans ----------

function Aujourdhui({ meta, aujourdhui }) {
  const { top = [], eviter = [], note } = aujourdhui || {};
  const pourcentage = meta.sources_total ? Math.round((meta.sources_branchees / meta.sources_total) * 100) : 0;
  return (
    <section>
      {top.length === 0 ? (
        <div className="carte heros">
          <p className="vide-titre">Pas encore de suggestions</p>
          <p className="discret">{note}</p>
        </div>
      ) : (
        <>
          <h2 className="section">À regarder</h2>
          {top.map((ev) => (
            <CarteEvenement key={ev.id} ev={ev} />
          ))}
          <h2 className="section">À éviter</h2>
          {eviter.map((ev) => (
            <CarteEvenement key={ev.id} ev={ev} />
          ))}
        </>
      )}

      <h2 className="section">Avancement</h2>
      <div className="carte">
        <div className="progres-texte">
          <span>Sources branchées</span>
          <strong>
            {meta.sources_branchees} / {meta.sources_total}
          </strong>
        </div>
        <div className="barre" role="progressbar" aria-valuenow={pourcentage} aria-valuemin={0} aria-valuemax={100}>
          <div style={{ width: `${Math.max(pourcentage, 2)}%` }} />
        </div>
        <ol className="phases">
          {PHASES.map((nom, i) => (
            <li key={nom} className={i < meta.phase ? "fait" : i === meta.phase ? "encours" : ""}>
              <span className="phase-num">{i < meta.phase ? "✓" : i}</span>
              {nom}
              {i === meta.phase && <span className="pill p-bleu">en cours</span>}
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Fil({ fil }) {
  const [filtre, setFiltre] = useState("tout");
  const liste = useMemo(() => (filtre === "tout" ? fil : fil.filter((e) => e.category === filtre)), [fil, filtre]);
  return (
    <section>
      <div className="filtres" role="tablist" aria-label="Catégories">
        {[["tout", "Tout"], ...Object.entries(CATEGORIES).map(([k, c]) => [k, `${c.icone} ${c.label}`])].map(([k, label]) => (
          <button key={k} type="button" className={filtre === k ? "filtre actif" : "filtre"} onClick={() => setFiltre(k)}>
            {label}
          </button>
        ))}
      </div>
      {liste.length === 0 ? (
        <Vide titre="Rien pour l'instant" texte="Les premières infos arrivent avec la phase 1 (SEC)." />
      ) : (
        liste.map((ev) => <CarteEvenement key={ev.id} ev={ev} />)
      )}
    </section>
  );
}

function AVerifier({ liste }) {
  return (
    <section>
      <p className="explication">
        Ces infos ont raté au moins un contrôle automatique. Elles n'entrent <strong>jamais</strong> dans les suggestions.
      </p>
      {liste.length === 0 ? (
        <Vide titre="Aucune info à vérifier" texte="Tout ce qui a été lu a passé les contrôles." />
      ) : (
        liste.map((ev) => <CarteEvenement key={ev.id} ev={ev} controlesOuverts />)
      )}
    </section>
  );
}

function Sources({ sources }) {
  const parStatut = useMemo(() => {
    const compte = {};
    for (const s of sources) compte[s.statut] = (compte[s.statut] || 0) + 1;
    return compte;
  }, [sources]);
  const groupes = useMemo(() => {
    const g = {};
    for (const s of sources) (g[s.categorie] ||= []).push(s);
    return g;
  }, [sources]);
  return (
    <section>
      <div className="resume-statuts">
        {ORDRE_STATUTS.filter((s) => parStatut[s]).map((s) => (
          <span key={s} className={`pill p-${COULEUR_STATUT[s]}`}>
            {LIBELLE_STATUT[s]} : {parStatut[s]}
          </span>
        ))}
      </div>
      {Object.entries(CATEGORIES).map(([cat, c]) =>
        groupes[cat] ? (
          <div key={cat}>
            <h2 className="section">
              {c.icone} {c.label}
            </h2>
            <ul className="carte liste-sources">
              {groupes[cat].map((s) => (
                <li key={s.id} className={s.statut === "ecartee" ? "source ecartee" : "source"}>
                  <span className={`point point-${COULEUR_STATUT[s.statut]}`} aria-hidden="true" />
                  <div className="source-texte">
                    <div className="source-nom">
                      {s.nom}
                      {!s.officielle && <span className="pill p-gris">non officielle</span>}
                    </div>
                    <div className="discret">
                      {s.libelle}
                      {s.dernier_succes ? ` · lue ${ilYa(s.dernier_succes)}` : ""}
                      {s.explication ? ` · ${s.explication}` : ""}
                    </div>
                  </div>
                  <a className="source-lien" href={s.site} target="_blank" rel="noopener noreferrer" aria-label={`Site officiel : ${s.nom}`}>
                    ↗
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ) : null,
      )}
    </section>
  );
}

// ---------- App ----------

function App() {
  const { chargement, erreur, donnees, charger } = useDonnees();
  const [onglet, setOnglet] = useState(() => lireStockage("radar-onglet", "aujourdhui"));
  const choisir = (id) => {
    setOnglet(id);
    ecrireStockage("radar-onglet", id);
    window.scrollTo(0, 0);
  };

  const meta = donnees?.meta;
  const vieilles = donneesVieilles(meta?.genere_a);
  const noms = useMemo(() => Object.fromEntries((donnees?.sources || []).map((s) => [s.id, s.nom])), [donnees]);

  return (
    <div className="app">
      <style>{CSS}</style>
      <header className="entete">
        <div>
          <h1>Radar</h1>
          <p className="discret">{meta ? `Mis à jour ${ilYa(meta.genere_a)}` : "Chargement…"}</p>
        </div>
        <button type="button" className="actualiser" onClick={charger} disabled={chargement} aria-label="Actualiser">
          {chargement ? "…" : "↻"}
        </button>
      </header>

      {vieilles && (
        <div className="alerte" role="alert">
          ⚠️ Données vieilles ({ilYa(meta.genere_a)}) : le robot n'a pas roulé. Ne te fie pas aux infos récentes.
        </div>
      )}
      {erreur && (
        <div className="alerte" role="alert">
          Impossible de charger les données ({erreur}).{" "}
          <button type="button" className="lien" onClick={charger}>
            Réessayer
          </button>
        </div>
      )}

      <NomsSources.Provider value={noms}>
        <main>
          {donnees && onglet === "aujourdhui" && <Aujourdhui meta={donnees.meta} aujourdhui={donnees.aujourdhui} />}
          {donnees && onglet === "fil" && <Fil fil={donnees.fil} />}
          {donnees && onglet === "verifier" && <AVerifier liste={donnees.a_verifier} />}
          {donnees && onglet === "sources" && <Sources sources={donnees.sources} />}
        </main>
      </NomsSources.Provider>

      <nav className="onglets" aria-label="Navigation">
        {ONGLETS.map((o) => (
          <button
            key={o.id}
            type="button"
            className={onglet === o.id ? "onglet actif" : "onglet"}
            onClick={() => choisir(o.id)}
            aria-current={onglet === o.id ? "page" : undefined}
          >
            <span className="onglet-icone" aria-hidden="true">
              {o.icone}
            </span>
            {o.label}
            {o.id === "verifier" && donnees?.a_verifier?.length > 0 && <span className="compteur">{donnees.a_verifier.length}</span>}
          </button>
        ))}
      </nav>
    </div>
  );
}

const CSS = `
:root {
  --fond: #f6f7f9; --carte: #ffffff; --texte: #111827; --discret: #6b7280; --bord: #e5e7eb; --accent: #2563eb;
  --vert: #16a34a; --jaune: #b45309; --rouge: #dc2626; --bleu: #2563eb; --gris: #9ca3af;
  --t-vert: #dcfce7; --t-jaune: #fef3c7; --t-rouge: #fee2e2; --t-bleu: #dbeafe; --t-gris: #f3f4f6;
  color-scheme: light dark;
}
@media (prefers-color-scheme: dark) {
  :root {
    --fond: #0e1116; --carte: #161b22; --texte: #e6edf3; --discret: #8b949e; --bord: #30363d; --accent: #58a6ff;
    --vert: #3fb950; --jaune: #d29922; --rouge: #f85149; --bleu: #58a6ff; --gris: #6e7681;
    --t-vert: #12261a; --t-jaune: #2b2111; --t-rouge: #2d1416; --t-bleu: #102236; --t-gris: #21262d;
  }
}
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--fond); color: var(--texte);
  font: 16px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; -webkit-text-size-adjust: 100%; }
a { color: var(--accent); text-decoration: none; }
button { font: inherit; color: inherit; }
.app { max-width: 640px; margin: 0 auto; padding: calc(env(safe-area-inset-top) + 8px) 16px calc(env(safe-area-inset-bottom) + 84px); }
.entete { display: flex; align-items: center; justify-content: space-between; padding: 8px 0 12px; }
.entete h1 { margin: 0; font-size: 28px; letter-spacing: -0.02em; }
.entete p { margin: 0; }
.actualiser { width: 44px; height: 44px; border-radius: 22px; border: 1px solid var(--bord); background: var(--carte); font-size: 20px; }
.discret { color: var(--discret); font-size: 14px; margin: 4px 0 0; }
.section { font-size: 13px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--discret); margin: 24px 4px 8px; }
.carte { background: var(--carte); border: 1px solid var(--bord); border-radius: 14px; padding: 14px; margin: 0 0 10px; }
.heros { text-align: center; padding: 24px 16px; }
.vide { text-align: center; padding: 40px 16px; }
.vide-titre { font-weight: 600; font-size: 17px; margin: 0; }
.explication { font-size: 15px; color: var(--discret); margin: 0 4px 12px; }
.alerte { background: var(--t-jaune); color: var(--texte); border: 1px solid var(--jaune); border-radius: 12px; padding: 10px 12px; margin-bottom: 12px; font-size: 14px; }
.ligne-haut { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.date { margin-left: auto; color: var(--discret); font-size: 13px; }
.titre { font-size: 16px; margin: 8px 0 4px; line-height: 1.35; }
.badge, .chip, .pill { display: inline-flex; align-items: center; gap: 4px; border-radius: 999px; padding: 2px 9px; font-size: 12.5px; font-weight: 600; white-space: nowrap; }
.chip { background: var(--t-gris); color: var(--discret); font-weight: 500; }
.b-confirme { background: var(--t-vert); color: var(--vert); }
.b-officiel { background: var(--t-bleu); color: var(--bleu); }
.b-verifier { background: var(--t-jaune); color: var(--jaune); }
.p-vert { background: var(--t-vert); color: var(--vert); } .p-jaune { background: var(--t-jaune); color: var(--jaune); }
.p-rouge { background: var(--t-rouge); color: var(--rouge); } .p-bleu { background: var(--t-bleu); color: var(--bleu); }
.p-gris { background: var(--t-gris); color: var(--discret); font-weight: 500; }
.ligne-infos { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin: 6px 0; }
.symbole { font: 600 13px ui-monospace, SFMono-Regular, Menlo, monospace; background: var(--t-bleu); color: var(--bleu); padding: 2px 7px; border-radius: 6px; }
.montant { font-weight: 600; font-size: 14px; }
.note { font-size: 13.5px; margin: 6px 0 0; }
.actions { display: flex; justify-content: space-between; gap: 12px; margin-top: 10px; font-size: 14.5px; }
.lien { background: none; border: none; padding: 0; color: var(--accent); cursor: pointer; }
.controles { list-style: none; margin: 10px 0 0; padding: 10px 0 0; border-top: 1px solid var(--bord); font-size: 14px; }
.controles li { padding: 3px 0; }
.controles .ok { color: var(--vert); } .controles .rate { color: var(--rouge); font-weight: 600; }
.progres-texte { display: flex; justify-content: space-between; font-size: 15px; }
.barre { height: 8px; border-radius: 4px; background: var(--t-gris); margin: 8px 0 14px; overflow: hidden; }
.barre div { height: 100%; background: var(--accent); border-radius: 4px; }
.phases { list-style: none; margin: 0; padding: 0; }
.phases li { display: flex; align-items: center; gap: 10px; padding: 7px 0; color: var(--discret); font-size: 15px; }
.phases li.encours { color: var(--texte); font-weight: 600; }
.phases li.fait { color: var(--vert); }
.phase-num { width: 24px; height: 24px; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center; background: var(--t-gris); font-size: 13px; flex: none; }
.phases li.encours .phase-num { background: var(--accent); color: #fff; }
.phases li.fait .phase-num { background: var(--t-vert); }
.filtres { display: flex; gap: 8px; overflow-x: auto; padding: 2px 2px 12px; margin: 0 -16px; padding-left: 16px; padding-right: 16px; scrollbar-width: none; }
.filtres::-webkit-scrollbar { display: none; }
.filtre { flex: none; border: 1px solid var(--bord); background: var(--carte); border-radius: 999px; padding: 8px 14px; font-size: 14px; min-height: 40px; }
.filtre.actif { background: var(--texte); color: var(--fond); border-color: var(--texte); }
.resume-statuts { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 4px; }
.liste-sources { list-style: none; padding: 4px 14px; }
.source { display: flex; align-items: flex-start; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--bord); }
.source:last-child { border-bottom: none; }
.source.ecartee { opacity: 0.6; }
.source-texte { flex: 1; min-width: 0; }
.source-nom { font-size: 15px; font-weight: 500; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.source-lien { padding: 4px 6px; font-size: 18px; }
.point { width: 10px; height: 10px; border-radius: 5px; margin-top: 6px; flex: none; }
.point-vert { background: var(--vert); } .point-jaune { background: var(--jaune); } .point-rouge { background: var(--rouge); }
.point-bleu { background: var(--bleu); } .point-gris { background: var(--gris); }
.onglets { position: fixed; left: 0; right: 0; bottom: 0; display: flex; justify-content: center; background: var(--carte);
  border-top: 1px solid var(--bord); padding: 6px 8px calc(env(safe-area-inset-bottom) + 6px); }
.onglet { flex: 1; max-width: 160px; display: flex; flex-direction: column; align-items: center; gap: 2px; background: none; border: none;
  color: var(--discret); font-size: 11.5px; padding: 4px 0; min-height: 48px; position: relative; }
.onglet.actif { color: var(--accent); font-weight: 600; }
.onglet-icone { font-size: 20px; line-height: 1.1; }
.compteur { position: absolute; top: 0; right: calc(50% - 22px); background: var(--rouge); color: #fff; border-radius: 9px; font-size: 10.5px; padding: 0 5px; min-width: 18px; }
`;

createRoot(document.getElementById("root")).render(<App />);
