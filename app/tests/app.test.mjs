// Tests de l'app dans un vrai navigateur (données TEST : 20 infos validées + 1 piège ; score : AMD, NVDA, XMPL).
import { chromium } from "playwright";
import assert from "node:assert";

const ADRESSE = process.env.ADRESSE || "http://localhost:8766/";
(async () => {
  // Sur GitHub, on utilise le Chrome déjà installé (pas de téléchargement).
  const b = await chromium.launch(process.env.CI ? { channel: "chrome" } : {});
  const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, locale: "fr-CA", colorScheme: "dark" });
  const p = await ctx.newPage();
  p.setDefaultTimeout(5000);
  p.on("dialog", (d) => d.accept());
  const erreurs = [];
  p.on("pageerror", (e) => erreurs.push(String(e)));
  p.on("console", (m) => m.type() === "error" && erreurs.push(m.text()));
  const res = [];
  const verifier = async (nom, fn) => { try { await fn(); res.push(`OK     ${nom}`); } catch (e) { res.push(`ÉCHEC  ${nom} : ${e.message.split("\n")[0]}`); } };
  const onglet = async (n) => { await p.locator("nav.onglets button", { hasText: n }).click(); await p.waitForTimeout(250); };
  const lignes = () => p.locator(".ligne").count();
  const inter = (nom) => p.getByRole("switch", { name: nom }).click();
  const reglages = async () => { await onglet("Réglages"); };
  const filTout = async () => { await onglet("Fil"); await p.locator(".puce", { hasText: "Tout" }).click(); await p.waitForTimeout(150); };
  const fermer = async () => { await p.locator(".feuille-fermer").click(); await p.waitForTimeout(400); };
  // Les chiffres défilent 0,65 s : on lit la valeur finale (data-final="1")
  const chiffresFinis = () => p.waitForFunction(() => [...document.querySelectorAll("[data-defile]")].every((e) => e.dataset.final === "1"));

  await p.goto(ADRESSE);
  await p.evaluate(() => localStorage.clear());
  await p.reload(); await p.waitForSelector(".tuiles");
  // Quitter une page marque les suggestions comme vues : on simule une dernière visite très ancienne, une seule fois.
  await p.evaluate(() => sessionStorage.setItem("visite-ancienne", "1"));
  await p.addInitScript(() => {
    if (sessionStorage.getItem("visite-ancienne")) { sessionStorage.removeItem("visite-ancienne"); localStorage.setItem("radar-suggestions-vues", "0"); }
  });
  await p.reload(); await p.waitForSelector(".tuiles");

  await verifier("Thème sombre par défaut", async () => assert.equal(await p.evaluate(() => document.documentElement.dataset.theme), "sombre"));
  await verifier("Accueil : compteurs du robot (3 publiées aujourd'hui, 1 confirmée, 1 à vérifier)", async () => {
    await chiffresFinis();
    const v = await p.locator(".tuile-valeur").allInnerTexts();
    assert.deepEqual(v.slice(0, 3), ["3", "1", "1"]);
    assert.ok((await p.locator(".tuile-label").first().innerText()).startsWith("Publiées le"));
  });
  await verifier("Accueil : top à la hausse (AMD puis NVDA), pastille Nouveau sur AMD seulement", async () => {
    const l = p.locator(".ligne.suggestion");
    assert.equal(await l.count(), 2);
    assert.ok((await l.nth(0).innerText()).includes("AMD") && (await l.nth(1).innerText()).includes("NVDA"));
    assert.equal(await l.nth(0).locator(".nouveau").count(), 1);
    assert.equal(await l.nth(1).locator(".nouveau").count(), 0);
  });
  await verifier("Accueil : notes sur 10 (7/10 et plus) et « Récent » pour un dépôt de moins de 3 jours de bourse", async () => {
    const l = p.locator(".ligne.suggestion");
    for (let i = 0; i < 2; i++) {
      const n = (await l.nth(i).locator(".score-pastille").innerText()).replace(/\s+/g, "");
      assert.ok(/^\d+,\d\/10$/.test(n) && parseFloat(n.replace(",", ".")) >= 7, n);
    }
    assert.equal(await l.nth(1).locator(".recent").count(), 1); // NVDA : déposé aujourd'hui
  });
  await verifier("Radar animé : 3 points (AMD et NVDA en hausse, XMPL en baisse), plus près du centre = note plus forte", async () => {
    const cibles = p.locator(".radar-cible");
    assert.equal(await cibles.count(), 3);
    const etiquettes = await p.locator(".radar-etiquette").allInnerTexts();
    assert.deepEqual([...etiquettes].sort(), ["AMD", "NVDA", "XMPL"]);
    assert.equal(await p.locator(".radar-cible.baisse").count(), 1);
    assert.ok((await p.locator(".radar-cible.baisse").getAttribute("aria-label")).startsWith("XMPL, à la baisse, note 0,0 sur 10"));
    // Le balayage tourne et chaque point s'allume (animations CSS actives)
    assert.equal(await p.locator(".radar-balai").evaluate((e) => getComputedStyle(e).animationName), "balayage");
    // Distance au centre : la note la plus forte (la plus loin de 5) est la plus proche du centre
    const pos = await cibles.evaluateAll((els) => els.map((e) => [e.getAttribute("aria-label"), Math.hypot(parseFloat(e.style.left) - 50, parseFloat(e.style.top) - 50)]));
    const note = (l) => Math.abs(parseFloat(l.match(/note (\d+,\d)/)[1].replace(",", ".")) - 5);
    const tries = [...pos].sort((a, b) => note(b[0]) - note(a[0]));
    assert.ok(tries.every((x, i) => i === 0 || x[1] >= tries[i - 1][1] - 0.01), JSON.stringify(pos));
  });
  await verifier("Radar : toucher un point ouvre la fiche, avec la note dans un anneau", async () => {
    await p.locator(".radar-cible", { hasText: "NVDA" }).click(); await p.waitForTimeout(250);
    assert.equal(await p.locator(".grand-titre h1").innerText(), "NVDA");
    await chiffresFinis();
    const n = (await p.locator(".fiche-score").innerText()).replace(/\s+/g, "");
    assert.ok(/^\d+,\d\/10$/.test(n), n);
    assert.equal(await p.locator(".anneau").getAttribute("aria-label"), `Note ${n.replace("/10", "")} sur 10`);
    await p.locator(".retour").click(); await p.waitForTimeout(200);
  });
  await verifier("Aide : bouton « ? » du Radar, chemin en 5 étapes, heures des robots, sources refusées, liens", async () => {
    try {
      await p.getByRole("button", { name: "Aide" }).click(); await p.waitForSelector(".flux-etape");
      assert.equal(await p.locator(".grand-titre h1").innerText(), "Aide");
      const etapes = await p.locator(".flux-etape b").allInnerTexts();
      assert.deepEqual(etapes, ["1. Sources officielles", "2. Robots", "3. Contrôles", "4. Labo", "5. Note"]);
      assert.deepEqual(await p.locator(".passage b").allInnerTexts(), ["7 h 07", "9 h 47", "12 h 37", "18 h 17", "23 h 17"]);
      const texte = (await p.locator(".ecran").innerText()).replace(/\u00a0/g, " ");
      assert.ok(texte.includes("Aujourd'hui : 1 source dans ce cas.") && texte.includes("2 jours ouvrables après la transaction")
        && texte.includes("Note sur 10 = 5 + points × 5/6") && texte.includes("Pas un conseil financier"), texte.slice(0, 300));
      await p.locator(".lien-rangee", { hasText: "État des sources" }).click(); await p.waitForTimeout(250);
      assert.equal(await p.locator(".grand-titre h1").innerText(), "Sources");
      await p.locator(".retour").click(); await p.waitForTimeout(200);
      assert.equal(await p.locator(".grand-titre h1").innerText(), "Aide");
    } finally {
      await onglet("Radar"); // retour à l'accueil, même en cas d'échec
    }
  });
  await verifier("Accueil : 1 à surveiller à la baisse", async () => {
    assert.ok((await p.locator(".alerte-baisse").innerText()).includes("1 à surveiller à la baisse"));
  });
  await verifier("Fiche AMD : groupe d'achats, 1 info comptée sur 2, 13G sans points", async () => {
    await p.locator(".ligne.suggestion", { hasText: "AMD" }).click(); await p.waitForTimeout(250);
    assert.equal(await p.locator(".grand-titre h1").innerText(), "AMD");
    assert.equal(await p.locator(".ligne.raison").count(), 3);
    const t = (await p.locator(".ecran").innerText()).replace(/\u00a0/g, " "); // espaces insécables (typographie)
    assert.ok(t.includes("Groupe d'achats ×1,75") && t.includes("PDG, directeur financier ou président du conseil ×1,5"), t);
    assert.equal(await p.locator(".raison-points.pas-compte").count(), 1);
    assert.ok(t.toLowerCase().includes("autres infos (0 point)") && t.includes("13G : placement passif"), t);
  });
  await verifier("Fiche AMD : une raison ouvre le document officiel", async () => {
    await p.locator(".ligne.raison").first().click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.ok(await p.getByText("Document officiel").isVisible()); await fermer();
  });
  await verifier("Comment le score est calculé : 13 règles, 20 liens d'études (dont Brochet pour « Récent »), règles des chefs", async () => {
    await p.getByRole("button", { name: "Comment le score est calculé" }).click(); await p.waitForTimeout(250);
    assert.equal(await p.locator(".regle").count(), 13);
    assert.equal(await p.locator("a.etude").count(), 20);
    const calcul = (await p.locator(".groupe", { hasText: "Le calcul" }).innerText()).replace(/\u00a0/g, " ");
    assert.ok(calcul.includes("Note sur 10 = 5 + points × 5/6") && calcul.includes("à partir de 7/10") && calcul.includes("Brochet (2010)"), calcul);
    const chef = (await p.locator(".regle", { hasText: "Un chef du Congrès achète" }).innerText()).replace(/\u00a0/g, " ");
    assert.ok(chef.includes("+2") && chef.includes("Wei et Zhou"), chef);
    assert.ok((await p.locator(".regle", { hasText: "Un chef du Congrès vend" }).innerText()).replace(/\u00a0/g, " ").includes("−1"));
    assert.ok((await p.locator(".ecran").innerText()).includes("Pas un conseil financier"));
  });
  await verifier("Baisse : Exemple Corp., faillite + vente du PDG, bonus 2 familles", async () => {
    await onglet("Radar"); await p.locator(".alerte-baisse").click(); await p.waitForTimeout(250);
    assert.equal(await p.locator(".segment.actif").innerText(), "Baisse · 1");
    await p.locator(".ligne.suggestion", { hasText: "XMPL" }).click(); await p.waitForTimeout(250);
    await chiffresFinis();
    const t = (await p.locator(".calcul").innerText()).replace(/\u00a0/g, " ");
    // Infos TEST datées d'hier (jour UTC) ; le score compte les jours à l'heure de Toronto : 0 ou 1 jour selon l'heure
    const age = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Toronto" }).format(new Date()) === new Date().toISOString().slice(0, 10) ? 1 : 0;
    assert.ok(t.includes("bonus ×1,25 (2 familles d'accord)") && t.includes(`Score : ${age ? "−6,7" : "−6,9"} points → note 0,0/10`), t);
    assert.equal((await p.locator(".fiche-score").innerText()).replace(/\s+/g, ""), "0,0/10");
    assert.ok(t.includes(`Note = 5 + (${age ? "−6,7" : "−6,9"}`) && t.includes(") × 5/6, entre 0 et 10, arrondie au dixième"), t);
  });
  await verifier("Retour : Suggestions puis Accueil", async () => {
    await p.locator(".retour").click(); await p.waitForTimeout(200);
    assert.equal(await p.locator(".grand-titre h1").innerText(), "Suggestions");
    await p.locator(".segment", { hasText: "Hausse" }).click(); assert.equal(await p.locator(".ligne.suggestion").count(), 2);
    await p.locator(".retour").click(); await p.waitForTimeout(200); assert.ok(await p.locator(".tuiles").isVisible());
  });
  await verifier("Nouveau : disparaît une fois la liste vue (visite suivante)", async () => {
    await p.evaluate(() => localStorage.setItem("radar-suggestions-vues", JSON.stringify(Date.now())));
    await p.reload(); await p.waitForSelector(".tuiles");
    assert.equal(await p.locator(".ligne.suggestion .nouveau").count(), 0);
  });
  // Chaque test de fiche revient à l'accueil même s'il échoue (sinon les suivants échouent aussi).
  const fiche = async (symbole, fn, baisse = false) => {
    if (baisse) { await p.locator(".alerte-baisse").click(); await p.waitForTimeout(250); }
    await p.locator(".ligne.suggestion", { hasText: symbole }).click(); await p.waitForTimeout(250);
    try { await fn(); } finally {
      await p.locator(".retour").click(); await p.waitForTimeout(200);
      if (baisse) { await p.locator(".retour").click(); await p.waitForTimeout(200); }
    }
  };
  await verifier("Fiche AMD : lobbying (total, firme incluse, sujets, 2 rapports, phrase du Sénat)", () => fiche("AMD", async () => {
    // Le format compact varie selon la version de Chrome (« 1,23 M$ US » ou « 1,23 M $ US ») : on compare sans espaces
    const total = (await p.locator(".lobbying-total").innerText()).replace(/\s/g, "");
    assert.ok(total.includes("1,23M$US"), total);
    const t = (await p.locator(".lobbying").innerText()).replace(/\u00a0|\u202f/g, " ");
    assert.ok(t.includes("Dépenses déclarées par la compagnie elle-même : elles incluent ce qu'elle paie à 1 firme de lobbying, qui déclare 40"), t);
    assert.ok(t.includes("Sujets : Commerce (intérieur et extérieur) · Fiscalité (impôts)"), t);
    assert.equal(await p.locator(".lobbying .transaction").count(), 2);
    assert.ok((await p.locator(".lobbying .transaction").first().innerText()).includes("La compagnie elle-même"));
    const pied = await p.locator(".congres-source").last().innerText();
    assert.ok(pied.includes("Senate Office of Public Records cannot vouch for the data") && pied.includes("Lu sur LDA.gov le"), pied);
  }));
  await verifier("Fiche NVDA : aucun rapport au nom exact (et pas « 0 $ »)", () => fiche("NVDA", async () => {
    const t = await p.locator(".lobbying").innerText();
    assert.ok(t.includes("Aucun rapport de lobbying au nom exact « NVIDIA CORP »") && !t.includes("$"), t);
  }));
  await verifier("Fiche XMPL : recherche trop large, pas vérifié", () => fiche("XMPL", async () => {
    assert.ok((await p.locator(".lobbying").innerText()).includes("Recherche trop large (« EXEMPLE ») : pas vérifié."));
  }, true));
  await verifier("Sans fichier du lobbying : la fiche s'affiche sans la section", async () => {
    const avant = erreurs.length;
    await p.route("**/data/app/lobbying.json", (route) => route.fulfill({ status: 404, body: "" }));
    try {
      await p.reload(); await p.waitForSelector(".tuiles");
      await p.locator(".ligne.suggestion", { hasText: "AMD" }).click(); await p.waitForTimeout(250);
      assert.equal(await p.locator(".grand-titre h1").innerText(), "AMD"); assert.equal(await p.locator(".lobbying").count(), 0);
      await p.locator(".retour").click(); await p.waitForTimeout(200);
    } finally {
      await p.unroute("**/data/app/lobbying.json"); await p.reload(); await p.waitForSelector(".tuiles");
      erreurs.splice(avant, erreurs.length - avant, ...erreurs.slice(avant).filter((e) => !e.includes("404")));
    }
  });
  await verifier("Tuile catégorie Militaire ouvre le fil filtré (1 info)", async () => {
    await p.locator(".cat", { hasText: "Militaire" }).click(); await p.waitForTimeout(250); assert.equal(await lignes(), 1);
  });
  await verifier("Fil : 20 infos, le piège est caché", async () => { await p.locator(".puce", { hasText: "Tout" }).click(); assert.equal(await lignes(), 20); });
  await verifier("Fil se souvient du filtre choisi (Tout) après un changement d'onglet", async () => {
    await onglet("Favoris"); await onglet("Fil"); assert.equal(await lignes(), 20);
    assert.equal(await p.locator(".puce.actif").innerText(), "Tout");
  });
  await verifier("Fil groupé par jour (Aujourd'hui, Hier…)", async () => {
    const t = await p.locator("h2.section").allInnerTexts(); assert.ok(t[0].toLowerCase().includes("aujourd") && t[1].toLowerCase().includes("hier"), t.join("|"));
  });
  await verifier("Recherche « nvda » : 1 résultat", async () => { await p.fill("input[type=search]", "nvda"); await p.waitForTimeout(150); assert.equal(await lignes(), 1); await p.fill("input[type=search]", ""); });
  await verifier("Recherche sans résultat : message clair", async () => { await p.fill("input[type=search]", "zzzz"); await p.waitForTimeout(150); assert.ok(await p.getByText("Aucun résultat").isVisible()); await p.fill("input[type=search]", ""); });
  await verifier("Détail : s'ouvre, montre 14 contrôles (9 communs + 5 d'USAspending) et 1 confirmation, se ferme", async () => {
    await p.locator(".ligne").first().click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.equal(await p.locator(".feuille .controle").count(), 15); // 14 contrôles + 1 confirmation
    await fermer(); assert.equal(await p.locator(".feuille").count(), 0);
  });
  await verifier("Détail d'un élu : transactions déclarées et avis légal", async () => {
    await p.locator(".ligne", { hasText: "Microsoft" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.equal(await p.locator(".transactions .transaction").count(), 1);
    const t = await p.locator(".transactions .transaction").innerText();
    assert.ok(t.includes("conjoint·e") && t.includes("15") && t.includes("50"), t);
    assert.ok((await p.locator(".detail-pied").innerText()).includes("non commercial"));
    assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
    await fermer();
  });
  await verifier("Détail d'un élu : au Congrès (pas chef, comités, ses 2 votes sur H.R. 7008)", async () => {
    await p.locator(".ligne", { hasText: "Microsoft" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.equal(await p.locator(".congres-chef").innerText(), "Pas un des 12 chefs du Congrès.");
    const comites = await p.locator(".congres .transaction").allInnerTexts();
    assert.equal(comites.length, 2); assert.ok(comites[0].includes("Financial Services") && comites[0].includes("président·e"), comites[0]);
    const t = await p.locator(".feuille").innerText();
    assert.ok(/motion de renvoi en comité \(procédure\)\s*contre/.test(t) && /adoption du projet de loi\s*pour/.test(t), t);
    assert.ok((await p.locator(".congres-source").innerText()).includes("Élu·e Exemple · listes officielles"));
    await fermer();
  });
  await verifier("Chef du Congrès : bandeau affiché (fichier des élus modifié pour le test)", async () => {
    const r = await (await p.request.get(`${ADRESSE}data/app/elus.json`)).json();
    r.par_elu["Élu·e (exemple)"].chef = { poste: "whip (2e rang du parti)", titre: "Majority Whip" };
    await p.route("**/data/app/elus.json", (route) => route.fulfill({ json: r }));
    try {
      await p.reload(); await p.waitForSelector(".onglets"); await onglet("Fil"); await p.locator(".puce", { hasText: "Tout" }).click();
      await p.locator(".ligne", { hasText: "Microsoft" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
      const t = await p.locator(".congres-chef.est-chef").innerText();
      assert.ok(t.includes("Chef du Congrès") && t.includes("whip (2e rang du parti) (Majority Whip)") && t.includes("comptent double"), t);
      await fermer();
    } finally { await p.unroute("**/data/app/elus.json"); await p.reload(); await p.waitForSelector(".onglets"); }
  });
  await verifier("Fil Politiciens : carte H.R. 7008 (étape officielle et 3 votes)", async () => {
    await onglet("Fil"); await p.locator(".puce", { hasText: "Politiciens" }).click(); await p.waitForTimeout(150);
    const c = p.locator(".carte-projet");
    assert.ok((await c.innerText()).includes("Bloqué au Sénat (clôture rejetée, 53 pour, 47 contre, 60 voix requises)"));
    const v = await p.locator(".carte-projet-vote").allInnerTexts();
    assert.equal(v.length, 3);
    assert.ok(v[0].includes("La Chambre rejette la motion de renvoi en comité (procédure), 211 pour, 218 contre"), v[0]);
    assert.ok(v[1].includes("La Chambre adopte le projet de loi, 232 pour, 198 contre"), v[1]);
    assert.ok(v[2].includes("Le Sénat rejette la clôture (60 voix requises pour ouvrir le débat), 53 pour, 47 contre"), v[2]);
    assert.equal(await c.getAttribute("href"), "https://www.govinfo.gov/bulkdata/BILLSTATUS/119/hr/BILLSTATUS-119hr7008.xml");
    await p.locator(".puce", { hasText: "Tout" }).click(); await p.waitForTimeout(150);
    assert.equal(await p.locator(".carte-projet").count(), 0);
  });
  await verifier("Sans fichier des élus : l'app marche quand même", async () => {
    const avant = erreurs.length;
    await p.route("**/data/app/elus.json", (route) => route.fulfill({ status: 404, body: "" }));
    try {
      await p.reload(); await p.waitForSelector(".onglets"); await onglet("Fil");
      await p.locator(".puce", { hasText: "Politiciens" }).click(); await p.waitForTimeout(150);
      assert.equal(await p.locator(".carte-projet").count(), 0); assert.equal(await lignes(), 2); // la transaction d'élu et le rapport de l'OGE
      await p.locator(".ligne", { hasText: "Microsoft" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
      assert.equal(await p.locator(".congres").count(), 0); await fermer();
    } finally {
      await p.unroute("**/data/app/elus.json"); await p.reload(); await p.waitForSelector(".onglets");
      await onglet("Fil"); await p.locator(".puce", { hasText: "Tout" }).click();
      // Le 404 voulu s'affiche dans la console du navigateur : ce n'est pas une erreur de l'app
      erreurs.splice(avant, erreurs.length - avant, ...erreurs.slice(avant).filter((e) => !e.includes("404")));
    }
  });
  await verifier("Détail d'un rapport de l'OGE : mention légale de l'OGE et ses 3 contrôles", async () => {
    await p.locator(".ligne", { hasText: "278-T" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    const pied = await p.locator(".detail-pied").innerText();
    assert.ok(pied.includes("Office of Government Ethics") && pied.includes("non commercial") && !pied.includes("du Congrès"), pied);
    const ok = await p.locator(".feuille .controle.ok").allInnerTexts();
    for (const c of ["Publié sans formulaire 201 (lien direct de l'OGE)", "Président, vice-président ou poste de niveau I ou II", "Document PDF officiel",
      "Nom du déclarant = index de l'OGE", "Type reconnu (achat, vente, échange)"])
      assert.ok(ok.some((x) => x.includes(c)), c);
    assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
    await fermer();
  });
  await verifier("Détail d'un rapport de l'OGE : ses 2 lignes (type, montant, symbole, avis tardif, note du déclarant)", async () => {
    await p.locator(".ligne", { hasText: "278-T" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.equal(await p.locator(".lignes-oge .ligne-oge").count(), 2);
    assert.ok((await p.locator("h3.section", { hasText: "lignes du rapport" }).innerText()).toLowerCase().includes("les 2 lignes du rapport"));
    const [l1, l2] = (await p.locator(".lignes-oge .ligne-oge").allInnerTexts()).map((t) => t.replace(/\u00a0|\u202f/g, " "));
    assert.ok(l1.includes("vente") && l1.includes("XMPL") && l1.includes("1. Exemple Corp. (XMPL)") && /15 001\s*\$ US à 50 000\s*\$ US/.test(l1), l1);
    assert.ok(l2.includes("achat") && l2.includes("avis reçu plus de 30 jours après") && l2.includes("Note du déclarant : « Placement fait par le gestionnaire (exemple). »"), l2);
    await fermer();
  });
  await verifier("Détail Gazette : encadré Détails (numéro, loi) et mention « reproduction non officielle »", async () => {
    await p.locator(".ligne", { hasText: "DORS/2026-999" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    const d = (await p.locator(".details-officiels .detail-officiel").allInnerTexts()).map((x) => x.replace(/\s+/g, " "));
    assert.equal(d.length, 3); assert.ok(d[0].includes("DORS/2026-999") && d[1].includes("Tarif des douanes"), d.join("|"));
    const pied = await p.locator(".detail-pied .mention").innerText();
    assert.ok(pied.startsWith("Reproduction non officielle") && pied.includes("TR/97-5"), pied);
    assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
    await fermer();
  });
  await verifier("Détail fusion (Bureau de la concurrence) : mention et lien de la Licence du gouvernement ouvert", async () => {
    await p.locator(".ligne", { hasText: "Acheteur (exemple)" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    const m = p.locator(".detail-pied .mention");
    assert.equal(await m.innerText(), "Contient de l'information visée par la Licence du gouvernement ouvert – Canada.");
    assert.equal(await m.locator("a").getAttribute("href"), "https://ouvert.canada.ca/fr/licence-du-gouvernement-ouvert-canada");
    assert.ok((await p.locator(".details-officiels").innerText()).includes("lettre de non-intervention"));
    await fermer();
  });
  await verifier("Détail Santé Canada : encadré Détails et mention de la Licence du gouvernement ouvert", async () => {
    await p.locator(".ligne", { hasText: "EXEMPLA" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.ok((await p.locator(".details-officiels").innerText()).includes("exemplamab 10 MG"));
    assert.equal(await p.locator(".detail-pied .mention").innerText(), "Contient de l'information visée par la Licence du gouvernement ouvert – Canada.");
    assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
    await fermer();
  });
  await verifier("Détail CCC : les 2 transactions du rapport et la mention de la CCC (usage non commercial)", async () => {
    await p.locator(".ligne", { hasText: "2 transactions signées" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.equal(await p.locator(".lignes-ccc .ligne-oge").count(), 2);
    const l1 = (await p.locator(".lignes-ccc .ligne-oge").first().innerText()).replace(/\s+/g, " ");
    assert.ok(l1.includes("Exportateur (exemple) · United States") && l1.includes("1 M$ à 5 M$") && l1.includes("Produits de défense"), l1);
    assert.ok((await p.locator(".detail-pied .mention").innerText()).includes("conditions d'utilisation de la CCC"));
    assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
    await fermer();
  });
  await verifier("Détail Trésor : encadré Détails et mention de la source (Fiscal Data)", async () => {
    await p.locator(".ligne", { hasText: "adjudication de 44 G$" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.ok((await p.locator(".details-officiels").innerText()).includes("moyenne des 6 précédentes"));
    assert.equal(await p.locator(".detail-pied .mention").innerText(), "Source : Trésor des États-Unis, Bureau of the Fiscal Service (données ouvertes Fiscal Data).");
    assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
    await fermer();
  });
  await verifier("Détail douane : message CSMS, Détails et mention de la source (CBP)", async () => {
    await p.locator(".ligne", { hasText: "Section 232 Duties" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.ok((await p.locator(".details-officiels").innerText()).includes("CSMS # 99999999"));
    assert.equal(await p.locator(".detail-pied .mention").innerText(), "Source : U.S. Customs and Border Protection (messages CSMS).");
    assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
    await fermer();
  });
  await verifier("Détail USAspending : mention de la source, date de consultation et données D&B", async () => {
    await p.locator(".ligne", { hasText: "Lockheed Martin obtient" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    const m = await p.locator(".detail-pied .mention").innerText();
    assert.ok(m.startsWith("Source : USAspending.gov, Trésor des États-Unis (Bureau of the Fiscal Service), consulté le ") && m.includes("Dun & Bradstreet (D&B)"), m);
    assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
    await fermer();
  });
  await verifier("Détail participation du gouvernement : l'extrait exact du 8-K", async () => {
    await p.locator(".ligne", { hasText: "un 8-K dit que le ministère américain du Commerce" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.ok((await p.locator(".details-officiels").innerText()).includes("United States Department of Commerce to issue shares"));
    assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
    await fermer();
  });
  await verifier("Argent : onglet, thermomètre des dirigeants, lignes du plus gros montant au plus petit", async () => {
    await onglet("Argent"); await p.waitForSelector(".ligne.argent"); await chiffresFinis();
    assert.equal(await p.locator(".grand-titre h1").innerText(), "Argent");
    // Sans espaces : selon la version du navigateur, « 2 G$ US » ou « 2 G $ US » (même montant)
    const sans = (t) => t.replace(/\s+/g, "");
    const montants = (await p.locator(".ligne.argent .argent-montant").allInnerTexts()).map(sans);
    assert.equal(montants[0], "2G$US"); // le contrat de Lockheed (TEST), 2 G$
    const thermo = sans(await p.locator(".thermo").innerText());
    assert.ok(thermo.includes("10,1M$USachetés(3)") && thermo.includes("1,5M$USvendus(1)"), thermo);
    const nvda = sans(await p.locator(".ligne.argent", { hasText: "NVDA" }).innerText());
    assert.ok(nvda.includes(sans("Jensen Huang (CEO) achète 50 000 actions à 124,00 $ US")) && nvda.includes(sans("+5 % de ses actions")) && nvda.includes("6,2M$US"), nvda);
  });
  await verifier("Argent : la vente déclarée aussi par une entité liée compte une fois ; 20 % de ses actions vendues", async () => {
    assert.equal(await p.locator(".ligne.argent", { hasText: "XMPL" }).count(), 1);
    const x = (await p.locator(".ligne.argent", { hasText: "XMPL" }).innerText()).replace(/\s+/g, " ");
    assert.ok(x.includes("20 % de ses actions vendues") && x.includes("aussi déclarée par 1"), x);
  });
  await verifier("Argent : filtres Achats, Élus (fourchette officielle) et Contrats", async () => {
    try {
      await p.locator(".puce", { hasText: "Achats" }).click(); await p.waitForTimeout(150);
      assert.equal(await p.locator(".ligne.argent").count(), 3);
      assert.equal(await p.locator(".ligne.argent .argent-sens.achat").count(), 3);
      await p.locator(".puce", { hasText: "Élus" }).click(); await p.waitForTimeout(150);
      const elu = (await p.locator(".ligne.argent").first().innerText()).replace(/\s+/g, "");
      assert.ok(elu.includes("fourchetteofficielle") && elu.includes("15k$USà50k$US"), elu);
      await p.locator(".puce", { hasText: "Contrats" }).click(); await p.waitForTimeout(150);
      assert.equal(await p.locator(".ligne.argent").count(), 2);
    } finally {
      await p.locator(".puce", { hasText: "Tout" }).click(); await p.waitForTimeout(150); // même en cas d'échec
    }
  });
  await verifier("Argent : toucher une ligne ouvre le détail avec le document officiel", async () => {
    try {
      await p.locator(".ligne.argent", { hasText: "NVDA" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
      assert.ok((await p.locator(".detail-titre").innerText()).includes("le PDG de Nvidia achète 50 000 actions"));
      assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
      await fermer();
    } finally {
      await filTout(); // les tests suivants partent du fil, même en cas d'échec
    }
  });
  await verifier("Fil : tri sur place, plus gros montant d'abord (44 G$ du Trésor), puis retour au plus récent", async () => {
    try {
      await p.locator(".segment", { hasText: "Plus gros montant" }).click(); await p.waitForTimeout(200);
      assert.ok((await p.locator(".ligne").first().innerText()).includes("adjudication de 44 G$"));
    } finally {
      await p.locator(".segment", { hasText: "Plus récent" }).click(); await p.waitForTimeout(200);
    }
  });
  await verifier("Fil : une vente déclarée aussi par une entité liée n'apparaît qu'une fois, avec son nom", async () => {
    assert.equal(await p.locator(".ligne", { hasText: "vend 100 000 actions" }).count(), 1);
    await p.locator(".ligne", { hasText: "vend 100 000 actions" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.equal(await p.locator(".aussi-declare").innerText(),
      "Même transaction déclarée aussi par Fonds lié (exemple) (entités liées) : elle est comptée une seule fois.");
    await fermer();
  });
  await verifier("Détail d'un 13D : le but écrit par le déclarant", async () => {
    await p.locator(".ligne", { hasText: "Intel" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.ok((await p.locator(".feuille").innerText()).includes("But écrit par le déclarant (point 4 du 13D) : « The Reporting Persons believe the Shares are undervalued (exemple). »"));
    await fermer();
  });
  await verifier("Tuiles des catégories : un nombre partout (toutes branchées)", async () => {
    await onglet("Radar"); assert.equal(await p.locator(".cat-phase").count(), 0); assert.equal(await p.locator(".cat-nombre").count(), 6);
    await onglet("Fil");
  });
  await verifier("Étoile dans le détail : ajoute AAPL aux favoris", async () => {
    await p.locator(".ligne", { hasText: "Apple" }).click(); await p.waitForSelector(".feuille-fond.ouvert");
    await p.locator(".symbole-grand", { hasText: "AAPL" }).click(); await fermer();
    await onglet("Favoris"); assert.equal(await lignes(), 1);
  });
  await verifier("Favoris : ajout à la main (lmt → LMT)", async () => { await p.fill(".ajout input", "lmt"); await p.click(".ajout button[type=submit]"); assert.equal(await lignes(), 2); });
  await verifier("Favoris : symbole invalide refusé", async () => { await p.fill(".ajout input", "APPLE INC"); assert.ok(await p.locator(".ajout button[type=submit]").isDisabled()); await p.fill(".ajout input", ""); });
  await verifier("Favoris : retirer LMT", async () => { await p.getByRole("button", { name: "Retirer LMT" }).click(); assert.equal(await lignes(), 1); });

  const remettre = async (fn) => { await reglages(); await fn(); };
  await verifier("Réglage : seulement les confirmées (fil = 1)", async () => {
    await reglages(); await inter("Seulement les confirmées"); await filTout(); try { assert.equal(await lignes(), 1); } finally { await remettre(() => inter("Seulement les confirmées")); }
  });
  await verifier("Réglage : montrer les « À vérifier » (fil = 21)", async () => {
    await reglages(); await inter("Montrer les infos à vérifier"); await filTout(); try { assert.equal(await lignes(), 21); } finally { await remettre(() => inter("Montrer les infos à vérifier")); }
  });
  await verifier("Réglage : montant minimum 1 M$ (fil = 18 : les infos sans montant restent)", async () => {
    await reglages(); await p.getByRole("radio", { name: "1 M$" }).click(); await filTout(); try { assert.equal(await lignes(), 18); } finally { await remettre(() => p.getByRole("radio", { name: "Tous" }).click()); }
  });
  await verifier("Réglage : cacher Politiciens (fil = 18)", async () => {
    await reglages(); await inter("Politiciens"); await filTout(); try { assert.equal(await lignes(), 18); } finally { await remettre(() => inter("Politiciens")); }
  });
  await verifier("Réglage : catégorie cachée alors qu'elle était filtrée → retour à Tout", async () => {
    await onglet("Fil"); await p.locator(".puce", { hasText: "Politiciens" }).click(); await reglages(); await inter("Politiciens"); await onglet("Fil");
    try { assert.equal(await p.locator(".puce.actif").innerText(), "Tout"); assert.equal(await lignes(), 18); } finally { await remettre(() => inter("Politiciens")); await filTout(); }
  });
  await verifier("Réglage : trier par montant (1er = 44 G$ du Trésor, 2e = 2 G$ LMT)", async () => {
    await reglages(); await p.getByRole("radio", { name: "Plus gros montant" }).click(); await filTout();
    try {
      assert.ok((await p.locator(".ligne").nth(0).innerText()).includes("adjudication de 44 G$"));
      assert.ok((await p.locator(".ligne").nth(1).innerText()).includes("Lockheed"));
    } finally { await remettre(() => p.getByRole("radio", { name: "Plus récent" }).click()); }
  });
  await verifier("Réglage : thème clair", async () => { await reglages(); await p.getByRole("radio", { name: "Clair" }).click(); assert.equal(await p.evaluate(() => document.documentElement.dataset.theme), "clair"); });
  await verifier("Réglage : texte grand (18 px)", async () => { await reglages(); await p.getByRole("radio", { name: "Grande" }).click(); assert.equal(await p.evaluate(() => document.documentElement.style.fontSize), "18px"); });
  await verifier("Réglage : couleur verte", async () => { await reglages(); await p.getByRole("radio", { name: "vert" }).click(); assert.equal(await p.evaluate(() => document.documentElement.style.getPropertyValue("--accent")), "#2BD9A0"); });
  await verifier("Réglages gardés après fermeture de l'app", async () => { await p.reload(); await p.waitForSelector(".onglets"); assert.equal(await p.evaluate(() => document.documentElement.dataset.theme), "clair"); });
  await verifier("Réinitialiser les réglages (retour au sombre)", async () => {
    await reglages(); await p.getByRole("button", { name: /Réinitialiser/ }).click(); await p.waitForTimeout(200);
    assert.equal(await p.evaluate(() => document.documentElement.dataset.theme), "sombre");
  });
  await verifier("État des sources : 55 sources listées", async () => { await reglages(); await p.getByRole("button", { name: /État des sources/ }).click(); await p.waitForSelector(".source"); assert.equal(await p.locator(".source").count(), 55); });
  await verifier("Sources : un site qui refuse le robot (403) : « Refusée par le site », point violet, nouvel essai daté", async () => {
    const s = p.locator(".source", { hasText: "LEGISinfo" });
    const etat = await s.locator(".source-etat").innerText();
    assert.ok(etat.startsWith("Refusée par le site") && etat.includes("Le site refuse l'accès au robot (erreur 403) depuis le ")
      && etat.includes("Radar respecte ce refus et réessaie une fois le "), etat);
    assert.equal(await s.locator(".point.violet").count(), 1);
    assert.ok((await p.locator(".resume").innerText()).includes("Refusées par le site · 1"));
  });
  await verifier("Bouton retour vers Réglages", async () => { await p.locator(".retour").click(); await p.waitForTimeout(200); assert.ok(await p.getByRole("button", { name: /Comment c'est vérifié/ }).isVisible()); });
  await verifier("Réglages : « Comment marche Radar (aide) » ouvre l'aide", async () => {
    await p.getByRole("button", { name: /Comment marche Radar/ }).click(); await p.waitForSelector(".flux-etape");
    assert.equal(await p.locator(".flux-etape").count(), 5); await p.locator(".retour").click(); await p.waitForTimeout(200);
  });
  await verifier("Réglages : lien vers le calcul du score", async () => {
    await p.getByRole("button", { name: /Comment le score est calculé/ }).click(); await p.waitForTimeout(200);
    assert.equal(await p.locator(".regle").count(), 13); await p.locator(".retour").click(); await p.waitForTimeout(200);
  });
  await verifier("À vérifier : le piège y est, avec le contrôle raté", async () => {
    await p.getByRole("button", { name: /^À vérifier/ }).click(); await p.waitForSelector(".ligne"); assert.equal(await lignes(), 1);
    await p.locator(".ligne").first().click(); await p.waitForSelector(".feuille-fond.ouvert");
    const rates = await p.locator(".controle.rate").allInnerTexts();
    assert.ok(rates.some((r) => r.includes("site officiel")), rates.join(" | ")); await fermer();
  });
  await verifier("Hors ligne : l'app s'ouvre quand même (copie gardée)", async () => {
    await p.evaluate(async () => { await navigator.serviceWorker.register("./sw.js"); await navigator.serviceWorker.ready; });
    await p.reload(); await p.waitForSelector(".onglets"); await p.waitForTimeout(500);
    await ctx.setOffline(true); await p.reload(); await p.waitForSelector(".onglets", { timeout: 5000 });
    assert.ok(await p.locator(".grand-titre h1").isVisible()); await ctx.setOffline(false);
  });
  await verifier("Réglage iPhone « Réduire les animations » : radar immobile, chiffres finaux tout de suite", async () => {
    const calme = await b.newContext({ viewport: { width: 390, height: 844 }, locale: "fr-CA", reducedMotion: "reduce" });
    try {
      const q = await calme.newPage();
      await q.goto(ADRESSE); await q.waitForSelector(".radar-cible");
      assert.equal(await q.locator(".radar-balai").evaluate((e) => getComputedStyle(e).animationName), "none");
      assert.equal(await q.locator(".radar-marque").first().evaluate((e) => getComputedStyle(e).animationName), "none");
      const finals = await q.locator("[data-defile]").evaluateAll((els) => els.map((e) => e.dataset.final));
      assert.ok(finals.length >= 3 && finals.every((f) => f === "1"), finals.join(","));
      await q.getByRole("button", { name: "Aide" }).click(); await q.waitForSelector(".flux-point");
      assert.equal(await q.locator(".flux-point").evaluate((e) => getComputedStyle(e).animationName), "none");
    } finally {
      await calme.close();
    }
  });

  console.log(res.join("\n"));
  console.log(`\n${res.filter((r) => r.startsWith("OK")).length}/${res.length} réussis · erreurs navigateur : ${erreurs.length ? erreurs.join(" | ") : "aucune"}`);
  await b.close();
  if (res.some((r) => r.startsWith("ÉCHEC")) || erreurs.length) process.exit(1);
})();
