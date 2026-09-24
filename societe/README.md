# Une société

Simulation de société qui commence avec **une seule personne** débarquant sur
**un million de kilomètres carrés** de terre vierge. Elle plante sa tente, défriche
un champ, et c'est tout. Le reste dépend de vous : c'est **vous qui décidez quand
faire venir quelqu'un**, et avec quel savoir-faire.

Le développement du lieu suit la démarche de [Project Kamp](https://projectkamp.com/) :
partir d'un terrain nu, viser l'autonomie en eau, en énergie et en nourriture,
construire avec ce qu'on a sur place, et ne rien jeter — les déchets récupérés
deviennent la matière première de l'atelier.

## Lancer

```bash
python -m societe            # puis ouvrir http://127.0.0.1:8000
python -m societe --port 9000
```

Aucune dépendance : la simulation et le serveur n'utilisent que la bibliothèque
standard de Python (≥ 3.11).

## Ce que vous pilotez

| Levier | Effet |
|---|---|
| **Le temps** | il n'avance que si vous le demandez (+1, +7, +30 jours, ou en continu) |
| **Les arrivées** | nom, âge, savoir-faire, histoire — à vous de choisir le moment |
| **Les affectations** | chacun ne fait qu'**une** chose par jour : cultiver, bûcheronner, bâtir, soigner, enseigner, coordonner… |
| **Les chantiers** | un seul à la fois, à choisir dans un catalogue de 34 constructions |

## Ce que la simulation gère toute seule

- **Les saisons** : un hiver à 20 % de rendement agricole se prépare dès l'automne.
- **La météo** : pluie qui remplit les réserves, gel, sécheresse, tempête.
- **Les corps** : énergie, santé, moral. On s'épuise, on a faim, on part si le moral s'effondre.
- **L'apprentissage** : les compétences montent par la pratique, et se transmettent par l'enseignement.
- **La coordination** : au-delà de ce que la gouvernance peut tenir (5 personnes au début),
  chaque personne supplémentaire fait baisser le rendement de tout le monde. La salle
  commune, puis le conseil, repoussent ce plafond. C'est le cœur du jeu : **faire venir
  du monde n'est pas gratuit**.
- **La maturation** : un verger planté aujourd'hui ne nourrit personne avant trois ans.

## Les grandes étapes

```
cueillette → campement → potager → captage de la source → cabane
   → atelier → scierie → cuisine → salle commune → énergie solaire
   → recyclerie plastique → verger, troupeau → école, conseil
```

L'atelier est le verrou technique : sans lui, pas de scierie, pas de recyclerie,
pas d'éolienne. La salle commune est le verrou social : sans elle, le groupe
plafonne à cinq personnes.

## Architecture

```
societe/
  modele.py      personnes, parcelles, stocks, chantiers — tout est sérialisable
  catalogue.py   les 34 chantiers : coûts, prérequis, effets
  moteur.py      une journée de simulation ; constantes de calibrage en tête de fichier
  serveur.py     API JSON + service des fichiers web (bibliothèque standard)
  web/           interface : index.html, style.css, app.js (aucune dépendance)
```

L'état complet tient dans un objet `Etat` sérialisable : la sauvegarde est un
simple JSON, et l'API renvoie à chaque action un instantané complet que
l'interface se contente d'afficher.

## Piloter sans l'interface

```python
from societe import creer_societe, avancer, lancer_chantier, affecter, ajouter_personne

e = creer_societe("Ana", 30, graine=3)
affecter(e, 1, "nourriture"); avancer(e, 14)
lancer_chantier(e, "campement"); affecter(e, 1, "construction"); avancer(e, 10)
ajouter_personne(e, "Tomas", 28, "construction", "a marché trois semaines")
print(e.date_lisible, e.stocks, e.batiments)
```

## Tests

```bash
python -m pytest tests/test_societe_moteur.py tests/test_societe_serveur.py
```

## Limites assumées

Pas de concurrence entre groupes, pas de naissances ni de démographie endogène
(les arrivées sont votre décision), pas d'économie monétaire ni d'échange avec
l'extérieur — seul le chemin d'accès fait rentrer un peu de matière récupérée.
Les chiffres sont plausibles, pas mesurés : la simulation sert à comparer des
trajectoires, pas à prédire une société réelle.
