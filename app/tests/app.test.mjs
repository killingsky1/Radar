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
  await verifier("Radar animé : seulement les hausses (AMD, NVDA), la baisse (XMPL) dans sa carte, plus près du centre = note plus haute", async () => {
    const cibles = p.locator(".radar-cible");
    assert.equal(await cibles.count(), 2);
    const etiquettes = await p.locator(".radar-etiquette").allInnerTexts();
    assert.deepEqual([...etiquettes].sort(), ["AMD", "NVDA"]);
    assert.equal(await p.locator(".radar-cible.baisse").count(), 0);
    assert.ok((await p.locator(".alerte-baisse").innerText()).includes("1 à surveiller à la baisse"));
    const legende = (await p.locator(".radar-legende").innerText()).replace(/\u00a0|\u202f/g, " ");
    assert.ok(legende.includes("À la hausse") && legende.includes("Plus près du centre : note plus haute") && !legende.includes("Baisse"), legende);
    // Le balayage tourne et chaque point s'allume (animations CSS actives)
    assert.equal(await p.locator(".radar-balai").evaluate((e) => getComputedStyle(e).animationName), "balayage");
    // Distance au centre : la note la plus haute est la plus proche du centre
    const pos = await cibles.evaluateAll((els) => els.map((e) => [e.getAttribute("aria-label"), Math.hypot(parseFloat(e.style.left) - 50, parseFloat(e.style.top) - 50)]));
    const note = (l) => parseFloat(l.match(/note (\d+,\d)/)[1].replace(",", "."));
    const tries = [...pos].sort((a, b) => note(b[0]) - note(a[0]));
    assert.ok(tries.every((x, i) => i === 0 || x[1] >= tries[i - 1][1] - 0.01), JSON.stringify(pos));
    assert.ok(tries[0][1] < tries[tries.length - 1][1], JSON.stringify(pos));
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
  await verifier("Aide : bouton « ? » du Radar, chemin en 5 étapes, heures des robots, « Bon à savoir », liens", async () => {
    try {
      await p.getByRole("button", { name: "Aide" }).click(); await p.waitForSelector(".flux-etape");
      assert.equal(await p.locator(".grand-titre h1").innerText(), "Aide");
      const etapes = await p.locator(".flux-etape b").allInnerTexts();
      assert.deepEqual(etapes, ["1. Sources officielles", "2. Robots", "3. Contrôles", "4. Labo", "5. Note"]);
      assert.deepEqual(await p.locator(".passage b").allInnerTexts(), ["7 h 07", "9 h 47", "12 h 37", "18 h 17", "23 h 17"]);
      const texte = (await p.locator(".ecran").innerText()).replace(/\u00a0/g, " ");
      assert.ok(texte.includes("2 jours ouvrables après la transaction") && texte.toLowerCase().includes("bon à savoir")
        && texte.includes("Note sur 10 = 5 + points × 5/6") && texte.includes("Pas un conseil financier"), texte.slice(0, 300));
      for (const mot of ["laissées de côté", "403", "dans ce cas", "les limites", "vente de l'app", "aucune source de prix", "ne mesure pas"]) assert.ok(!texte.toLowerCase().includes(mot), mot);
      assert.ok(texte.includes("Santé financière : sur la fiche, 9 critères") && texte.includes("Piotroski (2000)"), "santé financière dans l'aide");
      assert.equal(await p.locator('a.etude[href*="ivey.uwo.ca"]').count(), 1);
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
  await verifier("Comment le score est calculé : 13 règles, 21 liens d'études (dont Brochet pour « Récent ») + le rejeu du labo, règles des chefs", async () => {
    await p.getByRole("button", { name: "Comment le score est calculé" }).click(); await p.waitForTimeout(250);
    assert.equal(await p.locator(".regle").count(), 13);
    // lot L : Cohen, Malloy et Pomorski aussi sous les ventes (routiniers) ; lot M : + le rejeu de 3 ans du labo
    assert.equal(await p.locator("a.etude").count(), 22);
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
    // La formule montre les points avec 2 décimales (ex. « −6,88 ») : arrondis au dixième, ce sont ceux du score
    const formule = t.match(/Note = 5 \+ \((−?\d+(?:,\d+)?)\)/);
    assert.ok(formule && (Math.round(parseFloat(formule[1].replace("−", "-").replace(",", ".")) * 10) / 10).toLocaleString("fr-CA")
      .replace("-", "−") === (age ? "−6,7" : "−6,9") && t.includes(") × 5/6, entre 0 et 10, arrondie au dixième"), t);
  });
  await verifier("Retour : Suggestions puis Accueil", async () => {
    await p.locator(".retour").click(); await p.waitForTimeout(200);
    assert.equal(await p.locator(".grand-titre h1").innerText(), "Suggestions");
    // Hausse : AMD et NVDA, puis MIKR dans « Écartées » (lot M)
    await p.locator(".segment", { hasText: "Hausse" }).click(); assert.equal(await p.locator(".ligne.suggestion").count(), 3);
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
  await verifier("Fiche : bouton « Voir le cours » (Yahoo Finance, nouvel onglet), aussi pour une baisse", async () => {
    for (const [sym, baisse] of [["AMD", false], ["XMPL", true]]) {
      await fiche(sym, async () => {
        const a = p.locator("a.bouton-cours");
        assert.equal(await a.count(), 1);
        assert.equal((await a.innerText()).trim(), "Voir le cours");
        assert.equal(await a.getAttribute("href"), `https://finance.yahoo.com/quote/${sym}/`);
        assert.equal(await a.getAttribute("target"), "_blank");
        assert.ok((await a.getAttribute("rel")).includes("noopener"));
        assert.ok((await p.locator(".fiche-cours-source").innerText()).includes("Yahoo Finance, un site externe"));
      }, baisse);
    }
  });
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
  await verifier("Fiche NVDA : aucun rapport de lobbying ce trimestre → pas de section (ni « Aucun rapport »)", () => fiche("NVDA", async () => {
    assert.equal(await p.locator(".lobbying").count(), 0);
    const t = await p.locator(".ecran").last().innerText();
    assert.ok(!t.includes("Lobbying à Washington") && !t.includes("Aucun rapport") && !t.includes("ne sont pas cherchés"), t);
  }));
  await verifier("Fiche AMD : rachats d'actions faits (rapport annuel, XBRL de la SEC), lien du rapport", () => fiche("AMD", async () => {
    const total = (await p.locator(".rachats-total").innerText()).replace(/\s/g, "");
    assert.ok(total.includes("1,23G$US"), total);
    const t = (await p.locator(".rachats-faits").innerText()).replace(/\u00a0|\u202f/g, " ");
    assert.ok(t.includes("pendant l'exercice du 29 décembre 2024 au 27 décembre 2025, selon son rapport annuel") && t.includes("0000002488-26-000018"), t);
    assert.equal(await p.locator(".rachats-faits a.transaction").getAttribute("href"), "https://www.sec.gov/Archives/edgar/data/2488/000000248826000018/0000002488-26-000018-index.htm");
    const pied = (await p.locator(".rachats-source").innerText()).replace(/\u00a0/g, " ");
    assert.ok(pied.includes("Payments for Repurchase of Common Stock") && pied.includes("l'année 2025") && pied.includes("0 point"), pied);
  }));
  await verifier("Fiche NVDA : aucun montant de rachat (XBRL) → pas de section (ni « Aucun montant »)", () => fiche("NVDA", async () => {
    assert.equal(await p.locator(".rachats-faits").count(), 0);
    const t = await p.locator(".ecran").last().innerText();
    assert.ok(!t.includes("Rachats d'actions faits") && !t.includes("Aucun montant") && !t.includes("autre étiquette"), t);
  }));
  await verifier("Fiche AMD : santé financière 8/9 (9 critères en clair, rapport annuel à la SEC, étude de Piotroski)", () => fiche("AMD", async () => {
    assert.equal((await p.locator(".sante-total").innerText()).replace(/\s/g, ""), "8/9");
    assert.equal(await p.locator(".sante .critere").count(), 9);
    assert.equal(await p.locator(".sante .critere.oui").count(), 8);
    assert.equal(await p.locator(".sante .critere-titre").first().innerText(), "Fait des profits");
    const titre = (await p.locator("h2.section", { hasText: "Santé financière" }).innerText()).toLowerCase().replace(/\u00a0|\u202f/g, " ");
    assert.ok(titre.includes("santé financière · exercice terminé le"), titre);
    assert.ok(/^https:\/\/www\.sec\.gov\/Archives\/edgar\/data\/2488\/\d{18}\/\d{10}-\d{2}-\d{6}-index\.htm$/.test(await p.locator(".sante a.transaction").getAttribute("href")));
    // Le numéro du rapport tient sur une seule ligne (iPhone 390 px : pas coupé au trait d'union)
    const lignesAccn = await p.locator(".sante a.transaction .accn").evaluate((el) => {
      const r = document.createRange();
      r.selectNodeContents(el);
      return new Set([...r.getClientRects()].map((x) => Math.round(x.top))).size;
    });
    assert.equal(lignesAccn, 1);
    const pied = (await p.locator(".sante-source").innerText()).replace(/\u00a0/g, " ");
    assert.ok(pied.includes("Piotroski (2000)") && pied.includes("0 point dans la note"), pied);
  }));
  await verifier("Fiche NVDA : santé financière incomplète → pas de section", () => fiche("NVDA", async () => {
    assert.equal(await p.locator(".sante").count(), 0);
    assert.ok(!(await p.locator(".ecran").last().innerText()).toLowerCase().includes("santé financière"));
  }));
  await verifier("Fiche AMD : taille en bourse (grande, actions × prix de la SEC, vrais seuils du NYSE), pas de bonus", () => fiche("AMD", async () => {
    const t = (await p.locator(".taille").innerText()).replace(/\u00a0|\u202f/g, " ");
    const sans = t.replace(/\s/g, "");
    assert.ok(t.includes("Grande compagnie") && t.includes("1 620 000 000 actions déclarées au") && t.includes("(prix de la SEC du"), t);
    assert.ok(sans.includes("259,2G$US") && sans.includes("Petite:moinsde2,24G$US(30ecentiledescompagniesduNYSE,août2026);grande:13,37G$USetplus(70ecentile)."), t);
    assert.ok(!t.includes("×1,5"), t);
    assert.ok((await p.locator(".taille-source").innerText()).includes("Kenneth French"));
    assert.ok(!(await p.locator(".calcul").innerText()).includes("Petite compagnie"));
  }));
  await verifier("Fiche NVDA : taille inconnue (prix de la SEC trop vieux), avec la raison", () => fiche("NVDA", async () => {
    const t = (await p.locator(".taille").innerText()).replace(/\u00a0|\u202f/g, " ");
    assert.ok(t.includes("Taille inconnue") && t.includes("Pas calculée : pas de prix de la SEC depuis 60 jours. Pas de bonus de petite compagnie."), t);
  }));
  await verifier("Fiche XMPL : sans fiche SEC → pas de section taille ; vente d'un initié routinier (exemple) : 0 point, raison et mois", () => fiche("XMPL", async () => {
    assert.equal(await p.locator(".taille").count(), 0);
    const t = (await p.locator(".ecran").last().innerText()).replace(/\u00a0|\u202f/g, " ");
    const an = new Date().getFullYear();
    assert.ok(t.toLowerCase().includes("autres infos (0 point)") && t.includes("Fonds lié (exemple) vend"), t); // titre en majuscules (CSS)
    assert.ok(t.includes("Initié « routinier » : il a acheté ou vendu des actions de cette compagnie en bourse dans le même mois de l'année") &&
      t.includes(`Mois : mars et septembre (${an - 3}, ${an - 2} et ${an - 1}).`), t);
  }, true));
  await verifier("Fiche XMPL : recherche de lobbying trop large → pas de section (ni « pas vérifié »)", () => fiche("XMPL", async () => {
    assert.equal(await p.locator(".lobbying").count(), 0);
    assert.ok(!(await p.locator(".ecran").last().innerText()).includes("pas vérifié"));
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
      await p.locator(".puce", { hasText: /^Achats$/ }).click(); await p.waitForTimeout(150);
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
  await verifier("Argent : filtre Rachats (un plafond, pas un achat fait ; 0 point), détail avec l'extrait officiel", async () => {
    try {
      await p.locator(".puce", { hasText: "Rachats" }).click(); await p.waitForTimeout(150);
      assert.equal(await p.locator(".ligne.argent").count(), 1);
      const l = (await p.locator(".ligne.argent").first().innerText()).replace(/\s+/g, " ");
      assert.ok(l.includes("AMD") && l.includes("Nouveau programme de rachat d'actions autorisé par le conseil : un plafond, pas un achat fait"), l);
      assert.ok(l.replace(/\s/g, "").includes("1,5G$US"), l);
      assert.equal(await p.locator(".ligne.argent .argent-sens.rachat").count(), 1);
      const e = (await p.locator(".explication").last().innerText()).replace(/\u00a0/g, " ");
      assert.ok(e.includes("1 annonce de rachat d'actions") && e.includes("pas un achat fait") && e.includes("0 point dans la note"), e);
      await p.locator(".ligne.argent").first().click(); await p.waitForSelector(".feuille-fond.ouvert");
      const titre = await p.locator(".detail-titre").innerText();
      assert.ok(titre.includes("nouveau programme de rachat d'actions, jusqu'à 1,5 G$"), titre);
      const d = (await p.locator(".feuille").innerText()).replace(/\u00a0/g, " ");
      assert.ok(d.includes("the Board of Directors approved a new $1.5 billion share repurchase program") && d.includes("pas un achat fait"), d.slice(0, 400));
      assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
      for (const c of ["Formule d'autorisation lue (nouveau programme, hausse ou nouveau total)", "Conseil d'administration nommé dans la phrase", "Même plafond partout dans le dépôt", "Point du 8-K lu (2.02, 7.01 ou 8.01)", "10 M$ et plus (ou un nombre d'actions)", "Pas déjà annoncé dans ses 8-K des 90 jours avant"]) {
        assert.equal(await p.locator(".feuille .controle", { hasText: c }).count(), 1, c);
      }
      await fermer();
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
  await verifier("Radar : la page ne dépasse jamais l'écran sur le côté pendant le balayage (390 px)", async () => {
    await onglet("Radar");
    const largeurMax = await p.evaluate(() => new Promise((ok) => {
      let max = 0; const t0 = performance.now();
      const f = () => { max = Math.max(max, document.documentElement.scrollWidth); performance.now() - t0 < 4200 ? requestAnimationFrame(f) : ok(max); };
      requestAnimationFrame(f);
    }));
    assert.equal(largeurMax, 390); // un tour complet du balayage (4 s)
  });
  await verifier("Calendrier : sur le Radar, les 3 prochaines fins de blocage (pas la passée), dans l'ordre", async () => {
    await onglet("Radar");
    const l = p.locator(".carte.calendrier .cal-ligne");
    assert.equal(await l.count(), 3);
    const noms = (await l.locator(".ligne-titre").allInnerTexts()).map((t) => t.split("\n").pop().trim());
    assert.deepEqual(noms, ["Fusée Exemple Inc.", "Biotech Exemple Inc.", "Ferme Exemple Inc."]);
    assert.ok((await l.nth(0).innerText()).includes("Fin du blocage de 180 jours"));
  });
  await verifier("Calendrier : toucher une fin de blocage ouvre la fiche officielle (0 point)", async () => {
    await p.locator(".carte.calendrier .cal-ligne").first().click(); await p.waitForSelector(".feuille-fond.ouvert");
    const t = (await p.locator(".feuille").textContent()).replace(/\u00a0/g, " ");
    assert.ok(t.includes("TEST : Fusée Exemple Inc. : fin prévue du blocage de 180 jours le") && t.includes("Fin prévue du blocage")
      && t.includes("0 point dans la note"), t.slice(0, 300));
    for (const c of ["Vraie entrée en bourse (pas un SPAC ni une inscription directe)", "Date du prospectus écrite dans le document",
      "Une seule durée de blocage, dans la phrase citée", "Fin = date du prospectus + durée", "Aucune levée anticipée mentionnée"]) {
      assert.ok(t.includes(c), c);
    }
    assert.equal(await p.locator(".feuille .controle.rate").count(), 0);
    await fermer();
  });
  await verifier("Calendrier : « Tout voir » groupe par mois, la fin passée est marquée", async () => {
    try {
      await p.locator(".section-ligne", { hasText: "Fins de blocage à venir" }).locator(".lien").click(); await p.waitForTimeout(250);
      assert.equal(await p.locator(".grand-titre h1").innerText(), "Calendrier");
      const noms = (await p.locator(".cal-ligne .ligne-titre").allInnerTexts()).map((t) => t.split("\n").pop().trim());
      assert.deepEqual(noms, ["Ancienne Exemple Inc.", "Fusée Exemple Inc.", "Biotech Exemple Inc.", "Ferme Exemple Inc."]);
      assert.equal(await p.locator(".cal-ligne.passee").count(), 1);
      assert.ok((await p.locator(".cal-ligne.passee").innerText()).includes("Blocage terminé le"));
      const mois = await p.locator(".groupe .section").allInnerTexts();
      assert.ok(mois.length >= 2 && mois.every((m) => /^[a-zéû]+ \d{4}$/i.test(m)), mois.join(" | "));
      assert.ok((await p.locator(".explication").innerText()).includes("0 point dans la note"));
    } finally {
      await onglet("Radar");
    }
  });
  await verifier("Aide : les rachats d'actions (0 point, l'étude et sa limite)", async () => {
    try {
      await p.getByRole("button", { name: "Aide" }).click(); await p.waitForSelector(".flux-etape");
      const t = (await p.locator(".ecran").innerText()).replace(/\u00a0/g, " ");
      assert.ok(t.includes("Rachats : quand le conseil d'une compagnie autorise un rachat de ses actions (8-K), le plafond annoncé, pas un achat fait.") && t.includes("Rachats d'actions (8-K)"), t.slice(0, 200));
      assert.ok(t.includes("+12,1 % sur 4 ans") && t.includes("+45,3 % pour les actions bon marché"), t.slice(0, 200));
      assert.equal(await p.locator('a.etude[href="https://www.nber.org/papers/w4965"]').count(), 1);
    } finally {
      await onglet("Radar");
    }
  });
  await verifier("Aide : le calendrier (0 point), sa limite et son lien", async () => {
    try {
      await p.getByRole("button", { name: "Aide" }).click(); await p.waitForSelector(".flux-etape");
      const t = (await p.locator(".ecran").innerText()).replace(/\u00a0/g, " ");
      assert.ok(t.includes("Information seulement : 0 point dans la note.") && t.includes("Fins de blocage (prospectus 424B4)"), t.slice(0, 200));
      await p.locator(".lien-rangee", { hasText: "Voir le calendrier" }).click(); await p.waitForTimeout(250);
      assert.equal(await p.locator(".grand-titre h1").innerText(), "Calendrier");
    } finally {
      await onglet("Radar");
    }
  });
  await verifier("Résultats : carte du Radar (taux sur les prix officiels de la SEC)", async () => {
    await onglet("Radar");
    const t = (await p.locator(".res-carte").innerText()).replace(/\u00a0/g, " ");
    assert.equal(t.trim(), "1 semaine : 1 sur 1 ont frappé juste · 1 mois : 0 sur 1 ont frappé juste");
  });
  await verifier("Résultats : page — taux, verdicts en mots, cas douteux montrés mais pas comptés", async () => {
    try {
      await p.locator(".res-carte").click(); await p.waitForTimeout(300);
      assert.equal(await p.locator(".grand-titre h1").innerText(), "Résultats");
      const t = (await p.locator(".ecran").textContent()).replace(/\u00a0/g, " ");
      for (const attendu of [
        "1 sur 1 · écart moyen +6,1 points", // 1 semaine, hausse : AAPL
        "0 sur 1 · écart moyen -7,5 points", // 1 mois, hausse : AAPL
        "+3,8 % au 30 juill. · marché -2,4 % (IVV) : a battu le marché", // fr-CA : « juill. »
        "-5,1 % au 24 août · marché +2,5 % (SPY) : n'a pas battu le marché",
        "pas comparable : nouveau code de titre (CUSIP 26923N173 → 26923Y708)",
        "+172,4 % à vérifier : saut de prix anormal",
        "Départ : en attente des prix de la SEC (vers le 15 octobre 2026)",
        "Départ : pas de prix officiel ces jours-là",
        "Prix de la SEC publiés jusqu'au 14 septembre 2026.",
      ]) assert.ok(t.replace(/−/g, "-").includes(attendu), attendu);
      // + l'écartée (lot M, à part) : 1 semaine rouge (la règle s'est trompée), 1 mois vert (la règle avait raison)
      assert.equal(await p.locator(".res-horizon.vert").count(), 2);
      assert.equal(await p.locator(".res-horizon.rouge").count(), 2);
      assert.equal(await p.locator(".res-ligne").count(), 7);
      assert.equal(await p.locator(".groupe", { hasText: "Compagnies suivies (6)" }).locator(".res-ligne").count(), 6);
      assert.ok(t.includes("jamais une clôture que Radar connaissait"));
    } finally {
      await onglet("Radar");
    }
  });
  await verifier("Résultats : par signal (une entrée compte dans chacun de ses signaux) et pourquoi de chaque entrée", async () => {
    try {
      await p.locator(".res-carte").click(); await p.waitForTimeout(300);
      const groupes = await p.locator("h2.section", { hasText: "Par signal" }).allTextContents(); // texte, pas les majuscules du CSS
      assert.deepEqual(groupes, ["Par signal · à la hausse", "Par signal · à la baisse"]);
      const achat = (await p.locator(".res-signal", { hasText: "Achat d'actions par un dirigeant ou un administrateur" }).innerText()).replace(/\u00a0/g, " ").replace(/−/g, "-");
      assert.ok(achat.includes("3 entrées · 1 semaine : 1 sur 1 (+6,1 points) · 1 mois : 0 sur 1 (-7,5 points)"), achat);
      const taille = (await p.locator(".res-signal", { hasText: "Entrée grâce au bonus de petite compagnie" }).innerText()).replace(/\u00a0/g, " ");
      assert.ok(taille.includes("1 entrée · pas encore mesuré"), taille);
      const baisse = (await p.locator(".res-signal", { hasText: "La SEC ouvre une procédure contre la compagnie" }).innerText()).replace(/\u00a0/g, " ");
      assert.ok(baisse.includes("1 entrée"), baisse);
      const t = (await p.locator(".ecran").textContent()).replace(/\u00a0/g, " ");
      assert.ok(t.includes("2 entrées d'avant le 5 octobre 2026 : raisons pas notées"), t);
      assert.ok(t.includes("Pourquoi : Achat d'actions par un dirigeant ou un administrateur (Petite compagnie) · petite compagnie · entrée grâce au bonus de petite compagnie"), t);
      assert.ok(t.includes("Pourquoi : Achat d'actions par un dirigeant ou un administrateur · Un gestionnaire de fonds dépasse 5 % avec des intentions actives (13D) · compagnie moyenne · entrée grâce au bonus de familles"), t);
      assert.equal(await p.locator(".res-ligne", { hasText: "Pourquoi" }).count(), 5); // LESL et XMPL : d'avant (sans raisons) ; + l'écartée
    } finally {
      await onglet("Radar");
    }
  });
  await verifier("Aide et méthode : petite compagnie ×1,5 et initiés routiniers à 0 point expliqués", async () => {
    try {
      await p.getByRole("button", { name: "Aide" }).click(); await p.waitForSelector(".flux-etape");
      const t = (await p.locator(".ecran").last().innerText()).replace(/\u00a0/g, " ");
      assert.ok(t.includes("Taille en bourse = actions en circulation déclarées à la SEC × dernier prix de la SEC") && t.includes("30e centile"), t);
      assert.ok(t.includes("Un initié qui achète ou vend en bourse dans le même mois de l'année, chacune des 3 années précédentes"), t);
      assert.ok(t.includes("chaque entrée garde ses raisons"), t);
      await p.locator(".lien-rangee", { hasText: "Comment le score est calculé" }).click(); await p.waitForTimeout(250);
      const r = (await p.locator(".regle", { hasText: "Achat d'actions par un dirigeant" }).innerText()).replace(/\u00a0/g, " ");
      assert.ok(r.includes("×1,5 si c'est une petite compagnie") && r.includes("0 point si l'initié est « routinier »"), r);
    } finally {
      await onglet("Radar");
    }
  });
  await verifier("Suggestions : les écartées (moins de 100 M$) sous la liste hausse, avec la raison ; rien sous la baisse", async () => {
    try {
      await onglet("Radar"); await p.locator(".alerte-baisse").click(); await p.waitForTimeout(250);
      assert.equal(await p.locator("h2.section", { hasText: "Écartées" }).count(), 0); // vue « baisse »
      await p.locator(".segment", { hasText: "Hausse" }).click(); await p.waitForTimeout(150);
      assert.equal(await p.locator(".segment.actif").innerText(), "Hausse · 2");
      assert.equal(await p.locator("h2.section", { hasText: "Écartées" }).textContent(), "Écartées · 1");
      const t = (await p.locator(".ecran").innerText()).replace(/\u00a0/g, " ");
      assert.ok(t.includes("Moins de 100 M$ en bourse : hors de la liste « hausse ». Dans le rejeu de 3 ans du labo, ces compagnies ont fait pire que le S&P 500 chacune des 3 années."), t);
      const listes = p.locator(".carte.liste");
      assert.deepEqual(await listes.nth(0).locator(".symbole").allTextContents(), ["AMD", "NVDA"]);
      assert.deepEqual(await listes.nth(1).locator(".symbole").allTextContents(), ["MIKR"]);
      // La note dépend du jour du test (les bonus « Récent » des autres compagnies d'essai changent le calcul) : on la lit
      // dans les données servies à l'app, et on vérifie qu'elle est bien dans la zone « hausse » (7/10 et plus)
      const s = await p.evaluate(async () => (await fetch("./data/app/aujourdhui.json", { cache: "no-store" })).json());
      const mikr = s.ecartees.find((x) => x.symbole === "MIKR");
      assert.ok(mikr.note10 >= 7, `note de MIKR : ${mikr.note10}`);
      const attendu = mikr.note10.toLocaleString("fr-CA", { minimumFractionDigits: 1, maximumFractionDigits: 1 }) + "/10";
      assert.equal((await listes.nth(1).locator(".score-pastille").innerText()).replace(/\s+/g, ""), attendu.replace(/\s+/g, ""));
    } finally {
      await onglet("Radar");
    }
  });
  await verifier("Fiche MIKR (écartée) : la raison, la taille de 50 M$ et sa preuve officielle", async () => {
    try {
      await onglet("Radar"); await p.locator(".alerte-baisse").click(); await p.waitForTimeout(250);
      await p.locator(".segment", { hasText: "Hausse" }).click(); await p.waitForTimeout(150);
      await p.locator(".ligne.suggestion", { hasText: "MIKR" }).click(); await p.waitForTimeout(250);
      assert.ok((await p.locator(".fiche-sens").innerText()).startsWith("Écartée : moins de 100 M$ en bourse")); // + « Récent »
      const taille = (await p.locator(".taille").innerText()).replace(/\u00a0|\u202f/g, " ");
      const sans = taille.replace(/\s/g, ""); // les espaces des montants varient d'un navigateur à l'autre (« 50 M $ US »)
      assert.ok(taille.includes("Petite compagnie") && sans.includes("50M$US") && sans.includes("20000000actions")
        && sans.includes("Moinsde100M$:horsdelaliste«hausse»."), taille.replace(/\n/g, " | "));
      // Étape 1 (données sûres) : actions déclarées avant le regroupement d'actions → le prix de l'ancien CUSIP (2,50 $),
      // pas le nouveau (25 $ : la 0.27.0 aurait calculé 500 M$)
      assert.ok(sans.includes("×2,50$US") && !sans.includes("25,00$US") && taille.includes("Prix de l'ancien code du titre "
        + "(CUSIP 000000AA1)") && taille.includes("regroupement ou fractionnement d'actions possible"), taille.replace(/\n/g, " | "));
      const calcul = (await p.locator(".ecran").innerText()).replace(/\u00a0/g, " ");
      assert.ok(calcul.includes("la directrice financière de Micro Exemple achète 40 000 actions"), calcul);
    } finally {
      await onglet("Radar");
    }
  });
  await verifier("Fiche AMD (grande) : pas de phrase des 100 M$", () => fiche("AMD", async () => {
    assert.ok(!(await p.locator(".taille").innerText()).includes("100 M$"));
    assert.ok(!(await p.locator(".taille").innerText()).includes("CUSIP"));  // même code depuis plus d'un an : aucune note
  }));
  await verifier("Résultats : écartées à part — la règle a-t-elle raison, verdicts en mots, pas dans le taux des listes", async () => {
    try {
      await p.locator(".res-carte").click(); await p.waitForTimeout(300);
      const g = (await p.locator(".groupe", { hasText: "la règle des 100 M$ a-t-elle raison" }).innerText()).replace(/\u00a0/g, " ").replace(/−/g, "-");
      assert.ok(g.includes("0 sur 1 · écart moyen +6,1 points") && g.includes("1 sur 1 · écart moyen -7,5 points"), g);
      assert.ok(g.includes("La règle a raison quand la compagnie fait moins bien que le marché."), g);
      const e = (await p.locator(".groupe", { hasText: "Écartées suivies (1)" }).innerText()).replace(/\u00a0/g, " ").replace(/−/g, "-");
      assert.ok(e.includes("Écartée (moins de 100 M$) · entrée le 20 juillet 2026 · 7,6/10"), e);
      assert.ok(e.includes("+3,8 % au 30 juill. · marché -2,4 % (IVV) : a fait mieux que le marché : la règle s'est trompée"), e);
      assert.ok(e.includes("-5,1 % au 24 août · marché +2,5 % (SPY) : a fait moins bien que le marché : la règle avait raison"), e);
      assert.ok(e.includes("Pourquoi : Achat d'actions par un dirigeant ou un administrateur (Petite compagnie) · petite compagnie"), e);
      const t = (await p.locator(".ecran").textContent()).replace(/\u00a0/g, " ");
      assert.ok(t.includes("Écartées : les compagnies de moins de 100 M$ en bourse, hors de la liste « hausse » depuis la version 0.27"), t);
    } finally {
      await onglet("Radar");
    }
  });
  await verifier("Méthode et aide : la règle des 100 M$ et le lien du rejeu du labo", async () => {
    try {
      await reglages(); await p.getByRole("button", { name: /Comment le score est calculé/ }).click(); await p.waitForTimeout(250);
      const calcul = (await p.locator(".groupe", { hasText: "Le calcul" }).innerText()).replace(/\u00a0/g, " ");
      assert.ok(calcul.includes("Moins de 100 M$ en bourse : la compagnie n'entre pas dans la liste « hausse ».") && calcul.includes("Taille inconnue : rien n'est écarté."), calcul);
      assert.equal(await p.locator("a.etude", { hasText: "Rejeu de 3 ans du labo" }).getAttribute("href"),
        "https://github.com/killingsky1/Radar/blob/labo/labo/rejeu3/facteurs.md");
      await p.locator(".retour").click(); await p.waitForTimeout(200);
      await p.getByRole("button", { name: /Comment marche Radar/ }).click(); await p.waitForTimeout(250);
      assert.ok((await p.locator(".ecran").last().innerText()).replace(/\u00a0/g, " ").includes("Moins de 100 M$ en bourse : la compagnie n'entre pas dans la liste « hausse »."));
    } finally {
      await onglet("Radar");
    }
  });
  await verifier("Aide : les résultats de Radar et leur lien", async () => {
    try {
      await p.getByRole("button", { name: "Aide" }).click(); await p.waitForSelector(".flux-etape");
      await p.locator(".lien-rangee", { hasText: "Voir les résultats" }).click(); await p.waitForTimeout(250);
      assert.equal(await p.locator(".grand-titre h1").innerText(), "Résultats");
    } finally {
      await onglet("Radar");
    }
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
  await verifier("État des sources : seulement les sources qui servent (ni laissées de côté, ni refusées)", async () => {
    await reglages(); await p.getByRole("button", { name: /État des sources/ }).click(); await p.waitForSelector(".source");
    const toutes = await p.evaluate(async () => (await (await fetch("data/app/sources.json")).json()).map((s) => s.statut));
    const attendues = toutes.filter((s) => !["ecartee", "refusee", "a_venir"].includes(s)).length;
    assert.ok(toutes.includes("ecartee") && toutes.includes("refusee") && attendues < toutes.length, "les données de test doivent en avoir");
    assert.equal(await p.locator(".source").count(), attendues);
  });
  await verifier("Sources : rien qui dit « Refusée », « Laissée de côté » ou « 403 » ; LEGISinfo (refusée) pas affichée", async () => {
    assert.equal(await p.locator(".source", { hasText: "LEGISinfo" }).count(), 0);
    const t = await p.locator(".ecran").last().innerText();
    for (const mot of ["Refusée", "Laissée", "laissée", "403", "Payant", "interdit"]) assert.ok(!t.includes(mot), mot);
    assert.ok((await p.locator(".resume").innerText()).startsWith("OK ·"));
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
  await verifier("App finie : aucun écran ne dit qu'une chose n'a pas marché ou n'a pas pu être ajoutée", async () => {
    // Comparé en minuscules : les titres de groupe sont écrits en majuscules par le style (« BON À SAVOIR »).
    const interdits = ["laissée de côté", "laissées de côté", "refusée par le site", "erreur 403", "phase 1", "arrive bientôt",
      "aucune source de prix", "vente de l'app", "ne sont pas cherchés", "autre étiquette", "pas vérifié", "ne lit pas",
      "image numérisée", "ne mesure pas", "en liste seulement", "les limites"];
    const vus = [];
    const lire = async (ou, selecteur = ".ecran") => {
      const t = (await p.locator(selecteur).last().innerText()).replace(/\u00a0|\u202f/g, " ").toLowerCase();
      for (const mot of interdits) assert.ok(!t.includes(mot), `« ${mot} » sur ${ou}`);
      vus.push(ou);
    };
    try {
      for (const o of ["Radar", "Argent", "Fil", "Favoris", "Réglages"]) { await onglet(o); await lire(o); }
      for (const b of [/État des sources/, /Comment marche Radar/, /Comment c'est vérifié/, /Comment le score est calculé/]) {
        await reglages(); await p.getByRole("button", { name: b }).click(); await p.waitForTimeout(250);
        await lire(String(b));
        await p.locator(".retour").click(); await p.waitForTimeout(200);
      }
      for (const lien of ["Voir le calendrier", "Voir les résultats"]) {
        await reglages(); await p.getByRole("button", { name: /Comment marche Radar/ }).click(); await p.waitForTimeout(250);
        await p.locator(".lien-rangee", { hasText: lien }).click(); await p.waitForTimeout(250);
        await lire(lien);
        await p.locator(".retour").click(); await p.waitForTimeout(200);
      }
      await onglet("Fil");
      await p.locator(".ligne", { hasText: "278-T" }).first().click(); await p.waitForSelector(".feuille-fond.ouvert", { timeout: 20000 }); await p.waitForTimeout(300);
      await lire("détail d'un rapport de l'OGE", ".feuille");
      await p.locator(".feuille-fermer").click(); await p.waitForTimeout(300);
      await onglet("Radar");
      for (const s of ["AMD", "NVDA"]) await fiche(s, () => lire(`fiche ${s}`));
    } finally {
      await onglet("Radar");
    }
    assert.equal(vus.length, 14, vus.join(" | "));
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
