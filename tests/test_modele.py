import pytest

from onair.modele import Animateur, Creneau, Emission, Grille

ANIM = Animateur("Test", 0.5)


def emission(**kw):
    base = dict(nom="E", genre="musique", qualite=0.5, animateur=ANIM)
    return Emission(**{**base, **kw})


def test_charge_pub():
    assert emission(pubs_par_heure=2, duree_pub=3.0).charge_pub == pytest.approx(0.1)


def test_parametres_invalides():
    with pytest.raises(ValueError):
        emission(genre="podcast")
    with pytest.raises(ValueError):
        emission(qualite=1.5)
    with pytest.raises(ValueError):
        Creneau("lundi", 25.0, 1.0, emission())


def test_grille_detecte_chevauchement_et_trou():
    g = Grille()
    g.ajouter(Creneau("lundi", 6.0, 2.0, emission(nom="A")))
    g.ajouter(Creneau("lundi", 7.0, 1.0, emission(nom="B")))
    g.ajouter(Creneau("lundi", 12.0, 1.0, emission(nom="C")))
    anomalies = g.verifier()
    assert any("chevauche" in a for a in anomalies)
    assert any("trou" in a for a in anomalies)


def test_creneau_tous_les_jours():
    c = Creneau("*", 0.0, 1.0, emission())
    assert len(c.jours()) == 7
