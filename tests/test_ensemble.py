from lava.candidates import Candidate
from lava.ensemble import MedianEnsemble


def test_median_v2g_and_traceability():
    ensemble = MedianEnsemble(min_confidence=0.3, max_divergence=1.0)
    decision = ensemble.combine_v2g(
        [
            Candidate("v2g", None, 0, 0.8, "rules", "no stress"),
            Candidate("v2g", None, 80, 0.7, "optimizer", "stress"),
            Candidate("v2g", None, 30, 0.9, "constraints", "safe"),
        ]
    )
    assert decision["value_kw"] == 30
    assert len(decision["trace"]) == 3
