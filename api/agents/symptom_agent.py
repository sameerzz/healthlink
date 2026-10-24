from llm import generate
from schemas import IntakeReview
import json
import re


def chat_symptom_agent(state):
    review = generate(
        "Review this conversation for a fictional clinic appointment. Extract only "
        "the patient's explicitly provided name, reported symptoms, and duration. "
        "Leave missing name/duration null and symptoms empty; never invent them. "
        "Choose an available specialty and assess urgency conservatively. "
        "Ask one brief follow-up when information is missing. Do not diagnose or prescribe.",
        json.dumps({"conversation": state["messages"][-30:],
                    "known_details": state.get("intake")}), IntakeReview,
    )
    updates = {"intake": review.model_dump()}
    if review.urgency != "routine":
        return {**updates, "phase": "urgent", "available_slots": [],
                "reply": "Your symptoms may need prompt professional attention. Please seek urgent medical care; do not wait for a routine appointment in this demo."}
    missing = []
    if not review.symptoms:
        missing.append("what symptoms you're experiencing")
    wants_doctors = bool(re.search(r"\b(doctors?|recommend|appointments?|book)\b", state["messages"][-1]["content"], re.I))
    if not review.duration or not review.duration.strip():
        missing.append("how long you've had them")
    # Browsing doctors never requires a booking name or a completed intake form.
    if missing and not wants_doctors:
        return {**updates, "phase": "intake",
                "reply": "Could you tell me " + ", and ".join(missing) + "?"}
    return {**updates, "phase": "selecting"}
