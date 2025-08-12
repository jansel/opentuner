import math

from opentuner.resultsdb.models import Result, Configuration, Program
from opentuner.search.objective import MaximizeAttribute, MinimizeAttribute


def test_result_extra_persistence(tmp_path, Session=None):
    # Create a couple of Results and ensure extra dict persists values
    r1 = Result(time=1.0)
    r1.set_attribute('qps', 100.0)
    assert r1.get_attribute('qps') == 100.0
    r1.update_attributes({'latency_ms': 10.0})
    assert r1.get_attribute('latency_ms') == 10.0


def test_objective_with_custom_metric_compare():
    # Two results with only extra metric
    r1 = Result(time=2.0).update_attributes({'qps': 100.0})
    r2 = Result(time=2.0).update_attributes({'qps': 120.0})

    max_qps = MaximizeAttribute('qps', missing_value=float('-inf'))
    max_qps.set_driver(type('D', (), {})())  # minimal driver stub
    assert max_qps.result_compare(r2, r1) < 0  # r2 better than r1

    min_lat = MinimizeAttribute('latency_ms', missing_value=float('inf'))
    min_lat.set_driver(type('D', (), {})())
    r3 = Result(time=1.0).update_attributes({'latency_ms': 5.0})
    r4 = Result(time=1.0).update_attributes({'latency_ms': 10.0})
    assert min_lat.result_compare(r3, r4) < 0  # r3 better (lower latency) 