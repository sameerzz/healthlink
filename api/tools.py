"""Deterministic tools: local data lookup and sample slot generation."""
from datetime import date, timedelta

from database import SlotTaken, booking_for, book_appointment, list_doctors, occupied_slots
from schemas import AppointmentSlot, Doctor


def find_doctors(specialty=None):
    return [Doctor.model_validate(doctor) for doctor in list_doctors(specialty)]


def get_booking(user_id):
    return booking_for(user_id)


def reserve_appointment(user_id, patient_name, slot):
    return book_appointment(user_id, patient_name, slot)


def available_slots(doctors):
    taken = occupied_slots()
    slots = []
    # Small fixed clinic calendar: next five weekdays, 10:00 and 14:00.
    day = date.today()
    weekdays = 0
    while weekdays < 5:
        day += timedelta(days=1)
        if day.weekday() >= 5:
            continue
        weekdays += 1
        for doctor in doctors:
            for time in ("10:00", "14:00"):
                if (doctor.id, day.isoformat(), time) not in taken:
                    slots.append(AppointmentSlot(doctor_id=doctor.id, doctor_name=doctor.name,
                                                 date=day, time=time).model_dump(mode="json"))
    return slots[:8]
