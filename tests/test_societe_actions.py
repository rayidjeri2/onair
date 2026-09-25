import pytest

from societe import actions, moteur
from societe.modele import Etat


def labo(personnes=4):
    e = moteur.creer_societe("Abeba", 28, graine=6)
    if personnes:
        moteur.faire_venir(e, personnes)
    return e


def test_catalogue_coherent():
    assert len(actions.ACTIONS) >= 20
    for a in actions.catalogue():
        assert a["categorie"] in actions.CATEGORIES
        assert a["nom"] and a["description"]
        for p in a["parametres"]:
            assert p["type"] in ("nombre", "choix", "interrupteur")
            if p["type"] == "choix":
                assert p["defaut"] in p["options"]
            else:
                assert p["min"] <= p["defaut"] <= p["max"]


def test_action_inconnue():
    with pytest.raises(ValueError, match="action inconnue"):
        actions.appliquer(labo(), "invoquer-la-pluie-de-grenouilles")


def test_parametres_bornes_et_valides():
    e = labo()
    actions.appliquer(e, "arrivees", {"nombre": 9999})
    assert e.interventions[-1]["parametres"]["nombre"] == 50
    with pytest.raises(ValueError, match="valeur inconnue"):
        actions.appliquer(e, "don", {"ressource": "or", "quantite": 10})
    with pytest.raises(ValueError, match="nombre attendu"):
        actions.appliquer(e, "arrivees", {"nombre": "beaucoup"})


def test_chaque_intervention_est_consignee():
    e = labo()
    actions.appliquer(e, "fete", {"intensite": 10})
    trace = e.interventions[-1]
    assert trace["cle"] == "fete" and trace["jour"] == e.jour and trace["resultat"]
    assert any(j["genre"] == "intervention" for j in e.journal.entrees)


def test_arrivees_et_famille():
    e = labo(0)
    actions.appliquer(e, "arrivees", {"nombre": 6})
    assert e.population == 7
    actions.appliquer(e, "famille", {"enfants": 3})
    assert e.population == 12
    couple = [p for p in e.personnes if p.partenaire]
    assert len(couple) >= 2
    enfants = [p for p in e.personnes if p.parents]
    assert len(enfants) == 3


def test_epidemie_frappe_puis_s_eteint():
    e = labo(5)
    actions.appliquer(e, "epidemie", {"gravite": 10, "contagion": 100, "duree": 5})
    sante = e.moyenne("sante")
    moteur.avancer(e, 3)
    assert e.moyenne("sante") < sante
    moteur.avancer(e, 10)
    assert not e.epidemie


def test_le_dispensaire_attenue_l_epidemie():
    def frappe(avec_soins):
        e = labo(5)
        if avec_soins:
            actions.appliquer(e, "construire", {"chantier": "dispensaire", "nombre": 1})
            actions.appliquer(e, "construire", {"chantier": "filtre", "nombre": 1})
        actions.appliquer(e, "epidemie", {"gravite": 20, "contagion": 100, "duree": 6})
        moteur.avancer(e, 6)
        return e.moyenne("sante")

    assert frappe(True) > frappe(False)


def test_climat_saisons_et_hiver():
    e = labo()
    actions.appliquer(e, "saisons", {"jours": 30})
    assert e.jours_par_an == 120
    actions.appliquer(e, "hiver", {"valeur": 200})
    assert e.climat["durete_hiver"] == 2.0
    actions.appliquer(e, "pluie", {"valeur": 0})
    moteur.avancer(e, 60)
    assert e.meteo.pluie == 0


def test_fertilite_change_les_recoltes():
    def recolte(fertilite):
        e = labo(3)
        actions.appliquer(e, "fertilite", {"valeur": fertilite})
        for p in e.personnes:
            if not p.enfant:
                moteur.affecter(e, p.id, "nourriture")
        e.stocks["nourriture"] = 0
        moteur.avancer(e, 20)
        return e.stocks["nourriture"]

    assert recolte(200) > recolte(50)


def test_incendie_transforme_la_foret_en_friche():
    e = labo()
    foret = e.territoire.surface("foret")
    actions.appliquer(e, "incendie", {"hectares": 10})
    assert e.territoire.surface("foret") == pytest.approx(foret - 10)
    assert e.territoire.surface("friche") > 100


def test_tempete_detruit_des_batiments():
    e = labo()
    actions.appliquer(e, "construire", {"chantier": "atelier", "nombre": 1})
    actions.appliquer(e, "construire", {"chantier": "cabane", "nombre": 1})
    avant = sum(e.batiments.values())
    actions.appliquer(e, "tempete", {"batiments": 2})
    assert sum(e.batiments.values()) < avant


def test_construire_et_demolir():
    e = labo()
    actions.appliquer(e, "construire", {"chantier": "dispensaire", "nombre": 1})
    assert e.batiment("dispensaire") == 1
    actions.appliquer(e, "demolir", {"chantier": "dispensaire"})
    assert e.batiment("dispensaire") == 0


def test_construire_ajoute_les_parcelles():
    e = labo()
    surface = e.territoire.surface("potager")
    actions.appliquer(e, "construire", {"chantier": "potager", "nombre": 4})
    assert e.territoire.surface("potager") == pytest.approx(surface + 2.0)


def test_scission_emmene_les_enfants():
    e = labo(8)
    parent = e.personnes[1]
    enfant = moteur.ajouter_personne(e, "Nino", 5, "agriculture")
    enfant.parents = [parent.id]
    parent.enfants = [enfant.id]
    avant = e.population
    actions.appliquer(e, "scission", {"part": 90})
    assert e.population < avant
    assert e.personne(parent.id) is None or e.personne(enfant.id) is not None


def test_fete_et_discorde_jouent_sur_la_cohesion():
    e = labo()
    e.cohesion = 0.5
    actions.appliquer(e, "discorde", {"intensite": 40})
    assert e.cohesion < 0.5
    basse = e.cohesion
    actions.appliquer(e, "fete", {"intensite": 20})
    assert e.cohesion > basse


def test_savoir_eleve_les_competences():
    e = labo(3)
    avant = max(p.competences["agriculture"] for p in e.personnes)
    actions.appliquer(e, "savoir", {"specialite": "agriculture", "gain": 50})
    assert max(p.competences["agriculture"] for p in e.personnes) > avant


def test_don_et_vidage():
    e = labo()
    actions.appliquer(e, "don", {"ressource": "planches", "quantite": 200})
    assert e.stocks["planches"] >= 200
    actions.appliquer(e, "vider", {"ressource": "planches"})
    assert e.stocks["planches"] == 0


def test_valeurs_courantes_suivent_les_reglages():
    e = labo()
    actions.appliquer(e, "saisons", {"jours": 45})
    actions.appliquer(e, "natalite", {"valeur": 80})
    valeurs = actions.valeurs_courantes(e)
    assert valeurs["saisons.jours"] == 45
    assert valeurs["natalite.valeur"] == 80


def test_interventions_survivent_a_la_sauvegarde():
    e = labo()
    actions.appliquer(e, "fete", {"intensite": 12})
    actions.appliquer(e, "saisons", {"jours": 60})
    copie = Etat.depuis_dict(e.vers_dict())
    assert copie.interventions == e.interventions
    assert copie.climat == e.climat
    assert copie.jours_par_an == e.jours_par_an


# --- audit de bout en bout : chaque intervention agit et laisse une trace ----

def labo_complet():
    """Une société viable, équipée, pour éprouver les interventions."""
    e = moteur.creer_societe("Abeba", 30, graine=7)
    moteur.faire_venir(e, 10)
    e.batiments.update({"source": 1, "puits": 2, "maison_terre": 6, "atelier": 1,
                        "forge": 1, "cave": 1, "ecole": 1, "place": 1, "scierie": 1})
    e.decouvertes += ["ecriture", "poterie", "metallurgie"]
    e.stocks.update({"planches": 300, "bois": 100, "pierre": 100, "recup": 300,
                     "nourriture": 400})
    e.tresor = 1500.0
    moteur.avancer(e, 5)
    moteur.lancer_chantier(e, "defrichage")   # de quoi embaucher des bras
    return e


def photo(e):
    return {
        "pop": e.population, "stocks": dict(e.stocks), "bat": dict(e.batiments),
        "climat": dict(e.climat), "cohesion": e.cohesion,
        "sante": round(e.moyenne("sante"), 2), "moral": round(e.moyenne("moral"), 2),
        "decouvertes": list(e.decouvertes), "epidemie": dict(e.epidemie),
        "natalite": e.politique.get("natalite"), "foret": e.territoire.surface("foret"),
        "potager": e.territoire.surface("potager"),
        "chantiers": [c.cle for c in e.chantiers],
        "avancement": [round(c.travail_fait, 2) for c in e.chantiers],
        "tresor": round(e.tresor, 2),
        "politique": dict(e.politique),
        "avoirs": round(sum(p.avoir for p in e.personnes), 2),
        "competences": round(sum(sum(p.competences.values()) for p in e.personnes), 2),
        "taches": sorted(p.tache for p in e.personnes),
    }


# paramètres choisis pour différer de l'état de départ, sinon « ne rien changer »
# serait le comportement correct et le test ne prouverait rien
PARAMETRES = {
    "natalite": {"valeur": 90},
    "impot": {"part": 80},
    "reserve": {"jours": 200},
    "route": {"ouverte": False},
    "tresor": {"pieces": 2500},
    "embaucher": {"pieces": 600},
    "redistribuer": {"part": 100},
    "saisons": {"jours": 40},
    "hiver": {"valeur": 180},
    "pluie": {"valeur": 0},
    "temperature": {"valeur": -12},
    "fertilite": {"valeur": 250},
    "offrir_savoir": {"savoir": "engrenage"},
    "effacer_savoir": {"savoir": "metallurgie"},
    "ouvrir_chantier": {"chantier": "reforestation"},
    "construire": {"chantier": "poulailler", "nombre": 3},
    "demolir": {"chantier": "atelier"},
}


@pytest.mark.parametrize("cle", sorted(actions.ACTIONS))
def test_chaque_intervention_agit_et_laisse_une_trace(cle):
    e = labo_complet()
    avant = photo(e)
    resultat = actions.appliquer(e, cle, PARAMETRES.get(cle, {}))
    apres = photo(e)

    assert resultat, f"{cle} ne dit pas ce qu'elle a fait"
    changements = [k for k in avant if avant[k] != apres[k]]
    assert changements, f"{cle} n'a rien changé dans l'état"

    trace = e.interventions[-1]
    assert trace["cle"] == cle and trace["jour"] == e.jour and trace["resultat"]
    assert any(j["genre"] == "intervention" and actions.ACTIONS[cle].nom in j["texte"]
               for j in e.journal.entrees)


def test_les_parametres_hors_bornes_sont_ramenes_dans_les_clous():
    e = labo_complet()
    actions.appliquer(e, "temperature", {"valeur": -99})
    assert e.climat["temperature"] == -15.0        # borne basse du paramètre
    actions.appliquer(e, "fertilite", {"valeur": 9999})
    assert e.climat["fertilite"] == 3.0            # borne haute


def test_un_reglage_durable_agit_sur_la_simulation():
    froid = labo_complet()
    actions.appliquer(froid, "temperature", {"valeur": -12})
    temoin = labo_complet()
    releves = []
    for _ in range(60):
        moteur.avancer(froid, 1)
        moteur.avancer(temoin, 1)
        releves.append(temoin.meteo.temperature - froid.meteo.temperature)
    assert all(abs(d - 12) < 1e-6 for d in releves)


def test_une_intervention_impossible_est_refusee_clairement():
    e = labo_complet()
    e.batiments["dispensaire"] = 1
    with pytest.raises(ValueError, match="déjà construit"):
        actions.appliquer(e, "ouvrir_chantier", {"chantier": "dispensaire"})
