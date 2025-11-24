import random
import time

from locust import HttpUser, between, task


class ChatUser(HttpUser):
    wait_time = between(5, 20)

    @task
    def ask_question(self) -> None:
        self.client.get("/")
        time.sleep(5)
        self.client.post(
            "/chat",
            json={
                "messages": [
                    {
                        "content": random.choice(
                            ["Che informazioni posso avere?", "Chi sei?"]
                        ),
                        "role": "user",
                    }
                ],
                "context": {
                    "overrides": {
                        "use_advanced_flow": True,
                        "top": 3,
                        "retrieval_mode": "hybrid",
                        "temperature": 0.3,
                    }
                },
            },
        )
        time.sleep(5)
        self.client.post(
            "/chat",
            json={
                "messages": [
                    {"content": "Chi sei?", "role": "user"},
                    {
                        "content": "Sono un assistenze virtuale, chiedimi informazioni su procedure o documenti.",
                        "role": "assistant",
                    },
                    {"content": "grazie.", "role": "user"},
                ],
                "context": {
                    "overrides": {
                        "use_advanced_flow": True,
                        "top": 3,
                        "retrieval_mode": "hybrid",
                        "temperature": 0.3,
                    }
                },
            },
        )
