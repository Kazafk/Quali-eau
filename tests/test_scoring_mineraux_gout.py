from pipeline.scoring import (
    score_nitrates_mineraux,
    score_chlorures,
    score_sulfates,
    score_mineraux,
    score_chlore_gout,
    score_turbidite,
    score_gout,
)


def test_nitrates_mineraux_bandes():
    assert score_nitrates_mineraux(5.0) == 100.0
    assert score_nitrates_mineraux(15.0) == 85.0
    assert score_nitrates_mineraux(30.0) == 65.0
    assert score_nitrates_mineraux(45.0) == 40.0
    assert score_nitrates_mineraux(60.0) == 0.0


def test_chlorures_bandes():
    assert score_chlorures(50.0) == 100.0
    assert abs(score_chlorures(150.0) - 70.0) < 1e-9  # milieu 100-200 -> 100-60*0.5=70
    assert abs(score_chlorures(400.0) - 20.0) < 1e-9  # 40*200/400=20


def test_sulfates_bandes():
    assert score_sulfates(100.0) == 100.0
    assert abs(score_sulfates(200.0) - 70.0) < 1e-9  # milieu 150-250 -> 70
    assert abs(score_sulfates(500.0) - 20.0) < 1e-9  # 40*250/500=20


def test_mineraux_ponderation():
    # nitrates=100 (0.70), chlorures=100 (0.15), sulfates=100 (0.15) -> 100
    assert abs(score_mineraux(nitrates=5.0, chlorures=50.0, sulfates=100.0) - 100.0) < 1e-9
    # nitrates=0 (60mg/L), chlorures=100, sulfates=100 -> 0.70*0+0.15*100+0.15*100=30
    assert abs(score_mineraux(nitrates=60.0, chlorures=50.0, sulfates=50.0) - 30.0) < 1e-9


def test_chlore_gout_bandes():
    assert score_chlore_gout(0.03) == 100.0
    assert score_chlore_gout(0.10) == 80.0
    assert score_chlore_gout(0.20) == 50.0
    assert score_chlore_gout(0.40) == 20.0


def test_turbidite_bandes():
    assert score_turbidite(0.1) == 100.0
    assert score_turbidite(0.5) == 80.0
    assert score_turbidite(1.5) == 55.0
    assert score_turbidite(3.0) == 30.0


def test_gout_ponderation():
    # chlore=100 (0.60), turbidite=100 (0.40) -> 100
    assert abs(score_gout(chlore=0.03, turbidite=0.1) - 100.0) < 1e-9
    # chlore=20 (0.60), turbidite=30 (0.40) -> 0.6*20+0.4*30=12+12=24
    assert abs(score_gout(chlore=0.40, turbidite=3.0) - 24.0) < 1e-9
