# Radar

Robot qui lit chaque jour des sources **officielles** (SEC, Pentagone, Congrès, Registre fédéral, gouvernement du Canada…) et une app iPhone qui montre ce qui bouge, avec le lien vers le document original.

**Projet personnel. Ce ne sont pas des conseils financiers.** Le robot suggère, il n'achète jamais.

## Comment c'est fiable

- Seules les sources officielles peuvent créer une info. Les autres servent seulement à recouper.
- Chaque info garde : le lien du document original, son numéro officiel, l'heure de lecture et l'empreinte (SHA-256) du document.
- Contrôles automatiques à chaque info. Une info qui en rate un seul va dans « À vérifier » et n'entre jamais dans les suggestions.
- Badges : ✅✅ Confirmé (2 sources officielles) · ✅ Officiel · 🟡 À vérifier.
- Page « Sources » : l'état de chaque source (OK, en retard, en panne, en pause). Rien plutôt que faux.
- Les tests roulent avant chaque passage du robot. S'ils échouent, le robot ne publie rien.

## Organisation

- `robot/` : le robot (Python). `python -m pytest` pour les tests.
- `app/` : l'app (React, un seul fichier `app.jsx`). `npm ci && node build.mjs` pour construire, `tests/lancer.sh` pour la tester dans un vrai navigateur.
- `data/` : les données, mises à jour par le robot (tout l'historique est dans git).
- `.github/workflows/radar.yml` : le robot roule 5 fois par jour de semaine, puis le site est remis en ligne.
