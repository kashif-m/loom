from __future__ import annotations

from locust import HttpUser, between, task


class LoomUser(HttpUser):
    wait_time = between(1, 3)

    @task
    def ff_request(self):
        self.client.post(
            "/ingress/ff",
            json={"request": "enhance these docs https://example.com", "domain_pack": "docs"},
        )
