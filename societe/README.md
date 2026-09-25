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
| **Les arrivées** | nom, âge, sexe, savoir-faire, histoire — à vous de choisir le moment |
| **Le désir d'enfants** | un curseur, de « aucun enfant voulu » à « autant que le lieu peut en porter » |
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
- **La démographie** (voir ci-dessous) : la population grandit toute seule, une fois
  qu'il y a de quoi nourrir et loger des enfants.

## La démographie

Les arrivées restent votre décision, mais elles ne sont plus la seule source de
population.

**Les couples** se forment entre adultes libres d'âges proches, jamais entre
apparentés, d'autant plus facilement que la cohésion et le moral sont bons.

**Les conceptions** dépendent du curseur de natalité *et* des conditions
réelles : santé de la mère, vivres d'avance, place disponible à l'abri, nombre
de tout-petits déjà à charge, âge. On ne fait pas d'enfant à jeun ni sans lit
pour le coucher. La gestation dure 274 jours, avec un risque de fausse couche
quand la santé est basse, et un risque à l'accouchement que le dispensaire et
la salubrité réduisent nettement.

**L'enfance** : pas de travail avant 14 ans, une ration réduite (40 % avant
5 ans, 70 % ensuite), et un apprentissage qui se fait d'abord auprès des
parents — un enfant ne peut hériter que de ce que quelqu'un autour de lui sait
faire. L'école et les enseignants accélèrent la transmission. À 14 ans,
l'enfant prend sa part du travail.

**La mortalité** suit une loi de Gompertz : un risque qui double environ tous
les huit ans, modulé par la santé, les soins et la salubrité, avec une
mortalité de la petite enfance à part. Construire les toilettes sèches, le
filtre à eau et le dispensaire change l'espérance de vie de la société de
façon visible.

**Les départs** sont progressifs : on ne part que découragé, jamais en laissant
de jeunes enfants derrière soi, et jamais tout le monde le même jour.

### Ce que la démographie apprend

Le curseur de natalité produit trois régimes nettement différents sur 80 ans,
avec la même stratégie de construction par ailleurs :

| Désir d'enfants | Issue |
|---|---|
| **0,3** | croissance lente et tenue — environ 180 personnes, quatre générations, des anciens |
| **0,6** | effondrement vers l'an 55 : les adultes s'épuisent plus vite qu'ils ne sont remplacés |
| **0,9** | effondrement vers l'an 50, avec une espérance de vie très dégradée |

Le mécanisme est le taux de dépendance : chaque enfant mange et occupe un lit
pendant quatorze ans avant de produire quoi que ce soit. Une société qui fait
des enfants plus vite qu'elle n'augmente ses vivres, son eau, ses abris et sa
capacité de coordination meurt de sa propre croissance — et c'est bien sa
croissance, pas un malheur extérieur, qui la tue.

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
