import time
import json
import os
from datetime import datetime

class PipelineMonitor:
    """Tracks performance metrics for the ShortsForge pipeline."""
    def __init__(self):
        self.log_file = "data/metrics/performance_log.json"
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        self.current_run = {}
        self.run_start = 0
        self.stage_start = 0
        self.current_stage = None

    def start_run(self, input_title):
        self.run_start = time.time()
        self.current_run = {
            "timestamp": datetime.now().isoformat(),
            "input_title": input_title,
            "stages": {},
            "total_time_seconds": 0
        }

    def start_stage(self, stage_name):
        self.current_stage = stage_name
        self.stage_start = time.time()

    def end_stage(self):
        if self.current_stage:
            duration = time.time() - self.stage_start
            self.current_run["stages"][self.current_stage] = round(duration, 2)
            self.current_stage = None

    def end_run(self, output_summary):
        self.current_run["output_summary"] = output_summary
        self.current_run["total_time_seconds"] = round(time.time() - self.run_start, 2)
        self._export()

    def _export(self):
        data = []
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    data = json.load(f)
            except json.JSONDecodeError:
                pass
                
        data.append(self.current_run)
        
        with open(self.log_file, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"\n[METRICS] Performance metrics exported to {self.log_file}")
