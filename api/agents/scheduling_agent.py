import json
import re

from tools import SlotTaken, reserve_appointment
from llm import generate
from schemas import Doctor, PatientDetails, SlotChoice
from tools import available_slots


def offer_slots(state, introduction="Here are available appointments in the demo clinic:"):
    slots = available_slots([Doctor.model_validate(doctor) for doctor in state["doctors"]])
    if not slots:
        return {"phase": "selecting", "available_slots": [], "selected_slot": None,
                "reply": "There are no appointments available in the next five weekdays. Start a new chat to search again later."}
    lines = [f"{i}. {slot['doctor_name']} — {slot['date']} at {slot['time']}"
             for i, slot in enumerate(slots, 1)]
    doctors = "\n\n".join(f"{doctor['name']} — {doctor['specialty']}, {doctor['location']}" for doctor in state["doctors"])
    return {"phase": "selecting", "available_slots": slots, "selected_slot": None,
            "reply": "Suggested doctors:\n\n" + doctors + "\n\n" + introduction + "\n\n" + "\n\n".join(lines) + "\n\nYou can browse without giving a name. If you'd like to book, choose an option. Nothing is booked yet."}


def ask_confirmation(slot, name):
    return {"phase": "confirming", "selected_slot": slot,
            "reply": f"Book {slot['doctor_name']} on {slot['date']} at {slot['time']} for {name}? Reply 'yes' to confirm or 'no' to choose again."}


def chat_scheduling_agent(state):
    text = state["messages"][-1]["content"].strip().lower().rstrip(".!?")
    if re.search(r"\b(recommend|show|list|find)\b.*\bdoctors?\b", text) or text in {"doctors", "doctor recommendations"}:
        return offer_slots(state)
    if state["phase"] == "name":
        if text in {"no", "cancel", "no thanks", "change", "change slot"}:
            return offer_slots(state, "No booking made. You can browse or choose another slot:")
        details = generate(
            "Extract the patient's name only if the latest message supplies one. "
            "A bare name is valid because we just asked for it. Questions, refusals, "
            "doctor requests, and appointment preferences are not names; return null for them.",
            state["messages"][-1]["content"], PatientDetails,
        )
        if not details.patient_name or not details.patient_name.strip():
            return {"reply": "You can browse doctors without a name. To book the selected slot, what patient name should I use? Or say 'cancel' to keep browsing."}
        name = details.patient_name.strip()
        return {**ask_confirmation(state["selected_slot"], name),
                "intake": {**state["intake"], "patient_name": name}}
    if state["phase"] == "confirming":
        if text in {"yes", "yes please", "confirm", "confirm booking", "book it", "yes book it", "yes confirm", "go ahead"}:
            try:
                booking = reserve_appointment(state["user_id"], state["intake"]["patient_name"], state["selected_slot"])
            except SlotTaken:
                return offer_slots(state, "That slot was just booked by someone else. Please choose another:")
            return {"phase": "booked", "booking": booking}
        if text in {"no", "cancel", "no thanks", "change", "change slot"}:
            return offer_slots(state, "No booking made. Choose another slot:")
    if not state.get("available_slots"):
        return offer_slots(state)
    match = re.fullmatch(r"(?:option\s*|slot\s*|#)?(\d+)", text)
    if match:
        number = int(match.group(1))
    else:
        choice = generate(
            "Map the user's latest message to a numbered offered appointment. "
            "Return slot_number only when the choice is unambiguous. Otherwise return null. "
            "Do not invent availability or treat a general yes as a slot selection.",
            json.dumps({"message": text, "slots": state["available_slots"]}), SlotChoice,
        )
        number = choice.slot_number
    if number is None or not 1 <= number <= len(state["available_slots"]):
        return {"reply": "Please choose one of the listed appointment numbers. If you've already selected one, reply 'yes' to confirm or 'no' to change it."}
    slot = state["available_slots"][number - 1]
    name = state["intake"].get("patient_name")
    if not name or not name.strip():
        return {"phase": "name", "selected_slot": slot,
                "reply": f"You've selected {slot['doctor_name']} on {slot['date']} at {slot['time']}. What patient name should I book it under? Nothing is booked yet."}
    return ask_confirmation(slot, name)
