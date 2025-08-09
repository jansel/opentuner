import random

import opentuner
from opentuner import MeasurementInterface
from opentuner import Result
from opentuner.search.manipulator import ConfigurationManipulator, IntegerParameter
from opentuner.search.objective import MaximizeAttribute


class CustomMetricExample(MeasurementInterface):
    def manipulator(self):
        m = ConfigurationManipulator()
        m.add_parameter(IntegerParameter('threads', 1, 8))
        return m

    def objective(self):
        return MaximizeAttribute('qps', missing_value=float('-inf'))

    def compile_and_run(self, desired_result, input, limit):
        cfg = desired_result.configuration.data
        threads = cfg['threads']
        # Synthetic: qps grows with threads but has diminishing returns and noise
        base_qps = 1000.0 * (1 - 0.1 / max(1, threads))
        noise = random.uniform(-10, 10)
        qps = base_qps + noise
        time = 1.0 / max(1, qps)  # smaller time for higher qps, just for demo
        return Result(time=time).update_attributes({'qps': qps, 'threads': threads})


if __name__ == '__main__':
    argparser = opentuner.default_argparser()
    CustomMetricExample.main(argparser.parse_args()) 