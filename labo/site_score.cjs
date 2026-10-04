// Vérifie le VRAI site : le score servi = celui publié par le robot sur main ; l'app l'affiche ; photos format iPhone.
const { chromium } = require("playwright");
const fs = require("fs");

(async () => {
  const [fichierMain, dossier, fichierElus, fichierLobbying] = process.argv.slice(2);
  const local = fs.readFileSync(fichierMain, "utf8");
  const elusLocal = fs.readFileSync(fichierElus, "utf8");
  const lobbyingLocal = fs.readFileSync(fichierLobbying, "utf8");
  const lobbying = JSON.parse(lobbyingLocal);
  const VERSION = "0.23.0";
  const base = process.env.BASE || "https://killingsky1.github.io/Radar/"; // BASE : essai local seulement
  const b = await chromium.launch(process.env.CI ? { channel: "chrome" } : {});
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true, locale: "fr-CA", colorScheme: "dark" });
  const p = await ctx.newPage();
  const erreurs = [];
  p.on("pageerror", (e) => erreurs.push(String(e)));
  p.on("console", (m) => m.type() === "error" && erreurs.push(m.text()));
  const lignes = [];
  const dire = (t) => { console.log(t); lignes.push(t); };
  const photo = async (nom) => { await p.waitForTimeout(600); await p.screenshot({ path: `${dossier}/${nom}.png` }); };
  // Les chiffres défilent 0,65 s : on lit la valeur finale (data-final="1")
  const chiffresFinis = () => p.waitForFunction(() => [...document.querySelectorAll("[data-defile]")].every((e) => e.dataset.final === "1"));

  // Attendre que GitHub Pages serve la nouvelle app (au plus 6 minutes).
  for (let i = 0; i < 24; i++) {
    const t = await (await ctx.request.get(`${base}app.js?x=${Date.now()}`)).text();
    if (t.includes(VERSION)) break;
    await new Promise((ok) => setTimeout(ok, 15000));
  }
  // Attendre que le site serve le score publié par le robot sur main (au plus 6 minutes).
  let r, servi;
  for (let i = 0; i < 24; i++) {
    r = await ctx.request.get(`${base}data/app/aujourdhui.json?x=${Date.now()}`);
    servi = await r.text();
    if (servi === local) break;
    await new Promise((ok) => setTimeout(ok, 15000));
  }
  let elusServi = "";
  for (let i = 0; i < 12; i++) {
    elusServi = await (await ctx.request.get(`${base}data/app/elus.json?x=${Date.now()}`)).text();
    if (elusServi === elusLocal) break;
    await new Promise((ok) => setTimeout(ok, 15000));
  }
  const elusPareil = elusServi === elusLocal;
  let lobbyingServi = "";
  for (let i = 0; i < 12; i++) {
    lobbyingServi = await (await ctx.request.get(`${base}data/app/lobbying.json?x=${Date.now()}`)).text();
    if (lobbyingServi === lobbyingLocal) break;
    await new Promise((ok) => setTimeout(ok, 15000));
  }
  const lobbyingPareil = lobbyingServi === lobbyingLocal;
  dire(`Fichier du lobbying sur le site : identique à celui du robot sur main : ${lobbyingPareil ? "OUI" : "NON"} · ${Object.keys(lobbying.par_symbole).length} compagnies · ${lobbying.trimestre.libelle}`);
  const elus = JSON.parse(elusLocal);
  dire(`Fichier des élus sur le site : identique à celui du robot sur main : ${elusPareil ? "OUI" : "NON"} · ${Object.keys(elus.par_elu).length} élus reliés, ${elus.chefs.length} chefs`);
  const a = JSON.parse(servi);
  const pareil = servi === local;
  dire(`Fichier du score sur le site : HTTP ${r.status()} · identique à celui du robot sur main : ${pareil ? "OUI" : "NON"}`);
  dire(`Version ${a.version} · calculé le ${a.genere_a} · compagnies notées : ${a.compagnies_notees}`);
  dire(`Hausse (${a.hausse.length}) : ${a.hausse.map((x) => `${x.symbole} ${x.score} pts = ${x.note10}/10${x.recent ? " récent" : ""}`).join(", ")}`);
  dire(`Baisse (${a.baisse.length}) : ${a.baisse.map((x) => `${x.symbole} ${x.score} pts = ${x.note10}/10`).join(", ")}`);
  const sur10 = (n) => n.toLocaleString("fr-CA", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "/10";
  const js = await (await ctx.request.get(`${base}app.js?x=${Date.now()}`)).text();
  dire(`App en ligne : version ${VERSION} ${js.includes(VERSION) ? "OUI" : "NON"}`);

  await p.goto(base);
  await p.waitForSelector(".tuiles");
  await chiffresFinis();
  await photo("v1-accueil");
  // Lot D : le radar = les compagnies du score (8 premières à la hausse, 3 à la baisse) ; un point ouvre sa fiche
  const etiquettesRadar = (await p.locator(".radar-etiquette").allInnerTexts()).sort();
  const attendusRadar = [...a.hausse.slice(0, 8), ...a.baisse.slice(0, 3)].map((x) => x.symbole).sort();
  const balai = await p.locator(".radar-balai").evaluate((e) => getComputedStyle(e).animationName);
  await p.locator(".radar").evaluate((e) => e.scrollIntoView({ block: "center" }));
  await photo("v34-radar");
  await p.locator(".radar-cible").first().click(); await p.waitForTimeout(300); await chiffresFinis();
  const ficheRadar = await p.locator(".grand-titre h1").innerText();
  await photo("v35-fiche-anneau");
  const radarOk = JSON.stringify(etiquettesRadar) === JSON.stringify(attendusRadar) && balai === "balayage"
    && attendusRadar.includes(ficheRadar);
  dire(`Radar : ${etiquettesRadar.length} points ${etiquettesRadar.join(", ")} · attendus ${attendusRadar.join(", ")} · balayage ${balai} · point touché → fiche ${ficheRadar} · conforme : ${radarOk ? "OUI" : "NON"}`);
  await p.locator(".retour").click(); await p.waitForTimeout(300);
  // Lot E : l'aide (bouton « ? ») : 5 étapes, nombre de sources = fichier du robot, délais légaux, avertissement
  let aideOk = false;
  try {
    const sourcesAide = JSON.parse(fs.readFileSync(fichierMain.replace(/aujourdhui\.json$/, "sources.json"), "utf8"));
    const branchees = sourcesAide.filter((x) => !["ecartee", "refusee", "a_venir"].includes(x.statut)).length;
    await p.getByRole("button", { name: "Aide" }).click(); await p.waitForSelector(".flux-etape"); await p.waitForTimeout(900);
    await photo("v36-aide");
    const etapesAide = await p.locator(".flux-etape b").allInnerTexts();
    const texteAide = (await p.locator(".ecran").innerText()).replace(/\u00a0/g, " ");
    await p.locator(".delai").first().evaluate((e) => e.scrollIntoView({ block: "center" }));
    await photo("v37-aide-bon-a-savoir");
    const aideSansEchec = !/laissées de côté|erreur 403|dans ce cas|les limites|vente de l'app|aucune source de prix|ne mesure pas/i.test(texteAide);
    aideOk = etapesAide.length === 5 && texteAide.includes(`${branchees} sources branchées`) && aideSansEchec && texteAide.toLowerCase().includes("bon à savoir")
      && texteAide.includes("2 jours ouvrables après la transaction") && texteAide.includes("Pas un conseil financier")
      && texteAide.includes("Rachats : quand le conseil d'une compagnie autorise un rachat de ses actions (8-K)")
      && (await p.locator('a.etude[href="https://www.nber.org/papers/w4965"]').count()) === 1;
    dire(`Aide : ${etapesAide.join(" → ")} · ${branchees} sources branchées (fichier du robot, sans les sources laissées de côté ou refusées) · rien sur les sources laissées de côté, le 403, « les limites », une vente ou l'absence de prix : ${aideSansEchec ? "OUI" : "NON"} · conforme : ${aideOk ? "OUI" : "NON"}`);
    await p.locator(".retour").click(); await p.waitForTimeout(300);
  } catch (e) {
    dire(`Aide : ERREUR ${String(e).slice(0, 200)}`);
  }
  // Lot F : le calendrier (fins de blocage) servi = fichier du robot ; carte du Radar (3 prochaines), page complète,
  // fiche officielle (titre du robot, 0 point)
  let calOk = false;
  try {
    const calLocal = JSON.parse(fs.readFileSync(fichierMain.replace(/aujourdhui\.json$/, "calendrier.json"), "utf8"));
    let calServi = null;
    for (let i = 0; i < 12; i++) {
      calServi = await (await ctx.request.get(`${base}data/app/calendrier.json?x=${Date.now()}`)).json().catch(() => null);
      if (JSON.stringify(calServi) === JSON.stringify(calLocal)) break;
      await new Promise((ok) => setTimeout(ok, 15000));
    }
    const servi = JSON.stringify(calServi) === JSON.stringify(calLocal);
    const prochaines = calLocal.lignes.filter((l) => !l.passee).slice(0, 3).map((l) => l.compagnie);
    const nom = (t) => t.split("\n").pop().trim(); // la date cachée (lecteurs d'écran) est sur sa propre ligne
    if (prochaines.length === 0) {
      calOk = servi && (await p.locator(".carte.calendrier").count()) === 0;
      dire(`Calendrier : aucune fin de blocage à venir · carte absente du Radar · conforme : ${calOk ? "OUI" : "NON"}`);
    } else {
      await p.locator(".carte.calendrier").evaluate((e) => e.scrollIntoView({ block: "center" }));
      await photo("v38-calendrier-radar");
      const carte = (await p.locator(".carte.calendrier .cal-ligne .ligne-titre").allInnerTexts()).map(nom);
      await p.locator(".section-ligne", { hasText: "Fins de blocage à venir" }).locator(".lien").click(); await p.waitForTimeout(500);
      await photo("v39-calendrier");
      const page = (await p.locator(".cal-ligne .ligne-titre").allInnerTexts()).map(nom);
      const l0 = calLocal.lignes[0];
      await p.locator(".cal-ligne").first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(500);
      await photo("v40-fiche-blocage");
      const fiche = (await p.locator(".feuille").textContent()).replace(/\u00a0/g, " ");
      const ratesC = await p.locator(".feuille .controle.rate").count();
      await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
      await p.locator(".retour").click(); await p.waitForTimeout(300);
      calOk = servi && JSON.stringify(carte) === JSON.stringify(prochaines)
        && JSON.stringify(page) === JSON.stringify(calLocal.lignes.map((l) => l.compagnie))
        && fiche.includes(calLocal.evenements[l0.id].title) && fiche.includes("0 point dans la note") && ratesC === 0;
      dire(`Calendrier : ${calLocal.lignes.length} fins de blocage (${calLocal.lignes.filter((l) => l.passee).length} passée) · `
        + `carte du Radar ${carte.join(", ")} · page ${page.length} lignes · fiche de ${l0.compagnie} (${ratesC} contrôle raté) · `
        + `servi = fichier du robot : ${servi ? "OUI" : "NON"} · conforme : ${calOk ? "OUI" : "NON"}`);
    }
  } catch (e) {
    dire(`Calendrier : ERREUR ${String(e).slice(0, 200)}`);
  }
  // Lot G : résultats de Radar (prix officiels de la SEC) : servi = fichier du robot ; carte du Radar ; page complète
  let resOk = false;
  try {
    const resLocal = JSON.parse(fs.readFileSync(fichierMain.replace(/aujourdhui\.json$/, "resultats.json"), "utf8"));
    let resServi = null;
    for (let i = 0; i < 12; i++) {
      resServi = await (await ctx.request.get(`${base}data/app/resultats.json?x=${Date.now()}`)).json().catch(() => null);
      if (JSON.stringify(resServi) === JSON.stringify(resLocal)) break;
      await new Promise((ok) => setTimeout(ok, 15000));
    }
    const servi = JSON.stringify(resServi) === JSON.stringify(resLocal);
    const mesurees = Object.values(resLocal.resume).reduce((n, x) => n + x.mesurees, 0);
    const vers = await p.evaluate((j) => new Date(`${j}T12:00:00`).toLocaleDateString("fr-CA", { day: "numeric", month: "long", year: "numeric" }), resLocal.prochains_prix_vers || "2026-01-01");
    await p.locator(".res-carte").evaluate((e) => e.scrollIntoView({ block: "center" }));
    await photo("v41-resultats-radar");
    const carte = (await p.locator(".res-carte").innerText()).replace(/\u00a0/g, " ").trim();
    const carteOk = mesurees === 0 ? carte === `${resLocal.lignes.length} compagnies suivies. Premiers prix officiels de la SEC vers le ${vers}.`
      : carte.includes("ont frappé juste");
    await p.locator(".res-carte").click(); await p.waitForTimeout(500);
    await photo("v42-resultats");
    const nLignes = await p.locator(".res-ligne").count();
    await p.locator(".res-ligne").first().evaluate((e) => e.scrollIntoView({ block: "start" }));
    await photo("v43-resultats-lignes");
    const titreRes = await p.locator(".grand-titre h1").innerText();
    await p.locator(".retour").click(); await p.waitForTimeout(300);
    resOk = servi && carteOk && nLignes === resLocal.lignes.length && titreRes === "Résultats";
    dire(`Résultats : ${resLocal.lignes.length} compagnies suivies, ${mesurees} mesures · carte « ${carte} » · page ${nLignes} lignes · `
      + `servi = fichier du robot : ${servi ? "OUI" : "NON"} · conforme : ${resOk ? "OUI" : "NON"}`);
  } catch (e) {
    dire(`Résultats : ERREUR ${String(e).slice(0, 200)}`);
  }
  const affiches = await p.locator(".ligne.suggestion .symbole").allInnerTexts();
  const attendus = a.hausse.slice(0, 5).map((x) => x.symbole);
  // Lot B : chaque note affichée = la note publiée par le robot ; « Récent » au même endroit
  const notesAff = (await p.locator(".ligne.suggestion .score-pastille").allInnerTexts()).map((t) => t.replace(/\s+/g, ""));
  const notesAtt = a.hausse.slice(0, 5).map((x) => sur10(x.note10));
  const recentsAff = [];
  for (let i = 0; i < affiches.length; i++) recentsAff.push((await p.locator(".ligne.suggestion").nth(i).locator(".recent").count()) === 1);
  const recentsAtt = a.hausse.slice(0, 5).map((x) => !!x.recent);
  const memeTop = JSON.stringify(affiches) === JSON.stringify(attendus) && JSON.stringify(notesAff) === JSON.stringify(notesAtt)
    && JSON.stringify(recentsAff) === JSON.stringify(recentsAtt) && a.hausse.every((x) => x.note10 >= 7) && a.baisse.every((x) => x.note10 <= 3);
  dire(`Accueil : top 5 affiché ${affiches.map((t, i) => `${t} ${notesAff[i]}${recentsAff[i] ? " Récent" : ""}`).join(", ")} · conforme au fichier : ${memeTop ? "OUI" : "NON"}`);
  await p.getByRole("button", { name: "Tout voir" }).first().click();
  await photo("v2-hausse");
  await p.locator(".ligne.suggestion").first().click();
  await photo("v3-fiche-1re");
  const titre = await p.locator(".grand-titre h1").innerText();
  await chiffresFinis();
  const noteFiche = (await p.locator(".fiche-score").innerText()).replace(/\s+/g, "");
  const ficheOk = noteFiche === sur10(a.hausse[0].note10) && titre === a.hausse[0].symbole;
  dire(`Fiche ouverte : ${titre} · note affichée ${noteFiche} · publiée ${sur10(a.hausse[0].note10)} · conforme : ${ficheOk ? "OUI" : "NON"}`);
  // Le lobbying de cette compagnie, comme dans lobbying.json
  let lobbyingOk = false;
  const entree = lobbying.par_symbole[titre];
  // Lot I : la section n'apparaît que s'il y a des rapports (pas encore lu, recherche trop large ou aucun rapport : absente)
  const lobbyingAttendu = !!(entree && entree.complet && entree.total != null);
  if (await p.locator(".lobbying").count()) {
    await p.locator(".lobbying").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo("v9-fiche-lobbying");
    const texte = (await p.locator(".lobbying").innerText()).replace(/\u00a0|\u202f/g, " ");
    const pied = await p.locator(".congres-source").last().innerText();
    const attendu = lobbyingAttendu && entree.base === "compagnie" ? "Dépenses déclarées par la compagnie" : "Payés à";
    lobbyingOk = lobbyingAttendu && texte.includes(attendu) && pied.includes("Senate Office of Public Records cannot vouch");
    dire(`Lobbying sur la fiche ${titre} : « ${texte.split("\n")[0]} » · conforme : ${lobbyingOk ? "OUI" : "NON"}`);
  } else {
    lobbyingOk = !lobbyingAttendu && !(await p.locator(".ecran").last().innerText()).includes("Lobbying à Washington");
    dire(`Lobbying sur la fiche ${titre} : rien à montrer ce trimestre (${!entree ? "pas encore lu" : !entree.complet ? "recherche trop large" : "aucun rapport"}) → section absente, comme prévu : ${lobbyingOk ? "OUI" : "NON"}`);
  }
  // Lot H : rachats d'actions faits (XBRL de la SEC) sur la même fiche, comme dans rachats.json (servi = fichier du robot)
  let rachatsFaitsOk = false;
  try {
    const rfLocal = JSON.parse(fs.readFileSync(fichierMain.replace(/aujourdhui\.json$/, "rachats.json"), "utf8"));
    let rfServi = null;
    for (let i = 0; i < 12; i++) {
      rfServi = await (await ctx.request.get(`${base}data/app/rachats.json?x=${Date.now()}`)).json().catch(() => null);
      if (JSON.stringify(rfServi) === JSON.stringify(rfLocal)) break;
      await new Promise((ok) => setTimeout(ok, 15000));
    }
    const servi = JSON.stringify(rfServi) === JSON.stringify(rfLocal);
    const x = rfLocal.par_symbole[titre];
    // Lot I : la section n'apparaît que s'il y a un montant (pas encore lu, aucun montant ou montant illisible : absente)
    const rfAttendu = !!(x && !x.illisible && x.montant != null);
    if (await p.locator(".rachats-faits").count()) {
      await p.locator(".rachats-faits").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
      await photo("v46-fiche-rachats-faits");
      const texteRf = (await p.locator(".rachats-faits").innerText()).replace(/\u00a0|\u202f/g, " ");
      const sans = (t) => t.replace(/\s+/g, "");
      const court = (n) => new Intl.NumberFormat("fr-CA", { style: "currency", currency: "USD", notation: "compact", minimumFractionDigits: 0, maximumFractionDigits: Math.abs(n) >= 1e9 ? 2 : 1 }).format(n);
      const attendu = rfAttendu && x.montant > 0 ? "Argent dépensé pour racheter ses actions" : "Aucun rachat d'actions pendant l'exercice";
      const montantOk = rfAttendu && sans(await p.locator(".rachats-total").innerText()) === sans(court(x.montant));
      const lienOk = rfAttendu && (await p.locator(".rachats-faits a.transaction").getAttribute("href")) === x.lien;
      rachatsFaitsOk = servi && texteRf.includes(attendu) && montantOk && lienOk;
      dire(`Rachats faits sur la fiche ${titre} : « ${texteRf.split("\n").slice(0, 2).join(" · ")} » · ${Object.keys(rfLocal.par_symbole).length} compagnies dans le fichier (${rfLocal.cadre}) · servi = fichier du robot : ${servi ? "OUI" : "NON"} · conforme : ${rachatsFaitsOk ? "OUI" : "NON"}`);
    } else {
      await p.locator(".avertissement").last().evaluate((el) => el.scrollIntoView({ block: "end" }));
      await photo("v46-fiche-sans-section-vide");
      const texteFiche = await p.locator(".ecran").last().innerText();
      rachatsFaitsOk = servi && !rfAttendu && !texteFiche.includes("Rachats d'actions faits") && !texteFiche.includes("Aucun montant");
      dire(`Rachats faits sur la fiche ${titre} : aucun montant dans le fichier de la SEC (${rfLocal.cadre}) → section absente, comme prévu · servi = fichier du robot : ${servi ? "OUI" : "NON"} · conforme : ${rachatsFaitsOk ? "OUI" : "NON"}`);
    }
  } catch (e) {
    dire(`Rachats faits : ERREUR ${String(e).slice(0, 200)}`);
  }
  await p.locator(".retour").click();
  await p.locator(".segment", { hasText: "Baisse" }).click();
  await photo("v4-baisse");
  await p.getByRole("button", { name: "Comment le score est calculé" }).click();
  await photo("v5-methode");
  const regles = await p.locator(".regle").count();
  const calculTxt = (await p.locator(".groupe", { hasText: "Le calcul" }).innerText()).replace(/\u00a0/g, " ");
  const texteMethode = (await p.locator(".ecran").last().innerText()).replace(/\u00a0/g, " ");
  const methodeSansEchec = !/aucune source de prix|ne mesure pas|en liste seulement|images numérisées/i.test(texteMethode);
  const methodeOk = calculTxt.includes("Note sur 10 = 5 + points × 5/6") && calculTxt.includes("à partir de 7/10") && calculTxt.includes("Brochet (2010)") && methodeSansEchec;
  dire(`Page de la méthode : ${regles} règles · note sur 10 et seuil de 7/10 expliqués · rien qui dit « pas de prix », « ne mesure pas » ou « en liste seulement » : ${methodeSansEchec ? "OUI" : "NON"} · conforme : ${methodeOk ? "OUI" : "NON"}`);
  await p.locator(".regle", { hasText: "Un chef du Congrès achète" }).scrollIntoViewIfNeeded();
  await p.evaluate(() => window.scrollBy(0, -120));
  await photo("v5b-methode-chefs");
  const regleChef = (await p.locator(".regle", { hasText: "Un chef du Congrès achète" }).innerText()).replace(/\u00a0/g, " ");
  dire(`Règle des chefs affichée : ${regleChef.split("\n").slice(0, 2).join(" · ")}`);

  // Fil Politiciens : la carte H.R. 7008
  await p.locator("nav.onglets button", { hasText: "Fil" }).click();
  await p.locator(".puce", { hasText: "Politiciens" }).click();
  await photo("v6-politiciens");
  const carte = await p.locator(".carte-projet").innerText();
  const etape = elus.projet.etape.charAt(0).toUpperCase() + elus.projet.etape.slice(1);
  const carteOk = carte.includes(etape) && (await p.locator(".carte-projet-vote").count()) === elus.projet.votes.length;
  dire(`Carte H.R. 7008 : « ${etape} » · ${elus.projet.votes.length} votes · conforme : ${carteOk ? "OUI" : "NON"}`);

  // Une transaction d'élu : la section « Au Congrès »
  await p.locator(".ligne", { hasText: / achète | vend / }).first().click();
  await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
  let congresOk = false;
  if (await p.locator(".congres").count()) {
    // Le titre « Au Congrès » en haut de l'écran : on voit le rôle, les comités et les votes
    await p.locator(".congres").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo("v7-elu-au-congres");
    const source = await p.locator(".congres-source").innerText();
    const entree = Object.values(elus.par_elu).find((x) => source.startsWith(x.nom_officiel + " ·"));
    const comites = await p.locator(".congres .transaction").count();
    const votes = await p.locator(".votes-elu .transaction").count();
    const chef = await p.locator(".congres-chef").innerText();
    congresOk = !!entree && comites === entree.comites.length && votes === entree.votes_hr7008.length && (entree.chef ? chef.includes("Chef du Congrès") : chef === "Pas un des 12 chefs du Congrès.");
    dire(`Au Congrès (${entree ? entree.nom_officiel : "?"}) : ${comites} comités, ${votes} votes, « ${chef} » · conforme : ${congresOk ? "OUI" : "NON"}`);
  } else dire("Au Congrès : section absente");
  await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  // Un rapport 278-T de l'OGE : mention légale de l'OGE, aucun contrôle raté
  let ogeOk = false;
  const ligneOge = p.locator(".ligne", { hasText: "278-T" });
  if (await ligneOge.count()) {
    await ligneOge.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    await photo("v10-rapport-oge");
    const pied = await p.locator(".detail-pied").innerText();
    const rates = await p.locator(".feuille .controle.rate").count();
    ogeOk = pied.includes("Office of Government Ethics") && rates === 0;
    dire(`Rapport de l'OGE : « ${(await p.locator(".detail-titre").innerText()).slice(0, 90)} » · ${rates} contrôle(s) raté(s) · conforme : ${ogeOk ? "OUI" : "NON"}`);
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  } else dire("Rapport de l'OGE : aucun dans le fil Politiciens");
  // Lot I : un rapport du président (OGE) : titre sans « image numérisée », note « Les transactions sont dans le document officiel. »
  let presidentOk = true;
  const lignePres = p.locator(".ligne", { hasText: "président des États-Unis" });
  if (await lignePres.count()) {
    await lignePres.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    await photo("v47-rapport-du-president");
    const titreP = (await p.locator(".detail-titre").innerText()).replace(/\u00a0/g, " ");
    const texteP = await p.locator(".feuille").innerText();
    presidentOk = titreP.endsWith("(278-T)") && texteP.includes("Les transactions sont dans le document officiel.") && !/numérisée|ne lit pas|trop de risque/i.test(texteP);
    dire(`Rapport du président (OGE) : « ${titreP.slice(0, 100)} » · note « Les transactions sont dans le document officiel. » · conforme : ${presidentOk ? "OUI" : "NON"}`);
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  } else dire("Rapport du président (OGE) : aucun dans le fil Politiciens");
  // Transactions du cabinet : un rapport lu (ses lignes) et une info de compagnie
  let cabinetOk = false;
  const ligneRapport = p.locator(".ligne", { hasText: /278-T\), \d+ transactions?/ });
  if (await ligneRapport.count()) {
    await ligneRapport.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    const titreR = await p.locator(".detail-titre").innerText();
    const n = Number(titreR.match(/(\d+) transactions?$/)[1]);
    await p.locator(".lignes-oge").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo("v11-rapport-cabinet-lignes");
    const lues = await p.locator(".lignes-oge .ligne-oge").count();
    const ratesR = await p.locator(".feuille .controle.rate").count();
    dire(`Rapport du cabinet : « ${titreR.slice(0, 80)}… » · ${lues} lignes affichées pour ${n} annoncées · ${ratesR} contrôle(s) raté(s)`);
    cabinetOk = lues === n && ratesR === 0;
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  } else dire("Rapport du cabinet : aucun dans le fil Politiciens");
  const ligneCie = p.locator(".ligne", { hasText: /niveau I+\) (vend|achète|échange) / });
  if (await ligneCie.count()) {
    await ligneCie.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    await photo("v12-cabinet-compagnie");
    const titreC = await p.locator(".detail-titre").innerText();
    const lignesC = await p.locator(".lignes-oge .ligne-oge").count();
    const ratesC = await p.locator(".feuille .controle.rate").count();
    const pied = await p.locator(".detail-pied").innerText();
    dire(`Info de compagnie : « ${titreC} » · ${lignesC} ligne(s) · ${ratesC} contrôle(s) raté(s)`);
    cabinetOk = cabinetOk && lignesC >= 1 && ratesC === 0 && pied.includes("Office of Government Ethics");
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  } else { dire("Info de compagnie du cabinet : aucune dans le fil Politiciens"); cabinetOk = false; }
  dire(`Transactions du cabinet affichées : ${cabinetOk ? "OUI" : "NON"}`);
  const ligneVote = p.locator(".ligne", { hasText: "le Sénat rejette la clôture" });
  if (await ligneVote.count()) {
    await ligneVote.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    await photo("v8-vote-senat");
    dire(`Vote du Sénat : ${await p.locator(".feuille .controle.rate").count()} contrôle(s) raté(s)`);
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  }
  // Canada (lot 3c, livraison 1) : une fiche de chaque source, l'encadré « Détails » et la mention exigée
  await p.locator("nav.onglets button", { hasText: "Fil" }).click();
  await p.locator(".puce", { hasText: "Canada" }).click();
  await photo("v13-fil-canada");
  const CANADA = [
    ["v14-gazette", "Gazette du Canada :", "Reproduction non officielle"],
    ["v15-concurrence", "Bureau de la concurrence :", "Contient de l'information visée par la Licence du gouvernement ouvert"],
    ["v16-grand-projet", "Projet d'intérêt national :", "Reproduction non officielle"],
    ["v17-statcan", "Statistique Canada :", "Source : Statistique Canada, Le Quotidien"],
    ["v18-legisinfo", "Projet de loi ", "Source : LEGISinfo, Parlement du Canada"],
    ["v19-sanctions", "Sanctions canadiennes", "Contient de l'information visée par la Licence du gouvernement ouvert"],
    // Lot 3c, livraison 2
    ["v20-sante-canada", "Santé Canada : nouveau médicament", "Contient de l'information visée par la Licence du gouvernement ouvert"],
    ["v21-ccc", "Corporation commerciale canadienne :", "Source : Corporation commerciale canadienne. Usage personnel et non commercial"],
  ];
  let canadaOk = true;
  for (const [nom, debut, mention] of CANADA) {
    const l = p.locator(".ligne", { hasText: debut });
    if (!(await l.count())) { dire(`Canada : aucune info « ${debut} » dans le fil`); canadaOk = false; continue; }
    await l.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    const titreC = await p.locator(".detail-titre").innerText();
    const details = await p.locator(".details-officiels .detail-officiel").count();
    if (details) await p.locator(".details-officiels").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo(nom);
    const m = (await p.locator(".detail-pied .mention").count()) ? await p.locator(".detail-pied .mention").innerText() : "";
    const rates = await p.locator(".feuille .controle.rate").count();
    const bon = titreC.includes(debut.trim()) && details > 0 && m.startsWith(mention) && rates === 0;
    dire(`Canada : « ${titreC.slice(0, 95)} » · ${details} détails · mention « ${m.slice(0, 60)}… » · ${rates} contrôle(s) raté(s) · conforme : ${bon ? "OUI" : "NON"}`);
    canadaOk = canadaOk && bon;
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  }
  dire(`Fiches du Canada affichées : ${canadaOk ? "OUI" : "NON"}`);
  // CCC : chaque transaction du rapport est listée (autant de lignes que le nombre écrit dans le titre)
  let cccOk = false;
  const lc = p.locator(".ligne", { hasText: "Corporation commerciale canadienne :" });
  if (await lc.count()) {
    await lc.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    const titreCcc = await p.locator(".detail-titre").innerText();
    const n = Number((titreCcc.match(/(\d+) transactions signées/) || [])[1]);
    const lignesCcc = await p.locator(".lignes-ccc .ligne-oge").count();
    if (lignesCcc) await p.locator(".lignes-ccc").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo("v22-ccc-transactions");
    const premiere = lignesCcc ? (await p.locator(".lignes-ccc .ligne-oge").first().innerText()).replace(/\s+/g, " ") : "";
    cccOk = n > 0 && lignesCcc === n;
    dire(`CCC : ${n} transactions dans le titre, ${lignesCcc} lignes listées · 1re : « ${premiere.slice(0, 110)} » · conforme : ${cccOk ? "OUI" : "NON"}`);
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  } else dire("CCC : aucune info dans le fil");
  // Contrats fédéraux : 1re lecture silencieuse (aucune info), l'état de la source se voit dans l'écran Sources
  await p.locator("nav.onglets button", { hasText: "Radar" }).click(); await p.waitForTimeout(400);
  await p.locator(".tuile", { hasText: "Sources actives" }).click(); await p.waitForTimeout(600);
  let sourcesOk = true;
  for (const nom of ["Santé Canada : nouveaux médicaments", "Contrats fédéraux de 10 M$ et plus", "Corporation commerciale canadienne : transactions"]) {
    const s = p.locator(".source", { hasText: nom });
    const etat = (await s.count()) ? await s.first().locator(".source-etat").innerText() : "absente";
    if (nom.startsWith("Contrats")) { await s.first().evaluate((el) => el.scrollIntoView({ block: "center" })); await photo("v23-sources-canada"); }
    dire(`Source « ${nom} » : ${etat}`);
    sourcesOk = sourcesOk && etat.startsWith("OK");
  }
  await p.locator(".ecran-retour, .retour").first().click().catch(() => {});
  // Lot 3d : une adjudication du Trésor et un message de la douane (catégorie Gouvernement), puis les sources laissées de côté
  await p.locator("nav.onglets button", { hasText: "Fil" }).click();
  await p.locator(".puce", { hasText: "Gouvernement" }).click();
  let etatsUnisOk = true;
  for (const [nom, debut, mention] of [
    ["v24-tresor", "Trésor américain : adjudication", "Source : Trésor des États-Unis, Bureau of the Fiscal Service"],
    ["v25-douane", "Douane américaine :", "Source : U.S. Customs and Border Protection (messages CSMS)."],
  ]) {
    const l = p.locator(".ligne", { hasText: debut });
    if (!(await l.count())) { dire(`États-Unis : aucune info « ${debut} » dans le fil`); etatsUnisOk = false; continue; }
    await l.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    const titreU = await p.locator(".detail-titre").innerText();
    const detailsU = await p.locator(".details-officiels .detail-officiel").count();
    if (detailsU) await p.locator(".details-officiels").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo(nom);
    const mU = (await p.locator(".detail-pied .mention").count()) ? await p.locator(".detail-pied .mention").innerText() : "";
    const ratesU = await p.locator(".feuille .controle.rate").count();
    const bonU = titreU.includes(debut) && detailsU > 0 && mU.startsWith(mention) && ratesU === 0;
    dire(`États-Unis : « ${titreU.slice(0, 110)} » · ${detailsU} détails · mention « ${mU.slice(0, 70)}… » · ${ratesU} contrôle(s) raté(s) · conforme : ${bonU ? "OUI" : "NON"}`);
    etatsUnisOk = etatsUnisOk && bonU;
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  }
  await p.locator("nav.onglets button", { hasText: "Radar" }).click(); await p.waitForTimeout(400);
  await p.locator(".tuile", { hasText: "Sources actives" }).click(); await p.waitForTimeout(600);
  // Lot I : la page Sources montre seulement les sources qui servent (fichier du robot) : ni laissées de côté, ni refusées
  let ecarteesOk = true;
  const sourcesMain = JSON.parse(fs.readFileSync(fichierMain.replace("aujourdhui.json", "sources.json"), "utf8"));
  const cachees = sourcesMain.filter((s) => ["ecartee", "refusee", "a_venir"].includes(s.statut));
  const montrees = sourcesMain.filter((s) => !["ecartee", "refusee", "a_venir"].includes(s.statut));
  await photo("v26-sources");
  const nAffichees = await p.locator(".source").count();
  const texteSources = await p.locator(".ecran").last().innerText();
  let cacheesVues = 0;
  for (const c of cachees) if (await p.locator(".source-nom", { hasText: c.nom }).count()) cacheesVues += 1;
  ecarteesOk = nAffichees === montrees.length && cacheesVues === 0 && !/laissée|refusée|erreur 403|payant/i.test(texteSources);
  dire(`Sources : ${nAffichees} affichées = ${montrees.length} qui servent dans le fichier du robot · ${cachees.length} cachées (laissées de côté ou refusées), dont ${cacheesVues} affichée(s) · rien qui dit « Laissée », « Refusée » ou « 403 » · conforme : ${ecarteesOk ? "OUI" : "NON"}`);
  // Lot G : la source des échecs de livraison est branchée, seulement pour ses prix (jamais un signal)
  for (const nom of ["Trésor américain : adjudications", "Douane américaine : directives", "USAspending : contrats fédéraux américains",
                     "Gouvernement américain actionnaire", "SEC : prix de clôture des fichiers d'échecs de livraison"]) {
    const s = p.locator(".source", { hasText: nom });
    const etat = (await s.count()) ? await s.first().locator(".source-etat").innerText() : "absente";
    if (nom.startsWith("USAspending") && (await s.count())) { await s.first().evaluate((el) => el.scrollIntoView({ block: "center" })); await photo("v27-sources-usaspending"); }
    dire(`Source « ${nom} » : ${etat}`);
    ecarteesOk = ecarteesOk && etat.startsWith("OK");
  }
  await p.locator(".retour").first().click().catch(() => {});
  // Lot C : l'onglet Argent = le fichier du robot (montants, ordre, thermomètre) ; une ligne ouvre son info officielle
  let argentOk = false;
  let rachatsOk = false;
  try {
    const dossierMain = fichierMain.replace(/aujourdhui\.json$/, "");
    const ag = JSON.parse(fs.readFileSync(dossierMain + "argent.json", "utf8"));
    const agInfos = JSON.parse(fs.readFileSync(dossierMain + "argent_infos.json", "utf8"));
    const court = (n) => new Intl.NumberFormat("fr-CA", { style: "currency", currency: "USD", notation: "compact", minimumFractionDigits: 0, maximumFractionDigits: Math.abs(n) >= 1e9 ? 2 : 1 }).format(n);
    await p.locator("nav.onglets button", { hasText: "Argent" }).click();
    await p.waitForSelector(".ligne.argent", { timeout: 20000 });
    await p.locator(".segment", { hasText: "30 jours" }).click(); await p.waitForTimeout(300);
    await photo("v31-argent");
    // Sans espaces : le navigateur et Node n'écrivent pas toujours l'espace avant « $ » (même montant)
    const sans = (t) => t.replace(/\s+/g, "");
    const vus = (await p.locator(".ligne.argent .argent-montant").allInnerTexts()).slice(0, 5).map(sans);
    const attendus = ag.lignes.slice(0, 5).map((l) => sans(l.montant != null ? court(l.montant) : `${court(l.montant_min)} à ${court(l.montant_max)}`));
    const th = ag.thermometre;
    await chiffresFinis();
    const thermo = sans(await p.locator(".thermo").innerText());
    const thermoOk = thermo.includes(sans(`${court(th.achats.montant)} achetés (${th.achats.nombre})`))
      && thermo.includes(sans(`${court(th.ventes_libres.montant)} vendus (${th.ventes_libres.nombre})`));
    await p.locator(".ligne.argent").first().click(); await p.waitForSelector(".feuille-fond.ouvert", { timeout: 20000 }); await p.waitForTimeout(400);
    const titreA = await p.locator(".detail-titre").innerText();
    await photo("v32-argent-detail");
    const ratesA = await p.locator(".feuille .controle.rate").count();
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
    await p.locator(".puce", { hasText: /^Achats$/ }).click(); await p.waitForTimeout(300);
    await photo("v33-argent-achats");
    argentOk = JSON.stringify(vus) === JSON.stringify(attendus) && thermoOk && titreA === agInfos[ag.lignes[0].id].title && ratesA === 0;
    dire(`Argent : ${ag.lignes.length} lignes · 5 premiers montants affichés ${vus.join(" | ")} · attendus ${attendus.join(" | ")} · thermomètre conforme : ${thermoOk ? "OUI" : "NON"} · 1re ligne ouverte « ${titreA.slice(0, 90)} » (${ratesA} contrôle raté) · conforme : ${argentOk ? "OUI" : "NON"}`);
    // Lot H : filtre Rachats (30 jours) = les lignes « rachats » du fichier ; la 1re ouvre son 8-K, aucun contrôle raté
    const rachats = ag.lignes.filter((l) => l.famille === "rachats");
    await p.locator(".puce", { hasText: "Rachats" }).click(); await p.waitForTimeout(300);
    await photo("v44-argent-rachats");
    const nR = await p.locator(".ligne.argent").count();
    const montantsR = (await p.locator(".ligne.argent .argent-montant").allInnerTexts()).map(sans);
    let titreR = "", ratesR = 0;
    if (rachats.length) {
      await p.locator(".ligne.argent").first().click(); await p.waitForSelector(".feuille-fond.ouvert", { timeout: 20000 }); await p.waitForTimeout(400);
      titreR = await p.locator(".detail-titre").innerText();
      await photo("v45-rachat-detail");
      ratesR = await p.locator(".feuille .controle.rate").count();
      await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
    }
    rachatsOk = nR === rachats.length && JSON.stringify(montantsR) === JSON.stringify(rachats.map((l) => sans(court(l.montant))))
      && (!rachats.length || (titreR === agInfos[rachats[0].id].title && ratesR === 0));
    dire(`Argent, Rachats : ${nR} annonces affichées · ${rachats.length} dans le fichier · ${montantsR.join(" | ")}${rachats.length ? ` · 1re ouverte « ${titreR.slice(0, 90)} » (${ratesR} contrôle raté)` : ""} · conforme : ${rachatsOk ? "OUI" : "NON"}`);
  } catch (e) {
    dire(`Argent : ERREUR ${String(e).slice(0, 200)}`);
  }
  // Lot 3d, livraison 2 : une participation du gouvernement (s'il y en a une) : l'extrait officiel est affiché, rien de raté.
  // USAspending : 1re lecture silencieuse, donc aucune info attendue aujourd'hui (l'état de la source est vérifié plus haut).
  let participationOk = true;
  await p.locator("nav.onglets button", { hasText: "Fil" }).click();
  await p.locator(".puce", { hasText: "Gouvernement" }).click();
  const lp = p.locator(".ligne", { hasText: "un 8-K dit que" });
  if (await lp.count()) {
    await lp.first().click(); await p.waitForSelector(".feuille-fond.ouvert"); await p.waitForTimeout(400);
    const titreP = await p.locator(".detail-titre").innerText();
    await photo("v29-participation-titre");
    // textContent : le texte brut (les noms des détails sont en majuscules par le CSS, innerText les rendrait en majuscules)
    const noms = await p.locator(".details-officiels .detail-officiel-nom").allTextContents();
    const valeurs = await p.locator(".details-officiels .detail-officiel-valeur").allTextContents();
    const extrait = valeurs.find((v, i) => noms[i].startsWith("Extrait (")) || "";
    if (noms.length) await p.locator(".details-officiels").evaluate((el) => el.previousElementSibling.scrollIntoView({ block: "start" }));
    await photo("v28-participation");
    const ratesP = await p.locator(".feuille .controle.rate").count();
    participationOk = extrait.length > 40 && ratesP === 0 && !/\([^()]*\(/.test(titreP);
    dire(`Participation : « ${titreP.slice(0, 120)} » · extrait affiché : « ${extrait.slice(0, 140)}… » · ${ratesP} contrôle(s) raté(s) · conforme : ${participationOk ? "OUI" : "NON"}`);
    await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400);
  } else dire("Participation : aucune info dans le fil (aucun cas dans les 8-K lus)");
  dire(`Erreurs du navigateur : ${erreurs.length ? erreurs.join(" | ") : "aucune"}`);
  const ok = pareil && elusPareil && lobbyingPareil && memeTop && radarOk && aideOk && calOk && resOk && ficheOk && methodeOk && argentOk && rachatsOk && rachatsFaitsOk && presidentOk && regles === a.methode.regles.length && carteOk && congresOk && lobbyingOk && ogeOk && cabinetOk && canadaOk && cccOk && sourcesOk && etatsUnisOk && ecarteesOk && participationOk && !erreurs.length && js.includes(VERSION);
  dire(ok ? "VERDICT : OK" : "VERDICT : PROBLÈME");
  fs.writeFileSync(`${dossier}/site.txt`, lignes.join("\n") + "\n");
  await b.close();
  process.exit(ok ? 0 : 1);
})();
