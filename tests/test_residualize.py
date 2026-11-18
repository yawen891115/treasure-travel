import numpy as np

from src.residualize import mean_correlation, residualize_on_popularity


def test_residual_has_no_popularity_left():
    rng = np.random.default_rng(0)
    log_pop = rng.normal(size=200)
    taste = rng.normal(size=(50, 200))
    scores = 2.0 * log_pop[None, :] + taste  # every user's scores lean toward popular places
    assert mean_correlation(scores, log_pop) > 0.8
    resid, slope = residualize_on_popularity(scores, log_pop)
    assert abs(mean_correlation(resid, log_pop)) < 1e-6
    assert np.allclose(slope, 2.0, atol=0.4)  # it found the popularity lean


def test_worked_example_from_the_guide():
    x = np.array([0, 1, 2, 3, 4.0])
    s = np.array([[0.5, 1.4, 1.6, 2.9, 3.1]])
    resid, slope = residualize_on_popularity(s, x)
    assert abs(slope[0] - 0.67) < 1e-6
    assert np.allclose(resid[0], [-0.06, 0.17, -0.30, 0.33, -0.14], atol=1e-6)


def test_constant_popularity_is_centered_without_nan():
    scores = np.array([[1.0, 2.0, 3.0], [4.0, 4.0, 4.0]])
    resid, slope = residualize_on_popularity(scores, np.ones(3))
    assert np.isfinite(resid).all()
    assert np.allclose(slope, 0)
    assert np.allclose(resid, [[-1, 0, 1], [0, 0, 0]])
