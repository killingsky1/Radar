export const meta = {
  name: 'radar-tournoi-debat',
  description: 'Tournoi Radar, étape 3 : pour chaque règle retenue, un avocat et deux sceptiques, puis un juge qui choisit au plus 3 finalistes pour l’examen final',
  phases: [
    { title: 'Débat', detail: 'avocat + 2 sceptiques par règle' },
    { title: 'Juge', detail: 'failles prouvées, choix de 3 finalistes au plus' },
  ],
}

// args : { regles: ["id", ...] } — les règles qui passent la découverte, sinon les 3 meilleures selon le t (regles_du_jeu.md, partie 4)
const S = '/tmp/claude-0/-home-user/8609c384-84d9-54df-a01a-3330555229ff/scratchpad'
const W = S + '/labo-wt'
const P = S + '/venv-essai-zip/bin/python'
const R = W + '/labo/tournoi/resultats/decouverte'

const AVIS = {
  type: 'object',
  properties: {
    id: { type: 'string' },
    these: { type: 'string', description: 'en 3 à 6 phrases simples' },
    preuves: { type: 'array', items: { type: 'string' }, description: 'chiffres tirés des fichiers, avec le fichier' },
    faille_fatale: { type: ['string', 'null'], description: 'une faille qui invalide le résultat, prouvée, sinon null' },
  },
  required: ['id', 'these', 'preuves', 'faille_fatale'],
}

const JUGE = {
  type: 'object',
  properties: {
    verdicts: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          id: { type: 'string' },
          faille_prouvee: { type: ['string', 'null'] },
          resume: { type: 'string', description: 'en français simple, pour un non-financier' },
        },
        required: ['id', 'faille_prouvee', 'resume'],
      },
    },
    finalistes: { type: 'array', items: { type: 'string' }, maxItems: 3 },
    raison_du_choix: { type: 'string' },
  },
  required: ['verdicts', 'finalistes', 'raison_du_choix'],
}

const COMMUN = `Tournoi de Radar (app personnelle qui suit les achats d'actions des dirigeants). Une règle a été écrite AVANT les données, programmée 2 fois sans se voir, puis testée sur la découverte (juillet 2023 à juin 2026), après tous les frais.
Fichiers (lecture seulement, n'utilise jamais git, ne modifie rien) :
- règles : ${W}/labo/tournoi/regles_preenregistrees.json ; programmes : ${W}/labo/tournoi/regles/<id>.py et regles_verif/<id>.py
- règles du jeu : ${W}/labo/tournoi/regles_du_jeu.md ; banc : ${W}/labo/tournoi/banc.py ; données : ${W}/labo/tournoi/dictionnaire.md
- résultats : ${R}/resume.md, ${R}/tous.json, ${R}/<id>.json, ${R}/<id>.transactions.json (chaque achat et vente)
Python pour calculer sur ces fichiers : ${P}. INTERDIT : changer la règle, proposer d'autres seuils, ou juger d'après une autre période (le coffre-fort 2016-2023 reste fermé).`

function avocat(id) {
  return `${COMMUN}

Tu es l'AVOCAT de la règle ${id}. Montre, chiffres à l'appui (tirés des fichiers), pourquoi son résultat sur la découverte peut être réel : régularité par année, nombre d'achats, part des gains qui ne vient pas de 2 ou 3 transactions, lien avec les études citées. Sois honnête : si un point est faible, dis-le.`
}

function sceptique(id, angle) {
  const quoi = angle === 'hasard'
    ? "le HASARD : environ 39 règles essayées sur seulement 3 ans ; gains concentrés dans peu de transactions (recalcule le résultat sans les 3 meilleures) ; une seule bonne année ; dépendance aux petites compagnies (compare avec IWM) ; t de l'écart mensuel"
    : "les BIAIS et les COÛTS : information du futur dans le programme (lis les 2 programmes ligne par ligne), signaux perdus faute de prix de la SEC (un prix n'existe que les jours d'échecs de livraison : sélection possible), écart achat-vente réaliste pour la taille des compagnies achetées, positions trop petites pour les frais de 10 $, compagnies disparues"
  return `${COMMUN}

Tu es SCEPTIQUE de la règle ${id}. Ton angle : ${quoi}. Cherche une faille qui rendrait son résultat faux ou trompeur, et PROUVE-la avec les fichiers (chiffres, lignes de code). Une faille « fatale » = le résultat ne tient plus une fois la faille corrigée ; sinon, c'est une faiblesse, pas une faille fatale.`
}

phase('Débat')
const ids = (args && args.regles) || []
log(`${ids.length} règles au débat : ${ids.join(', ')}`)
const debats = await parallel(ids.map(id => () => parallel([
  () => agent(avocat(id), { label: `avocat:${id}`, phase: 'Débat', schema: AVIS }),
  () => agent(sceptique(id, 'hasard'), { label: `sceptique-hasard:${id}`, phase: 'Débat', schema: AVIS }),
  () => agent(sceptique(id, 'biais'), { label: `sceptique-biais:${id}`, phase: 'Débat', schema: AVIS }),
]).then(a => ({ id, avocat: a[0], hasard: a[1], biais: a[2] }))))

phase('Juge')
const juge = await agent(`${COMMUN}

Tu es le JUGE. Voici le débat (avocat et 2 sceptiques) pour chaque règle :
${JSON.stringify(debats.filter(Boolean), null, 1)}

Pour chaque règle : une faille fatale est-elle PROUVÉE (vérifie toi-même dans les fichiers) ? Tu ne peux pas changer une règle. Puis choisis AU PLUS 3 finalistes pour l'examen final (une seule chance chacune sur 2016-2023) : seulement des règles sans faille fatale prouvée ; moins de 3, ou aucune, si c'est plus honnête.
Tests multiples : environ 39 règles ont été essayées sur les mêmes 3 ans ; un bon résultat peut venir du hasard. Doublons : lis "critique" → "doublons" dans regles_preenregistrees.json ; deux règles en doublon ne peuvent pas être finalistes ensemble : garde celle que le critique recommande, sauf faille prouvée chez elle. Un témoin (temoin-meteo) ne peut jamais être finaliste.
Explique ton choix en français simple, pour quelqu'un qui n'est pas financier.`, { label: 'juge', phase: 'Juge', schema: JUGE })

return { debats: debats.filter(Boolean), juge }
