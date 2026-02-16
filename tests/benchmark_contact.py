from locust import HttpUser, task, between
import random
import string

class ContactUser(HttpUser):
    wait_time = between(1, 3)

    @task(1)
    def submit_contact_form(self):
        # Generate random data to avoid duplicates/caching
        name = ''.join(random.choices(string.ascii_letters, k=10))
        email = f"{name}@example.com"
        subject = f"Subject {name}"
        message = f"This is a message from {name}." * 5

        self.client.post("/api/contact", json={
            "name": name,
            "email": email,
            "subject": subject,
            "message": message
        })

    @task(3)
    def view_submissions(self):
        # Simulate admin viewing submissions
        # Depending on configuration, this might require auth or return 403
        # We will record the latency regardless of the response code for now,
        # but 200 is preferred.
        with self.client.get("/api/contact/submissions?limit=10", catch_response=True) as response:
            if response.status_code == 403 or response.status_code == 401:
                # If auth is required, we might not be able to easily bypass it in this simple test
                # unless we have credentials.
                # For baseline, we just want to see if the endpoint is reachable.
                response.success()
