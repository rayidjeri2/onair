"""Interventions du joueur : agir sur la société pour observer ce qui s'ensuit.

Le temps tourne tout seul et l'intendance gère le quotidien. Ce module
rassemble les leviers extérieurs — faire venir du monde, envoyer une maladie,
allonger les saisons, offrir des matériaux — afin d'étudier la réaction de la
société à un choc précis.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Callable

from .catalogue import MODELES
from .modele import COMPETENCES, Etat

CATEGORIES = {
    "population": "Population",
    "epreuve": "Épreuves",
    "climat": "Climat et temps",
    "ressources": "Ressources",
    "batir": "Bâtir",
    "social": "Vie collective",
}


@dataclass(frozen=True)
class Parametre:
    cle: str
    libelle: str
    type: str = "nombre"          # nombre | choix | interrupteur
    defaut: Any = 1
    min: float = 0
    max: float = 100
    pas: float = 1
    options: list[str] = field(default_factory=list)
    unite: str = ""


@dataclass(frozen=True)
class Action:
    cle: str
    nom: str
    categorie: str
    description: str
    parametres: list[Parametre] = field(default_factory=list)
    effet: Callable[[Etat, dict, random.Random], str] = None  # type: ignore[assignment]
    durable: bool = False         # modifie un réglage plutôt que d'assener un choc


ACTIONS: dict[str, Action] = {}


def _a(**kw) -> None:
    action = Action(**kw)
    ACTIONS[action.cle] = action


# --- population -----------------------------------------------------------

def _venir(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    venus = moteur.faire_venir(etat, int(p["nombre"]))
    return f"{len(venus)} arrivée(s) : {', '.join(x.nom for x in venus)}."


_a(cle="arrivees", nom="Faire venir des gens", categorie="population",
   description="Des inconnus s'installent : nom, âge, sexe et savoir-faire tirés au sort.",
   parametres=[Parametre("nombre", "Combien", defaut=5, min=1, max=50)],
   effet=_venir)


def _famille(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    ages = [alea.randint(24, 40), alea.randint(24, 40)]
    parents = [
        moteur.ajouter_personne(etat, "", ages[0], alea.choice(COMPETENCES), sexe="f"),
        moteur.ajouter_personne(etat, "", ages[1], alea.choice(COMPETENCES), sexe="h"),
    ]
    parents[0].partenaire, parents[1].partenaire = parents[1].id, parents[0].id
    enfants = []
    for _ in range(int(p["enfants"])):
        e = moteur.ajouter_personne(etat, "", alea.randint(1, 13), "agriculture",
                                    sexe="f" if alea.random() < 0.5 else "h")
        e.parents = [parents[0].id, parents[1].id]
        parents[0].enfants.append(e.id)
        parents[1].enfants.append(e.id)
        enfants.append(e)
    return (f"Une famille s'installe : {parents[0].nom} et {parents[1].nom}"
            f"{' avec ' + str(len(enfants)) + ' enfant(s)' if enfants else ''}.")


_a(cle="famille", nom="Accueillir une famille", categorie="population",
   description="Un couple et ses enfants — deux bras de plus, et des bouches à nourrir tout de suite.",
   parametres=[Parametre("enfants", "Enfants", defaut=2, min=0, max=8)],
   effet=_famille)


def _depart(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    adultes = [x for x in etat.personnes if x.adulte and not any(
        e.id in x.enfants and e.enfant for e in etat.personnes)]
    partants = alea.sample(adultes, min(int(p["nombre"]), len(adultes)))
    for x in partants:
        etat.personnes.remove(x)
        moteur._detacher(etat, x)
    return f"{len(partants)} départ(s) : {', '.join(x.nom for x in partants) or 'personne'}."


_a(cle="depart", nom="Provoquer des départs", categorie="population",
   description="Des adultes sans jeunes enfants quittent le lieu.",
   parametres=[Parametre("nombre", "Combien", defaut=3, min=1, max=30)],
   effet=_depart)


def _expert(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    specialite = p.get("specialite") or alea.choice(COMPETENCES)
    personne = moteur.personne_au_hasard(etat, alea)
    personne.age = max(25, min(55, personne.age))
    personne.competences[specialite] = 1.0
    personne.polyvalence = 0.7
    personne.histoire = f"maîtrise {specialite} comme personne ici"
    return f"{personne.nom} arrive, {specialite} au plus haut niveau."


_a(cle="expert", nom="Faire venir une sommité", categorie="population",
   description="Une personne au sommet d'un savoir-faire : de quoi voir ce que change un seul individu.",
   parametres=[Parametre("specialite", "Savoir-faire", type="choix",
                         defaut="construction", options=list(COMPETENCES))],
   effet=_expert)


def _natalite(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    moteur.regler_politique(etat, "natalite", float(p["valeur"]) / 100)
    return f"Désir d'enfants réglé à {int(p['valeur'])} %."


_a(cle="natalite", nom="Régler le désir d'enfants", categorie="population", durable=True,
   description="De « aucun enfant voulu » à « autant que le lieu peut en porter ».",
   parametres=[Parametre("valeur", "Niveau", defaut=50, min=0, max=100, pas=5, unite="%")],
   effet=_natalite)


# --- épreuves -------------------------------------------------------------

def _epidemie(etat: Etat, p: dict, alea: random.Random) -> str:
    etat.epidemie = {
        "nom": p.get("nom") or "fièvre",
        "gravite": float(p["gravite"]),
        "contagion": float(p["contagion"]) / 100,
        "jours": float(p["duree"]),
    }
    return (f"Une {etat.epidemie['nom']} se déclare : {int(p['contagion'])} % de la population "
            f"touchée chaque jour pendant {int(p['duree'])} jours.")


_a(cle="epidemie", nom="Déclencher une épidémie", categorie="epreuve",
   description="Frappe chaque jour une part de la population. Le dispensaire et la salubrité en atténuent l'effet.",
   parametres=[
       Parametre("gravite", "Gravité (points de santé par jour)", defaut=8, min=1, max=60),
       Parametre("contagion", "Part touchée par jour", defaut=25, min=5, max=100, pas=5, unite="%"),
       Parametre("duree", "Durée", defaut=15, min=1, max=200, unite="jours"),
   ],
   effet=_epidemie)


def _famine(etat: Etat, p: dict, alea: random.Random) -> str:
    perdu = etat.stocks["nourriture"] * float(p["part"]) / 100
    etat.stocks["nourriture"] -= perdu
    return f"{perdu:.0f} portions détruites."


_a(cle="famine", nom="Détruire les réserves", categorie="epreuve",
   description="Charançons, moisissure, vol : une part du grenier disparaît.",
   parametres=[Parametre("part", "Part détruite", defaut=50, min=5, max=100, pas=5, unite="%")],
   effet=_famine)


def _secheresse(etat: Etat, p: dict, alea: random.Random) -> str:
    etat.stocks["eau"] *= 1 - float(p["part"]) / 100
    etat.climat["pluie"] = max(0.0, etat.climat.get("pluie", 1.0) * 0.2)
    return (f"Les réserves d'eau chutent de {int(p['part'])} % et la pluie se raréfie. "
            "Rétablissez le régime des pluies quand vous voudrez.")


_a(cle="secheresse", nom="Sécheresse", categorie="epreuve",
   description="Vide les réserves et coupe la pluie — l'effet sur la pluie reste jusqu'à ce que vous le leviez.",
   parametres=[Parametre("part", "Réserves perdues", defaut=70, min=10, max=100, pas=5, unite="%")],
   effet=_secheresse)


def _tempete(etat: Etat, p: dict, alea: random.Random) -> str:
    detruits = []
    reparables = [c for c in etat.batiments if etat.batiments[c] > 0 and c != "campement"]
    for _ in range(int(p["batiments"])):
        if not reparables:
            break
        cle = alea.choice(reparables)
        etat.batiments[cle] -= 1
        if etat.batiments[cle] <= 0:
            del etat.batiments[cle]
            reparables.remove(cle)
        detruits.append(MODELES[cle].nom)
    etat.stocks["planches"] *= 0.7
    for chantier in etat.chantiers:
        chantier.travail_fait *= 0.5
    return f"Tempête : {', '.join(detruits) if detruits else 'des dégâts matériels'}."


_a(cle="tempete", nom="Tempête", categorie="epreuve",
   description="Emporte des constructions et une partie des planches.",
   parametres=[Parametre("batiments", "Bâtiments détruits", defaut=1, min=0, max=10)],
   effet=_tempete)


def _incendie(etat: Etat, p: dict, alea: random.Random) -> str:
    brulee = min(etat.territoire.surface("foret"), float(p["hectares"]))
    restant = brulee
    for parcelle in list(etat.territoire.parcelles):
        if parcelle.type == "foret" and restant > 0:
            pris = min(parcelle.hectares, restant)
            parcelle.hectares -= pris
            restant -= pris
            if parcelle.hectares <= 0.01:
                etat.territoire.parcelles.remove(parcelle)
    etat.territoire.ajouter("friche", brulee)
    etat.stocks["bois"] *= 0.4
    return f"{brulee:.0f} hectares de forêt partis en fumée."


_a(cle="incendie", nom="Incendie de forêt", categorie="epreuve",
   description="La forêt brûle et repasse en friche : le bois manquera pendant des années.",
   parametres=[Parametre("hectares", "Surface brûlée", defaut=20, min=1, max=200, unite="ha")],
   effet=_incendie)


def _blessure(etat: Etat, p: dict, alea: random.Random) -> str:
    if not etat.personnes:
        return "Personne à frapper."
    victime = alea.choice(etat.personnes)
    victime.sante = max(1.0, victime.sante - float(p["gravite"]))
    victime.energie = max(0.0, victime.energie - 40)
    return f"{victime.nom} est gravement blessé(e)."


_a(cle="blessure", nom="Accident", categorie="epreuve",
   description="Une personne au hasard est blessée : voir si le groupe absorbe la perte.",
   parametres=[Parametre("gravite", "Gravité", defaut=45, min=5, max=99)],
   effet=_blessure)


# --- climat ---------------------------------------------------------------

def _saisons(etat: Etat, p: dict, alea: random.Random) -> str:
    etat.climat["jours_par_saison"] = float(p["jours"])
    return (f"Une saison dure désormais {int(p['jours'])} jours, "
            f"soit une année de {etat.jours_par_an} jours.")


_a(cle="saisons", nom="Durée des saisons", categorie="climat", durable=True,
   description="Change la longueur de l'année : des cycles courts ne laissent pas le temps de stocker.",
   parametres=[Parametre("jours", "Jours par saison", defaut=91, min=5, max=180)],
   effet=_saisons)


def _hiver(etat: Etat, p: dict, alea: random.Random) -> str:
    etat.climat["durete_hiver"] = float(p["valeur"]) / 100
    return f"Dureté de l'hiver réglée à {int(p['valeur'])} %."


_a(cle="hiver", nom="Dureté de l'hiver", categorie="climat", durable=True,
   description="À 200 %, l'hiver gèle et ne laisse presque rien pousser.",
   parametres=[Parametre("valeur", "Dureté", defaut=100, min=0, max=200, pas=10, unite="%")],
   effet=_hiver)


def _pluie(etat: Etat, p: dict, alea: random.Random) -> str:
    etat.climat["pluie"] = float(p["valeur"]) / 100
    return f"Régime des pluies réglé à {int(p['valeur'])} %."


_a(cle="pluie", nom="Régime des pluies", categorie="climat", durable=True,
   description="Coupez la pluie et l'eau ne viendra plus que de la source et des puits.",
   parametres=[Parametre("valeur", "Pluie", defaut=100, min=0, max=300, pas=10, unite="%")],
   effet=_pluie)


def _temperature(etat: Etat, p: dict, alea: random.Random) -> str:
    etat.climat["temperature"] = float(p["valeur"])
    return f"Températures décalées de {float(p['valeur']):+.0f} °C."


_a(cle="temperature", nom="Décaler les températures", categorie="climat", durable=True,
   description="Un réchauffement ou un refroidissement durable du lieu.",
   parametres=[Parametre("valeur", "Décalage", defaut=0, min=-15, max=15, unite="°C")],
   effet=_temperature)


def _fertilite(etat: Etat, p: dict, alea: random.Random) -> str:
    etat.climat["fertilite"] = float(p["valeur"]) / 100
    return f"Fertilité des sols réglée à {int(p['valeur'])} %."


_a(cle="fertilite", nom="Fertilité des sols", categorie="climat", durable=True,
   description="Sol épuisé ou terre noire : agit sur toutes les récoltes.",
   parametres=[Parametre("valeur", "Fertilité", defaut=100, min=10, max=300, pas=10, unite="%")],
   effet=_fertilite)


# --- ressources -----------------------------------------------------------

def _don(etat: Etat, p: dict, alea: random.Random) -> str:
    ressource = p["ressource"]
    etat.stocks[ressource] = etat.stocks.get(ressource, 0.0) + float(p["quantite"])
    return f"{int(p['quantite'])} de {ressource} livrés."


_a(cle="don", nom="Livrer des ressources", categorie="ressources",
   description="Un convoi arrive de l'extérieur : de quoi lever un goulot d'étranglement.",
   parametres=[
       Parametre("ressource", "Ressource", type="choix", defaut="planches",
                 options=["nourriture", "eau", "bois", "pierre", "terre", "recup",
                          "planches", "outils", "compost", "electricite"]),
       Parametre("quantite", "Quantité", defaut=100, min=1, max=5000),
   ],
   effet=_don)


def _vider(etat: Etat, p: dict, alea: random.Random) -> str:
    ressource = p["ressource"]
    perdu = etat.stocks.get(ressource, 0.0)
    etat.stocks[ressource] = 0.0
    return f"{perdu:.0f} de {ressource} perdus."


_a(cle="vider", nom="Vider un stock", categorie="ressources",
   description="Tout perdre d'un coup sur une ressource, pour voir comment le groupe s'en remet.",
   parametres=[Parametre("ressource", "Ressource", type="choix", defaut="bois",
                         options=["nourriture", "eau", "bois", "pierre", "terre", "recup",
                                  "planches", "outils", "compost", "electricite"])],
   effet=_vider)


def _defricher(etat: Etat, p: dict, alea: random.Random) -> str:
    etat.territoire.ajouter(p["type"], float(p["hectares"]),
                            0.05 if p["type"] in ("verger", "foret") else 1.0)
    return f"{float(p['hectares']):.0f} hectares de {p['type']} ajoutés."


_a(cle="terrain", nom="Aménager du terrain", categorie="ressources",
   description="Convertir de la friche d'un coup, sans y passer des jours-homme.",
   parametres=[
       Parametre("type", "En quoi", type="choix", defaut="potager",
                 options=["potager", "verger", "foret", "pature", "eau"]),
       Parametre("hectares", "Surface", defaut=5, min=1, max=200, unite="ha"),
   ],
   effet=_defricher)


# --- bâtir ----------------------------------------------------------------

def _construire(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    cle = p["chantier"]
    modele = MODELES.get(cle)
    if modele is None:
        raise ValueError("chantier inconnu")
    combien = int(p.get("nombre", 1))
    if not modele.repetable:
        combien = 1
    for _ in range(combien):
        etat.batiments[cle] = etat.batiment(cle) + 1
        for effet, valeur in modele.effets.items():
            if effet.startswith("parcelle_"):
                type_parcelle = effet.removeprefix("parcelle_")
                if type_parcelle != "friche":
                    etat.territoire.ajouter(
                        type_parcelle, valeur,
                        0.05 if type_parcelle in ("verger", "foret") else 1.0)
            elif effet in etat.stocks:
                etat.stocks[effet] += valeur
    return f"{modele.nom} ×{combien} sort de terre sans un jour de travail."


_a(cle="construire", nom="Bâtir instantanément", categorie="batir",
   description="Poser une construction sans travail ni matériaux, pour tester son effet isolément.",
   parametres=[
       Parametre("chantier", "Quoi", type="choix", defaut="maison_terre",
                 options=sorted(MODELES)),
       Parametre("nombre", "Combien", defaut=1, min=1, max=20),
   ],
   effet=_construire)


def _demolir(etat: Etat, p: dict, alea: random.Random) -> str:
    cle = p["chantier"]
    if not etat.batiment(cle):
        return "Rien à démolir."
    etat.batiments[cle] -= 1
    if etat.batiments[cle] <= 0:
        del etat.batiments[cle]
    return f"{MODELES[cle].nom} démoli."


_a(cle="demolir", nom="Démolir", categorie="batir",
   description="Retirer une construction pour mesurer ce qu'elle apportait.",
   parametres=[Parametre("chantier", "Quoi", type="choix", defaut="dispensaire",
                         options=sorted(MODELES))],
   effet=_demolir)


def _chantier(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    if len(etat.chantiers) >= etat.chantiers_max and etat.chantiers:
        moteur.annuler_chantier(etat, etat.chantiers[0].cle)
    moteur.lancer_chantier(etat, p["chantier"])
    return f"Chantier ouvert : {MODELES[p['chantier']].nom}."


_a(cle="ouvrir_chantier", nom="Imposer un chantier", categorie="batir",
   description="Ouvrir ce chantier maintenant, à la place de ce que l'intendance avait prévu.",
   parametres=[Parametre("chantier", "Quoi", type="choix", defaut="place",
                         options=sorted(MODELES))],
   effet=_chantier)


# --- vie collective -------------------------------------------------------

def _fete(etat: Etat, p: dict, alea: random.Random) -> str:
    cout = min(etat.stocks["nourriture"], etat.population * 2.0)
    etat.stocks["nourriture"] -= cout
    for x in etat.personnes:
        x.moral = min(100.0, x.moral + float(p["intensite"]))
    etat.cohesion = min(1.0, etat.cohesion + 0.12)
    return f"On festoie : {cout:.0f} portions consommées, le moral remonte."


_a(cle="fete", nom="Organiser une fête", categorie="social",
   description="Remonte le moral et la cohésion, au prix de quelques réserves.",
   parametres=[Parametre("intensite", "Effet sur le moral", defaut=15, min=1, max=50)],
   effet=_fete)


def _discorde(etat: Etat, p: dict, alea: random.Random) -> str:
    etat.cohesion = max(0.0, etat.cohesion - float(p["intensite"]) / 100)
    for x in etat.personnes:
        x.moral = max(0.0, x.moral - float(p["intensite"]) / 2)
    return "Une dispute divise le lieu."


_a(cle="discorde", nom="Semer la discorde", categorie="social",
   description="Fait chuter la cohésion : la coordination du travail en pâtit aussitôt.",
   parametres=[Parametre("intensite", "Intensité", defaut=30, min=5, max=100, pas=5, unite="%")],
   effet=_discorde)


def _scission(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    adultes = [x for x in etat.personnes if x.adulte]
    combien = min(int(len(adultes) * float(p["part"]) / 100), len(adultes) - 1)
    if combien <= 0:
        return "Le groupe est trop petit pour se scinder."
    partants = alea.sample(adultes, combien)
    emmenes: dict[int, Any] = {x.id: x for x in partants}
    for x in partants:
        for enfant in etat.personnes:
            if enfant.id in x.enfants and enfant.enfant:
                emmenes[enfant.id] = enfant
    for x in emmenes.values():
        if x in etat.personnes:
            etat.personnes.remove(x)
            moteur._detacher(etat, x)
    return f"{len(emmenes)} personnes partent fonder un autre lieu."


_a(cle="scission", nom="Provoquer une scission", categorie="social",
   description="Une partie du groupe s'en va avec ses enfants — la façon la plus nette de tester la taille critique.",
   parametres=[Parametre("part", "Part des adultes", defaut=40, min=5, max=90, pas=5, unite="%")],
   effet=_scission)


def _savoir(etat: Etat, p: dict, alea: random.Random) -> str:
    specialite = p["specialite"]
    for x in etat.personnes:
        if not x.enfant:
            x.competences[specialite] = min(1.0, x.competences[specialite]
                                            + float(p["gain"]) / 100)
    return f"Tout le monde progresse en {specialite}."


_a(cle="savoir", nom="Transmettre un savoir", categorie="social",
   description="Élève d'un coup une compétence chez tous les adultes.",
   parametres=[
       Parametre("specialite", "Savoir-faire", type="choix", defaut="agriculture",
                 options=list(COMPETENCES)),
       Parametre("gain", "Gain", defaut=25, min=5, max=100, pas=5, unite="points"),
   ],
   effet=_savoir)


def _repos(etat: Etat, p: dict, alea: random.Random) -> str:
    for x in etat.personnes:
        x.tache = "repos"
        x.energie = min(100.0, x.energie + 30)
    return "Tout le monde s'arrête. L'intendance reprendra demain matin."


_a(cle="repos", nom="Décréter un repos", categorie="social",
   description="Une pause générale : l'énergie remonte, rien ne se produit.",
   effet=_repos)


def _offrir_savoir(etat: Etat, p: dict, alea: random.Random) -> str:
    from .savoirs import SAVOIRS

    cle = p["savoir"]
    if cle in etat.decouvertes:
        return f"{SAVOIRS[cle].nom} était déjà connu."
    etat.decouvertes.append(cle)
    return f"{SAVOIRS[cle].nom} tombe du ciel, des siècles trop tôt."


def _effacer_savoir(etat: Etat, p: dict, alea: random.Random) -> str:
    from .savoirs import SAVOIRS

    cle = p["savoir"]
    if cle not in etat.decouvertes:
        return f"{SAVOIRS[cle].nom} n'était pas connu."
    etat.decouvertes.remove(cle)
    etat.savoirs.pop(cle, None)
    return f"{SAVOIRS[cle].nom} est effacé des mémoires."


def _relancer_recherche(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    combien = 0
    for personne in etat.personnes:
        if personne.enfant or personne.metier:
            continue
        if combien >= int(p["chercheurs"]):
            break
        try:
            moteur.affecter(etat, personne.id, "recherche")
            combien += 1
        except ValueError:
            continue
    return f"{combien} personne(s) mises à chercher. L'intendance rendra la main demain."


def _enregistrer_savoirs() -> None:
    from .savoirs import SAVOIRS

    liste = sorted(SAVOIRS)
    _a(cle="offrir_savoir", nom="Offrir une découverte", categorie="social",
       description="Donner un savoir que la société n'a pas encore gagné : "
                   "pour voir ce que change une technologie arrivée trop tôt.",
       parametres=[Parametre("savoir", "Découverte", type="choix",
                             defaut="metallurgie", options=liste)],
       effet=_offrir_savoir)
    _a(cle="effacer_savoir", nom="Effacer une découverte", categorie="epreuve",
       description="Le savoir se perd. Ce qu'il débloquait redevient inaccessible.",
       parametres=[Parametre("savoir", "Découverte", type="choix",
                             defaut="agronomie", options=liste)],
       effet=_effacer_savoir)
    _a(cle="recherche", nom="Mettre des gens à chercher", categorie="social",
       description="Détourner des bras vers la recherche, le temps d'une journée.",
       parametres=[Parametre("chercheurs", "Combien", defaut=3, min=1, max=30)],
       effet=_relancer_recherche)


_enregistrer_savoirs()


# --- commerce et monnaie --------------------------------------------------

def _caravane(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import marche

    bilan = marche.caravane(etat, alea, forcee=True)
    if not bilan.get("passee"):
        return "La route est fermée."
    ventes = ", ".join(f"{o['quantite']:g} {o['ressource']}" for o in bilan["ventes"])
    achats = ", ".join(f"{o['quantite']:g} {o['ressource']}" for o in bilan["achats"])
    return (f"Vendu {ventes or 'rien'} pour {bilan['recette']:.0f} pièces ; "
            f"acheté {achats or 'rien'} pour {bilan['depense']:.0f}.")


_a(cle="caravane", nom="Appeler une caravane", categorie="ressources",
   description="Faire venir les marchands maintenant : on vend le surplus, on achète ce qui bloque.",
   effet=_caravane)


def _route(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    moteur.regler_politique(etat, "commerce", 1.0 if p["ouverte"] else 0.0)
    return "La route est ouverte." if p["ouverte"] else "Le lieu se ferme au commerce."


_a(cle="route", nom="Ouvrir ou fermer la route", categorie="ressources", durable=True,
   description="Vivre en autarcie, ou dépendre du dehors : deux trajectoires différentes.",
   parametres=[Parametre("ouverte", "Route ouverte", type="interrupteur", defaut=True)],
   effet=_route)


def _impot(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    moteur.regler_politique(etat, "impot", float(p["part"]) / 100)
    return f"{int(p['part'])} % des ventes vont au trésor commun, le reste aux gens."


_a(cle="impot", nom="Fixer l'impôt", categorie="social", durable=True,
   description="Part des ventes versée au trésor commun. À 100 %, personne ne s'enrichit "
               "en propre ; à 0 %, tout va aux individus et les écarts se creusent.",
   parametres=[Parametre("part", "Part commune", defaut=25, min=0, max=100, pas=5, unite="%")],
   effet=_impot)


def _reserve(etat: Etat, p: dict, alea: random.Random) -> str:
    from . import moteur

    moteur.regler_politique(etat, "reserve_jours", float(p["jours"]))
    return f"On garde {int(p['jours'])} jours de vivres avant de vendre quoi que ce soit."


_a(cle="reserve", nom="Réserve stratégique", categorie="ressources", durable=True,
   description="Combien de jours de vivres garder avant de vendre le surplus. "
               "Vendre trop tôt, c'est risquer l'hiver.",
   parametres=[Parametre("jours", "Jours gardés", defaut=90, min=0, max=365, pas=5)],
   effet=_reserve)


def _embaucher(etat: Etat, p: dict, alea: random.Random) -> str:
    from .catalogue import MODELES

    if not etat.chantiers:
        return "Aucun chantier où mettre ces bras."
    depense = min(etat.tresor, float(p["pieces"]))
    if depense < 10:
        return "Le trésor est vide."
    etat.tresor = round(etat.tresor - depense, 2)
    apport = depense / 18.0        # ce que coûte une journée de travail au-dehors
    part = apport / len(etat.chantiers)
    for chantier in etat.chantiers:
        chantier.travail_fait += part
    return (f"{depense:.0f} pièces dépensées : {apport:.0f} jours-homme "
            f"de main-d'œuvre extérieure.")


_a(cle="embaucher", nom="Embaucher des bras", categorie="batir",
   description="Payer des ouvriers du dehors pour avancer les chantiers en cours.",
   parametres=[Parametre("pieces", "Pièces dépensées", defaut=200, min=10, max=20000)],
   effet=_embaucher)


def _tresor(etat: Etat, p: dict, alea: random.Random) -> str:
    etat.tresor = round(max(0.0, etat.tresor + float(p["pieces"])), 2)
    return f"Le trésor compte maintenant {etat.tresor:.0f} pièces."


_a(cle="tresor", nom="Verser ou retirer de l'argent", categorie="ressources",
   description="Un héritage, un tribut, un vol : de quoi tester ce que l'argent change.",
   parametres=[Parametre("pieces", "Pièces", defaut=1000, min=-50000, max=50000, pas=100)],
   effet=_tresor)


def _redistribuer(etat: Etat, p: dict, alea: random.Random) -> str:
    adultes = [x for x in etat.personnes if not x.enfant]
    if not adultes:
        return "Personne à qui donner."
    total = sum(x.avoir for x in adultes) + etat.tresor * float(p["part"]) / 100
    etat.tresor = round(etat.tresor * (1 - float(p["part"]) / 100), 2)
    pour_chacun = total / len(adultes)
    for x in adultes:
        x.avoir = round(pour_chacun, 2)
    return f"Tout est remis à plat : {pour_chacun:.0f} pièces pour chacun."


_a(cle="redistribuer", nom="Tout redistribuer", categorie="social",
   description="Égaliser les fortunes et vider une part du trésor : "
               "l'indice d'inégalité retombe à zéro.",
   parametres=[Parametre("part", "Part du trésor partagée", defaut=50, min=0, max=100,
                         pas=10, unite="%")],
   effet=_redistribuer)


# --- application ----------------------------------------------------------

def appliquer(etat: Etat, cle: str, parametres: dict[str, Any] | None = None) -> str:
    """Applique une intervention et la consigne dans le journal."""
    action = ACTIONS.get(cle)
    if action is None:
        raise ValueError(f"action inconnue : {cle}")
    valeurs = _valider(action, parametres or {})
    alea = random.Random(etat.graine * 31 + etat.jour * 7 + len(etat.interventions))
    texte = action.effet(etat, valeurs, alea)
    etat.journal.noter(etat.jour, f"⟡ {action.nom} — {texte}", "intervention")
    etat.interventions.append({
        "jour": etat.jour, "annee": etat.annee, "cle": cle,
        "nom": action.nom, "parametres": valeurs, "resultat": texte,
    })
    del etat.interventions[:-200]
    return texte


def _valider(action: Action, fournis: dict[str, Any]) -> dict[str, Any]:
    valeurs: dict[str, Any] = {}
    for parametre in action.parametres:
        brut = fournis.get(parametre.cle, parametre.defaut)
        if parametre.type == "choix":
            if brut not in parametre.options:
                raise ValueError(f"{parametre.cle} : valeur inconnue ({brut})")
            valeurs[parametre.cle] = brut
        elif parametre.type == "interrupteur":
            valeurs[parametre.cle] = bool(brut)
        else:
            try:
                nombre = float(brut)
            except (TypeError, ValueError):
                raise ValueError(f"{parametre.cle} : nombre attendu") from None
            valeurs[parametre.cle] = max(parametre.min, min(parametre.max, nombre))
    return valeurs


def valeurs_courantes(etat: Etat) -> dict[str, Any]:
    """Valeur actuelle des réglages durables, pour pré-remplir l'interface."""
    climat = etat.climat
    return {
        "saisons.jours": climat.get("jours_par_saison", 91.0),
        "hiver.valeur": round(climat.get("durete_hiver", 1.0) * 100),
        "pluie.valeur": round(climat.get("pluie", 1.0) * 100),
        "temperature.valeur": climat.get("temperature", 0.0),
        "fertilite.valeur": round(climat.get("fertilite", 1.0) * 100),
        "natalite.valeur": round(etat.politique.get("natalite", 0.5) * 100),
    }


def catalogue() -> list[dict[str, Any]]:
    """Le catalogue des interventions, pour l'interface."""
    return [
        {
            "cle": a.cle, "nom": a.nom, "categorie": a.categorie,
            "categorie_nom": CATEGORIES[a.categorie],
            "description": a.description, "durable": a.durable,
            "parametres": [
                {"cle": p.cle, "libelle": p.libelle, "type": p.type, "defaut": p.defaut,
                 "min": p.min, "max": p.max, "pas": p.pas, "options": p.options,
                 "unite": p.unite}
                for p in a.parametres
            ],
        }
        for a in ACTIONS.values()
    ]
