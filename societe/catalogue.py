"""Catalogue des chantiers — inspiré de la démarche de Project Kamp.

Chaque chantier a un coût en jours-homme, des matériaux, des prérequis et
des effets. Les effets sont lus par le moteur : ils ouvrent des capacités
(stocker l'eau, abriter des gens, produire de l'électricité) plutôt que de
donner des points abstraits.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Modele:
    cle: str
    nom: str
    categorie: str
    travail: float  # jours-homme
    materiaux: dict[str, float] = field(default_factory=dict)
    prerequis: list[str] = field(default_factory=list)
    savoir: str = ""            # découverte exigée pour seulement l'envisager
    population_min: int = 1
    repetable: bool = False
    description: str = ""
    effets: dict[str, float] = field(default_factory=dict)


CATEGORIES = ["abri", "eau", "nourriture", "energie", "atelier", "commun", "terre"]

MODELES: dict[str, Modele] = {}


def _m(**kw) -> None:
    m = Modele(**kw)
    MODELES[m.cle] = m


# --- abri -----------------------------------------------------------------
_m(cle="campement", nom="Campement de toile", categorie="abri", travail=2,
   description="Un abri de fortune pour tenir les premières semaines.",
   effets={"abri": 2, "confort": 2})
_m(cle="cabane", nom="Cabane en bois", categorie="abri", travail=25,
   materiaux={"bois": 8, "planches": 20}, prerequis=["campement"],
   description="Le premier vrai toit : sec, chaud, réparable.",
   effets={"abri": 3, "confort": 8, "isolation": 1})
_m(cle="maison_terre", nom="Maison en terre et pierre", categorie="abri", travail=90,
   materiaux={"terre": 40, "pierre": 12, "bois": 10, "planches": 30},
   prerequis=["cabane"], repetable=True,
   description="Murs en terre crue, fondations en pierre locale. Dure des générations.",
   effets={"abri": 5, "confort": 14, "isolation": 2})
_m(cle="douche_solaire", nom="Douche solaire", categorie="abri", travail=8,
   materiaux={"planches": 6, "recup": 20}, prerequis=["reservoir"],
   description="De l'eau chaude gratuite : le premier confort qui change tout.",
   effets={"confort": 10, "hygiene": 1})

# --- eau ------------------------------------------------------------------
_m(cle="source", nom="Captage de la source", categorie="eau", travail=6,
   description="Repérer la source, la dégager, la protéger.",
   effets={"eau_jour": 300})
_m(cle="reservoir", nom="Réservoir et adduction gravitaire", categorie="eau", travail=20,
   materiaux={"pierre": 4, "recup": 30}, prerequis=["source"], repetable=True,
   description="Stocker l'eau en hauteur, et récupérer celle des toitures.",
   effets={"eau_max": 8000, "captage": 1, "eau_jour": 80})
_m(cle="puits", nom="Puits", categorie="eau", travail=24,
   materiaux={"pierre": 6}, prerequis=["source"], repetable=True,
   description="Creuser plus bas que la source. C'est ce qui permet au groupe de grandir.",
   effets={"eau_jour": 320})
_m(cle="filtre", nom="Filtre à sable lent", categorie="eau", travail=10,
   materiaux={"pierre": 2, "recup": 10}, prerequis=["source"],
   description="De l'eau potable sans électricité ni produit.",
   effets={"salubrite": 12})
_m(cle="toilettes_seches", nom="Toilettes sèches", categorie="eau", travail=6,
   materiaux={"planches": 8}, repetable=True,
   description="Zéro eau gaspillée, et du compost en sortie.",
   effets={"salubrite": 14, "compost_jour": 0.04})
_m(cle="etang", nom="Retenue d'eau", categorie="eau", travail=45,
   materiaux={"terre": 30}, prerequis=["source"], population_min=4,
   description="Une réserve pour les étés secs, et un lieu où se baigner.",
   effets={"eau_max": 40000, "eau_jour": 260, "irrigation": 1, "confort": 6})

# --- nourriture -----------------------------------------------------------
_m(cle="potager", nom="Potager", categorie="nourriture", travail=12, repetable=True,
   description="Un demi-hectare défriché, bêché, semé.",
   effets={"parcelle_potager": 0.5})
_m(cle="compostage", nom="Aire de compostage", categorie="nourriture", travail=5,
   materiaux={"planches": 4}, prerequis=["potager"],
   description="Fermer le cycle des nutriments : rien ne sort du terrain.",
   effets={"rendement": 0.18})
_m(cle="poulailler", nom="Poulailler", categorie="nourriture", travail=15,
   materiaux={"planches": 12, "bois": 3}, prerequis=["potager"], repetable=True,
   description="Œufs quotidiens, déchets recyclés, sol travaillé.",
   effets={"nourriture_jour": 2.2, "variete": 6})
_m(cle="verger", nom="Verger / forêt comestible", categorie="nourriture", travail=30,
   prerequis=["potager"], repetable=True,
   description="Long à entrer en production, puis nourrit sans travail.",
   effets={"parcelle_verger": 1.0, "variete": 8})
_m(cle="serre", nom="Serre", categorie="nourriture", travail=35,
   materiaux={"planches": 20, "recup": 40}, prerequis=["atelier"],
   description="Décale les saisons : des semis en février, des tomates en octobre.",
   effets={"saison_froide": 0.35, "rendement": 0.1})
_m(cle="cuisine", nom="Cuisine collective et four à pain", categorie="nourriture", travail=22,
   materiaux={"pierre": 6, "terre": 10, "planches": 10}, prerequis=["cabane"],
   description="Cuire, conserver, manger ensemble.",
   effets={"variete": 10, "confort": 8, "conservation": 0.15})
_m(cle="cave", nom="Cave et silo", categorie="nourriture", travail=18,
   materiaux={"pierre": 8, "terre": 15}, prerequis=["potager"],
   description="Passer l'hiver sur les récoltes de l'automne.",
   effets={"conservation": 0.25})
_m(cle="troupeau", nom="Chèvres et pâture", categorie="nourriture", travail=28,
   materiaux={"planches": 15}, prerequis=["verger"], population_min=5,
   description="Lait, fromage, entretien des broussailles.",
   effets={"nourriture_jour": 3.0, "variete": 7, "parcelle_pature": 2.0})
_m(cle="ruches", nom="Rucher", categorie="nourriture", travail=12,
   materiaux={"planches": 8}, prerequis=["verger"], repetable=True,
   description="Miel, cire, et surtout pollinisation.",
   effets={"nourriture_jour": 0.8, "rendement": 0.08, "variete": 4})

# --- énergie --------------------------------------------------------------
_m(cle="solaire", nom="Panneaux solaires", categorie="energie", travail=14,
   materiaux={"recup": 25}, prerequis=["cabane"], repetable=True,
   description="La première électricité du lieu.",
   effets={"solaire": 6.0})
_m(cle="batteries", nom="Parc de batteries", categorie="energie", travail=10,
   materiaux={"recup": 40}, prerequis=["solaire"], repetable=True,
   description="Stocker le soleil de midi pour le soir.",
   effets={"elec_max": 20})
_m(cle="eolienne", nom="Éolienne", categorie="energie", travail=40,
   materiaux={"recup": 60, "planches": 10}, prerequis=["atelier", "solaire"],
   description="Prend le relais l'hiver, quand le soleil manque.",
   effets={"eolien": 4.0})
_m(cle="rocket_stove", nom="Poêles de masse", categorie="energie", travail=16,
   materiaux={"terre": 12, "pierre": 6}, prerequis=["cabane"],
   description="Chauffer beaucoup en brûlant peu.",
   effets={"isolation": 2, "bois_economie": 0.4})

# --- atelier et matériaux -------------------------------------------------
_m(cle="atelier", nom="Atelier", categorie="atelier", travail=30,
   materiaux={"bois": 10, "planches": 25}, prerequis=["cabane"],
   description="Sans atelier, on ne fabrique rien : c'est le verrou technique.",
   effets={"artisanat": 0.8, "outils_jour": 0.05})
_m(cle="scierie", nom="Scierie", categorie="atelier", travail=26,
   materiaux={"recup": 30, "bois": 5}, prerequis=["atelier"],
   description="Transformer les troncs en planches sur place.",
   effets={"planches_ratio": 2.5})
_m(cle="recyclerie", nom="Recyclerie plastique", categorie="atelier", travail=32,
   materiaux={"recup": 35, "planches": 10}, prerequis=["atelier", "solaire"],
   description="Broyer, fondre, remouler : les déchets deviennent la matière première.",
   effets={"recup_jour": 6.0, "planches_jour": 1.2})
_m(cle="forge", nom="Forge", categorie="atelier", travail=34,
   materiaux={"pierre": 10, "terre": 8, "recup": 20}, prerequis=["atelier"],
   population_min=4,
   description="Réparer et fabriquer les outils au lieu de les remplacer.",
   effets={"outils_jour": 0.18, "artisanat": 0.5})
_m(cle="hangar", nom="Hangar de stockage", categorie="atelier", travail=20,
   materiaux={"planches": 25, "bois": 8}, prerequis=["cabane"], repetable=True,
   description="Ce qui n'est pas abrité pourrit.",
   effets={"stock_max": 400, "conservation": 0.1})

# --- vie commune ----------------------------------------------------------
_m(cle="place", nom="Salle commune", categorie="commun", travail=30,
   materiaux={"bois": 12, "planches": 30, "pierre": 6}, prerequis=["cabane"],
   population_min=3,
   description="Un lieu pour décider ensemble et passer l'hiver au chaud.",
   effets={"cohesion": 0.22, "confort": 8, "gouvernance": 4})
_m(cle="dispensaire", nom="Dispensaire", categorie="commun", travail=25,
   materiaux={"planches": 18}, prerequis=["cabane"], population_min=4,
   description="Soigner sur place au lieu de perdre des gens.",
   effets={"salubrite": 10, "soin": 0.5})
_m(cle="ecole", nom="École et bibliothèque", categorie="commun", travail=35,
   materiaux={"planches": 25, "bois": 8}, prerequis=["place"], population_min=6,
   description="Transmettre les savoir-faire au lieu de les perdre avec les gens.",
   effets={"enseignement": 0.6, "cohesion": 0.1})
_m(cle="chemin", nom="Chemin d'accès", categorie="commun", travail=24,
   materiaux={"pierre": 15}, population_min=3,
   description="Sortir du terrain et y faire entrer ce qu'on ne produit pas.",
   effets={"logistique": 0.25, "recup_jour": 3.0})
_m(cle="conseil", nom="Conseil du collectif", categorie="commun", travail=10,
   prerequis=["place"], population_min=8,
   description="Formaliser la décision collective avant que la coordination ne s'effondre.",
   effets={"gouvernance": 10, "cohesion": 0.15})

_m(cle="quartiers", nom="Fédération de quartiers", categorie="commun", travail=55,
   materiaux={"planches": 40, "pierre": 12}, prerequis=["conseil"], population_min=20,
   repetable=True,
   description="Découper le collectif en groupes qui décident chez eux et se fédèrent : "
               "la seule façon connue de dépasser la trentaine sans se paralyser.",
   effets={"gouvernance": 16, "cohesion": 0.12, "confort": 4})
_m(cle="archives", nom="Archives du lieu", categorie="commun", travail=28,
   materiaux={"planches": 20}, prerequis=["ecole"], population_min=12,
   description="Écrire ce qu'on a appris, pour que la génération suivante ne recommence pas.",
   effets={"enseignement": 0.5, "gouvernance": 4, "cohesion": 0.08})

# --- outillage et machines, ouverts par les découvertes -------------------
_m(cle="moulin", nom="Moulin", categorie="atelier", travail=40,
   materiaux={"pierre": 12, "bois": 8, "planches": 20}, prerequis=["atelier"],
   savoir="charpente",
   description="Moudre le grain sans bras : la farine se conserve mieux que l'épi.",
   effets={"conservation": 0.18, "nourriture_jour": 1.5})
_m(cle="aqueduc", nom="Aqueduc", categorie="eau", travail=55,
   materiaux={"pierre": 25, "terre": 15}, prerequis=["reservoir"], savoir="hydraulique",
   description="Amener l'eau de loin, en continu, sans personne pour la porter.",
   effets={"eau_jour": 900, "eau_max": 12000})
_m(cle="four_poterie", nom="Four de potier", categorie="atelier", travail=26,
   materiaux={"terre": 14, "pierre": 8}, prerequis=["atelier"], savoir="poterie",
   description="Jarres et tuiles : le grain reste sec, les toits tiennent.",
   effets={"conservation": 0.15, "stock_max": 250})
_m(cle="charrue", nom="Charrue", categorie="nourriture", travail=22,
   materiaux={"planches": 10, "recup": 15}, prerequis=["forge"], savoir="metallurgie",
   repetable=True,
   description="Retourner la terre au lieu de la gratter : le rendement change d'échelle.",
   effets={"rendement_agricole": 0.35})
_m(cle="haut_fourneau", nom="Haut-fourneau", categorie="atelier", travail=60,
   materiaux={"pierre": 30, "terre": 20, "bois": 15}, prerequis=["forge"],
   savoir="metallurgie",
   description="Produire du métal en quantité, au lieu de récupérer des ferrailles.",
   effets={"outils_jour": 0.5, "recup_jour": 8.0})
_m(cle="brouettes", nom="Brouettes et charrettes", categorie="atelier", travail=20,
   materiaux={"planches": 16}, prerequis=["atelier"], savoir="roue", repetable=True,
   description="Tout ce qu'on porte, on le roule désormais.",
   effets={"rendement_bois": 0.2, "rendement_pierre": 0.25, "logistique": 0.1})
_m(cle="attelage", nom="Attelage et bêtes de trait", categorie="nourriture", travail=45,
   materiaux={"planches": 20, "bois": 10}, prerequis=["troupeau"], savoir="traction",
   description="Un attelage laboure en un jour ce qu'une équipe ferait en dix.",
   effets={"rendement_agricole": 0.45, "rendement_construction": 0.1})
_m(cle="metier_tisser", nom="Métier à tisser", categorie="atelier", travail=38,
   materiaux={"planches": 22, "recup": 10}, prerequis=["atelier"], savoir="engrenage",
   description="Habiller tout le monde sans rien acheter au-dehors.",
   effets={"confort": 14, "isolation": 1})
_m(cle="scierie_hydraulique", nom="Scierie hydraulique", categorie="atelier", travail=55,
   materiaux={"planches": 30, "pierre": 15, "recup": 25}, prerequis=["scierie", "reservoir"],
   savoir="engrenage",
   description="La rivière débite les troncs à la place des bras.",
   effets={"planches_ratio": 3.0, "rendement_artisanat": 0.25})
_m(cle="hopital", nom="Hôpital", categorie="commun", travail=70,
   materiaux={"planches": 40, "pierre": 20}, prerequis=["dispensaire"], savoir="medecine",
   population_min=12,
   description="Soigner ce qui tuait : l'espérance de vie fait un bond.",
   effets={"soin": 1.2, "salubrite": 18})
_m(cle="atelier_mecanise", nom="Atelier mécanisé", categorie="atelier", travail=90,
   materiaux={"planches": 45, "recup": 60, "pierre": 20}, prerequis=["haut_fourneau"],
   savoir="vapeur", population_min=15,
   description="La vapeur entraîne les machines : un artisan vaut désormais dix.",
   effets={"rendement_artisanat": 0.6, "artisanat": 1.0, "outils_jour": 0.6})
_m(cle="reseau_electrique", nom="Réseau électrique", categorie="energie", travail=80,
   materiaux={"recup": 90, "planches": 20}, prerequis=["batteries"], savoir="electricite",
   population_min=15,
   description="Porter l'énergie jusque dans les maisons et les ateliers.",
   effets={"confort": 18, "elec_max": 60, "rendement_artisanat": 0.2})

# --- terre ----------------------------------------------------------------
_m(cle="defrichage", nom="Défricher un hectare", categorie="terre", travail=10, repetable=True,
   description="Gagner de la terre utile sur la friche — et récupérer du bois.",
   effets={"parcelle_friche": 1.0, "bois": 6})
_m(cle="reforestation", nom="Planter une forêt", categorie="terre", travail=14, repetable=True,
   description="Du bois pour plus tard, de l'ombre et de l'eau retenue tout de suite.",
   effets={"parcelle_foret": 2.0, "rendement": 0.04})


def disponibles(etat) -> list[dict]:
    """Chantiers proposables maintenant, avec la raison d'un éventuel blocage."""
    from .savoirs import SAVOIRS

    resultat = []
    for m in MODELES.values():
        construit = etat.batiment(m.cle)
        raisons = []
        if construit and not m.repetable:
            continue
        if m.savoir and m.savoir not in etat.decouvertes:
            # tant que la découverte n'est pas faite, le chantier n'existe pas
            continue
        for pre in m.prerequis:
            if not etat.batiment(pre):
                raisons.append(f"exige : {MODELES[pre].nom}")
        if etat.population < m.population_min:
            raisons.append(f"exige {m.population_min} personnes")
        manquants = {
            r: round(q - etat.stocks.get(r, 0), 1)
            for r, q in m.materiaux.items()
            if etat.stocks.get(r, 0) < q
        }
        resultat.append({
            "cle": m.cle, "nom": m.nom, "categorie": m.categorie,
            "travail": m.travail, "materiaux": m.materiaux, "description": m.description,
            "construit": construit, "repetable": m.repetable,
            "bloque": bool(raisons), "raisons": raisons, "manquants": manquants,
            "effets": m.effets,
        })
    return resultat


def effet_total(etat, nom: str) -> float:
    """Somme d'un effet sur tous les bâtiments construits."""
    return sum(
        MODELES[cle].effets.get(nom, 0.0) * nombre
        for cle, nombre in etat.batiments.items()
        if cle in MODELES
    )
