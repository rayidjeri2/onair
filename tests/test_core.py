import pytest

from onair.core import Echeancier, Repartiteur


def test_evenements_dans_lordre_chronologique():
    e = Echeancier()
    e.planifier(10, "b")
    e.planifier(5, "a")
    e.planifier(10, "c")  # même date que "b" : ordre d'insertion conservé
    assert [ev.type for ev in e.derouler(20)] == ["a", "b", "c"]
    assert e.horloge == 20


def test_planifier_dans_le_passe_est_refuse():
    e = Echeancier()
    e.planifier(10, "a")
    list(e.derouler(10))
    with pytest.raises(ValueError):
        e.planifier(5, "b")


def test_derouler_sarrete_a_la_borne():
    e = Echeancier()
    for t in (1, 2, 30):
        e.planifier(t, "x")
    assert len(list(e.derouler(5))) == 2
    assert len(e) == 1


def test_repartiteur_sans_gestionnaire():
    r = Repartiteur()
    e = Echeancier()
    with pytest.raises(KeyError):
        r.traiter(e.planifier(0, "inconnu"))
