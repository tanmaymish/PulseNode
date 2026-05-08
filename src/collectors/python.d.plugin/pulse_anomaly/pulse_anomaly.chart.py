# -*- coding: utf-8 -*-
# Description: PulseNode Custom Anomaly Score Calculator
# This is a custom module built for the PulseNode engine to demonstrate ML/Anomaly scoring telemetry.

import random
from bases.FrameworkServices.SimpleService import SimpleService

# default module values
update_every = 1
priority = 90000
retries = 60

ORDER = ['anomaly_score']

CHARTS = {
    'anomaly_score': {
        'options': [None, 'PulseNode System Anomaly Score', 'score', 'PulseNode Security', 'pulsenode.anomaly', 'line'],
        'lines': [
            ['threat_level', 'Threat Level', 'absolute']
        ]
    }
}

class Service(SimpleService):
    def __init__(self, configuration=None, name=None):
        SimpleService.__init__(self, configuration=configuration, name=name)
        self.order = ORDER
        self.definitions = CHARTS
        self.base_score = 10

    def check(self):
        return True

    def get_data(self):
        # Simulate an anomaly detection heuristic score
        # In a real environment, this might read from eBPF or a local ML model inference engine
        fluctuation = random.randint(-5, 15)
        self.base_score = max(0, min(100, self.base_score + fluctuation))
        
        data = dict()
        data['threat_level'] = self.base_score
        return data
