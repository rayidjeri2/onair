import random

import pytest

from societe import metiers, moteur, savoirs
from societe.catalogue import MODELES, disponibles
from societe.modele import Etat


def village(personnes=8, graine=4, avec_eau=True):
    """Un village de test, doté d'eau pour qu'on puisse étudier autre chose."""
    e = moteur.creer_societe("Abeba", 28, graine=graine)
    moteur.faire_venir(e, personnes)
    if avec_eau:
        # de l'eau et un toit pour tous : on veut étudier la technique,
        # pas refaire chaque fois la bataille de la survie
        e.batiments["source"] = 1
        e.batiments["puits"] = 2
        e.batiments["maison_terre"] = 6
        e.batiments["cave"] = 1
    return e


# --- découvertes ----------------------------------------------------------

def test_catalogue_des_savoirs_coherent():
    for s in savoirs.SAVOIRS.values():
        assert s.age in savoirs.AGES
        assert s.cout > 0 and s.sources and s.description
        for p in s.prerequis:
            assert p in savoirs.SAVOIRS, s.cle
        for b in s.batiments:
            assert b in MODELES, b


def test_un_savoir_s_acquiert_en_pratiquant():
    e = village(10)
    for p in e.personnes:
        if not p.enfant:
            moteur.affecter(e, p.id, "nourriture")
    moteur.avancer(e, 400)
    assert "agronomie" in e.decouvertes
    assert e.savoirs.get("agronomie") is None  # les points sont consommés


def test_la_recherche_accelere_les_decouvertes():
    def points(tache):
        e = village(10, graine=9)
        for p in e.personnes:
            if not p.enfant:
                moteur.affecter(e, p.id, tache)
        moteur.avancer(e, 120)
        return len(e.decouvertes) * 1000 + sum(e.savoirs.values())

    assert points("recherche") > points("repos")


def test_les_prerequis_bloquent():
    e = village(20)
    assert not savoirs._accessible(e, savoirs.SAVOIRS["metallurgie"])
    e.decouvertes += ["vannerie", "poterie"]
    assert savoirs._accessible(e, savoirs.SAVOIRS["metallurgie"])


def test_un_savoir_exige_une_societe_assez_grande():
    petit = village(2)
    grand = village(30)
    vapeur = savoirs.SAVOIRS["vapeur"]
    petit.decouvertes += vapeur.prerequis
    grand.decouvertes += vapeur.prerequis
    assert not savoirs._accessible(petit, vapeur)
    assert savoirs._accessible(grand, vapeur)


def test_un_savoir_se_perd_si_plus_personne_ne_le_pratique():
    e = village(3)
    e.decouvertes.append("agronomie")
    for p in e.personnes:
        p.competences["agriculture"] = 0.0
    alea = random.Random(0)
    for _ in range(3000):
        savoirs._oublier(e, alea)
        if "agronomie" not in e.decouvertes:
            break
    assert "agronomie" not in e.decouvertes


def test_l_ecrit_protege_de_l_oubli():
    e = village(3)
    e.decouvertes += ["agronomie", "ecriture"]
    e.batiments["archives"] = 1
    assert e.memoire_ecrite
    for p in e.personnes:
        p.competences["agriculture"] = 0.0
    alea = random.Random(0)
    for _ in range(3000):
        savoirs._oublier(e, alea)
    assert "agronomie" in e.decouvertes


def test_une_decouverte_ouvre_des_chantiers():
    e = village(12)
    fermes = {c["cle"] for c in disponibles(e)}
    assert "charrue" not in fermes
    e.decouvertes.append("metallurgie")
    e.batiments["forge"] = 1
    ouverts = {c["cle"] for c in disponibles(e)}
    assert "charrue" in ouverts and "haut_fourneau" in ouverts


# --- outillage ------------------------------------------------------------

def test_l_outillage_multiplie_la_productivite():
    e = village(6)
    base = moteur.multiplicateur(e, "rendement_agricole")
    e.decouvertes.append("agronomie")
    apres_savoir = moteur.multiplicateur(e, "rendement_agricole")
    e.batiments["charrue"] = 1
    apres_outil = moteur.multiplicateur(e, "rendement_agricole")
    assert base == 1.0 < apres_savoir < apres_outil


def test_la_charrue_augmente_vraiment_les_recoltes():
    def recolte(avec_charrue):
        e = village(6, graine=15)
        e.stocks["nourriture"] = 0
        if avec_charrue:
            e.batiments["charrue"] = 2
        for p in e.personnes:
            if not p.enfant:
                moteur.affecter(e, p.id, "nourriture")
        moteur.avancer(e, 30)
        return e.stocks["nourriture"]

    assert recolte(True) > recolte(False) * 1.15


# --- métiers --------------------------------------------------------------

def test_un_metier_exige_son_atelier():
    e = village(9)
    with pytest.raises(ValueError, match="atelier"):
        metiers.attribuer(e, e.personnes[0].id, "charpentier")
    e.batiments["atelier"] = 1
    metiers.attribuer(e, e.personnes[0].id, "charpentier")
    assert e.personnes[0].metier == "charpentier"


def test_le_nombre_de_metiers_est_borne_par_le_surplus():
    e = village(6)          # 7 personnes, dont quelques enfants
    e.batiments["atelier"] = 1
    adultes = [p for p in e.personnes if not p.enfant]
    places = metiers.places(e)
    for p in adultes[:places]:
        metiers.attribuer(e, p.id, "carrier" if p is not adultes[0] else "charpentier")
    with pytest.raises(ValueError, match="entretenir"):
        metiers.attribuer(e, adultes[places].id, "carrier")


def test_un_metier_rend_bien_meilleur_sur_sa_tache():
    e = village(9)
    e.batiments["atelier"] = 1
    p = e.personnes[0]
    avant = p.efficacite("construction")
    metiers.attribuer(e, p.id, "charpentier")
    assert p.efficacite("construction") == pytest.approx(avant * 1.8)
    assert p.efficacite("nourriture") == pytest.approx(
        p.niveau_effectif("nourriture") * 1.3 + 0.35, abs=0.3)


def test_un_metier_fixe_la_tache():
    e = village(9)
    e.batiments["atelier"] = 1
    p = e.personnes[0]
    metiers.attribuer(e, p.id, "charpentier")
    assert p.tache == "construction"
    with pytest.raises(ValueError, match="métier"):
        moteur.affecter(e, p.id, "bois")
    metiers.attribuer(e, p.id, None)
    moteur.affecter(e, p.id, "bois")


def test_un_metier_verrouille_par_un_savoir():
    e = village(12)
    e.batiments["forge"] = 1
    assert "forgeron" not in metiers.possibles(e)
    e.decouvertes.append("metallurgie")
    assert "forgeron" in metiers.possibles(e)


# --- chantiers simultanés -------------------------------------------------

def test_l_intendance_mene_plusieurs_chantiers():
    e = village(10)
    moteur.regler_intendance(e, True)
    moteur.avancer(e, 400)
    assert len(e.batiments) > 5


def test_annuler_un_chantier_nomme():
    e = village(8)
    moteur.lancer_chantier(e, "defrichage")
    moteur.lancer_chantier(e, "potager")
    moteur.annuler_chantier(e, "defrichage")
    assert [c.cle for c in e.chantiers] == ["potager"]


# --- sérialisation --------------------------------------------------------

def test_savoirs_et_metiers_survivent_a_la_sauvegarde():
    e = village(10)
    e.batiments["atelier"] = 1
    e.decouvertes.append("charpente")
    e.savoirs["agronomie"] = 120.0
    metiers.attribuer(e, e.personnes[0].id, "charpentier")
    moteur.lancer_chantier(e, "potager")
    copie = Etat.depuis_dict(e.vers_dict())
    assert copie.decouvertes == e.decouvertes
    assert copie.savoirs == e.savoirs
    assert copie.personne(e.personnes[0].id).metier == "charpentier"
    assert [c.cle for c in copie.chantiers] == ["potager"]
