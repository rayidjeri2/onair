"""La division du travail : des métiers à plein temps.

Un artisan qui ne fait que forger devient bien meilleur qu'un polyvalent —
mais il ne produit rien de comestible. Une société ne peut donc en entretenir
qu'à proportion de son surplus. C'est le seuil historique du passage du
hameau au village.
"""

from __future__ import annotations

from dataclasses import dataclass

from .modele import Etat, Personne


@dataclass(frozen=True)
class Metier:
    cle: str
    nom: str
    tache: str
    bonus: float          # multiplicateur d'efficacité sur sa tâche
    batiment: str         # l'atelier qu'il lui faut
    description: str
    savoir: str = ""


METIERS: dict[str, Metier] = {}


def _m(**kw) -> None:
    metier = Metier(**kw)
    METIERS[metier.cle] = metier


_m(cle="charpentier", nom="Charpentier", tache="construction", bonus=1.8,
   batiment="atelier", description="Ne fait que bâtir, et bâtit deux fois mieux.")
_m(cle="bucheron", nom="Bûcheron", tache="bois", bonus=1.7,
   batiment="scierie", description="Connaît chaque arbre du versant.")
_m(cle="carrier", nom="Carrier", tache="pierre", bonus=1.7,
   batiment="atelier", description="Tire la pierre et la terre sans se casser le dos.")
_m(cle="fontainier", nom="Fontainier", tache="eau", bonus=1.8,
   batiment="reservoir", description="Entretient les conduites et ne laisse pas une goutte se perdre.")
_m(cle="cuisinier", nom="Cuisinier", tache="cuisine", bonus=1.8,
   batiment="cuisine", description="Nourrit mieux avec moins.")
_m(cle="soigneur", nom="Soigneur", tache="soin", bonus=2.0,
   batiment="dispensaire", description="Veille sur les corps à plein temps.")
_m(cle="enseignant", nom="Enseignant", tache="enseignement", bonus=2.0,
   batiment="ecole", description="Transmet au lieu de produire : c'est un investissement.")
_m(cle="intendant", nom="Intendant", tache="organisation", bonus=1.9,
   batiment="place", description="Tient les comptes et la coordination du lieu.")
_m(cle="potier", nom="Potier", tache="artisanat", bonus=1.7,
   batiment="four_poterie", savoir="poterie",
   description="Jarres, tuiles, creusets : tout ce qui cuit.")
_m(cle="forgeron", nom="Forgeron", tache="artisanat", bonus=1.9,
   batiment="forge", savoir="metallurgie",
   description="Le métier qui fait tous les autres outils.")
_m(cle="laboureur", nom="Laboureur", tache="nourriture", bonus=1.8,
   batiment="charrue", savoir="metallurgie",
   description="Mène la charrue du premier au dernier sillon.")
_m(cle="tisserand", nom="Tisserand", tache="artisanat", bonus=1.8,
   batiment="metier_tisser", savoir="engrenage",
   description="Habille tout le monde sans rien acheter dehors.")
_m(cle="scribe", nom="Scribe", tache="recherche", bonus=2.0,
   batiment="archives", savoir="ecriture",
   description="Consigne, compare, cherche. La mémoire du lieu.")
_m(cle="mecanicien", nom="Mécanicien", tache="artisanat", bonus=2.2,
   batiment="atelier_mecanise", savoir="vapeur",
   description="Fait tourner les machines, et les répare.")


def places(etat: Etat) -> int:
    """Combien de bouches non nourricières la société peut entretenir."""
    adultes = sum(1 for p in etat.personnes if not p.enfant)
    return max(0, adultes // 3)


def exerces(etat: Etat) -> int:
    return sum(1 for p in etat.personnes if p.metier)


def possibles(etat: Etat) -> list[str]:
    """Métiers dont l'atelier est bâti et le savoir acquis."""
    return [
        m.cle for m in METIERS.values()
        if etat.batiment(m.batiment) and (not m.savoir or m.savoir in etat.decouvertes)
    ]


def attribuer(etat: Etat, id_personne: int, cle: str | None) -> None:
    """Donne (ou retire) un métier. Le métier fixe la tâche de la personne."""
    personne = etat.personne(id_personne)
    if personne is None:
        raise ValueError("personne inconnue")
    if cle in (None, ""):
        if personne.metier:
            etat.journal.noter(etat.jour,
                               f"{personne.nom} quitte son métier de "
                               f"{METIERS[personne.metier].nom.lower()}.", "info")
        personne.metier = ""
        return
    metier = METIERS.get(cle)
    if metier is None:
        raise ValueError(f"métier inconnu : {cle}")
    if personne.enfant:
        raise ValueError(f"{personne.nom} est trop jeune")
    if cle not in possibles(etat):
        raise ValueError(f"il faut {metier.batiment} pour un {metier.nom.lower()}")
    if not personne.metier and exerces(etat) >= places(etat):
        raise ValueError(
            f"le lieu ne peut entretenir que {places(etat)} métier(s) à plein temps")
    personne.metier = cle
    personne.tache = metier.tache
    etat.journal.noter(etat.jour, f"{personne.nom} devient {metier.nom.lower()}.", "jalon")


def bonus(personne: Personne, tache: str) -> float:
    """Ce que le métier ajoute, uniquement sur sa propre tâche."""
    metier = METIERS.get(personne.metier)
    if metier is None or metier.tache != tache:
        return 1.0
    return metier.bonus


def resume(etat: Etat) -> dict:
    ouverts = possibles(etat)
    return {
        "places": places(etat),
        "exerces": exerces(etat),
        "possibles": [
            {"cle": c, "nom": METIERS[c].nom, "tache": METIERS[c].tache,
             "bonus": METIERS[c].bonus, "description": METIERS[c].description}
            for c in ouverts
        ],
        "a_venir": [
            {"cle": m.cle, "nom": m.nom,
             "exige": m.batiment if not etat.batiment(m.batiment) else m.savoir}
            for m in METIERS.values() if m.cle not in ouverts
        ],
    }
