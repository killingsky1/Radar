// Radar : l'app iPhone. Elle lit les fichiers préparés par le robot (data/app/*.json).
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";

const VERSION = "0.27.1";

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

// Contrôles propres à chaque source (le nom technique vient du robot).
const CONTROLES_SOURCES = {
  code_achat_ou_vente_reel: "Vrai achat ou vraie vente (code P ou S)",
  prix_et_actions_positifs: "Prix et nombre d'actions positifs",
  symbole_conforme_sec: "Symbole conforme à la liste SEC",
  montant_recalcule: "Montant recalculé",
  dates_transaction_valides: "Dates des transactions valides",
  prix_plausible: "Prix plausible",
  montant_plausible: "Montant plausible",
  items_officiels_reconnus: "Points officiels du 8-K reconnus",
  type_8k: "Vrai formulaire 8-K",
  pourcentage_valide: "Pourcentage valide",
  emetteur_coherent: "Compagnie visée cohérente",
  numero_officiel: "Numéro officiel du Registre",
  lien_du_meme_document: "Lien vers le même document",
  texte_du_meme_document: "Texte lu du même document",
  non_retire: "Pas retiré avant sa parution",
  acheteur_lu: "Pays acheteur lu",
  lien_identique_au_fil: "Lien identique au fil officiel",
  ministere_reconnu: "Ministère reconnu",
  type_communique: "Communiqué officiel",
  lien_ministere_coherent: "Lien d'une page de nouvelles",
  lecture_complete: "Document lu au complet",
  recoupements_index_document: "Index et document concordent",
  montants_officiels: "Fourchettes de montants officielles",
  dates_transactions_valides: "Dates des transactions valides",
  symbole_cote_sec: "Action cotée (liste SEC)",
  nom_coherent_avec_symbole: "Nom cohérent avec le symbole",
  lien_d_une_action_presidentielle: "Lien d'une action présidentielle",
  categorie_officielle_reconnue: "Catégorie officielle reconnue",
  texte_officiel_lu: "Texte officiel lu",
  decision_lue: "Décision lue dans le communiqué",
  fourchette_plausible: "Fourchette de taux plausible",
  vote_lu: "Vote lu",
  taux_plausible: "Taux plausible",
  titre_officiel_concorde: "Le titre officiel dit la même chose",
  actions_et_valeur_positives: "Actions et valeur positives",
  prix_implicite_plausible: "Prix par action plausible",
  forme_reconnue: "Formulaire officiel reconnu",
  acheteur_different_de_la_cible: "L'acheteur n'est pas la compagnie visée",
  marche_attendu: "Bon marché (code officiel)",
  positions_coherentes: "Positions cohérentes",
  variation_coherente: "Variation cohérente",
  approbation_originale: "Approbation originale (pas un générique)",
  nouvelle_molecule: "Nouvelle molécule (classe 1 dans la base de la FDA)",
  projet_suivi: "Bon projet de loi (H.R. 7008, 119e Congrès)",
  etape_datee: "Étape officielle datée",
  vote_du_projet_suivi: "Vote sur le bon projet de loi",
  total_recompte: "Total officiel = votes recomptés un par un",
  sans_formulaire_201: "Publié sans formulaire 201 (lien direct de l'OGE)",
  poste_publie_sans_201: "Président, vice-président ou poste de niveau I ou II",
  document_pdf: "Document PDF officiel",
  declarant_concorde: "Nom du déclarant = index de l'OGE",
  type_reconnu: "Type reconnu (achat, vente, échange)",
  resultat_officiel_connu: "Résultat officiel connu (note du rapport du Bureau)",
  dates_dans_l_ordre: "Dates dans l'ordre (début, puis conclusion)",
  industrie_scian: "Code d'industrie SCIAN valide",
  date_d_inscription_valide: "Date d'inscription valide",
  chaque_inscription_nommee: "Chaque inscription a un nom",
  regime_lu: "Régime de sanctions lu",
  indicateur_de_la_liste_officielle: "Grand indicateur de la liste officielle de Statistique Canada",
  lien_du_quotidien: "Lien du Quotidien (statcan.gc.ca)",
  resume_lu: "Résumé officiel lu",
  numero_dors_ou_tr: "Numéro officiel (DORS ou TR) identique au lien",
  loi_liee_a_l_argent: "Loi liée à l'argent (liste fixe)",
  titre_officiel_lu: "Titre officiel lu sur la page du texte",
  meme_numero_que_l_index: "Même numéro que l'index de la Gazette",
  date_d_enregistrement_lue: "Date d'enregistrement lue",
  projet_nomme: "Projet nommé",
  page_du_bureau_des_grands_projets: "Page du Bureau des grands projets",
  loi_visant_a_batir_le_canada: "Loi visant à bâtir le Canada",
  lien_de_la_gazette: "Lien de la Gazette du Canada",
  texte_officiel_de_l_avis: "Texte officiel de l'avis lu (inscription à l'annexe 1)",
  projet_du_gouvernement: "Projet de loi du gouvernement",
  sanction_confirmee: "Sanction royale confirmée",
  lien_legisinfo: "Lien LEGISinfo",
  nouvelle_substance_active: "Nouvelle substance active (NSA ou Priorité-NSA)",
  avis_actif: "Avis de conformité actif",
  marque_et_ingredient_lus: "Marque et ingrédient lus",
  fiches_du_meme_avis: "Fiches du même avis (marque, ingrédient)",
  seuil_de_10_millions: "10 M$ et plus (nouveau contrat ou hausse)",
  valeurs_lues: "Valeurs du contrat lues",
  type_d_instrument_connu: "Type connu (contrat, modification, commande)",
  trimestre_declare_valide: "Trimestre déclaré valide",
  lien_de_la_fiche_du_contrat: "Lien de la fiche publique du contrat",
  periode_lue: "Période du rapport lue",
  meme_periode_que_le_lien: "Même période que le lien de la page des rapports",
  lignes_lues: "Chaque ligne lue (exportateur, destination, description)",
  fourchettes_reconnues: "Fourchettes de montants reconnues",
  resultats_publies: "Résultats officiels publiés",
  parts_qui_s_additionnent: "Les 3 catégories d'acheteurs font le total",
  obligation_du_tresor: "Obligation du Trésor (pas un bon de moins d'un an)",
  resultat_officiel_du_jour: "Résultat officiel du jour de l'adjudication",
  mois_publie: "Mois publié",
  solde_egal_depenses_moins_recettes: "Solde = dépenses moins recettes",
  cumul_de_l_exercice_lu: "Cumul de l'exercice lu",
  numero_csms: "Numéro du message de la douane (CSMS)",
  lien_du_message: "Lien du message officiel",
  sujet_surtaxes: "Surtaxes ou interdiction d'importation",
  date_d_envoi_lue: "Date d'envoi lue",
  seuil_de_100_millions: "100 M$ et plus engagés",
  contrat_federal: "Contrat fédéral (pas une subvention ni un prêt)",
  date_de_signature_lue: "Date de signature lue",
  fournisseur_lu: "Fournisseur lu",
  extrait_officiel: "Extrait exact du dépôt officiel",
  gouvernement_nomme: "Gouvernement américain nommé dans l'extrait",
  titre_de_propriete: "Actions ou bons de souscription dans l'extrait",
  point_8k_retenu: "Point du 8-K lu (1.01, 3.02 ou 8.01)",
  entree_en_bourse: "Vraie entrée en bourse (pas un SPAC ni une inscription directe)",
  date_du_prospectus_prouvee: "Date du prospectus écrite dans le document",
  une_seule_duree: "Une seule durée de blocage, dans la phrase citée",
  fin_calculee: "Fin = date du prospectus + durée",
  sans_levee_anticipee: "Aucune levée anticipée mentionnée",
  compagnie_cotee: "Compagnie cotée en bourse",
  formule_d_autorisation: "Formule d'autorisation lue (nouveau programme, hausse ou nouveau total)",
  conseil_nomme: "Conseil d'administration nommé dans la phrase",
  meme_montant_partout: "Même plafond partout dans le dépôt",
  point_8k_des_rachats: "Point du 8-K lu (2.02, 7.01 ou 8.01)",
  rachat_de_10_millions_et_plus: "10 M$ et plus (ou un nombre d'actions)",
  pas_deja_annonce: "Pas déjà annoncé dans ses 8-K des 90 jours avant",
  lettre_officielle: "Lettre d'approbation officielle",
  trimestres_consecutifs: "Trimestres consécutifs comparés",
  rapports_complets: "Deux rapports complets comparés",
  variation_recalculee: "Variation recalculée",
  part_du_portefeuille_coherente: "Montant cohérent avec le portefeuille",
  numero_de_rappel_officiel: "Numéro de rappel officiel",
  nombre_plausible: "Nombre de véhicules plausible",
  lien_du_meme_rappel: "Lien vers le même rappel",
  communique_officiel: "Communiqué officiel",
  document_officiel_sec: "Document officiel de la SEC",
  action_officielle: "Action officielle de l'OFAC",
  date_de_l_adresse_concorde: "Date de l'adresse officielle concorde",
  liste_sdn_lue: "Liste des sanctions lue",
  titre_et_liste_concordent: "Le titre et la liste concordent",
  numero_de_transaction_officiel: "Numéro de transaction officiel",
  feu_vert_accorde: "Feu vert accordé",
  parties_lues: "Parties lues",
};

// Qui détient l'actif, selon les codes officiels du Congrès.
const PROPRIETAIRES = {
  "": "l'élu·e",
  Self: "l'élu·e",
  SP: "conjoint·e",
  Spouse: "conjoint·e",
  JT: "compte conjoint",
  Joint: "compte conjoint",
  DC: "enfant à charge",
  Child: "enfant à charge",
};

const STATUTS = {
  ok: { label: "OK", couleur: "vert" },
  en_retard: { label: "En retard", couleur: "jaune" },
  en_panne: { label: "En panne", couleur: "rouge" },
  en_pause: { label: "En pause", couleur: "bleu" },
};

// Les sources affichées : celles qui servent. Une source laissée de côté, refusée par son site ou pas encore branchée
// reste dans les données du robot mais n'est pas montrée ; si elle revient (ex. un site qui accepte de nouveau), elle
// réapparaît toute seule. Les alertes en direct (en retard, en panne, en pause) restent montrées.
const CACHES = ["ecartee", "refusee", "a_venir"];
const sourcesAffichees = (sources) => (sources || []).filter((s) => !CACHES.includes(s.statut));
// Actives = celles qui lisent (OK ou en retard) ; une source en panne ou en pause fait baisser le compte.
const compteSources = (sources) => {
  const vues = sourcesAffichees(sources);
  return { total: vues.length, actives: vues.filter((s) => s.statut === "ok" || s.statut === "en_retard").length };
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
  calendrier: (
    <>
      <rect x="3.5" y="5" width="17" height="15.5" rx="2.5" />
      <path d="M3.5 10h17M8 3v4M16 3v4M8 14h2M14 14h2M8 17h2" />
    </>
  ),
  billet: (
    <>
      <rect x="2.5" y="6" width="19" height="12" rx="2.5" />
      <circle cx="12" cy="12" r="2.6" />
      <path d="M6 9.5v5M18 9.5v5" />
    </>
  ),
  "fleche-haut": <path d="M12 19V5M6 11l6-6 6 6" />,
  "fleche-bas": <path d="M12 5v14M6 13l6 6 6-6" />,
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

function dateCourte(jour) {
  if (!jour) return "";
  return new Date(`${jour}T12:00:00`).toLocaleDateString("fr-CA", { day: "numeric", month: "short" });
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
  // Fourchette ouverte (ex. « Over $50,000,000 » chez les élus) : seul le minimum est connu.
  if (haut == null) return `plus de ${argent(bas - 1, currency)}`;
  if (bas != null && haut != null && bas !== haut) return `${argent(bas, currency)} à ${argent(haut, currency)}`;
  return argent(bas ?? haut, currency);
}

// « $15,001 - $50,000 » (texte officiel) → « 15 001 $ US à 50 000 $ US ». Autre format : le texte officiel tel quel.
function fourchette(texte) {
  const n = (texte || "").match(/\$[\d,]+/g)?.map((x) => Number(x.replace(/[$,]/g, "")));
  if (!n?.length) return texte || "";
  if (/^Over/i.test(texte) || n.length === 1) return `plus de ${argent(n[0], "USD")}`;
  return `${argent(n[0], "USD")} à ${argent(n[1], "USD")}`;
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
const FICHIERS_OPTIONNELS = ["elus", "lobbying", "calendrier", "resultats", "rachats", "sante"]; // absents ou illisibles : l'app fonctionne sans

function useDonnees() {
  const [etat, setEtat] = useState({ chargement: true, erreur: null, donnees: null });
  const charger = useCallback(async () => {
    setEtat((e) => ({ ...e, chargement: true, erreur: null }));
    try {
      const resultats = await Promise.all([
        ...FICHIERS.map(async (nom) => {
          const r = await fetch(`./data/app/${nom}.json`, { cache: "no-store" });
          if (!r.ok) throw new Error(`${nom}.json : HTTP ${r.status}`);
          return [nom, await r.json()];
        }),
        ...FICHIERS_OPTIONNELS.map(async (nom) => {
          try {
            const r = await fetch(`./data/app/${nom}.json`, { cache: "no-store" });
            return [nom, r.ok ? await r.json() : null];
          } catch {
            return [nom, null];
          }
        }),
      ]);
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

// ---------- Animations (le réglage iPhone « Réduire les animations » les coupe) ----------

function animationsReduites() {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Un nombre qui défile de 0 à sa valeur (0,65 s). data-final="1" quand il a fini (les tests attendent ce moment).
function useDefile(cible, duree = 650) {
  const reduit = animationsReduites();
  const [etat, setEtat] = useState({ v: reduit ? cible : 0, fini: reduit });
  useEffect(() => {
    if (reduit || typeof cible !== "number" || !Number.isFinite(cible)) {
      setEtat({ v: cible, fini: true });
      return undefined;
    }
    let image;
    let debut;
    const pas = (t) => {
      debut ??= t;
      const k = Math.min((t - debut) / duree, 1);
      if (k < 1) {
        setEtat({ v: cible * (1 - (1 - k) ** 3), fini: false });
        image = requestAnimationFrame(pas);
      } else setEtat({ v: cible, fini: true });
    };
    image = requestAnimationFrame(pas);
    return () => cancelAnimationFrame(image);
  }, [cible, duree, reduit]);
  return [etat.v, etat.fini];
}

function Defile({ valeur, format = (n) => nombre(n), className }) {
  const [v, fini] = useDefile(valeur);
  return (
    <span className={className} data-defile="" data-final={fini ? "1" : "0"}>
      {format(v)}
    </span>
  );
}

// La note sur 10 dans un anneau qui se remplit ; le chiffre défile.
function AnneauNote({ valeur, baisse }) {
  const r = 52;
  const tour = 2 * Math.PI * r;
  const reste = tour * (1 - Math.min(Math.max(valeur ?? 5, 0), 10) / 10);
  return (
    <div className="anneau" role="img" aria-label={`Note ${note(valeur)} sur 10`}>
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <circle className="anneau-fond" cx="60" cy="60" r={r} />
        <circle className={baisse ? "anneau-valeur baisse" : "anneau-valeur hausse"} cx="60" cy="60" r={r} style={{ "--tour": tour, "--reste": reste }} />
      </svg>
      <span className="anneau-texte fiche-score">
        <Defile valeur={valeur} format={note} className="fiche-score-chiffre" />
        <small>/10</small>
      </span>
    </div>
  );
}

// Le radar de l'accueil : les compagnies à la hausse (7/10 et plus). Plus près du centre = note plus haute.
// Les baisses n'y sont pas : elles ont leur carte « à surveiller à la baisse », juste en dessous (une note basse près du
// centre se lisait à l'envers). Symbole écrit à côté ; toucher un point ouvre la fiche.
// Angles : pas de 360/n, avec un saut pour que deux rangs qui se suivent ne soient pas voisins (étiquettes lisibles).
const TOUR_RADAR = 4; // secondes par tour du balayage

function pgcd(a, b) {
  return b ? pgcd(b, a % b) : a;
}

function RadarSuggestions({ hausse }) {
  const { ouvrirCompagnie } = useApp();
  const points = hausse.slice(0, 8);
  const n = points.length;
  const noteDe = (s) => s.note10 ?? 5;
  const niveaux = [...new Set(points.map(noteDe))].sort((a, b) => b - a); // de la plus haute à la plus basse
  let saut = Math.max(1, Math.round(n / 3));
  while (n > 1 && pgcd(saut, n) !== 1) saut += 1;
  return (
    <div className="carte radar-carte">
      <div className="radar" role="group" aria-label={`Radar : ${n} compagnies à la hausse. Plus près du centre, note plus haute.`}>
        <svg className="radar-grille" viewBox="0 0 100 100" aria-hidden="true">
          {[12.5, 25, 37.5, 49.5].map((r) => (
            <circle key={r} cx="50" cy="50" r={r} />
          ))}
          <path d="M50 .5V99.5M.5 50H99.5" />
        </svg>
        {/* Le balayage tourne : en diagonale, sa boîte dépasse le cercle (et l'écran : la page passait à 405 px, l'iPhone
            dézoomait). Le masque rond le coupe ; les étiquettes, à côté, ne sont pas coupées. */}
        <div className="radar-masque" aria-hidden="true">
          <div className="radar-balai" />
        </div>
        {points.map((s, i) => {
          // Distance au centre selon le RANG de la note : les points ne se tassent pas, l'ordre reste exact,
          // et deux notes égales sont à la même distance.
          const niveau = niveaux.indexOf(noteDe(s));
          const rayon = 0.24 + (niveaux.length > 1 ? (0.66 * niveau) / (niveaux.length - 1) : 0.3);
          const angle = (((i * saut) % n) * 360) / n;
          const rad = (angle * Math.PI) / 180;
          const x = 50 + 50 * rayon * Math.sin(rad);
          const y = 50 - 50 * rayon * Math.cos(rad);
          // Le symbole est écrit vers l'extérieur du radar, loin des points plus forts
          const dx = Math.sin(rad) * 21;
          const dy = -Math.cos(rad) * 15;
          return (
            <button
              key={s.symbole}
              type="button"
              className="radar-cible hausse"
              style={{ left: `${x}%`, top: `${y}%`, "--delai": `${((angle / 360 - 1) * TOUR_RADAR).toFixed(2)}s` }}
              onClick={() => ouvrirCompagnie(s.symbole)}
              aria-label={`${s.symbole}, note ${note(s.note10)} sur 10`}
            >
              <span className="radar-marque" />
              <span className="radar-etiquette" style={{ transform: `translate(calc(-50% + ${dx.toFixed(1)}px), calc(-50% + ${dy.toFixed(1)}px))` }}>
                {s.symbole}
              </span>
            </button>
          );
        })}
      </div>
      <p className="radar-legende">
        <span className="legende-marque hausse" /> À la hausse
        <span className="legende-texte">{fr("Plus près du centre : note plus haute. Touchez un point.")}</span>
      </p>
    </div>
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
      {ev.data?.resume && <p className="detail-resume">{ev.data.resume}</p>}
      {ev.source === "sec_13dg" && ev.data?.extrait_but && (
        <p className="detail-resume">
          But écrit par le déclarant (point 4 du 13D) : « {ev.data.extrait_but} »
        </p>
      )}
      {ev.data?.aussi_declare_par?.length > 0 && (
        <p className="detail-resume aussi-declare">
          Même transaction déclarée aussi par {ev.data.aussi_declare_par.join(", ")} (entités liées) : elle est comptée une
          seule fois.
        </p>
      )}
      {ev.data?.corrigee && (
        <p className="detail-note">
          <Icone nom="info" taille={16} epaisseur={2.2} /> Corrigée par Radar : {ev.data.corrigee}
        </p>
      )}
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

      <AuCongres ev={ev} />

      {ev.data?.details?.length > 0 && (
        <>
          <h3 className="section">Détails</h3>
          <div className="carte liste details-officiels">
            {ev.data.details.map(([nom, valeur]) => (
              <div key={nom} className="detail-officiel">
                <span className="detail-officiel-nom">{nom}</span>
                <span className="detail-officiel-valeur">{valeur}</span>
              </div>
            ))}
          </div>
        </>
      )}

      {ev.source === "oge_278t" && ev.data?.transactions?.length > 0 && <LignesOge ev={ev} />}

      {ev.source === "ccc" && ev.data?.transactions?.length > 0 && <LignesCcc ev={ev} />}

      {(ev.source === "chambre_ptr" || ev.source === "senat_ptr") && ev.data?.transactions?.length > 0 && (
        <>
          <h3 className="section">Transactions déclarées</h3>
          <div className="carte liste transactions">
            {ev.data.transactions.map((tr, i) => (
              <div key={i} className="transaction">
                <span className="transaction-qui">
                  {dateCourte(tr.date)} · {PROPRIETAIRES[tr.proprietaire] ?? tr.proprietaire}
                  {tr.partielle ? " · vente partielle" : ""}
                </span>
                <span className="transaction-montant">{fourchette(tr.montant)}</span>
              </div>
            ))}
          </div>
        </>
      )}

      <h3 className="section">{rates ? `${rates} contrôle(s) raté(s)` : "Tous les contrôles réussis"}</h3>
      <div className="carte liste controles">
        {controlesEnOrdre(ev.checks).map(([nom, ok]) => (
          <div key={nom} className={ok ? "controle ok" : "controle rate"}>
            <Icone nom={ok ? "double" : "x"} taille={16} epaisseur={2.4} />
            {CONTROLES[nom] || CONTROLES_SOURCES[nom] || nom.replaceAll("_", " ")}
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
        {(ev.source === "chambre_ptr" || ev.source === "senat_ptr") && (
          <>
            <br />
            <span className="mention">Rapports publics du Congrès : usage personnel et non commercial seulement (loi américaine 5 U.S.C. § 13107).</span>
          </>
        )}
        {ev.source === "oge_278t" && (
          <>
            <br />
            <span className="mention">Rapports publics de l'Office of Government Ethics : usage personnel et non commercial seulement (loi américaine 5 U.S.C. § 13107).</span>
          </>
        )}
        {ev.source === "fda" && (
          <>
            <br />
            <span className="mention">Données fournies par la Food and Drug Administration des États-Unis (open.fda.gov).</span>
          </>
        )}
        {ev.source === "tresor" && (
          <>
            <br />
            <span className="mention">Source : Trésor des États-Unis, Bureau of the Fiscal Service (données ouvertes Fiscal Data).</span>
          </>
        )}
        {ev.source === "tarifs" && (
          <>
            <br />
            <span className="mention">Source : U.S. Customs and Border Protection (messages CSMS).</span>
          </>
        )}
        {ev.source === "usaspending" && (
          <>
            <br />
            <span className="mention">
              Source : USAspending.gov, Trésor des États-Unis (Bureau of the Fiscal Service), consulté le {dateLongue((ev.collected_at || "").slice(0, 10))}. Noms
              et adresses d'entreprises : données Dun &amp; Bradstreet (D&amp;B), usage limité.
            </span>
          </>
        )}
        <MentionCanada ev={ev} />
      </p>
    </Feuille>
  );
}

// ---------- Canada : la mention exacte exigée par chaque licence ou permission ----------

const LICENCE_OUVERTE = "https://ouvert.canada.ca/fr/licence-du-gouvernement-ouvert-canada";

function MentionCanada({ ev }) {
  const s = ev.source;
  const gazette = s === "gazette_ca" || (s === "grands_projets_ca" && ev.kind !== "projet_soutenu");
  let texte = null;
  if (s === "concurrence_ca" || s === "sanctions_ca" || s === "sante_canada" || s === "contrats_ca_10k")
    texte = (
      <>
        Contient de l'information visée par la{" "}
        <a href={LICENCE_OUVERTE} target="_blank" rel="noopener noreferrer">
          Licence du gouvernement ouvert – Canada
        </a>
        .
      </>
    );
  else if (s === "statcan")
    texte = `Source : Statistique Canada, Le Quotidien, ${dateLongue(ev.published_on)}. Reproduit et diffusé « tel quel » avec la permission de Statistique Canada.`;
  else if (gazette)
    texte = "Reproduction non officielle : seule la version publiée dans la Gazette du Canada fait foi (Décret sur la reproduction de la législation fédérale, TR/97-5).";
  else if (s === "grands_projets_ca")
    texte = "Reproduction de la version disponible à l'adresse officielle (Bureau des grands projets, Bureau du Conseil privé) : usage personnel et non commercial.";
  else if (s === "legisinfo")
    texte = "Source : LEGISinfo, Parlement du Canada. Reproduction exacte et non officielle, pour un usage personnel et non commercial.";
  else if (s === "ccc")
    texte = "Source : Corporation commerciale canadienne. Usage personnel et non commercial seulement (conditions d'utilisation de la CCC).";
  if (!texte) return null;
  return (
    <>
      <br />
      <span className="mention">{texte}</span>
    </>
  );
}

// ---------- CCC : les transactions d'un rapport trimestriel (telles qu'écrites dans le PDF officiel) ----------

function LignesCcc({ ev }) {
  const ts = ev.data.transactions;
  return (
    <>
      <h3 className="section">{`Les ${ts.length} transactions du rapport`}</h3>
      <div className="carte liste lignes-oge lignes-ccc">
        {ts.map((t, i) => (
          <div key={i} className="ligne-oge">
            <div className="transaction">
              <span className="transaction-qui">
                {t.exportateur} · {t.destination}
              </span>
              <span className="transaction-montant">{t.fourchette}</span>
            </div>
            <p className="ligne-oge-desc">{t.description}</p>
          </div>
        ))}
      </div>
    </>
  );
}

// ---------- OGE : les lignes d'un rapport 278-T du cabinet (telles qu'écrites par le déclarant) ----------

const TYPES_278T = { Purchase: "achat", Sale: "vente", Exchange: "échange" };

function LignesOge({ ev }) {
  const ls = ev.data.transactions;
  const rapport = ev.kind === "rapport_278t";
  return (
    <>
      <h3 className="section">{rapport ? `Les ${ls.length} lignes du rapport` : "Transactions déclarées"}</h3>
      <div className="carte liste lignes-oge">
        {ls.map((t) => (
          <div key={t.n} className="ligne-oge">
            <div className="transaction">
              <span className="transaction-qui">
                {dateCourte(t.date)} · {TYPES_278T[t.type] ?? t.type}
                {t.symbole && rapport ? <span className="symbole">{t.symbole}</span> : null}
              </span>
              <span className="transaction-montant">{fourchette(t.montant)}</span>
            </div>
            <p className="ligne-oge-desc">
              {t.n}. {t.description}
              {t.avis === "Yes" ? " · avis reçu plus de 30 jours après" : ""}
            </p>
            {t.note && <p className="ligne-oge-note">Note du déclarant : « {t.note} »</p>}
          </div>
        ))}
      </div>
    </>
  );
}

// ---------- Congrès : chefs, comités, H.R. 7008 ----------

const ROLES_COMITE = {
  Chair: "président·e",
  Chairman: "président·e",
  Chairwoman: "président·e",
  "Vice Chair": "vice-président·e",
  "Vice Chairman": "vice-président·e",
  Ranking: "chef de l'opposition",
  "Ex Officio": "membre d'office",
};

function AuCongres({ ev }) {
  const { donnees } = useApp();
  const elus = donnees.elus;
  const info = (ev.source === "chambre_ptr" || ev.source === "senat_ptr") && elus?.par_elu?.[ev.data?.elu];
  if (!info) return null;
  return (
    <>
      <h3 className="section">Au Congrès</h3>
      <div className="carte liste congres">
        <div className={info.chef ? "congres-chef est-chef" : "congres-chef"}>
          {info.chef ? (
            <>
              <strong>Chef du Congrès</strong> : {info.chef.poste} ({info.chef.titre}). Ses achats comptent double dans le score.
            </>
          ) : (
            <>Pas un des 12 chefs du Congrès.</>
          )}
        </div>
        {info.comites.map((c) => (
          <div key={c.nom} className="transaction">
            <span className="transaction-qui">{c.nom}</span>
            {c.role && <span className="transaction-montant">{ROLES_COMITE[c.role] ?? c.role}</span>}
          </div>
        ))}
      </div>
      {info.votes_hr7008?.length > 0 && (
        <>
          <h3 className="section">Ses votes sur H.R. 7008</h3>
          <div className="carte liste votes-elu">
            {info.votes_hr7008.map((v) => (
              <div key={`${v.chambre}${v.numero}`} className="transaction">
                <span className="transaction-qui">
                  {dateCourte(v.date)} · {v.sujet}
                </span>
                <span className="transaction-montant">{v.vote_fr}</span>
              </div>
            ))}
          </div>
        </>
      )}
      <p className="congres-source">
        {info.nom_officiel} · listes officielles de la Chambre et du Sénat{elus.listes_lues ? `, lues ${ilYa(elus.listes_lues)}` : ""}
      </p>
    </>
  );
}

function CarteProjet() {
  const { donnees } = useApp();
  const p = donnees.elus?.projet;
  if (!p) return null;
  return (
    <a className="carte carte-projet presse" href={p.url} target="_blank" rel="noopener noreferrer">
      <span className="carte-projet-haut">
        <Icone nom="capitole" taille={18} epaisseur={2} />
        Projet de loi suivi · {dateCourte(p.date)}
      </span>
      <span className="carte-projet-titre">H.R. 7008 : interdire aux élus d'acheter des actions</span>
      <span className="carte-projet-etape">{majuscule(p.etape)}</span>
      {p.votes.map((v) => (
        <span key={`${v.chambre}${v.numero}`} className="carte-projet-vote">
          {dateCourte(v.date)} · {majuscule(v.phrase)}, {v.oui} pour, {v.non} contre
        </span>
      ))}
      <span className="carte-projet-pied">
        Source officielle : govinfo.gov
        <Icone nom="externe" taille={13} epaisseur={2.2} />
      </span>
    </a>
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

// ---------- Score ----------

// Noms courts des familles de sources (les noms complets viennent du robot).
const FAMILLES_COURTES = {
  inities: "Dirigeants",
  activistes: "Fonds activiste",
  fonds: "Grand fonds",
  elus: "Élus",
  fda: "FDA",
  sec: "SEC",
  rappels: "Rappel",
  compagnie: "8-K",
};

// 5.25 → « 5,3 » ; avec signe : « +5,3 », « −0,5 ».
function pts(n, signe = false) {
  const v = Math.round(Math.abs(n) * 10) / 10;
  const t = v.toLocaleString("fr-CA", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
  return `${n < 0 ? "−" : signe ? "+" : ""}${t}`;
}

// Les points exacts publiés (2 décimales) dans la formule de la note : 5.13 -> « 5,13 » ; −4.67 -> « (−4,67) ».
function formule(n) {
  const t = Math.abs(n).toLocaleString("fr-CA", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return n < 0 ? `(−${t})` : t;
}

// Note sur 10 publiée par le robot : 9.3 -> « 9,3 » (toujours une décimale).
function note(n) {
  return (n ?? 5).toLocaleString("fr-CA", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
}

// Typographie française : espace insécable avant « % : ; ! ? » (évite « 1,2 » en fin de ligne et « % » au début de la suivante).
function fr(texte) {
  return (texte || "").replace(/ ([%:;!?»])/g, "\u00a0$1").replace(/« /g, "«\u00a0");
}

function fois(m) {
  return `×${m.toLocaleString("fr-CA", { maximumFractionDigits: 2 })}`;
}

// Le calcul d'une info, en clair : « Base +2,0 · PDG… ×1,5 · Groupe d'achats ×1,75 · temps ×0,93 ».
function calculInfo(i) {
  const morceaux = [`Base ${pts(i.base, true)}`, ...i.facteurs.map(([l, m]) => `${l} ${fois(m)}`)];
  if (i.temps < 1) morceaux.push(`temps ${fois(i.temps)}`);
  return fr(morceaux.join(" · "));
}

function LigneSuggestion({ s }) {
  const { ouvrirCompagnie, estNouveau } = useApp();
  return (
    <button type="button" className="ligne suggestion presse" onClick={() => ouvrirCompagnie(s.symbole)}>
      <span className={s.score < 0 ? "score-pastille baisse" : "score-pastille"} aria-label={`Note ${note(s.note10)} sur 10`}>
        {note(s.note10)}
        <small>/10</small>
      </span>
      <span className="ligne-centre">
        <span className="ligne-titre">
          <span className="symbole">{s.symbole}</span> {s.nom}
        </span>
        <span className="ligne-meta">
          {estNouveau(s) && <span className="nouveau">Nouveau</span>}
          {s.recent && <span className="recent">Récent</span>}
          <span>{s.groupes.map((g) => FAMILLES_COURTES[g.famille] || g.famille).join(" · ")}</span>
        </span>
      </span>
      <Icone nom="chevron-d" taille={18} epaisseur={2.2} className="chevron" />
    </button>
  );
}

function ListeSuggestions({ liste }) {
  return (
    <div className="carte liste">
      {liste.map((s) => (
        <LigneSuggestion key={s.symbole} s={s} />
      ))}
    </div>
  );
}

function LienMethode() {
  const { pousser } = useApp();
  return (
    <button type="button" className="lien bloc-lien" onClick={() => pousser("methode")}>
      Comment le score est calculé
    </button>
  );
}

function EcranSuggestions({ retour }) {
  const { donnees, vueSuggestions, setVueSuggestions } = useApp();
  const s = donnees.aujourdhui || {};
  const baisse = vueSuggestions === "baisse";
  const liste = (baisse ? s.baisse : s.hausse) || [];
  return (
    <Ecran titre="Suggestions" retour={retour}>
      <Segments
        label="Sens"
        valeur={vueSuggestions}
        onChange={setVueSuggestions}
        options={[
          ["hausse", `Hausse · ${s.hausse?.length || 0}`],
          ["baisse", `Baisse · ${s.baisse?.length || 0}`],
        ]}
      />
      <p className="explication">
        {fr(baisse ? "Signaux négatifs : note de 3/10 et moins." : "Où le gros argent entre : note de 7/10 et plus.")} Calculé {ilYa(s.genere_a)}.
      </p>
      {liste.length === 0 ? (
        <div className="carte">
          <Vide titre="Personne pour l'instant" texte="Aucune compagnie n'atteint le seuil." />
        </div>
      ) : (
        <ListeSuggestions liste={liste} />
      )}
      {!baisse && s.ecartees?.length > 0 && (
        <>
          <h2 className="section">{`Écartées · ${s.ecartees.length}`}</h2>
          <p className="explication">
            {fr("Moins de 100 M$ en bourse : hors de la liste « hausse ». Dans le rejeu de 3 ans du labo, ces compagnies ont fait pire que le S&P 500 chacune des 3 années. Elles restent suivies dans les Résultats, pour vérifier la règle.")}
          </p>
          <ListeSuggestions liste={s.ecartees} />
        </>
      )}
      <LienMethode />
      <p className="avertissement">{s.note || "Pas des conseils financiers"}</p>
    </Ecran>
  );
}

// Le cours de l'action : un lien vers une page publique, ouverte dans Safari par la personne (le robot ne lit jamais ce
// site). Format de Yahoo Finance : le point d'une catégorie d'actions devient un tiret (ex. BRK.B → BRK-B).
const lienCours = (symbole) => `https://finance.yahoo.com/quote/${encodeURIComponent(symbole.replace(/\./g, "-"))}/`;

function EcranCompagnie({ retour }) {
  const { donnees, compagnie, ouvrirDetail, favoris, basculerFavori, estNouveau } = useApp();
  const s = donnees.aujourdhui || {};
  const c = [...(s.hausse || []), ...(s.baisse || []), ...(s.ecartees || [])].find((x) => x.symbole === compagnie);
  const ecartee = (s.ecartees || []).some((x) => x.symbole === compagnie);
  if (!c) {
    return (
      <Ecran titre={compagnie || "Compagnie"} retour={retour}>
        <div className="carte">
          <Vide titre="Plus dans les listes" texte="Cette compagnie est sortie des suggestions au dernier calcul." />
        </div>
      </Ecran>
    );
  }
  const evs = s.evenements || {};
  const noms = s.methode?.familles_noms || {};
  const suivi = favoris.includes(c.symbole);
  const baisse = c.score < 0;
  const ligneCalcul = (sens, total, bonus) => {
    const g = c.groupes.filter((x) => x.sens === sens);
    if (!g.length) return null;
    const somme = g.map((x) => pts(x.points, true)).join(" ");
    const avecBonus = bonus > 1 ? ` · bonus ${fois(bonus)} (${g.length} familles d'accord)` : "";
    return (
      <p>
        {sens > 0 ? "Hausse" : "Baisse"} : {somme}
        {avecBonus} = {pts(total, true)}
      </p>
    );
  };
  return (
    <Ecran titre={c.symbole} retour={retour}>
      <div className="carte fiche">
        <p className="fiche-nom">{c.nom}</p>
        <AnneauNote valeur={c.note10} baisse={baisse} />
        <p className="fiche-points">{fr(`${pts(c.score)} points`)}</p>
        <p className="fiche-sens">
          {baisse ? "À surveiller à la baisse" : ecartee ? "Écartée : moins de 100 M$ en bourse" : "À regarder à la hausse"}
          {estNouveau(c) && <span className="nouveau">Nouveau</span>}
          {c.recent && <span className="recent">Récent</span>}
        </p>
        <div className="fiche-boutons">
          <button type="button" className={suivi ? "symbole-grand bouton-favori suivi presse" : "symbole-grand bouton-favori presse"} onClick={() => basculerFavori(c.symbole)} aria-pressed={suivi}>
            <Icone nom="etoile" taille={16} rempli={suivi} epaisseur={2} />
            {suivi ? "Dans mes favoris" : "Ajouter aux favoris"}
          </button>
          <a className="symbole-grand bouton-cours presse" href={lienCours(c.symbole)} target="_blank" rel="noopener noreferrer">
            <Icone nom="externe" taille={16} epaisseur={2} />
            Voir le cours
          </a>
        </div>
        <p className="fiche-cours-source">Le cours s'ouvre sur Yahoo Finance, un site externe.</p>
      </div>

      {c.groupes.map((g) => (
        <section key={`${g.famille}${g.sens}`}>
          <div className="section-ligne">
            <h2 className="section">{noms[g.famille] || g.famille}</h2>
            <span className={g.sens < 0 ? "section-points t-rouge" : "section-points t-vert"}>{pts(g.points, true)}</span>
          </div>
          <div className="carte liste">
            {g.infos.map((i) => {
              const ev = evs[i.id];
              return (
                <button key={i.id} type="button" className="ligne raison presse" onClick={() => ev && ouvrirDetail(ev)}>
                  <span className="ligne-centre">
                    <span className="ligne-titre">{fr(ev?.title || i.id)}</span>
                    <span className="ligne-meta">
                      {dateCourte(ev?.published_on)} · {i.compte ? calculInfo(i) : fr("Même famille : seule l'info la plus forte compte")}
                    </span>
                  </span>
                  <span className={i.compte ? "raison-points" : "raison-points pas-compte"}>{i.compte ? pts(i.points, true) : "0"}</span>
                </button>
              );
            })}
          </div>
        </section>
      ))}

      <div className="carte calcul">
        {c.groupes.length > 1 && ligneCalcul(1, c.plus, c.bonus.plus)}
        {c.groupes.length > 1 && ligneCalcul(-1, c.moins, c.bonus.moins)}
        <p className="calcul-total">
          {fr(`Score : ${pts(c.score)} points → note ${note(c.note10)}/10`)}
          <small>{fr(`Note = 5 + ${formule(c.score)} × 5/6, entre 0 et 10, arrondie au dixième`)}</small>
        </p>
      </div>
      <TailleBourse t={c.taille} regle100={Boolean(s.methode?.trop_petites)} />
      <SanteFinanciere symbole={c.symbole} />

      {c.contexte.length > 0 && (
        <>
          <h2 className="section">Autres infos (0 point)</h2>
          <div className="carte liste">
            {c.contexte.map((x) => {
              const ev = evs[x.id];
              return (
                <button key={x.id} type="button" className="ligne raison presse" onClick={() => ev && ouvrirDetail(ev)}>
                  <span className="ligne-centre">
                    <span className="ligne-titre">{fr(ev?.title || x.id)}</span>
                    <span className="ligne-meta">
                      {dateCourte(ev?.published_on)} · {fr(x.pourquoi)}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </>
      )}
      <Lobbying symbole={c.symbole} />
      <RachatsFaits symbole={c.symbole} />
      <LienMethode />
      <p className="avertissement">{s.note || "Pas des conseils financiers"}</p>
    </Ecran>
  );
}

// Rachats d'actions faits pendant un exercice (rapport annuel, données XBRL de la SEC) : montré sur la fiche, 0 point.
function RachatsFaits({ symbole }) {
  const { donnees } = useApp();
  const r = donnees.rachats;
  const x = r?.par_symbole?.[symbole];
  // Rien à montrer (pas encore lu, aucun montant, montant illisible) : la section n'apparaît pas.
  if (!x || x.illisible || x.montant == null) return null;
  const contenu = (
    <>
      <p className="rachats-total">{argent(x.montant, "USD")}</p>
      <p className="rachats-texte">
        {fr(x.montant > 0 ? `Argent dépensé pour racheter ses actions pendant l'exercice du ${dateLongue(x.debut)} au ${dateLongue(x.fin)}, selon son rapport annuel.` : `Aucun rachat d'actions pendant l'exercice du ${dateLongue(x.debut)} au ${dateLongue(x.fin)}, selon son rapport annuel.`)}
      </p>
      <a className="transaction presse" href={x.lien} target="_blank" rel="noopener noreferrer">
        <span className="transaction-qui">Rapport à la SEC ({x.accn})</span>
        <span className="transaction-montant">
          <Icone nom="externe" taille={16} />
        </span>
      </a>
    </>
  );
  return (
    <>
      <h2 className="section">Rachats d'actions faits</h2>
      <div className="carte liste rachats-faits">{contenu}</div>
      <p className="rachats-source">{fr(`Données XBRL déclarées par la compagnie (« Payments for Repurchase of Common Stock »), API officielle de la SEC, exercice le plus proche de l'année ${r.cadre?.slice(2) || ""}. 0 point dans le score.`)}</p>
    </>
  );
}

// Santé financière : les 9 critères de Piotroski (2000), d'après le rapport annuel (données XBRL de la SEC). Montrée
// seulement si les 9 critères se calculent (sinon la section n'apparaît pas) ; 0 point dans la note.
const pct = (x) => `${(x * 100).toFixed(1).replace(".", ",").replace("-", "−")} %`;
const ratio2 = (x) => x.toFixed(2).replace(".", ",");
const CRITERES_SANTE = [
  ["ROA", "Fait des profits", (c) => `Bénéfice : ${pct(c.roa)} de l'actif`],
  ["CFO", "Génère de l'argent", (c) => `Flux de trésorerie d'exploitation : ${pct(c.cfo)} de l'actif`],
  ["ΔROA", "Profits en hausse", (c) => `${pct(c.roa_avant)} → ${pct(c.roa)} de l'actif`],
  ["ACCRUAL", "Profits appuyés par de l'argent réel", (c) => `Flux de trésorerie ${pct(c.cfo)}, bénéfice ${pct(c.roa)}`],
  ["ΔLEVER", "Dette à long terme en baisse", (c) => `${pct(c.levier_avant)} → ${pct(c.levier)} de l'actif`],
  ["ΔLIQUID", "Liquidité en hausse", (c) => `Actif à court terme ÷ passif à court terme : ${ratio2(c.liquidite_avant)} → ${ratio2(c.liquidite)}`],
  ["EQ_OFFER", "Aucune nouvelle action émise", (c) => (c.emission > 0 ? `${argent(c.emission, "USD")} d'actions émises` : "Aucune émission d'actions déclarée")],
  ["ΔMARGIN", "Marge brute en hausse", (c) => `${pct(c.marge_avant)} → ${pct(c.marge)} des ventes`],
  ["ΔTURN", "Plus de ventes par dollar d'actif", (c) => `${ratio2(c.rotation_avant)} $ → ${ratio2(c.rotation)} $`],
];

// ---------- Taille en bourse (lot L) : petite compagnie = ×1,5 sur les achats de dirigeants ----------

const TAILLES = { petite: "Petite compagnie", moyenne: "Compagnie moyenne", grande: "Grande compagnie" };
const MOIS_LONGS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];

// « 202608 » → « août 2026 »
function moisAnnee(aaaamm) {
  return `${MOIS_LONGS[Number(aaaamm.slice(4, 6)) - 1]} ${aaaamm.slice(0, 4)}`;
}

function TailleBourse({ t, regle100 }) {
  if (!t) return null;
  const s = t.seuils;
  const seuils = s
    ? `Petite : moins de ${argentCourt(s.p30 * 1e6)} (30e centile des compagnies du NYSE, ${moisAnnee(s.mois)}) ; grande : ${argentCourt(s.p70 * 1e6)} et plus (70e centile).`
    : "";
  const texte = t.taille
    ? `${nombre(t.actions[0])} actions déclarées au ${dateLongue(t.actions[1])} × ${prixAction(t.prix[1])} (prix de la SEC du ${jourSec(t.prix[0])}). ${seuils}${t.taille === "petite" ? " Les achats de dirigeants comptent ×1,5." : ""}${regle100 && t.valeur_m < 100 ? " Moins de 100 M$ : hors de la liste « hausse »." : ""}${t.note ? ` ${t.note}` : ""}`
    : `Pas calculée : ${t.raison}. Pas de bonus de petite compagnie.`;
  // Étape 1 (données sûres), autour d'un changement de CUSIP : deux valeurs possibles (même taille des deux côtés), ou
  // un maximum sûr après un regroupement d'actions probable
  const valeur = t.taille && (t.valeur_min_m != null
    ? `${argentCourt(t.valeur_min_m * 1e6)} à ${argentCourt(t.valeur_m * 1e6)}`
    : `${t.valeur_max ? "au plus " : ""}${argentCourt(t.valeur_m * 1e6)}`);
  return (
    <>
      <h2 className="section">Taille en bourse</h2>
      <div className="carte liste taille">
        <Rangee label={t.taille ? TAILLES[t.taille] : "Taille inconnue"}>
          {t.taille && <span className="rangee-valeur">{valeur}</span>}
        </Rangee>
        <div className="rangee bloc">
          <span className="rangee-texte">{fr(texte)}</span>
        </div>
      </div>
      <p className="taille-source">{fr("Actions en circulation déclarées à la SEC × prix officiel de la SEC ; seuils publiés chaque mois par Kenneth French (données CRSP). Lakonishok et Lee (2001) : les achats des dirigeants prédisent plus dans les petites compagnies.")}</p>
    </>
  );
}

function SanteFinanciere({ symbole }) {
  const { donnees } = useApp();
  const x = donnees.sante?.par_symbole?.[symbole];
  if (!x) return null; // pas de score complet : la section n'apparaît pas
  return (
    <>
      <h2 className="section">{fr(`Santé financière · exercice terminé le ${dateLongue(x.fin)}`)}</h2>
      <div className="carte liste sante">
        <p className="sante-total">
          {x.f_score}
          <small>/9</small>
        </p>
        <p className="sante-texte">{fr("critères positifs dans son dernier rapport annuel. Plus c'est haut, plus la compagnie est solide.")}</p>
        {CRITERES_SANTE.map(([code, titre, detail]) => {
          const oui = x.criteres[code] === 1;
          return (
            <div key={code} className={oui ? "critere oui" : "critere non"}>
              <Icone nom={oui ? "double" : "x"} taille={16} epaisseur={2.4} />
              <span className="critere-texte">
                <span className="critere-titre">{titre}</span>
                <span className="critere-detail">{fr(detail(x.chiffres))}</span>
              </span>
            </div>
          );
        })}
        <a className="transaction presse" href={x.lien} target="_blank" rel="noopener noreferrer">
          <span className="transaction-qui">
            Rapport annuel à la SEC <span className="accn">({x.accn})</span>
          </span>
          <span className="transaction-montant">
            <Icone nom="externe" taille={16} />
          </span>
        </a>
      </div>
      <p className="sante-source">{fr("Données XBRL officielles de la SEC. Critères de l'étude de Piotroski (2000), testée sur les actions bon marché par rapport à leur valeur comptable. 0 point dans la note.")}</p>
    </>
  );
}

// Lobbying à Washington (LDA.gov) : montré sur la fiche, 0 point. Conditions de l'API : date de lecture et avertissement.
function Lobbying({ symbole }) {
  const { donnees } = useApp();
  const l = donnees.lobbying;
  if (!l?.trimestre) return null;
  const x = l.par_symbole?.[symbole];
  // Rien à montrer (pas encore lu, recherche trop large, aucun rapport ce trimestre) : la section n'apparaît pas.
  if (!x || !x.complet || x.total == null) return null;
  const contenu = (
    <>
      <p className="lobbying-total">{argent(x.total, "USD")}</p>
      <p className="lobbying-texte">
        {x.base === "compagnie"
          ? `Dépenses déclarées par la compagnie elle-même${x.firmes ? ` : elles incluent ce qu'elle paie à ${x.firmes} firme${x.firmes > 1 ? "s" : ""} de lobbying, qui ${x.firmes > 1 ? "déclarent ensemble" : "déclare"} ${argent(x.revenus_firmes, "USD")}` : ""}.`
          : `Payés à ${x.firmes} firme${x.firmes > 1 ? "s" : ""} de lobbying (la compagnie n'a pas ses propres lobbyistes).`}
        {x.moins_de_5000 > 0 && ` ${x.moins_de_5000} rapport${x.moins_de_5000 > 1 ? "s" : ""} « moins de 5 000 $ » sans montant.`}
      </p>
      {x.sujets.length > 0 && (
        <p className="lobbying-sujets">
          Sujets : {x.sujets.slice(0, 6).map((u) => u.nom).join(" · ")}
          {x.sujets.length > 6 ? ` · et ${x.sujets.length - 6} autres` : ""}
        </p>
      )}
      {x.rapports.map((r) => (
        <a key={r.uuid} className="transaction presse" href={r.url} target="_blank" rel="noopener noreferrer">
          <span className="transaction-qui">
            {r.soi_meme ? "La compagnie elle-même" : r.registrant}
            {r.sans_activite ? " · sans activité" : ""}
          </span>
          <span className="transaction-montant">{r.montant != null ? argent(r.montant, "USD") : r.sans_activite ? "—" : "< 5 000 $"}</span>
        </a>
      ))}
    </>
  );
  return (
    <>
      <h2 className="section">Lobbying à Washington · {l.trimestre.libelle}</h2>
      <div className="carte liste lobbying">{contenu}</div>
      <p className="congres-source">
        {x?.lu ? `Lu sur LDA.gov le ${dateLongue(x.lu.slice(0, 10))}. ` : ""}Montants arrondis aux 10 000 $ par les déposants. 0 point dans le score. « {l.avertissement} » (Le bureau des
        documents publics du Sénat ne garantit pas ces données ni les analyses qu'on en tire une fois sorties de LDA.gov.)
      </p>
    </>
  );
}

function EcranMethode({ retour }) {
  const { donnees } = useApp();
  const m = donnees.aujourdhui?.methode;
  if (!m) {
    return (
      <Ecran titre="Le score" retour={retour}>
        <div className="carte">
          <Vide titre="Pas encore calculé" texte="Le robot n'a pas encore publié de score." />
        </div>
      </Ecran>
    );
  }
  return (
    <Ecran titre="Le score" retour={retour}>
      <p className="explication">{fr(m.resume)}</p>
      <Groupe titre="Les points">
        {m.regles.map((r) => (
          <div key={r.code} className="rangee bloc regle">
            <div className="regle-haut">
              <span className="rangee-label">{fr(r.libelle)}</span>
              <span className={r.points < 0 ? "regle-points t-rouge" : "regle-points t-vert"}>{pts(r.points, true)}</span>
            </div>
            {r.details.length > 0 && (
              <ul className="regle-details">
                {r.details.map((d) => (
                  <li key={d}>{fr(d)}</li>
                ))}
              </ul>
            )}
            {r.etudes
              .filter((e) => m.etudes[e])
              .map((e) => (
                <a key={e} className="etude" href={m.etudes[e].lien} target="_blank" rel="noopener noreferrer">
                  <Icone nom="document" taille={16} epaisseur={2} />
                  <span>
                    <b>{m.etudes[e].titre}</b>{fr(` : ${m.etudes[e].constat}`)}
                  </span>
                </a>
              ))}
          </div>
        ))}
      </Groupe>
      <Groupe titre="Le calcul">
        {[m.temps, m.familles, m.bonus, m.taille, m.trop_petites, m.routiniers, m.note10, m.seuil, m.recent, m.badges].filter(Boolean).map((t) => (
          <div key={t} className="rangee bloc">
            <span className="rangee-texte">{fr(t)}</span>
          </div>
        ))}
        {m.lien_labo && (
          <div className="rangee bloc">
            <a className="etude" href={m.lien_labo} target="_blank" rel="noopener noreferrer">
              <Icone nom="document" taille={16} epaisseur={2} />
              <span>
                <b>Rejeu de 3 ans du labo</b>
                {fr(" : les chiffres des compagnies de moins de 100 M$, année par année (GitHub).")}
              </span>
            </a>
          </div>
        )}
        {(m.etudes_note || [])
          .filter((e) => m.etudes[e])
          .map((e) => (
            <div key={e} className="rangee bloc">
              <a className="etude" href={m.etudes[e].lien} target="_blank" rel="noopener noreferrer">
                <Icone nom="document" taille={16} epaisseur={2} />
                <span>
                  <b>{m.etudes[e].titre}</b>{fr(` : ${m.etudes[e].constat}`)}
                </span>
              </a>
            </div>
          ))}
      </Groupe>
      <Groupe titre="Sans points (contexte)">
        {m.sans_points.map((t) => (
          <div key={t} className="rangee bloc">
            <span className="rangee-texte">{fr(t)}</span>
          </div>
        ))}
      </Groupe>
      <p className="avertissement">{m.avertissement}</p>
    </Ecran>
  );
}

// ---------- Écrans ----------

function Accueil({ pousser, allerAuFil }) {
  const { donnees, charger, chargement, ouvrirSuggestions } = useApp();
  const { meta, aujourdhui } = donnees;
  const visibles = useVisibles();
  // Les compteurs viennent du robot : calculés sur TOUTES les infos, selon la date de publication officielle.
  const c = meta.compteurs;
  const nouvelles = c ? c.publiees_dernier_jour : visibles.length;
  const confirmees = c ? c.confirmees_30j : visibles.filter((e) => e.badge === "confirme").length;
  const parCategorie = useMemo(() => {
    if (c) return c.par_categorie_30j || {};
    const n = {};
    for (const e of visibles) n[e.category] = (n[e.category] || 0) + 1;
    return n;
  }, [c, visibles]);
  // Une catégorie sans aucune source branchée affiche sa phase au lieu d'un 0 trompeur.
  const phaseCategorie = useMemo(() => {
    const branchee = {};
    const phase = {};
    for (const s of donnees.sources || []) {
      if (s.statut === "ecartee") continue;
      if (s.statut === "a_venir") phase[s.categorie] = Math.min(phase[s.categorie] ?? 9, s.phase);
      else branchee[s.categorie] = true;
    }
    return Object.fromEntries(Object.keys(CATEGORIES).map((k) => [k, branchee[k] ? null : phase[k] ?? null]));
  }, [donnees.sources]);
  const hausse = aujourdhui?.hausse || [];
  const baisse = aujourdhui?.baisse || [];
  const nbSources = compteSources(donnees.sources);
  const pourcentage = nbSources.total ? Math.round((nbSources.actives / nbSources.total) * 100) : 0;
  const date = majuscule(new Date().toLocaleDateString("fr-CA", { weekday: "long", day: "numeric", month: "long" }));

  return (
    <Ecran
      titre="Radar"
      sousTitre={date}
      droite={
        <span className="boutons-haut">
          <BoutonRond icone="info" label="Aide" onClick={() => pousser("aide")} />
          <BoutonRond icone="rafraichir" label="Actualiser" onClick={charger} tourne={chargement} />
        </span>
      }
    >
      <EtatDonnees />

      {hausse.length === 0 && baisse.length === 0 ? (
        <div className="heros">
          <RadarAnime />
          <div className="heros-texte">
            <p className="heros-titre">{aujourdhui?.version ? "Rien d'assez fort aujourd'hui" : "Aucune suggestion pour l'instant"}</p>
            <p className="heros-sous">
              {aujourdhui?.version ? "Aucune compagnie n'atteint 7/10." : "Le robot publie le score à son prochain passage."} En attendant, le fil montre tout ce que le robot lit.
            </p>
            <div className="mini-barre">
              <div style={{ width: `${Math.max(pourcentage, 3)}%` }} />
            </div>
            <p className="heros-pied">
              {nbSources.actives} sur {nbSources.total} sources actives
            </p>
          </div>
        </div>
      ) : (
        <>
          {hausse.length > 0 && <RadarSuggestions hausse={hausse} />}
          <div className="section-ligne">
            <h2 className="section">À regarder aujourd'hui</h2>
            <button type="button" className="lien" onClick={() => ouvrirSuggestions("hausse")}>
              Tout voir
            </button>
          </div>
          {hausse.length > 0 ? (
            <ListeSuggestions liste={hausse.slice(0, 5)} />
          ) : (
            <div className="carte">
              <Vide titre="Rien à la hausse" texte="Aucune compagnie n'atteint 7/10." />
            </div>
          )}
          {baisse.length > 0 && (
            <button type="button" className="carte alerte-baisse presse" onClick={() => ouvrirSuggestions("baisse")}>
              <Icone nom="alerte" taille={18} epaisseur={2.2} className="t-rouge" />
              <span>{baisse.length} à surveiller à la baisse</span>
              <Icone nom="chevron-d" taille={18} epaisseur={2.2} className="chevron" />
            </button>
          )}
        </>
      )}

      <CarteCalendrier />
      <CarteResultats />

      <div className="tuiles">
        <button type="button" className="tuile presse" onClick={() => allerAuFil("tout")}>
          <Icone nom="eclair" taille={20} epaisseur={2} className="t-accent" />
          <Defile valeur={nouvelles} className="tuile-valeur" />
          <span className="tuile-label">{c?.dernier_jour ? `Publiées le ${dateCourte(c.dernier_jour)}` : "Nouvelles"}</span>
        </button>
        <button type="button" className="tuile presse" onClick={() => allerAuFil("tout")}>
          <Icone nom="double" taille={20} epaisseur={2.2} className="t-vert" />
          <Defile valeur={confirmees} className="tuile-valeur" />
          <span className="tuile-label">Confirmées (30 j)</span>
        </button>
        <button type="button" className="tuile presse" onClick={() => pousser("a_verifier")}>
          <Icone nom="alerte" taille={20} epaisseur={2} className="t-jaune" />
          <Defile valeur={meta.a_verifier_3_mois ?? donnees.a_verifier.length} className="tuile-valeur" />
          <span className="tuile-label">À vérifier</span>
        </button>
        <button type="button" className="tuile presse" onClick={() => pousser("sources")}>
          <Icone nom="antenne" taille={20} epaisseur={2} className="t-bleu" />
          <span className="tuile-valeur">
            {nbSources.actives}
            <small>/{nbSources.total}</small>
          </span>
          <span className="tuile-label">Sources actives</span>
        </button>
      </div>

      <h2 className="section">Catégories · 30 jours</h2>
      <div className="grille-cat">
        {Object.entries(CATEGORIES).map(([k, c]) => (
          <button key={k} type="button" className="cat presse" onClick={() => allerAuFil(k)}>
            <IconeCategorie code={k} />
            <span className="cat-label">{c.label}</span>
            {phaseCategorie[k] ? (
              <span className="cat-phase">Phase {phaseCategorie[k]}</span>
            ) : (
              <span className="cat-nombre">{parCategorie[k] || 0}</span>
            )}
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
          <Vide titre="Rien pour l'instant" texte="Aucune info avec ces réglages." />
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
  const { reglages, setReglages } = useApp();
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
      <Segments label="Trier par" valeur={reglages.tri} onChange={(v) => setReglages({ ...reglages, tri: v })} options={[["recent", "Plus récent"], ["montant", "Plus gros montant"]]} />
      {filtre === "politiciens" && !recherche && <CarteProjet />}
      {liste.length === 0 ? (
        <Vide
          icone={recherche ? "loupe" : "radar"}
          titre={recherche ? "Aucun résultat" : "Rien pour l'instant"}
          texte={recherche ? "Essaie un autre mot ou un symbole (ex. LMT)." : "Aucune info avec ces filtres."}
        />
      ) : (
        <ListeEvenements liste={liste} groupee={reglages.tri === "recent"} />
      )}
    </Ecran>
  );
}

// ---------- Calendrier : fins prévues de blocage après une entrée en bourse (robot : data/app/calendrier.json) ----------

const MOIS_COURTS = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];

function LigneCalendrier({ l, ev }) {
  const { ouvrirDetail } = useApp();
  const [, mois, jour] = l.fin.split("-").map(Number);
  return (
    <button type="button" className={l.passee ? "ligne presse cal-ligne passee" : "ligne presse cal-ligne"} onClick={() => ev && ouvrirDetail(ev)}>
      <span className="cal-date" aria-hidden="true">
        <span className="cal-jour">{jour}</span>
        <span className="cal-mois">{MOIS_COURTS[mois - 1]}</span>
      </span>
      <span className="ligne-centre">
        <span className="ligne-titre">
          <span className="cache">{dateLongue(l.fin)} : </span>
          {l.compagnie}
        </span>
        <span className="ligne-meta">
          {l.symbole && <span className="symbole">{l.symbole}</span>}
          <span>{l.passee ? `Blocage terminé le ${dateLongue(l.fin)}` : `Fin du blocage de ${l.duree} jours`}</span>
        </span>
        <span className="cal-sous">Entrée en bourse : prospectus du {dateLongue(l.prospectus)}</span>
      </span>
      <Icone nom="chevron-d" taille={18} epaisseur={2.2} className="chevron" />
    </button>
  );
}

function CarteCalendrier() {
  const { donnees, pousser } = useApp();
  const cal = donnees.calendrier;
  const prochaines = (cal?.lignes || []).filter((l) => !l.passee).slice(0, 3);
  if (prochaines.length === 0) return null;
  return (
    <>
      <div className="section-ligne">
        <h2 className="section">Fins de blocage à venir</h2>
        <button type="button" className="lien" onClick={() => pousser("calendrier")}>
          Tout voir
        </button>
      </div>
      <div className="carte liste calendrier">
        {prochaines.map((l) => (
          <LigneCalendrier key={l.id} l={l} ev={cal.evenements?.[l.id]} />
        ))}
      </div>
    </>
  );
}

function EcranCalendrier({ retour }) {
  const { donnees } = useApp();
  const cal = donnees.calendrier;
  const parMois = useMemo(() => {
    const groupes = [];
    for (const l of cal?.lignes || []) {
      const mois = majuscule(new Date(`${l.fin}T12:00:00`).toLocaleDateString("fr-CA", { month: "long", year: "numeric" }));
      if (groupes.length === 0 || groupes[groupes.length - 1][0] !== mois) groupes.push([mois, []]);
      groupes[groupes.length - 1][1].push(l);
    }
    return groupes;
  }, [cal]);
  return (
    <Ecran titre="Calendrier" sousTitre="Fins de blocage" retour={retour}>
      <p className="explication">
        {fr(cal?.explication || "Après une entrée en bourse, les dirigeants et les anciens actionnaires s'engagent à ne pas vendre pendant une période écrite dans le prospectus.")}
      </p>
      {!cal ? (
        <div className="carte">
          <Vide icone="calendrier" titre="Calendrier pas encore publié" texte="Le robot le publie à son prochain passage." />
        </div>
      ) : parMois.length === 0 ? (
        <div className="carte">
          <Vide icone="calendrier" titre="Rien à venir" texte="Aucune fin de blocage dans les prospectus lus." />
        </div>
      ) : (
        parMois.map(([mois, lignes]) => (
          <Groupe key={mois} titre={mois}>
            {lignes.map((l) => (
              <LigneCalendrier key={l.id} l={l} ev={cal.evenements?.[l.id]} />
            ))}
          </Groupe>
        ))
      )}
      <p className="groupe-pied">
        {fr("Source : prospectus finals (424B4) déposés à la SEC. Radar publie une date seulement si tout est écrit clairement : une vraie entrée en bourse, la date du prospectus, une seule durée et aucune levée anticipée. Sinon, rien.")}
      </p>
    </Ecran>
  );
}

// ---------- Résultats de Radar : prix officiels de la SEC (robot : data/app/resultats.json) ----------

const SENS_RESULTATS = { hausse: "À la hausse", baisse: "À la baisse", ecartee: "Écartée (moins de 100 M$)" };

function variationSignee(v) {
  return `${v > 0 ? "+" : ""}${(v * 100).toLocaleString("fr-CA", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} %`;
}

function points(v) {
  return `${v > 0 ? "+" : ""}${(v * 100).toLocaleString("fr-CA", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} points`;
}

function jourSec(aaaammjj) {
  return dateCourte(`${aaaammjj.slice(0, 4)}-${aaaammjj.slice(4, 6)}-${aaaammjj.slice(6, 8)}`);
}

function verdict(h, sens) {
  if (sens === "ecartee" && h.battu != null)
    return h.battu ? "a fait moins bien que le marché : la règle avait raison" : "a fait mieux que le marché : la règle s'est trompée";
  if (h.battu === true) return sens === "hausse" ? "a battu le marché" : "a fait moins bien que le marché, comme prévu";
  if (h.battu === false) return sens === "hausse" ? "n'a pas battu le marché" : "n'a pas fait moins bien que le marché";
  return h.pourquoi || "pas de verdict";
}

function LigneHorizon({ nom, h, sens }) {
  let texte;
  let classe = "gris";
  if (h.statut === "mesure") {
    texte = `${variationSignee(h.variation)} au ${jourSec(h.date)}${h.marche ? ` · marché ${variationSignee(h.marche.variation)} (${h.marche.fonds})` : ""} : ${verdict(h, sens)}`;
    classe = h.battu === true ? "vert" : h.battu === false ? "rouge" : "gris";
  } else if (h.statut === "en_attente") {
    texte = `en attente des prix de la SEC (vers le ${dateLongue(h.attendu_vers)})`;
  } else if (h.statut === "pas_de_prix") {
    texte = "pas de prix officiel ces jours-là";
  } else if (h.statut === "pas_comparable") {
    texte = `pas comparable : ${h.pourquoi}`;
  } else {
    texte = `${variationSignee(h.variation)} à vérifier : ${h.pourquoi}`;
    classe = "jaune";
  }
  return (
    <span className={`res-horizon ${classe}`}>
      <b>{nom}</b> {fr(texte)}
    </span>
  );
}

// Pourquoi la compagnie est entrée (lot L) : « Achat d'actions par un dirigeant… (PDG…, Petite compagnie) · petite compagnie ».
function pourquoiEntree(l, libelles) {
  if (!l.signaux) return null;
  const s = l.sens === "baisse" ? -1 : 1;
  const morceaux = l.signaux
    .filter((x) => x.sens === s)
    .map((x) => `${(libelles || {})[x.regle] || x.regle}${x.facteurs.length ? ` (${x.facteurs.join(", ")})` : ""}`);
  if (l.taille) morceaux.push(TAILLES[l.taille].toLowerCase());
  if (l.grace_au_bonus) morceaux.push("entrée grâce au bonus de familles");
  if (l.grace_a_la_taille) morceaux.push("entrée grâce au bonus de petite compagnie");
  return morceaux.length ? `Pourquoi : ${morceaux.join(" · ")}` : null;
}

function LigneResultat({ l, horizons, libelles }) {
  const d = l.depart;
  const pourquoi = pourquoiEntree(l, libelles);
  return (
    <div className="rangee bloc res-ligne">
      <span className="res-tete">
        <span className="symbole">{l.symbole}</span> <b>{l.nom}</b>
      </span>
      <span className="res-sous">
        {SENS_RESULTATS[l.sens]} · entrée le {dateLongue(l.entree.slice(0, 10))}
        {l.note10 != null ? ` · ${String(l.note10).replace(".", ",")}/10` : ""}
      </span>
      {pourquoi && <span className="res-sous">{fr(pourquoi)}</span>}
      <span className="res-sous">
        {d.statut === "ok"
          ? `Départ : ${d.prix.toLocaleString("fr-CA", { style: "currency", currency: "USD" })} (prix de la SEC du ${jourSec(d.date)})`
          : d.statut === "en_attente"
            ? `Départ : en attente des prix de la SEC (vers le ${dateLongue(d.attendu_vers)})`
            : "Départ : pas de prix officiel ces jours-là"}
      </span>
      {d.statut === "ok" && Object.entries(horizons).map(([k, nom]) => <LigneHorizon key={k} nom={nom} h={l.horizons[k]} sens={l.sens} />)}
    </div>
  );
}

function resumeResultats(r) {
  const morceaux = [];
  for (const [k, nom] of Object.entries(r.horizons)) {
    const h = r.resume[`hausse_${k}`];
    const b = r.resume[`baisse_${k}`];
    const n = h.mesurees + b.mesurees;
    if (n) morceaux.push(`${nom} : ${h.battu + b.battu} sur ${n} ont frappé juste`);
  }
  return morceaux.length ? morceaux.join(" · ") : null;
}

// Le taux de réussite de chaque signal (lot L) : une entrée compte dans chacun de ses signaux.
function ParSignal({ p, horizons }) {
  return ["hausse", "baisse"].map((sens) => {
    const signaux = Object.entries(p[sens] || {}).sort((a, b) => b[1].entrees - a[1].entrees || a[1].libelle.localeCompare(b[1].libelle));
    if (!signaux.length) return null;
    return (
      <Groupe
        key={sens}
        titre={`Par signal · ${SENS_RESULTATS[sens].toLowerCase()}`}
        pied={sens === "hausse" && p.sans_raisons ? fr(`${p.sans_raisons} entrées d'avant le 5 octobre 2026 : raisons pas notées, comptées seulement dans le taux de réussite.`) : undefined}
      >
        {signaux.map(([cle, x]) => {
          const mesures = Object.entries(horizons)
            .filter(([k]) => x[k].mesurees)
            .map(([k, nom]) => `${nom} : ${x[k].battu} sur ${x[k].mesurees} (${points(x[k].ecart_moyen)})`);
          return (
            <div key={cle} className="rangee bloc res-signal">
              <span className="res-tete">
                <b>{fr(x.libelle)}</b>
              </span>
              <span className="res-sous">
                {fr(`${x.entrees} ${x.entrees > 1 ? "entrées" : "entrée"} · ${mesures.length ? mesures.join(" · ") : "pas encore mesuré"}`)}
              </span>
            </div>
          );
        })}
      </Groupe>
    );
  });
}

function CarteResultats() {
  const { donnees, pousser } = useApp();
  const r = donnees.resultats;
  if (!r || !r.lignes?.length) return null;
  const resume = resumeResultats(r);
  return (
    <>
      <div className="section-ligne">
        <h2 className="section">Résultats de Radar</h2>
        <button type="button" className="lien" onClick={() => pousser("resultats")}>
          Voir
        </button>
      </div>
      <button type="button" className="carte presse res-carte" onClick={() => pousser("resultats")}>
        <span className="pastille petite fond-accent">
          <Icone nom="tarte" taille={17} epaisseur={2} />
        </span>
        <span className="res-carte-texte">
          {resume ||
            fr(`${r.lignes.filter((l) => l.sens !== "ecartee").length} compagnies suivies. Premiers prix officiels de la SEC vers le ${dateLongue(r.prochains_prix_vers)}.`)}
        </span>
        <Icone nom="chevron-d" taille={18} epaisseur={2.2} className="chevron" />
      </button>
    </>
  );
}

function EcranResultats({ retour }) {
  const { donnees } = useApp();
  const r = donnees.resultats;
  if (!r) {
    return (
      <Ecran titre="Résultats" retour={retour}>
        <div className="carte">
          <Vide icone="tarte" titre="Résultats pas encore publiés" texte="Le robot les publie à son prochain passage." />
        </div>
      </Ecran>
    );
  }
  const lignes = r.lignes.filter((l) => l.sens !== "ecartee").reverse(); // les plus récentes d'abord
  const ecartees = r.lignes.filter((l) => l.sens === "ecartee").reverse(); // lot M : suivies à part
  return (
    <Ecran titre="Résultats" sousTitre="Radar a-t-il frappé juste ?" retour={retour}>
      <p className="explication">
        {fr("Chaque compagnie qui entre dans une liste est suivie avec les prix officiels de la SEC, 1 semaine et 1 mois plus tard, et comparée au marché (fonds qui suivent le S&P 500).")}
      </p>
      <Groupe titre="Taux de réussite" pied={r.prix_jusqu_au ? fr(`Prix de la SEC publiés jusqu'au ${dateLongue(r.prix_jusqu_au)}.`) : undefined}>
        {Object.entries(r.horizons).flatMap(([k, nom]) =>
          ["hausse", "baisse"].map((sens) => {
            const x = r.resume[`${sens}_${k}`];
            return (
              <Rangee key={`${k}-${sens}`} label={`${nom} · ${SENS_RESULTATS[sens].toLowerCase()}`}>
                <span className="rangee-valeur">
                  {x.mesurees ? `${x.battu} sur ${x.mesurees} · écart moyen ${points(x.ecart_moyen)}` : x.en_attente ? "en attente" : "aucune mesure"}
                </span>
              </Rangee>
            );
          }),
        )}
      </Groupe>
      {r.par_signal && <ParSignal p={r.par_signal} horizons={r.horizons} />}
      {r.resume.ecartee_7 && (
        <Groupe titre="Écartées : la règle des 100 M$ a-t-elle raison ?" pied={fr("Compagnies de moins de 100 M$ en bourse, hors de la liste « hausse » depuis la version 0.27, suivies de la même façon. La règle a raison quand la compagnie fait moins bien que le marché.")}>
          {Object.entries(r.horizons).map(([k, nom]) => {
            const x = r.resume[`ecartee_${k}`];
            return (
              <Rangee key={k} label={nom}>
                <span className="rangee-valeur">
                  {x.mesurees ? `${x.battu} sur ${x.mesurees} · écart moyen ${points(x.ecart_moyen)}` : x.en_attente ? "en attente" : "aucune mesure"}
                </span>
              </Rangee>
            );
          })}
        </Groupe>
      )}
      <Groupe titre={`Compagnies suivies (${lignes.length})`}>
        {lignes.map((l) => (
          <LigneResultat key={`${l.symbole}-${l.sens}-${l.entree}`} l={l} horizons={r.horizons} libelles={r.libelles_regles} />
        ))}
      </Groupe>
      {ecartees.length > 0 && (
        <Groupe titre={`Écartées suivies (${ecartees.length})`}>
          {ecartees.map((l) => (
            <LigneResultat key={`${l.symbole}-${l.sens}-${l.entree}`} l={l} horizons={r.horizons} libelles={r.libelles_regles} />
          ))}
        </Groupe>
      )}
      <Groupe titre="Comment c'est mesuré">
        {r.methode.map((m) => (
          <div key={m} className="rangee bloc">
            <span className="rangee-texte">{fr(m)}</span>
          </div>
        ))}
      </Groupe>
    </Ecran>
  );
}

// ---------- Argent : les vrais montants des dépôts officiels (robot : data/app/argent.json) ----------

// 254 540 → « 255 k$ US » ; 17 084 270 → « 17,1 M$ US » ; 2 000 000 000 → « 2 G$ US ».
function argentCourt(n, devise) {
  return new Intl.NumberFormat("fr-CA", {
    style: "currency", currency: devise || "USD", notation: "compact",
    minimumFractionDigits: 0, maximumFractionDigits: Math.abs(n) >= 1e9 ? 2 : 1,
  }).format(n);
}

// Le prix écrit dans le dépôt : 24.4061 → « 24,41 $ US ».
function prixAction(n, devise) {
  return new Intl.NumberFormat("fr-CA", { style: "currency", currency: devise || "USD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n);
}

function nombre(n) {
  return Math.round(n).toLocaleString("fr-CA");
}

function pourcent(n) {
  return `${n.toLocaleString("fr-CA", { maximumFractionDigits: n < 1 ? 2 : 1 })} %`;
}

const FAMILLES_ARGENT = [["tout", "Tout"], ["achats", "Achats"], ["ventes", "Ventes"], ["elus", "Élus"], ["contrats", "Contrats"], ["rachats", "Rachats"]];

function dansFamille(l, f) {
  if (f === "achats") return l.famille === "dirigeants" && l.sens > 0;
  if (f === "ventes") return (l.famille === "dirigeants" && l.sens < 0) || l.famille === "intentions";
  if (f === "elus") return l.famille === "elus";
  if (f === "contrats") return l.famille === "contrats";
  if (f === "rachats") return l.famille === "rachats";
  return true;
}

// La phrase d'une ligne : qui fait quoi, avec les chiffres du dépôt.
function phraseArgent(l) {
  const qui = l.role && l.famille !== "elus" ? `${l.qui} (${l.role})` : l.qui;
  if (l.famille === "dirigeants") {
    const verbe = l.sens > 0 ? "achète" : "vend";
    if (l.prix_multiples) return `${qui} ${verbe} : ${l.nb_lignes} lignes à des prix très différents (plusieurs titres)`;
    return `${qui} ${verbe} ${nombre(l.actions)} actions à ${prixAction(l.prix, l.devise)}`;
  }
  if (l.famille === "intentions") return `${qui} prévoit vendre ${nombre(l.actions)} actions (≈ ${prixAction(l.prix, l.devise)} l'action, avis 144 à la SEC)`;
  if (l.famille === "elus") return `${qui} ${l.sens > 0 ? "achète" : "vend"}${l.role === "options" ? " des options" : ""} · fourchette officielle`;
  if (l.famille === "rachats") {
    const quoi = { hausse: "Programme de rachat d'actions augmenté par le conseil", total: "Programme de rachat d'actions porté à ce total par le conseil" }[l.role] || "Nouveau programme de rachat d'actions autorisé par le conseil";
    return `${quoi} : un plafond, pas un achat fait`;
  }
  return `${l.qui}${l.role ? ` · ${l.role}` : ""}`;
}

function partArgent(l) {
  if (!l.part) return null;
  if (l.part.nouvelle) return "nouvelle position";
  if (l.part.pourcentage_compagnie != null) return `${pourcent(l.part.pourcentage_compagnie)} des actions de la compagnie`;
  return l.sens > 0 ? `+${pourcent(l.part.pourcentage)} de ses actions` : `${pourcent(l.part.pourcentage)} de ses actions vendues`;
}

function montantArgent(l) {
  if (l.montant != null) return argentCourt(l.montant, l.devise);
  if (l.montant_max == null) return `plus de ${argentCourt(l.montant_min, l.devise)}`;
  return `${argentCourt(l.montant_min, l.devise)} à ${argentCourt(l.montant_max, l.devise)}`;
}

function LigneArgent({ l, ouvrir }) {
  const genre = l.famille === "rachats" ? "rachat" : l.sens > 0 ? "achat" : l.sens < 0 ? "vente" : "contrat";
  const part = partArgent(l);
  return (
    <button type="button" className="ligne argent presse" onClick={() => ouvrir(l)}>
      <span className={`argent-sens ${genre}`}>
        <Icone nom={genre === "rachat" ? "rafraichir" : l.sens > 0 ? "fleche-haut" : l.sens < 0 ? "fleche-bas" : "document"} taille={18} epaisseur={2.4} />
      </span>
      <span className="ligne-centre">
        <span className="ligne-titre">
          {l.symbole && <span className="symbole">{l.symbole}</span>} {l.compagnie}
        </span>
        <span className="argent-phrase">{fr(phraseArgent(l))}</span>
        <span className="ligne-meta">
          <span>{dateCourte(l.publie)}</span>
          {part && <span>{fr(part)}</span>}
          {l.plan && <span className="argent-plan">planifiée d'avance</span>}
          {l.aussi?.length > 0 && <span>{`aussi déclarée par ${l.aussi.length}`}</span>}
        </span>
      </span>
      <span className={`argent-montant ${genre}`}>{montantArgent(l)}</span>
    </button>
  );
}

function Thermometre({ t }) {
  const achats = t.achats.montant;
  const ventes = t.ventes_libres.montant;
  const part = achats + ventes > 0 ? Math.round((achats / (achats + ventes)) * 100) : 50;
  return (
    <div className="carte thermo">
      <p className="thermo-titre">{fr(`Dirigeants, 7 derniers jours (depuis le ${dateCourte(t.depuis)})`)}</p>
      <div className="thermo-barre" role="img" aria-label={`Achats ${part} %, ventes décidées sur le moment ${100 - part} %`}>
        <span style={{ width: `${part}%` }} />
      </div>
      <div className="thermo-chiffres">
        <span className="t-vert">
          <b>
            <Defile valeur={achats} format={(n) => argentCourt(n)} />
          </b>{" "}
          achetés ({t.achats.nombre})
        </span>
        <span className="t-rouge">
          <b>
            <Defile valeur={ventes} format={(n) => argentCourt(n)} />
          </b>{" "}
          vendus ({t.ventes_libres.nombre})
        </span>
      </div>
      <p className="thermo-note">
        {fr(`Ventes planifiées d'avance (plan 10b5-1) : ${argentCourt(t.ventes_planifiees.montant)} (${t.ventes_planifiees.nombre}) — elles disent peu de choses. Intentions de vente (144) : ${argentCourt(t.intentions.montant)} (${t.intentions.nombre}).`)}
      </p>
    </div>
  );
}

// Les infos complètes ne se chargent qu'au premier toucher d'une ligne absente du fil.
let promesseInfosArgent = null;
function infosArgent() {
  promesseInfosArgent ??= fetch("./data/app/argent_infos.json", { cache: "no-store" })
    .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
    .catch((e) => {
      promesseInfosArgent = null;
      throw e;
    });
  return promesseInfosArgent;
}

const MAX_LIGNES_ARGENT = 60;

function EcranArgent() {
  const { donnees, ouvrirDetail } = useApp();
  const [etat, setEtat] = useState({ chargement: true, erreur: null, a: null });
  const [famille, setFamille] = useState("tout");
  const [periode, setPeriode] = useState("7");
  const [tout, setTout] = useState(false);
  const [ouverture, setOuverture] = useState(null);
  useEffect(() => {
    let fini = false;
    fetch("./data/app/argent.json", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then((a) => !fini && setEtat({ chargement: false, erreur: null, a }))
      .catch((e) => !fini && setEtat({ chargement: false, erreur: String(e.message || e), a: null }));
    return () => {
      fini = true;
    };
  }, []);
  const a = etat.a;
  const liste = useMemo(() => {
    if (!a) return [];
    const depuis = periode === "jour" ? a.dernier_jour : periode === "7" ? a.thermometre.depuis : a.depuis;
    return a.lignes.filter((l) => l.publie >= depuis && dansFamille(l, famille));
  }, [a, famille, periode]);
  const ouvrir = async (l) => {
    const ev = (donnees.fil || []).find((e) => e.id === l.id);
    if (ev) return ouvrirDetail(ev);
    setOuverture(l.id);
    try {
      const infos = await infosArgent();
      if (infos[l.id]) ouvrirDetail(infos[l.id]);
    } catch {
      /* hors ligne : la ligne reste affichée */
    } finally {
      setOuverture(null);
    }
  };
  const visibles = tout ? liste : liste.slice(0, MAX_LIGNES_ARGENT);
  return (
    <Ecran titre="Argent" sousTitre="Les vrais montants des dépôts officiels">
      {etat.chargement && <p className="explication">Chargement des montants…</p>}
      {etat.erreur && (
        <div className="carte">
          <Vide icone="alerte" titre="Montants indisponibles" texte={etat.erreur} />
        </div>
      )}
      {a && (
        <>
          <Thermometre t={a.thermometre} />
          <div className="puces" role="tablist" aria-label="Genre de transaction">
            {FAMILLES_ARGENT.map(([k, label]) => (
              <button key={k} type="button" role="tab" aria-selected={famille === k} className={famille === k ? "puce actif" : "puce"} onClick={() => { setFamille(k); setTout(false); }}>
                {label}
              </button>
            ))}
          </div>
          <Segments
            valeur={periode}
            onChange={(v) => { setPeriode(v); setTout(false); }}
            label="Période"
            options={[["jour", `Dernier jour${a.dernier_jour ? ` (${dateCourte(a.dernier_jour)})` : ""}`], ["7", "7 jours"], ["30", "30 jours"]]}
          />
          <p className="explication">
            {fr(
              famille === "rachats"
                ? `${liste.length} annonce${liste.length > 1 ? "s" : ""} de rachat d'actions, du plus gros plafond au plus petit. Un plafond autorisé par le conseil, pas un achat fait : la compagnie peut racheter moins, ou rien. 0 point dans la note.`
                : `${liste.length} transaction${liste.length > 1 ? "s" : ""}, du plus gros montant au plus petit${liste.some((l) => l.famille === "rachats") ? " (les rachats annoncés sont des plafonds, pas des achats faits)" : ""}. Touchez une ligne pour le document officiel.`,
            )}
          </p>
          {liste.length === 0 ? (
            <div className="carte">
              <Vide icone="billet" titre="Rien pour cette période" texte="Essaie 30 jours ou un autre genre." />
            </div>
          ) : (
            <div className={ouverture ? "carte liste attente" : "carte liste"}>
              {visibles.map((l) => (
                <LigneArgent key={l.id} l={l} ouvrir={ouvrir} />
              ))}
            </div>
          )}
          {!tout && liste.length > MAX_LIGNES_ARGENT && (
            <button type="button" className="bouton-second presse plein" onClick={() => setTout(true)}>
              {`Voir les ${liste.length - MAX_LIGNES_ARGENT} autres`}
            </button>
          )}
          <p className="avertissement">{fr(`${a.seuils} Pas de cours de bourse en direct : les prix sont ceux écrits dans les dépôts.`)}</p>
        </>
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
        <RangeeLien icone="antenne" couleur="bleu" label="État des sources" valeur={`${sourcesAffichees(donnees.sources).length} sources`} onClick={() => pousser("sources")} />
        <RangeeLien icone="alerte" couleur="jaune" label="À vérifier" valeur={donnees.a_verifier.length} onClick={() => pousser("a_verifier")} />
        <RangeeLien icone="info" couleur="accent" label="Comment marche Radar (aide)" onClick={() => pousser("aide")} />
        <RangeeLien icone="bouclier-ok" couleur="vert" label="Comment c'est vérifié" onClick={() => pousser("verification")} />
        <RangeeLien icone="tarte" couleur="accent" label="Comment le score est calculé" onClick={() => pousser("methode")} />
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
  const sources = sourcesAffichees(donnees.sources);
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
                <a key={s.id} className="source presse" href={s.site} target="_blank" rel="noopener noreferrer">
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

// ---------- Aide : comment marche Radar (les chiffres viennent des fichiers du robot) ----------

const PASSAGES_AIDE = [
  ["Matin", "7 h 07"], ["Jour", "9 h 47"], ["Midi", "12 h 37"], ["Soir", "18 h 17"], ["Nuit", "23 h 17"],
];

const DELAIS_AIDE = [
  ["Dirigeants (formulaire 4)", "2 jours ouvrables après la transaction"],
  ["Avis de vente (formulaire 144)", "au moment de l'ordre de vente"],
  ["Fonds activistes (13D)", "5 jours ouvrables après avoir passé 5 % des actions"],
  ["Grands fonds (13F)", "jusqu'à 45 jours après la fin du trimestre"],
  ["Élus du Congrès", "jusqu'à 45 jours après la transaction"],
  ["Contrats de la Défense (USAspending)", "publiés avec 90 jours de délai"],
  ["Fins de blocage (prospectus 424B4)", "dates prévues ; les banques peuvent lever le blocage plus tôt"],
  ["Rachats d'actions (8-K)", "un plafond, pas un achat ; les rachats faits arrivent dans le rapport annuel, jusqu'à 90 jours après la fin de l'exercice"],
  ["Santé financière (rapport annuel)", "jusqu'à 90 jours après la fin de l'exercice (4 mois pour une compagnie étrangère, rapport 20-F) ; le score change une fois par année"],
];

function EcranAide({ retour }) {
  const { donnees, pousser } = useApp();
  const sources = donnees.sources || [];
  const branchees = sourcesAffichees(sources).length;
  const m = donnees.aujourdhui?.methode || {};
  const etapes = [
    ["antenne", "Sources officielles", `${branchees} sources branchées : SEC, Congrès, Trésor, Maison-Blanche, gouvernement du Canada…`],
    ["radar", "Robots", "5 passages par jour de semaine. Ils respectent les règles de chaque site et attendent entre deux lectures."],
    ["bouclier-ok", "Contrôles", "Chaque info reçoit un badge : Officiel, Confirmé ou À vérifier. Une info « À vérifier » ne compte jamais."],
    ["double", "Labo", "Un programme à part relit les documents officiels et refait le calcul, sans rien prendre du robot."],
    ["tarte", "Note", "Les points des études deviennent une note sur 10 : Radar, Argent et Fil."],
  ];
  return (
    <Ecran titre="Aide" sousTitre="Comment marche Radar" retour={retour}>
      <p className="explication">{fr("Radar lit seulement des sources officielles et montre où va le gros argent, preuves à l'appui. Rien plutôt que faux. Pas un conseil financier.")}</p>

      <ol className="carte flux" aria-label="Le chemin d'une info, des sources officielles à la note">
        <span className="flux-ligne" aria-hidden="true">
          <span className="flux-point" />
        </span>
        {etapes.map(([icone, titre, texte], i) => (
          <li key={titre} className="flux-etape" style={{ "--i": i }}>
            <span className="flux-icone">
              <Icone nom={icone} taille={18} epaisseur={2.2} />
            </span>
            <span className="flux-texte">
              <b>{`${i + 1}. ${titre}`}</b>
              <span>{fr(texte)}</span>
            </span>
          </li>
        ))}
      </ol>

      <Groupe titre="Les robots" pied="Heure de l'Est en été ; une heure plus tôt en hiver. Le passage de nuit lit les dépôts de la SEC de la journée.">
        <div className="rangee bloc">
          <span className="rangee-texte">{fr("Chaque source a son lecteur. Il lit la page, le fichier ou l'API officielle, garde le lien, le numéro officiel et l'empreinte du document. Il s'identifie comme « Radar projet personnel » et respecte les robots.txt. Les tests passent avant chaque passage : s'ils échouent, rien n'est publié.")}</span>
        </div>
        <div className="passages">
          {PASSAGES_AIDE.map(([nom, heure]) => (
            <span key={nom} className="passage">
              <b>{heure}</b>
              {nom}
            </span>
          ))}
        </div>
        <RangeeLien icone="antenne" couleur="bleu" label="État des sources" valeur={`${branchees} branchées`} onClick={() => pousser("sources")} />
      </Groupe>

      <Groupe titre="Une info vérifiée">
        {Object.entries(BADGES).map(([code, b]) => (
          <div key={code} className="rangee bloc">
            <Badge code={code} grand />
            <span className="rangee-texte">{b.texte}</span>
          </div>
        ))}
        <div className="rangee bloc">
          <span className="rangee-texte">{fr("Le labo : un programme séparé relit les documents officiels (ex. chaque formulaire 4 à la SEC), refait le score de son côté et vérifie le vrai site, photos à l'appui. Il tourne à chaque changement de Radar.")}</span>
        </div>
        <RangeeLien icone="bouclier-ok" couleur="vert" label="Comment c'est vérifié" onClick={() => pousser("verification")} />
      </Groupe>

      <Groupe titre="Regroupées par compagnie">
        <div className="rangee bloc">
          <span className="rangee-texte">{fr("Chaque info est reliée à une compagnie par la liste officielle des symboles de la SEC, puis classée par famille : dirigeants, fonds activistes, grands fonds, élus, FDA, SEC, rappels, la compagnie elle-même. La même transaction déclarée par plusieurs entités liées compte une seule fois ; le même acte publié par deux sources devient « Confirmé ».")}</span>
        </div>
      </Groupe>

      <Groupe titre="La note sur 10">
        {[m.resume, m.temps, m.familles, m.bonus, m.taille, m.trop_petites, m.routiniers, m.note10, m.seuil, m.recent].filter(Boolean).map((t) => (
          <div key={t} className="rangee bloc">
            <span className="rangee-texte">{fr(t)}</span>
          </div>
        ))}
        <RangeeLien icone="tarte" couleur="accent" label="Comment le score est calculé" onClick={() => pousser("methode")} />
      </Groupe>

      <Groupe titre="L'onglet Argent">
        <div className="rangee bloc">
          <span className="rangee-texte">{fr("Les vrais montants des dépôts officiels des 30 derniers jours : nombre d'actions × prix écrit dans le dépôt, pourcentage de leurs actions quand le dépôt le permet, fourchettes officielles pour les élus. Le cours de l'action : bouton « Voir le cours » sur la fiche.")}</span>
        </div>
        <div className="rangee bloc">
          <span className="rangee-texte">{fr("Rachats : quand le conseil d'une compagnie autorise un rachat de ses actions (8-K), le plafond annoncé, pas un achat fait. Le robot publie seulement une phrase claire : le conseil, une formule d'autorisation, un montant, un signe que c'est récent (une date de moins de 30 jours, « today »), rien d'un ancien programme ; et il vérifie que la compagnie ne l'avait pas déjà annoncé dans ses 8-K des 90 jours avant. 0 point dans la note : l'étude d'Ikenberry, Lakonishok et Vermaelen trouve l'effet surtout pour les actions bon marché. Sur la fiche : les rachats vraiment faits, selon le rapport annuel.")}</span>
        </div>
        <div className="rangee bloc">
          <a className="etude" href="https://www.nber.org/papers/w4965" target="_blank" rel="noopener noreferrer">
            <Icone nom="document" taille={16} epaisseur={2} />
            <span>
              <b>Ikenberry, Lakonishok et Vermaelen (1995)</b>
              {fr(" : annonces de 1980 à 1990 ; +12,1 % sur 4 ans par rapport à des actions comparables, +45,3 % pour les actions bon marché, rien pour les chères.")}
            </span>
          </a>
        </div>
        <div className="rangee bloc">
          <span className="rangee-texte">{fr("Santé financière : sur la fiche, 9 critères tirés du dernier rapport annuel (profits, argent réel, dette, liquidité, actions émises, marge brute, ventes par dollar d'actif), quand les 9 se calculent avec les données de la SEC. 0 point dans la note.")}</span>
        </div>
        <div className="rangee bloc">
          <a className="etude" href="https://www.ivey.uwo.ca/media/3775523/value_investing_the_use_of_historical_financial_statement_information.pdf" target="_blank" rel="noopener noreferrer">
            <Icone nom="document" taille={16} epaisseur={2} />
            <span>
              <b>Piotroski (2000)</b>
              {fr(" : chez les actions bon marché (1976 à 1996), garder les compagnies solides ajoutait au moins 7,5 % par an.")}
            </span>
          </a>
        </div>
      </Groupe>

      <Groupe titre="Les résultats de Radar">
        <div className="rangee bloc">
          <span className="rangee-texte">{fr("Chaque compagnie qui entre dans une liste est suivie avec les prix officiels de la SEC (clôture de la veille, publiée 2 à 4 semaines plus tard), 1 semaine et 1 mois après, et comparée au marché. Les cas douteux (pas de prix, nouveau code de titre, saut anormal) sont montrés mais pas comptés.")}</span>
        </div>
        <div className="rangee bloc">
          <span className="rangee-texte">{fr("Depuis le 5 octobre 2026, chaque entrée garde ses raisons (achat d'un dirigeant, groupe d'achats, petite compagnie, bonus de familles…) : la page montre le taux de réussite de chaque signal, pour savoir lesquels marchent vraiment.")}</span>
        </div>
        <RangeeLien icone="tarte" couleur="accent" label="Voir les résultats" onClick={() => pousser("resultats")} />
      </Groupe>

      <Groupe titre="Le calendrier">
        <div className="rangee bloc">
          <span className="rangee-texte">{fr("Après une entrée en bourse, les dirigeants et les anciens actionnaires s'engagent à ne pas vendre pendant une période (souvent 180 jours). Le robot lit chaque prospectus final et publie la fin seulement si tout est écrit clairement. Information seulement : 0 point dans la note.")}</span>
        </div>
        <RangeeLien icone="calendrier" couleur="accent" label="Voir le calendrier" onClick={() => pousser("calendrier")} />
      </Groupe>

      <Groupe titre="Bon à savoir">
        {DELAIS_AIDE.map(([qui, delai]) => (
          <div key={qui} className="rangee bloc delai">
            <span className="rangee-texte">
              <b>{qui}</b> : {fr(delai)}
            </span>
          </div>
        ))}
        <div className="rangee bloc">
          <span className="rangee-texte">{fr("La note mesure la force des preuves officielles, pas une promesse de hausse : les études parlent de moyennes sur beaucoup de transactions. Certaines sources sont pour un usage personnel seulement.")}</span>
        </div>
      </Groupe>
      <p className="avertissement">{m.avertissement || "Pas un conseil financier."}</p>
    </Ecran>
  );
}

// ---------- App ----------

const ONGLETS = [
  { id: "accueil", label: "Radar", icone: "radar" },
  { id: "argent", label: "Argent", icone: "billet" },
  { id: "fil", label: "Fil", icone: "fil" },
  { id: "favoris", label: "Favoris", icone: "etoile" },
  { id: "reglages", label: "Réglages", icone: "reglages" },
];
const PAGES = {
  sources: EcranSources,
  a_verifier: EcranAVerifier,
  verification: EcranVerification,
  suggestions: EcranSuggestions,
  compagnie: EcranCompagnie,
  methode: EcranMethode,
  aide: EcranAide,
  calendrier: EcranCalendrier,
  resultats: EcranResultats,
};

// « Nouveau » : entrée dans les listes depuis la dernière visite (1re visite : depuis 24 h).
const CLE_VU = "radar-suggestions-vues";
function useDerniereVisite() {
  const [vu] = useState(() => lireJSON(CLE_VU, Date.now() - 864e5));
  useEffect(() => {
    const partir = () => document.visibilityState === "hidden" && ecrireJSON(CLE_VU, Date.now());
    document.addEventListener("visibilitychange", partir);
    return () => document.removeEventListener("visibilitychange", partir);
  }, []);
  return vu;
}
const TITRES_ONGLETS = { accueil: "Radar", argent: "Argent", fil: "Fil", favoris: "Favoris", reglages: "Réglages" };

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
  const [compagnie, setCompagnie] = useState(null);
  const [vueSuggestions, setVueSuggestions] = useState("hausse");
  const derniereVisite = useDerniereVisite();
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
  const ouvrirCompagnie = (symbole) => {
    setCompagnie(symbole);
    pousser("compagnie");
  };
  const ouvrirSuggestions = (vue) => {
    setVueSuggestions(vue);
    pousser("suggestions");
  };
  const estNouveau = (s) => Boolean(s.depuis) && Date.parse(s.depuis) > derniereVisite;
  const noms = useMemo(() => Object.fromEntries((donnees?.sources || []).map((s) => [s.id, s.nom])), [donnees]);

  const valeur = {
    donnees, chargement, charger, reglages, setReglages, favoris, basculerFavori, noms, ouvrirDetail: setDetail, pousser,
    compagnie, ouvrirCompagnie, vueSuggestions, setVueSuggestions, ouvrirSuggestions, estNouveau,
  };
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
  } else if (onglet === "argent") {
    contenu = <EcranArgent />;
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
  --radar-hausse: #1DAA80; --radar-baisse: #EE4F5C; --ligne-radar: rgba(255,255,255,.13);
  --barre: rgba(12,15,21,.92); --ombre: 0 12px 40px rgba(0,0,0,.5); --segment: #2A3142; --inter-off: #2B3142;
  color-scheme: dark;
}
[data-theme="clair"] {
  --fond: #F2F3F7; --fond-2: #FFFFFF; --carte: #FFFFFF; --carte-2: #EEF0F5; --ligne: rgba(15,23,42,.08);
  --texte: #0B1220; --texte-2: #586274; --texte-3: #8D95A5;
  --vert: #0E9F74; --jaune: #B97509; --rouge: #E5484D; --bleu: #2F6BEA; --gris: #A3AAB8; --violet: #7A5AF0; --cyan: #0A93C4; --olive: #5A9618;
  --radar-hausse: #0E9F74; --radar-baisse: #E5484D; --ligne-radar: rgba(15,23,42,.14);
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
.t-rouge { color: var(--rouge); }
.score-pastille { flex: none; min-width: 50px; height: 34px; padding: 0 8px; border-radius: 11px; display: inline-flex; align-items: center; justify-content: center;
  font-weight: 750; font-variant-numeric: tabular-nums; background: color-mix(in srgb, var(--vert) 16%, transparent); color: var(--vert); }
.score-pastille.baisse { background: color-mix(in srgb, var(--rouge) 16%, transparent); color: var(--rouge); }
.suggestion .ligne-titre .symbole { margin-right: 2px; vertical-align: 1px; }
.nouveau { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: .6875rem; font-weight: 700; background: var(--accent); color: #fff; margin-left: 6px; }
.ligne-meta .nouveau { margin-left: 0; }
.score-pastille small { font-size: .625rem; font-weight: 600; opacity: .75; margin-left: 1px; }
.recent { display: inline-block; padding: 1px 7px; border-radius: 999px; font-size: .6875rem; font-weight: 700; color: var(--vert); border: 1px solid color-mix(in srgb, var(--vert) 55%, transparent); margin-left: 6px; }
.ligne-meta .recent { margin-left: 0; }
.fiche-points { margin: 0; color: var(--texte-2); font-size: .875rem; font-weight: 600; font-variant-numeric: tabular-nums; }
.calcul-total small { display: block; margin-top: 2px; color: var(--texte-3); font-weight: 500; font-size: .8125rem; }
.alerte-baisse { width: 100%; display: flex; align-items: center; gap: 10px; padding: 13px 14px; margin-top: 10px; font-size: .9375rem; font-weight: 600; text-align: left; }
.alerte-baisse span { flex: 1; }
.fiche { padding: 18px 16px; text-align: center; }
.fiche-nom { margin: 0; color: var(--texte-2); font-weight: 600; }
.fiche-score { margin: 6px 0 0; font-size: 2.5rem; font-weight: 800; letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
.fiche-score small { font-size: 1rem; font-weight: 600; color: var(--texte-2); letter-spacing: 0; }
.fiche-sens { margin: 2px 0 14px; color: var(--texte-2); font-size: .9375rem; }
.section-points { font-weight: 700; margin-right: 6px; font-variant-numeric: tabular-nums; }
.raison-points { flex: none; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--texte); }
.raison-points.pas-compte { color: var(--texte-3); font-weight: 500; }
.calcul { padding: 10px 16px; margin-top: 16px; font-size: .875rem; color: var(--texte-2); }
.calcul p { margin: 4px 0; }
.calcul-total { color: var(--texte); font-weight: 700; font-size: .9375rem; }
.regle-haut { display: flex; justify-content: space-between; gap: 12px; align-items: baseline; }
.regle-points { font-weight: 750; font-variant-numeric: tabular-nums; white-space: nowrap; }
.regle-details { margin: 0; padding-left: 18px; color: var(--texte-2); font-size: .875rem; line-height: 1.45; }
.etude { display: flex; gap: 8px; align-items: flex-start; color: var(--texte-2); font-size: .8125rem; line-height: 1.4; }
.etude svg { flex: none; color: var(--accent); margin-top: 1px; }
.etude b { color: var(--accent); font-weight: 600; }
.bloc-lien { display: block; margin: 20px auto 0; }
.symbole-grand.bouton-favori { font-family: inherit; font-weight: 600; } /* plus précis que .symbole-grand (police à chasse fixe) */
.fiche-boutons { display: flex; flex-wrap: wrap; justify-content: center; gap: 8px; }
.symbole-grand.bouton-cours { font-family: inherit; font-weight: 600; text-decoration: none; }
.fiche-cours-source { margin: 8px 0 0; color: var(--texte-3); font-size: .75rem; }

/* Catégories */
.grille-cat { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.cat { position: relative; display: flex; flex-direction: column; align-items: flex-start; gap: 10px; padding: 12px; text-align: left;
  background: var(--carte); border: 1px solid var(--ligne); border-radius: var(--rayon); min-width: 0; }
.cat-label { font-size: .8125rem; font-weight: 600; line-height: 1.2; }
.cat-nombre { position: absolute; top: 12px; right: 12px; color: var(--texte-3); font-size: .875rem; font-weight: 650; font-variant-numeric: tabular-nums; }
.cat-phase { position: absolute; top: 12px; right: 10px; color: var(--texte-3); font-size: .6875rem; font-weight: 650; letter-spacing: .02em; text-transform: uppercase; }

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

/* Calendrier (fins de blocage) */
.cal-date { flex: none; width: 36px; height: 40px; border-radius: 10px; display: flex; flex-direction: column; align-items: center;
  justify-content: center; background: color-mix(in srgb, var(--accent) 14%, transparent); color: var(--accent); }
.cal-jour { font-size: 1rem; font-weight: 700; line-height: 1; font-variant-numeric: tabular-nums; }
.cal-mois { font-size: .625rem; font-weight: 700; line-height: 1; text-transform: uppercase; letter-spacing: .04em; margin-top: 3px; }
.cal-sous { color: var(--texte-2); font-size: .75rem; }
.cal-ligne.passee .cal-date { background: var(--carte-2); color: var(--texte-2); }

/* Résultats de Radar */
.res-carte { width: 100%; display: flex; align-items: center; gap: 12px; padding: 14px; text-align: left; }
.res-carte-texte { flex: 1; font-size: .9375rem; font-weight: 600; line-height: 1.35; }
.res-ligne { display: flex; flex-direction: column; align-items: flex-start; gap: 5px; }
.res-signal { display: flex; flex-direction: column; align-items: flex-start; gap: 3px; }
.res-tete { font-size: .9375rem; line-height: 1.3; }
.res-tete .symbole { margin-right: 2px; vertical-align: 1px; }
.res-sous { color: var(--texte-2); font-size: .8125rem; }
.res-horizon { font-size: .8125rem; line-height: 1.35; padding: 6px 9px; border-radius: 10px; background: var(--carte-2); }
.res-horizon.vert { color: var(--vert); background: color-mix(in srgb, var(--vert) 13%, transparent); }
.res-horizon.rouge { color: var(--rouge); background: color-mix(in srgb, var(--rouge) 12%, transparent); }
.res-horizon.jaune { color: var(--jaune); background: color-mix(in srgb, var(--jaune) 13%, transparent); }
.res-horizon b { color: var(--texte); }

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
.point.violet { background: var(--violet); }
.source { position: relative; display: flex; align-items: center; gap: 12px; padding: 12px 16px; color: var(--texte); }
.source + .source::before { left: 37px; }
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
.detail-resume { color: var(--texte-2); margin: 10px 0 0; font-size: .9375rem; line-height: 1.45; }
.transaction { position: relative; display: flex; justify-content: space-between; align-items: baseline; gap: 12px; padding: 11px 16px; font-size: .9375rem; }
.transaction + .transaction::before { content: ""; position: absolute; top: 0; left: 16px; right: 0; height: 1px; background: var(--ligne); transform: scaleY(.5); }
.transaction-qui { color: var(--texte-2); min-width: 0; }
.transaction-montant { color: var(--texte); font-weight: 600; font-variant-numeric: tabular-nums; text-align: right; white-space: nowrap; }
.congres-chef { padding: 11px 16px; font-size: .9375rem; color: var(--texte-2); }
.ligne-oge { position: relative; padding-bottom: 10px; }
.ligne-oge + .ligne-oge::before { content: ""; position: absolute; top: 0; left: 16px; right: 0; height: 1px; background: var(--ligne); transform: scaleY(.5); }
.ligne-oge .transaction { padding-bottom: 2px; }
.ligne-oge .transaction-qui { display: inline-flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.ligne-oge-desc { margin: 0; padding: 0 16px; color: var(--texte); font-size: .875rem; line-height: 1.4; overflow-wrap: anywhere; }
.ligne-oge-note { margin: 4px 0 0; padding: 0 16px; color: var(--texte-2); font-size: .8125rem; line-height: 1.4; }
.congres-source, .rachats-source, .sante-source, .taille-source { color: var(--texte-3); font-size: .75rem; margin: 8px 4px 0; line-height: 1.5; }
.sante .accn { white-space: nowrap; } /* le numéro du rapport reste entier (pas coupé au trait d'union) */
.sante-total { margin: 0; padding: 14px 16px 0; text-align: center; font-size: 2.25rem; font-weight: 750; font-variant-numeric: tabular-nums; }
.sante-total small { font-size: 1rem; font-weight: 600; color: var(--texte-3); }
.sante-texte { margin: 2px 16px 12px; text-align: center; color: var(--texte-2); font-size: .875rem; line-height: 1.4; }
.critere { display: flex; align-items: flex-start; gap: 10px; padding: 10px 16px; border-top: 1px solid var(--ligne); }
.critere svg { flex: none; margin-top: 2px; }
.critere.oui svg { color: var(--vert); }
.critere.non svg { color: var(--texte-3); }
.critere-texte { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.critere-titre { font-size: .9375rem; font-weight: 600; color: var(--texte); }
.critere.non .critere-titre { color: var(--texte-2); }
.critere-detail { font-size: .8125rem; color: var(--texte-3); font-variant-numeric: tabular-nums; }
.lobbying-total, .rachats-total { margin: 0; padding: 12px 16px 0; font-size: 1.375rem; font-weight: 750; font-variant-numeric: tabular-nums; }
.lobbying-texte, .rachats-texte { margin: 0; padding: 8px 16px 12px; color: var(--texte-2); font-size: .9375rem; line-height: 1.45; }
.lobbying-sujets { margin: 0; padding: 0 16px 12px; font-size: .875rem; line-height: 1.45; }
.lobbying .transaction, .rachats-faits .transaction { color: inherit; text-decoration: none; }
.lobbying-sujets + .transaction::before, .lobbying-texte + .transaction::before, .rachats-texte + .transaction::before { content: ""; position: absolute; top: 0; left: 16px; right: 0; height: 1px; background: var(--ligne); transform: scaleY(.5); }
.congres-chef + .transaction::before { content: ""; position: absolute; top: 0; left: 16px; right: 0; height: 1px; background: var(--ligne); transform: scaleY(.5); }
.congres-chef.est-chef { color: var(--texte); background: color-mix(in srgb, var(--violet) 14%, transparent); }
.congres .transaction-qui { overflow-wrap: anywhere; }
.carte-projet { display: flex; flex-direction: column; gap: 4px; padding: 14px 16px; margin: 0 0 6px; color: var(--texte);
  border-color: color-mix(in srgb, var(--violet) 40%, var(--ligne)); }
.carte-projet-haut { display: flex; align-items: center; gap: 6px; color: var(--violet); font-size: .8125rem; font-weight: 600; }
.carte-projet-titre { font-size: 1.0625rem; font-weight: 700; letter-spacing: -.01em; }
.carte-projet-etape { font-size: .9375rem; font-weight: 600; }
.carte-projet-vote { color: var(--texte-2); font-size: .8125rem; line-height: 1.4; }
.carte-projet-pied { display: inline-flex; align-items: center; gap: 4px; margin-top: 4px; color: var(--accent); font-size: .8125rem; font-weight: 500; }
.detail-note { display: flex; gap: 8px; align-items: flex-start; margin: 12px 0 0; padding: 10px 12px; border-radius: 12px; font-size: .875rem;
  background: color-mix(in srgb, var(--jaune) 14%, transparent); color: var(--jaune); }
.detail-actions { display: grid; grid-template-columns: 1fr auto; gap: 10px; margin-top: 20px; }
.detail-pied { color: var(--texte-3); font-size: .75rem; margin: 14px 4px 0; line-height: 1.6; word-break: break-all; }
.detail-pied .mention { word-break: normal; overflow-wrap: break-word; }
.detail-pied .mention a { color: inherit; }
.detail-officiel { position: relative; display: flex; flex-direction: column; gap: 2px; padding: 10px 16px; }
.detail-officiel + .detail-officiel::before { content: ""; position: absolute; top: 0; left: 16px; right: 0; height: 1px; background: var(--ligne); transform: scaleY(.5); }
.detail-officiel-nom { color: var(--texte-3); font-size: .75rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
.detail-officiel-valeur { color: var(--texte); font-size: .9375rem; line-height: 1.4; overflow-wrap: anywhere; }
.controle { position: relative; display: flex; align-items: center; gap: 10px; padding: 11px 16px; font-size: .9375rem; color: var(--texte); }
.controle svg:first-child { flex: none; }
.controle.ok svg:first-child { color: var(--vert); }
.controle.rate { color: var(--rouge); font-weight: 600; }
.etapes { list-style: none; padding: 0; margin: 6px 0 0; }
.etapes li { display: flex; align-items: center; gap: 12px; padding: 10px 0; font-size: 1rem; flex-wrap: wrap; }
.etape-num { flex: none; width: 28px; height: 28px; border-radius: 14px; display: inline-flex; align-items: center; justify-content: center; background: var(--accent); color: #fff; font-weight: 700; font-size: .875rem; }
.icone-inline { display: inline-flex; color: var(--accent); }

/* Radar de l'accueil (couleurs validées pour les daltoniens avec la forme : rond = hausse, losange = baisse) */
.radar-carte { padding: 18px 16px 12px; display: flex; flex-direction: column; align-items: center; gap: 12px; }
.radar { position: relative; width: min(100%, 300px); aspect-ratio: 1; border-radius: 50%; isolation: isolate;
  background: radial-gradient(circle, color-mix(in srgb, var(--radar-hausse) 9%, transparent), transparent 72%); }
.radar-grille { position: absolute; inset: 0; width: 100%; height: 100%; fill: none; stroke: var(--ligne-radar); stroke-width: .35; }
.radar-masque { position: absolute; inset: 0; border-radius: 50%; overflow: hidden; z-index: 0; pointer-events: none; }
.radar-balai { position: absolute; inset: 0; border-radius: 50%; z-index: 0; pointer-events: none;
  background: conic-gradient(from 0deg, transparent 0deg 285deg, color-mix(in srgb, var(--radar-hausse) 24%, transparent) 352deg, color-mix(in srgb, var(--radar-hausse) 55%, transparent) 360deg);
  animation: balayage 4s linear infinite; will-change: transform; }
@keyframes balayage { to { transform: rotate(360deg); } }
.radar-cible { position: absolute; z-index: 1; width: 44px; height: 44px; margin: -22px 0 0 -22px; display: flex; align-items: center; justify-content: center; }
.radar-marque { width: 10px; height: 10px; border-radius: 50%; color: var(--radar-hausse); background: currentColor; box-shadow: 0 0 0 2px var(--carte);
  animation: eclat 4s linear infinite; animation-delay: var(--delai, 0s); }
@keyframes eclat { 0% { opacity: 1; box-shadow: 0 0 0 2px var(--carte), 0 0 14px 4px currentColor; } 55%, 100% { opacity: .6; box-shadow: 0 0 0 2px var(--carte); } }
.radar-etiquette { position: absolute; left: 50%; top: 50%; font-size: .6875rem; font-weight: 700; letter-spacing: .02em; color: var(--texte-2); white-space: nowrap; pointer-events: none; }
.radar-legende { margin: 0; display: flex; flex-wrap: wrap; align-items: center; justify-content: center; gap: 4px 6px; font-size: .75rem; color: var(--texte-2); }
.legende-marque { display: inline-block; width: 8px; height: 8px; margin-left: 4px; border-radius: 50%; background: var(--radar-hausse); }
.legende-texte { flex-basis: 100%; text-align: center; color: var(--texte-3); }

/* Anneau de la note (fiche) */
.anneau { position: relative; width: 132px; height: 132px; margin: 6px auto 0; }
.anneau svg { width: 100%; height: 100%; transform: rotate(-90deg); }
.anneau-fond { fill: none; stroke: var(--carte-2); stroke-width: 10; }
.anneau-valeur { fill: none; stroke-width: 10; stroke-linecap: round; stroke-dasharray: var(--tour); stroke-dashoffset: var(--reste); animation: remplir .9s cubic-bezier(.2, .8, .2, 1) backwards; }
.anneau-valeur.hausse { stroke: var(--radar-hausse); } .anneau-valeur.baisse { stroke: var(--radar-baisse); }
@keyframes remplir { from { stroke-dashoffset: var(--tour); } }
.anneau-texte { position: absolute; inset: 0; margin: 0; display: flex; align-items: center; justify-content: center; font-size: 2.25rem; font-weight: 800; letter-spacing: -.02em; font-variant-numeric: tabular-nums; color: var(--texte); }
.anneau-texte small { align-self: center; margin: 10px 0 0 2px; font-size: .9375rem; font-weight: 600; color: var(--texte-2); letter-spacing: 0; }

/* Listes qui glissent à l'arrivée (seulement au début : « backwards », l'effet de pression reste) */
.carte.liste > * { animation: glisse .28s ease-out backwards; }
.carte.liste > :nth-child(2) { animation-delay: .03s; } .carte.liste > :nth-child(3) { animation-delay: .06s; }
.carte.liste > :nth-child(4) { animation-delay: .09s; } .carte.liste > :nth-child(5) { animation-delay: .12s; }
.carte.liste > :nth-child(n+6) { animation-delay: .15s; }
@keyframes glisse { from { opacity: 0; transform: translateY(6px); } }

/* Réglage iPhone « Réduire les animations » : tout reste immobile */
@media (prefers-reduced-motion: reduce) {
  .radar-balai, .radar-marque, .anneau-valeur, .carte.liste > *, .radar-point { animation: none !important; }
  .radar-balai { opacity: .4; transform: rotate(40deg); }
}

/* Aide : le chemin d'une info (un point descend le long de la ligne) */
.boutons-haut { display: inline-flex; gap: 8px; }
.flux { position: relative; list-style: none; margin: 0; padding: 14px 16px 14px 14px; display: flex; flex-direction: column; gap: 14px; }
.flux-ligne { position: absolute; left: 31px; top: 30px; bottom: 30px; width: 2px; border-radius: 1px; background: var(--ligne-radar); overflow: hidden; }
.flux-point { position: absolute; left: -3px; top: 0; width: 8px; height: 26px; border-radius: 4px;
  background: linear-gradient(to bottom, transparent, var(--accent)); animation: descente 2.6s ease-in-out infinite; }
@keyframes descente { from { top: -26px; } to { top: 100%; } }
.flux-etape { position: relative; display: flex; gap: 12px; align-items: flex-start; animation: glisse .3s ease-out backwards; animation-delay: calc(var(--i) * 70ms); }
.flux-icone { flex: none; z-index: 1; width: 36px; height: 36px; border-radius: 12px; display: inline-flex; align-items: center; justify-content: center;
  background: var(--carte-2); color: var(--accent); box-shadow: 0 0 0 3px var(--carte); }
.flux-texte { display: flex; flex-direction: column; gap: 2px; padding-top: 1px; font-size: .875rem; line-height: 1.4; color: var(--texte-2); }
.flux-texte b { color: var(--texte); font-size: .9375rem; }
.passages { display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; padding: 4px 16px 12px; }
.passage { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 8px 2px; border-radius: 10px; background: var(--carte-2); font-size: .6875rem; color: var(--texte-2); }
.passage b { color: var(--texte); font-size: .8125rem; font-variant-numeric: tabular-nums; }
.delai .rangee-texte b { color: var(--texte); }
@media (prefers-reduced-motion: reduce) { .flux-point, .flux-etape { animation: none !important; } .flux-point { top: 40%; } }

/* Argent */
.argent { align-items: flex-start; }
.argent-sens { flex: none; width: 34px; height: 34px; margin-top: 2px; border-radius: 11px; display: inline-flex; align-items: center; justify-content: center; }
.argent-sens.achat { background: color-mix(in srgb, var(--vert) 16%, transparent); color: var(--vert); }
.argent-sens.vente { background: color-mix(in srgb, var(--rouge) 16%, transparent); color: var(--rouge); }
.argent-sens.contrat { background: color-mix(in srgb, var(--bleu) 16%, transparent); color: var(--bleu); }
.argent-sens.rachat { background: color-mix(in srgb, var(--violet) 16%, transparent); color: var(--violet); }
.argent-phrase { display: block; margin-top: 2px; color: var(--texte-2); font-size: .875rem; line-height: 1.35; }
.argent-montant { flex: none; max-width: 38%; margin-top: 2px; text-align: right; font-weight: 800; font-size: .9375rem; font-variant-numeric: tabular-nums; }
.argent-montant.achat { color: var(--vert); } .argent-montant.vente { color: var(--rouge); } .argent-montant.contrat { color: var(--bleu); } .argent-montant.rachat { color: var(--violet); }
.argent-plan { color: var(--jaune); }
.thermo { padding: 14px 16px; display: flex; flex-direction: column; gap: 8px; }
.thermo-titre { margin: 0; font-size: .8125rem; font-weight: 700; color: var(--texte-2); text-transform: uppercase; letter-spacing: .04em; }
.thermo-barre { height: 10px; border-radius: 5px; overflow: hidden; background: var(--rouge); }
.thermo-barre span { display: block; height: 100%; background: var(--vert); border-radius: 5px 0 0 5px; }
.thermo-chiffres { display: flex; justify-content: space-between; gap: 8px; font-size: .9375rem; font-variant-numeric: tabular-nums; }
.thermo-note { margin: 0; color: var(--texte-3); font-size: .8125rem; line-height: 1.4; }
.carte.liste.attente { opacity: .6; }

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
