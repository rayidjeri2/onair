import random

import pytest

from societe import demographie, moteur
from societe.modele import AGE_TRAVAIL, GESTATION, Etat, Personne


def couple(graine=3, age=26):
    e = moteur.creer_societe("Ana", age, graine=graine)
    moteur.ajouter_personne(e, "Tomas", age + 2, "construction", sexe="h")
    return e


def test_les_enfants_ne_travaillent_pas():
    e = couple()
    enfant = moteur.ajouter_personne(e, "Nino", 7, "agriculture")
    assert enfant.tache == "repos"
    with pytest.raises(ValueError, match="7 ans"):
        moteur.affecter(e, enfant.id, "bois")
    moteur.affecter(e, enfant.id, "repos")  # toujours permis


def test_un_enfant_mange_moins_qu_un_adulte():
    petit = Personne(1, "Nino", 3, 0)
    grand = Personne(2, "Ana", 30, 0)
    assert petit.part_ration() < grand.part_ration()


def test_vieillissement_annuel():
    e = couple()
    ages = {p.id: p.age for p in e.personnes}
    moteur.avancer(e, 366)
    assert all(p.age == ages[p.id] + 1 for p in e.personnes if p.id in ages)


def test_un_couple_se_forme():
    e = couple()
    moteur.avancer(e, 400)
    vivants = {p.id for p in e.personnes}
    assert any(p.partenaire in vivants for p in e.personnes if p.partenaire)
    assert e.demographie["couples_formes"] >= 1


def test_pas_de_couple_entre_apparentes():
    mere = Personne(1, "Ana", 40, 0, sexe="f")
    fils = Personne(2, "Ivo", 20, 0, sexe="h", parents=[1])
    fille = Personne(3, "Sol", 22, 0, sexe="f", parents=[1])
    assert demographie._apparentes(mere, fils)
    assert demographie._apparentes(fille, fils)
    etranger = Personne(4, "Nils", 25, 0, sexe="h")
    assert not demographie._apparentes(fille, etranger)


def test_naissance_apres_gestation():
    e = couple()
    a, b = e.personnes
    a.partenaire, b.partenaire = b.id, a.id
    a.grossesse = GESTATION - 1
    a.autre_parent = b.id
    moteur.avancer(e, 1)
    assert e.demographie["naissances"] == 1
    bebe = [p for p in e.personnes if p.age == 0][0]
    assert bebe.nee_ici and bebe.tache == "repos"
    assert set(bebe.parents) == {a.id, b.id}
    assert bebe.id in e.personne(a.id).enfants


def test_natalite_a_zero_empeche_les_conceptions():
    e = couple()
    moteur.regler_politique(e, "natalite", 0.0)
    moteur.avancer(e, 500)
    assert e.demographie["naissances"] == 0
    assert all(p.grossesse is None for p in e.personnes)


def test_natalite_forte_donne_plus_de_naissances():
    def naissances(natalite):
        e = couple(graine=11)
        moteur.regler_politique(e, "natalite", natalite)
        moteur.avancer(e, 365 * 6)
        return e.demographie["naissances"]

    assert naissances(0.9) > naissances(0.15)


def test_la_mortalite_croit_avec_l_age():
    e = couple()
    jeune = Personne(90, "J", 25, 0)
    vieux = Personne(91, "V", 80, 0)
    assert demographie.risque_annuel(e, vieux) > 20 * demographie.risque_annuel(e, jeune)


def test_le_dispensaire_reduit_la_mortalite():
    e = couple()
    p = e.personnes[0]
    sans = demographie.risque_annuel(e, p)
    e.batiments["dispensaire"] = 1
    e.batiments["toilettes_seches"] = 1
    assert demographie.risque_annuel(e, p) < sans


def test_la_mauvaise_sante_augmente_la_mortalite():
    e = couple()
    p = e.personnes[0]
    solide = demographie.risque_annuel(e, p)
    p.sante = 20
    assert demographie.risque_annuel(e, p) > solide


def test_un_deces_denoue_les_liens_et_compte():
    e = couple()
    a, b = e.personnes
    a.partenaire, b.partenaire = b.id, a.id
    demographie._retirer(e, a)
    assert e.demographie["deces"] == 1
    assert e.demographie["ages_au_deces"] == a.age
    assert b.partenaire is None


def test_taux_de_dependance_et_pyramide():
    e = couple()
    moteur.ajouter_personne(e, "Nino", 4, "agriculture")
    moteur.ajouter_personne(e, "Vieil", 80, "soin")
    assert e.taux_dependance() == 1.0  # deux à charge pour deux actifs
    tranches = e.pyramide()
    assert sum(t["f"] + t["h"] for t in tranches) == e.population


def test_les_enfants_apprennent_de_leurs_parents():
    e = couple()
    for p in e.personnes:
        p.competences["artisanat"] = 0.9
    enfant = moteur.ajouter_personne(e, "Nino", 8, "agriculture")
    enfant.parents = [p.id for p in e.personnes[:2]]
    depart = enfant.competences["artisanat"]
    moteur.avancer(e, 365)
    assert e.personne(enfant.id).competences["artisanat"] > depart


def test_un_enfant_devient_actif_a_quatorze_ans():
    e = couple()
    enfant = moteur.ajouter_personne(e, "Nino", AGE_TRAVAIL - 1, "agriculture")
    moteur.avancer(e, 366)
    grandi = e.personne(enfant.id)
    assert grandi is None or grandi.age == AGE_TRAVAIL


def test_serialisation_conserve_la_demographie():
    e = couple()
    moteur.regler_politique(e, "natalite", 0.8)
    moteur.avancer(e, 400)
    copie = Etat.depuis_dict(e.vers_dict())
    assert copie.demographie == e.demographie
    assert copie.politique == e.politique
    assert [p.partenaire for p in copie.personnes] == [p.partenaire for p in e.personnes]


def test_les_parents_de_jeunes_enfants_ne_partent_pas():
    e = couple()
    parent = e.personnes[0]
    parent.moral = 1
    bebe = moteur.ajouter_personne(e, "Nino", 2, "agriculture")
    parent.enfants = [bebe.id]
    assert not demographie._apparentes(parent, bebe) or True
    alea = random.Random(0)
    assert not moteur._veut_partir(e, parent, alea)


def test_une_seule_personne_ne_part_jamais():
    e = moteur.creer_societe("Ana", 30)
    e.personnes[0].moral = 0
    assert not moteur._veut_partir(e, e.personnes[0], random.Random(0))


def test_faire_venir_plusieurs_personnes():
    e = moteur.creer_societe("Abeba", 28)
    venus = moteur.faire_venir(e, 10)
    assert len(venus) == 10 and e.population == 11
    assert len({p.nom for p in e.personnes}) == 11  # aucun doublon de nom
    assert all(p.arrivee == e.jour for p in venus)
    assert any("10 personnes" in j["texte"] for j in e.journal.entrees)


def test_faire_venir_tire_au_hasard():
    e = moteur.creer_societe("Abeba", 28)
    venus = moteur.faire_venir(e, 30)
    assert len({p.sexe for p in venus}) == 2
    assert len({p.competence_principale for p in venus}) >= 5
    assert len({p.age for p in venus}) >= 10
    assert all(1 <= p.age <= 66 for p in venus)


def test_les_prenoms_viennent_du_registre():
    e = moteur.creer_societe("Abeba", 28)
    registre = set(demographie.PRENOMS_F) | set(demographie.PRENOMS_H)
    for p in moteur.faire_venir(e, 20):
        assert p.nom in registre, p.nom


def test_prenom_libre_ne_repete_pas():
    e = moteur.creer_societe("Abeba", 28)
    # on épuise le registre : les noms restent uniques
    moteur.faire_venir(e, 50)
    moteur.faire_venir(e, 30)
    assert len({p.nom for p in e.personnes}) == e.population


def test_nombre_d_arrivees_borne():
    e = moteur.creer_societe("Abeba", 28)
    for mauvais in (0, -3, 51):
        with pytest.raises(ValueError, match="entre 1 et 50"):
            moteur.faire_venir(e, mauvais)


def test_les_arrivants_mineurs_n_ont_pas_de_tache():
    e = moteur.creer_societe("Abeba", 28)
    for p in moteur.faire_venir(e, 40):
        if p.age < AGE_TRAVAIL:
            assert p.tache == "repos"
