// Tests de l'app dans un vrai navigateur (données TEST : 7 infos validées + 1 piège).
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

  await p.goto(ADRESSE);
  await p.evaluate(() => localStorage.clear());
  await p.reload(); await p.waitForSelector(".tuiles");

  await verifier("Thème sombre par défaut", async () => assert.equal(await p.evaluate(() => document.documentElement.dataset.theme), "sombre"));
  await verifier("Accueil : compteurs (7 nouvelles, 1 confirmée, 1 à vérifier)", async () => {
    const v = await p.locator(".tuile-valeur").allInnerTexts();
    assert.deepEqual(v.slice(0, 3), ["7", "1", "1"]);
  });
  await verifier("Tuile catégorie Militaire ouvre le fil filtré (1 info)", async () => {
    await p.locator(".cat", { hasText: "Militaire" }).click(); await p.waitForTimeout(250); assert.equal(await lignes(), 1);
  });
  await verifier("Fil : 7 infos, le piège est caché", async () => { await p.locator(".puce", { hasText: "Tout" }).click(); assert.equal(await lignes(), 7); });
  await verifier("Fil se souvient du filtre choisi (Tout) après un changement d'onglet", async () => {
    await onglet("Favoris"); await onglet("Fil"); assert.equal(await lignes(), 7);
    assert.equal(await p.locator(".puce.actif").innerText(), "Tout");
  });
  await verifier("Fil groupé par jour (Aujourd'hui, Hier…)", async () => {
    const t = await p.locator("h2.section").allInnerTexts(); assert.ok(t[0].toLowerCase().includes("aujourd") && t[1].toLowerCase().includes("hier"), t.join("|"));
  });
  await verifier("Recherche « nvda » : 1 résultat", async () => { await p.fill("input[type=search]", "nvda"); await p.waitForTimeout(150); assert.equal(await lignes(), 1); await p.fill("input[type=search]", ""); });
  await verifier("Recherche sans résultat : message clair", async () => { await p.fill("input[type=search]", "zzzz"); await p.waitForTimeout(150); assert.ok(await p.getByText("Aucun résultat").isVisible()); await p.fill("input[type=search]", ""); });
  await verifier("Détail : s'ouvre, montre 9 contrôles, se ferme", async () => {
    await p.locator(".ligne").first().click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.equal(await p.locator(".feuille .controle").count(), 10); // 9 contrôles + 1 confirmation
    await fermer(); assert.equal(await p.locator(".feuille").count(), 0);
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
  await verifier("Réglage : montrer les « À vérifier » (fil = 8)", async () => {
    await reglages(); await inter("Montrer les infos à vérifier"); await filTout(); try { assert.equal(await lignes(), 8); } finally { await remettre(() => inter("Montrer les infos à vérifier")); }
  });
  await verifier("Réglage : montant minimum 1 M$ (fil = 6)", async () => {
    await reglages(); await p.getByRole("radio", { name: "1 M$" }).click(); await filTout(); try { assert.equal(await lignes(), 6); } finally { await remettre(() => p.getByRole("radio", { name: "Tous" }).click()); }
  });
  await verifier("Réglage : cacher Politiciens (fil = 6)", async () => {
    await reglages(); await inter("Politiciens"); await filTout(); try { assert.equal(await lignes(), 6); } finally { await remettre(() => inter("Politiciens")); }
  });
  await verifier("Réglage : catégorie cachée alors qu'elle était filtrée → retour à Tout", async () => {
    await onglet("Fil"); await p.locator(".puce", { hasText: "Politiciens" }).click(); await reglages(); await inter("Politiciens"); await onglet("Fil");
    try { assert.equal(await p.locator(".puce.actif").innerText(), "Tout"); assert.equal(await lignes(), 6); } finally { await remettre(() => inter("Politiciens")); await filTout(); }
  });
  await verifier("Réglage : trier par montant (1er = 2 G$ LMT)", async () => {
    await reglages(); await p.getByRole("radio", { name: "Plus gros montant" }).click(); await filTout();
    try { assert.ok((await p.locator(".ligne").first().innerText()).includes("Lockheed")); } finally { await remettre(() => p.getByRole("radio", { name: "Plus récent" }).click()); }
  });
  await verifier("Réglage : thème clair", async () => { await reglages(); await p.getByRole("radio", { name: "Clair" }).click(); assert.equal(await p.evaluate(() => document.documentElement.dataset.theme), "clair"); });
  await verifier("Réglage : texte grand (18 px)", async () => { await reglages(); await p.getByRole("radio", { name: "Grande" }).click(); assert.equal(await p.evaluate(() => document.documentElement.style.fontSize), "18px"); });
  await verifier("Réglage : couleur verte", async () => { await reglages(); await p.getByRole("radio", { name: "vert" }).click(); assert.equal(await p.evaluate(() => document.documentElement.style.getPropertyValue("--accent")), "#2BD9A0"); });
  await verifier("Réglages gardés après fermeture de l'app", async () => { await p.reload(); await p.waitForSelector(".onglets"); assert.equal(await p.evaluate(() => document.documentElement.dataset.theme), "clair"); });
  await verifier("Réinitialiser les réglages (retour au sombre)", async () => {
    await reglages(); await p.getByRole("button", { name: /Réinitialiser/ }).click(); await p.waitForTimeout(200);
    assert.equal(await p.evaluate(() => document.documentElement.dataset.theme), "sombre");
  });
  await verifier("État des sources : 54 sources listées", async () => { await reglages(); await p.getByRole("button", { name: /État des sources/ }).click(); await p.waitForSelector(".source"); assert.equal(await p.locator(".source").count(), 54); });
  await verifier("Bouton retour vers Réglages", async () => { await p.locator(".retour").click(); await p.waitForTimeout(200); assert.ok(await p.getByRole("button", { name: /Comment c'est vérifié/ }).isVisible()); });
  await verifier("À vérifier : le piège y est, avec le contrôle raté", async () => {
    await p.getByRole("button", { name: /^À vérifier/ }).click(); await p.waitForSelector(".ligne"); assert.equal(await lignes(), 1);
    await p.locator(".ligne").first().click(); await p.waitForSelector(".feuille-fond.ouvert");
    assert.ok((await p.locator(".controle.rate").innerText()).includes("site officiel")); await fermer();
  });
  await verifier("Hors ligne : l'app s'ouvre quand même (copie gardée)", async () => {
    await p.evaluate(async () => { await navigator.serviceWorker.register("./sw.js"); await navigator.serviceWorker.ready; });
    await p.reload(); await p.waitForSelector(".onglets"); await p.waitForTimeout(500);
    await ctx.setOffline(true); await p.reload(); await p.waitForSelector(".onglets", { timeout: 5000 });
    assert.ok(await p.locator(".grand-titre h1").isVisible()); await ctx.setOffline(false);
  });

  console.log(res.join("\n"));
  console.log(`\n${res.filter((r) => r.startsWith("OK")).length}/${res.length} réussis · erreurs navigateur : ${erreurs.length ? erreurs.join(" | ") : "aucune"}`);
  await b.close();
  if (res.some((r) => r.startsWith("ÉCHEC")) || erreurs.length) process.exit(1);
})();
