import json
import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda
from redis.exceptions import RedisError

from database import booking_for, connect, user_exists
from main import app

client = TestClient(app)
COMPLETE = {"patient_name": "Alex", "duration": "two days", "symptoms": ["itchy rash"],
            "specialty": "Dermatology", "urgency": "routine"}


class MemoryStore:
    """Redis interface used by tests; application code always uses real Redis."""
    def __init__(self):
        self.values = {}
        self.locks = {}

    def get(self, key):
        return self.values.get(key)

    def setex(self, key, ttl, value):
        self.values[key] = value

    def lock(self, key, **options):
        return self.locks.setdefault(key, threading.Lock())


def model_replies(*replies):
    iterator = iter(replies)
    return patch("llm.get_model", return_value=RunnableLambda(
        lambda prompt: AIMessage(content=json.dumps(next(iterator)))
    ))


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {"DATABASE_PATH": self.directory.name + "/clinic.db"})
        self.store = MemoryStore()
        self.redis = patch("config.get_redis", return_value=self.store)
        self.env.start()
        self.redis.start()

    def tearDown(self):
        self.redis.stop()
        self.env.stop()
        self.directory.cleanup()

    def start(self):
        response = client.post("/session")
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def headers(self, session):
        return {"Authorization": "Bearer " + session["token"]}

    def send(self, message, session):
        response = client.post("/chat", json={"message": message}, headers=self.headers(session))
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def offer(self, review=None):
        session = self.start()
        with model_replies(review or COMPLETE):
            offered = self.send("I have a mild itchy rash for two days.", session)
        return session, offered

    def test_session_token_and_database_user(self):
        session = self.start()
        self.assertTrue(user_exists(session["user_id"]))
        self.assertEqual(self.store.get("healthlink:session:" + session["token"]), session["user_id"])
        self.assertEqual(session["expires_in"], 86400)
        self.assertNotEqual(session["token"], session["user_id"])

    def test_missing_invalid_and_expired_token(self):
        self.assertEqual(client.post("/chat", json={"message": "hi"}).status_code, 401)
        self.assertEqual(client.get("/history", headers={"Authorization": "Bearer invalid"}).status_code, 401)
        session = self.start()
        del self.store.values["healthlink:session:" + session["token"]]
        self.assertEqual(client.get("/history", headers=self.headers(session)).status_code, 401)

    def test_follow_up_then_booking_and_repeated_confirmation(self):
        session = self.start()
        with model_replies({"symptoms": ["rash"], "specialty": "Dermatology"}):
            first = self.send("I have a rash.", session)
        self.assertEqual(first["phase"], "intake")
        self.assertIn("how long", first["reply"])
        self.assertNotIn("name", first["reply"])
        with model_replies(COMPLETE):
            offered = self.send("Two days, and my name is Alex.", session)
        self.assertEqual(offered["phase"], "selecting")
        self.assertTrue(offered["available_slots"])
        self.assertEqual(self.send("1", session)["phase"], "confirming")
        self.assertIsNone(booking_for(session["user_id"]))
        booked = self.send("yes", session)
        self.assertEqual(booked["phase"], "booked")
        self.assertEqual(booked["booking"]["patient_name"], "Alex")
        self.assertIn(booked["booking"]["booking_id"], booked["reply"])
        self.assertEqual(self.send("yes", session)["booking"], booked["booking"])
        self.assertEqual(booked["available_slots"], [])
        with connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM appointments").fetchone()[0], 1)

    def test_recommendations_do_not_require_name(self):
        session, offered = self.offer({**COMPLETE, "patient_name": None})
        self.assertEqual(offered["phase"], "selecting")
        self.assertIn("Dr.", self.send("Recommend me doctors", session)["reply"])
        self.assertEqual(self.send("1", session)["phase"], "name")
        self.assertEqual(self.send("Recommend me doctors", session)["phase"], "selecting")
        self.send("1", session)
        with model_replies({"patient_name": "Alex"}):
            self.assertEqual(self.send("Alex", session)["phase"], "confirming")
        self.assertIsNone(booking_for(session["user_id"]))
        self.assertEqual(self.send("yes", session)["booking"]["patient_name"], "Alex")

    def test_decline_and_slot_conflict(self):
        first, _ = self.offer()
        second, _ = self.offer()
        self.send("1", first)
        self.assertEqual(self.send("no", first)["phase"], "selecting")
        self.assertIsNone(booking_for(first["user_id"]))
        self.send("1", first)
        self.send("1", second)
        booked = self.send("yes", first)
        conflict = self.send("yes", second)
        self.assertEqual(conflict["phase"], "selecting")
        self.assertIn("just booked", conflict["reply"])
        self.assertIsNone(booking_for(second["user_id"]))
        taken = booked["booking"]
        self.assertFalse(any((s["doctor_id"], s["date"], s["time"]) ==
                             (taken["doctor_id"], taken["date"], taken["time"])
                             for s in conflict["available_slots"]))

    def test_history_isolated_and_raw_token_never_reaches_model(self):
        first, second = self.start(), self.start()
        prompts = []
        def respond(prompt):
            prompts.append(str(prompt))
            return AIMessage(content=json.dumps(COMPLETE))
        with patch("llm.get_model", return_value=RunnableLambda(respond)):
            self.send("I have an itchy rash for two days.", first)
        history = client.get("/history", headers=self.headers(first)).json()["messages"]
        self.assertEqual(len(history), 2)
        self.assertEqual(client.get("/history", headers=self.headers(second)).json()["messages"], [])
        self.assertNotIn(first["token"], "".join(prompts))
        response = client.post("/chat", headers=self.headers(second),
                               json={"message": "hi", "user_id": first["user_id"]})
        self.assertEqual(response.status_code, 422)

    def test_booking_recovered_when_history_save_fails(self):
        session, _ = self.offer()
        self.send("1", session)
        with patch("main.save_history", side_effect=RedisError("unavailable")):
            response = client.post("/chat", json={"message": "yes"}, headers=self.headers(session))
        self.assertEqual(response.status_code, 503)
        saved = booking_for(session["user_id"])
        self.assertIsNotNone(saved)
        recovered = self.send("yes", session)
        self.assertEqual(recovered["booking"]["booking_id"], saved["booking_id"])

    def test_urgent_concern_and_natural_language_slot(self):
        session, response = self.offer({**COMPLETE, "urgency": "emergency"})
        self.assertEqual(response["phase"], "urgent")
        self.assertEqual(response["available_slots"], [])
        session, _ = self.offer()
        with model_replies({"slot_number": 2}):
            self.assertEqual(self.send("The second one works.", session)["phase"], "confirming")

    def test_redis_unavailable_and_public_health(self):
        with patch("config.get_redis", side_effect=RedisError("private-details")):
            self.assertEqual(client.post("/session").status_code, 503)
            self.assertEqual(client.get("/health").status_code, 200)
        doctors = client.get("/doctors?specialty=cardiology").json()
        self.assertEqual(len(doctors), 2)


if __name__ == "__main__":
    unittest.main()
