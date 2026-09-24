# Dépôt de simulations

Deux simulations indépendantes vivent ici :

- **[`societe/`](societe/README.md)** — une société qui part d'une personne seule sur
  un million de km², avec interface web (`python -m societe`).
- **`onair/`** — un simulateur de grille radio à événements discrets (ci-dessous).

---

# onair — simulateur de grille radio

Simulation à événements discrets d'une station de radio : une grille de
programmes rencontre une population d'auditeurs, et on observe ce qui sort —
courbe d'audience, effet des coupures publicitaires, recette, classement des
émissions.

Sorties : **graphiques PNG** (matplotlib) et un **tableau de bord HTML
interactif** (autonome, sans dépendance réseau, thème clair/sombre).

## Installation

```bash
pip install matplotlib        # seule dépendance d'exécution
pip install pytest            # pour les tests
```

## Utilisation

```bash
python -m onair                                  # 7 jours, grille de référence
python -m onair --scenario pub-x2 --jours 14     # variante « deux fois plus de pub »
python -m onair --bruit 0 --sorties ./resultats  # simulation déterministe
python -m onair --ouvrir                         # ouvre le tableau de bord
```

Chaque exécution écrit dans `sorties/<scenario>/` :

| Fichier | Contenu |
|---|---|
| `tableau.html` | tableau de bord interactif (courbe, carte de chaleur, classement, tableau) |
| `resultats.json` | toutes les mesures, pour analyse externe |
| `journee_type.png` | audience moyenne heure par heure |
| `segments.png` | composition de l'audience par public |
| `carte_semaine.png` | carte de chaleur jour × heure |
| `classement.png` | audience moyenne par émission |

Scénarios fournis : `reference`, `pub-x2` (charge publicitaire doublée),
`sans-vedette` (tous les animateurs remplacés par le pilote automatique).

## Ce que le modèle simule

**Le temps** est en minutes ; l'échéancier (`onair/core.py`) est un moteur à
événements discrets générique — file de priorité + répartiteur — réutilisable
pour un tout autre domaine. Les événements sont : début d'émission, début et
fin de coupure publicitaire, et un pas de mesure toutes les 5 minutes.

**L'offre** (`onair/modele.py`) : des émissions (genre, qualité éditoriale,
animateur, charge publicitaire) placées dans des créneaux d'une grille
hebdomadaire. `Grille.verifier()` signale chevauchements et trous d'antenne.

**La demande** (`onair/audience.py`) : quatre publics types, chacun avec une
taille, des affinités par genre, un profil de disponibilité sur 24 heures, une
tolérance à la publicité et une inertie. On suit l'effectif à l'écoute par
segment plutôt que des auditeurs individuels : plus rapide, et suffisant pour
comparer des grilles.

**La dynamique** (`onair/simulation.py`) : à chaque pas, chaque segment vise une
audience cible (affinité × qualité × notoriété × disponibilité, amputée pendant
la pub selon la tolérance) et s'en approche exponentiellement — montée rapide,
descente freinée par l'inertie. La lassitude pénalise deux émissions de suite du
même genre. Les départs constatés pendant une coupure alimentent le compteur
d'abandons ; les auditeurs exposés aux spots produisent la recette (CPM ×
nombre de spots).

Toutes les valeurs sont **inventées** : le modèle sert à comparer des grilles
entre elles, pas à prédire une audience réelle.

## Structure

```
onair/
  core.py           moteur à événements discrets (générique)
  modele.py         émissions, animateurs, créneaux, grille, station
  audience.py       segments d'auditeurs
  simulation.py     boucle de simulation, mesures, export
  scenarios.py      station de référence et variantes
  graphiques.py     figures matplotlib
  web.py            génération du tableau de bord HTML
  cli.py            interface en ligne de commande
tests/              18 tests (pytest)
```

## Tests

```bash
python -m pytest
```

## Pistes d'extension

- Concurrence : plusieurs stations se disputant la même population.
- Optimisation de grille : recherche automatique du placement des émissions.
- Calage sur des données réelles (courbes Médiamétrie) pour ajuster les affinités.
- Événements exceptionnels : match, alerte info, panne d'émetteur.
