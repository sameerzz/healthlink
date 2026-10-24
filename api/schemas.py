from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class Doctor(BaseModel):
    id: int
    name: str
    specialty: str
    location: str


class AppointmentSlot(BaseModel):
    doctor_id: int
    doctor_name: str
    date: date
    time: str


class IntakeReview(BaseModel):
    patient_name: str | None = None
    duration: str | None = None
    symptoms: list[str] = Field(default_factory=list)
    specialty: Literal["General Medicine", "Cardiology", "Dermatology", "Pediatrics"] = "General Medicine"
    urgency: Literal["routine", "urgent", "emergency"] = "routine"
    follow_up: str = ""


class SlotChoice(BaseModel):
    slot_number: int | None = None


class PatientDetails(BaseModel):
    patient_name: str | None = None


class ChatRequest(BaseModel):
    model_config = {"extra": "forbid"}
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("Enter a message.")
        return value.strip()


class Booking(AppointmentSlot):
    booking_id: str
    patient_name: str


class ChatResponse(BaseModel):
    reply: str
    phase: Literal["intake", "selecting", "name", "confirming", "booked", "urgent"]
    available_slots: list[AppointmentSlot] = Field(default_factory=list)
    booking: Booking | None = None
    disclaimer: str = "Classroom demo only; not medical advice. Bookings are saved in this demo, not sent to a real clinic."


class SessionResponse(BaseModel):
    user_id: str
    token: str
    expires_in: int
