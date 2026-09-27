"""
locustfile.py — Stress test for Village Pond Planning System.
Run on machine 2207.

Install: pip install locust
Headless: locust -f locustfile.py --host http://MACHINE_2208_IP:5000 --headless -u 20 -r 5 --run-time 2m
With UI:  locust -f locustfile.py --host http://MACHINE_2208_IP:5000 --web-port 4000

External access: machine 2207 port 4000 → wifi port 4207
"""

import json
import random
from locust import HttpUser, task, between

# Chhattisgarh bounding boxes for testing — small enough to be fast
TEST_BBOXES = [
    {"min_lat": 21.20, "max_lat": 21.35, "min_lon": 81.55, "max_lon": 81.70},  # Raipur area
    {"min_lat": 21.10, "max_lat": 21.20, "min_lon": 81.60, "max_lon": 81.75},
    {"min_lat": 21.30, "max_lat": 21.40, "min_lon": 81.50, "max_lon": 81.60},
]


class PondUser(HttpUser):
    """Simulates a user visiting the app and running analysis."""
    wait_time = between(2, 8)  # realistic user think time

    @task(5)
    def load_homepage(self):
        """Most users just load the page."""
        self.client.get("/app/")

    @task(3)
    def health_check(self):
        """Health endpoint — lightweight."""
        self.client.get("/health")

    @task(1)
    def run_analysis(self):
        """Heavy: triggers SRTM load + pysheds analysis."""
        bbox = random.choice(TEST_BBOXES)
        payload = {
            "area": {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [[
                        [bbox["min_lon"], bbox["min_lat"]],
                        [bbox["max_lon"], bbox["min_lat"]],
                        [bbox["max_lon"], bbox["max_lat"]],
                        [bbox["min_lon"], bbox["max_lat"]],
                        [bbox["min_lon"], bbox["min_lat"]],
                    ]]
                }
            }
        }
        with self.client.post(
            "/api/analyze-area",
            json=payload,
            timeout=120,
            catch_response=True
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") == "success":
                    resp.success()
                else:
                    resp.failure(f"status={data.get('status')}")
            elif resp.status_code == 503:
                resp.failure("server busy / OOM")
            else:
                resp.failure(f"HTTP {resp.status_code}")
