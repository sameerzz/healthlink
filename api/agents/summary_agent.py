"""Format the summary from confirmed database facts; no extra model call."""


def chat_summary_agent(state):
    booking = state["booking"]
    intake = state.get("intake", {})
    symptoms = ", ".join(intake.get("symptoms", [])) or "Not recorded"
    reply = (
        f"Appointment booked!\n\nBooking ID: {booking['booking_id']}\n\n"
        f"Patient: {booking['patient_name']}\n\nDoctor: {booking['doctor_name']}\n\n"
        f"When: {booking['date']} at {booking['time']} (clinic local time)\n\n"
        f"Symptoms: {symptoms}\n\nDuration: {intake.get('duration') or 'Not recorded'}\n\n"
        "Your appointment is saved in this classroom application. No real clinic has been contacted."
    )
    return {"reply": reply, "available_slots": [], "selected_slot": None}
