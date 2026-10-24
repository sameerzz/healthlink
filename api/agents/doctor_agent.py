from tools import find_doctors


def chat_doctor_agent(state):
    doctors = find_doctors(state["intake"]["specialty"])
    return {"doctors": [doctor.model_dump() for doctor in doctors]}
