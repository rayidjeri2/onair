import pytest

from societe import moteur
from societe.catalogue import MODELES, disponibles
from societe.modele import Etat


def societe():
    return moteur.creer_societe("Ana", 30, graine=5)


def test_depart_une_seule_personne_sur_un_million_de_km2():
    e = societe()
    assert e.population == 1
    assert e.territoire.km2 == 1_000_000
    assert e.jour == 0 and e.saison == "printemps"
    assert e.stocks["nourriture"] > 0
    # elle s'installe : un abri et un champ, comme point de départ
    assert e.batiment("campement") == 1
    assert e.territoire.surface("potager") == 1.0


def test_deterministe_a_graine_fixee():
    a, b = moteur.creer_societe("Ana", 30, 7), moteur.creer_societe("Ana", 30, 7)
    moteur.avancer(a, 120)
    moteur.avancer(b, 120)
    assert a.stocks == b.stocks
    assert a.moyenne("moral") == b.moyenne("moral")


def test_graines_differentes_donnent_des_parties_differentes():
    a = moteur.avancer(moteur.creer_societe("Ana", 30, 1), 200)
    b = moteur.avancer(moteur.creer_societe("Ana", 30, 2), 200)
    assert a.journal.entrees != b.journal.entrees


def test_une_personne_seule_survit_en_cueillant():
    e = societe()
    moteur.avancer(e, 200)
    assert e.population == 1
    assert e.personnes[0].sante > 30


def test_chantier_consomme_les_materiaux_et_le_travail():
    e = societe()
    moteur.lancer_chantier(e, "source")
    assert e.chantier is not None
    moteur.affecter(e, 1, "construction")
    moteur.avancer(e, 25)
    assert e.batiment("source") == 1
    assert e.chantier is None


def test_prerequis_refuse():
    e = societe()
    with pytest.raises(ValueError, match="prérequis"):
        moteur.lancer_chantier(e, "scierie")


def test_materiaux_manquants_refuses():
    e = societe()
    with pytest.raises(ValueError, match="matériaux"):
        moteur.lancer_chantier(e, "toilettes_seches")


def test_un_seul_chantier_a_la_fois():
    e = societe()
    moteur.lancer_chantier(e, "source")
    with pytest.raises(ValueError, match="déjà en cours"):
        moteur.lancer_chantier(e, "potager")


def test_annulation_rend_une_partie_des_materiaux():
    e = societe()
    e.stocks["planches"] = 20
    moteur.lancer_chantier(e, "toilettes_seches")
    assert e.stocks["planches"] == 12
    moteur.annuler_chantier(e)
    assert e.stocks["planches"] == pytest.approx(12 + 8 * 0.6)


def test_arrivee_de_personne():
    e = societe()
    p = moteur.ajouter_personne(e, "Tomas", 28, "construction", "venu du nord")
    assert e.population == 2
    assert p.competences["construction"] > 0.5
    assert any("Tomas" in j["texte"] for j in e.journal.entrees)


def test_specialite_inconnue_refusee():
    e = societe()
    with pytest.raises(ValueError):
        moteur.ajouter_personne(e, "X", 30, "sorcellerie")


def test_coordination_se_degrade_avec_la_population():
    e = societe()
    seul = moteur.coordination(e)
    for i in range(12):
        moteur.ajouter_personne(e, f"P{i}", 30, "agriculture")
    assert moteur.coordination(e) < seul * 0.8


def test_salle_commune_restaure_la_coordination():
    a = societe()
    for i in range(10):
        moteur.ajouter_personne(a, f"P{i}", 30, "agriculture")
    b = Etat.depuis_dict(a.vers_dict())
    b.batiments["place"] = 1
    assert moteur.coordination(b) > moteur.coordination(a)


def test_verger_met_des_annees_a_produire():
    e = societe()
    e.territoire.ajouter("verger", 1.0, maturite=0.05)
    depart = e.territoire.surface_productive("verger")
    moteur.avancer(e, 365)
    assert e.territoire.surface_productive("verger") > depart * 3


def test_sans_personne_la_societe_s_eteint():
    e = societe()
    e.personnes.clear()
    moteur.avancer(e, 1)
    assert e.termine


def test_une_arrivee_relance_une_societe_eteinte():
    e = societe()
    e.personnes.clear()
    moteur.avancer(e, 1)
    moteur.ajouter_personne(e, "Iris", 30, "agriculture")
    assert e.termine is None
    moteur.avancer(e, 3)
    assert e.jour > 1


def test_serialisation_complete():
    e = societe()
    moteur.lancer_chantier(e, "source")
    moteur.ajouter_personne(e, "Tomas", 28, "eau")
    moteur.avancer(e, 40)
    copie = Etat.depuis_dict(e.vers_dict())
    assert copie.jour == e.jour
    assert copie.population == e.population
    assert copie.batiments == e.batiments
    assert copie.chantier == e.chantier
    moteur.avancer(copie, 10)
    moteur.avancer(e, 10)
    assert copie.stocks == e.stocks


def test_catalogue_coherent():
    for m in MODELES.values():
        for pre in m.prerequis:
            assert pre in MODELES, f"prérequis inconnu dans {m.cle}"
        assert m.travail > 0
        assert m.categorie
        assert m.description


def test_disponibles_signale_les_blocages():
    e = societe()
    par_cle = {c["cle"]: c for c in disponibles(e)}
    assert not par_cle["source"]["bloque"]
    assert par_cle["scierie"]["bloque"]
    assert par_cle["conseil"]["bloque"]
    assert "campement" not in par_cle  # déjà monté au départ, non répétable


def test_flux_du_jour_expose():
    e = societe()
    moteur.affecter(e, 1, "bois")
    moteur.avancer(e, 3)
    assert e.flux["bois"] > 0
    assert e.flux["nourriture"] < 0  # on mange sans produire
    assert set(e.flux) == set(e.stocks)


def test_capacites_grandissent_avec_le_groupe_et_les_hangars():
    e = societe()
    petites = moteur.capacites(e)
    for i in range(6):
        moteur.ajouter_personne(e, f"P{i}", 30, "agriculture")
    moyennes = moteur.capacites(e)
    assert moyennes["nourriture"] > petites["nourriture"]
    assert moyennes["bois"] > petites["bois"]
    e.batiments["hangar"] = 2
    grandes = moteur.capacites(e)
    assert grandes["planches"] > moyennes["planches"]


def test_les_stocks_ne_depassent_pas_leur_capacite():
    e = societe()
    for ressource in ("bois", "planches", "pierre", "terre", "compost", "recup", "outils"):
        e.stocks[ressource] = 10_000
    moteur.avancer(e, 1)
    plafonds = moteur.capacites(e)
    for ressource, plafond in plafonds.items():
        if plafond:
            assert e.stocks[ressource] <= plafond + 1e-6, ressource
    assert any("déborde" in j["texte"] for j in e.journal.entrees)


def test_apercu_porte_flux_et_capacites():
    e = societe()
    moteur.avancer(e, 2)
    a = moteur.apercu(e)
    assert a["flux"] == e.flux
    assert a["capacites"]["eau"] > 0
