"""
Scheduling agent.
Generates available appointment slots based on doctor recommendations.
"""
import logging
from typing import Optional, List
from datetime import datetime, timedelta, date

from core.llm import llm_generate, LLMClient
from core.schemas import DoctorRecommendation, SchedulingRecommendation, TimeSlot
from config.settings import Settings


logger = logging.getLogger("healthlink.agents.scheduling")


def generate_time_slots(
    doctor_name: str,
    start_date: date,
    num_days: int = 7,
    slots_per_day: int = 8
) -> List[TimeSlot]:
    """
    Generate mock available time slots for a doctor.

    In production, this would query a real scheduling system.

    Args:
        doctor_name: Doctor's name
        start_date: Starting date for slot generation
        num_days: Number of days to generate slots for
        slots_per_day: Number of slots per day

    Returns:
        List of available time slots
    """
    slots = []
    working_hours = [9, 10, 11, 12, 14, 15, 16, 17]

    for day_offset in range(num_days):
        current_date = start_date + timedelta(days=day_offset)

        if current_date.weekday() >= 5:
            continue

        for hour in working_hours[:slots_per_day]:
            slot = TimeSlot(
                doctor_name=doctor_name,
                date=current_date.strftime("%Y-%m-%d"),
                time=f"{hour:02d}:00",
                duration_minutes=30,
                slot_id=f"{doctor_name.replace(' ', '_')}_{current_date.strftime('%Y%m%d')}_{hour:02d}00"
            )
            slots.append(slot)

    return slots


def scheduling_agent(
    doctor_recommendation: DoctorRecommendation,
    urgency_level: str,
    llm_client: Optional[LLMClient] = None,
    settings: Optional[Settings] = None,
    preferred_date: Optional[str] = None
) -> SchedulingRecommendation:
    """
    Generate scheduling recommendations based on doctor availability and urgency.

    This is a pure function that takes doctor recommendations and returns scheduling options.

    Args:
        doctor_recommendation: Results from doctor agent
        urgency_level: Urgency assessment (low, medium, high, emergency)
        llm_client: LLM client instance (optional)
        settings: Application settings (optional)
        preferred_date: User's preferred date (YYYY-MM-DD) (optional)

    Returns:
        SchedulingRecommendation with available slots

    Example:
        >>> recommendation = scheduling_agent(doctor_rec, "medium")
        >>> print(len(recommendation.available_slots))
        15
    """
    logger.info(f"Scheduling agent processing with urgency: {urgency_level}")

    if settings is None:
        from config.settings import get_settings
        settings = get_settings()

    urgency_to_days = {
        "emergency": 0,
        "high": 1,
        "medium": 3,
        "low": 7
    }

    days_ahead = urgency_to_days.get(urgency_level, 3)

    start_date = datetime.now().date()
    if preferred_date:
        try:
            start_date = datetime.strptime(preferred_date, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Invalid preferred date: {preferred_date}, using today")

    all_slots = []

    for doctor in doctor_recommendation.recommended_doctors:
        doctor_slots = generate_time_slots(
            doctor_name=doctor.name,
            start_date=start_date,
            num_days=14,
            slots_per_day=8
        )
        all_slots.extend(doctor_slots)

    if not all_slots:
        logger.warning("No available slots generated")
        return SchedulingRecommendation(
            available_slots=[],
            recommended_slot=None,
            scheduling_notes="No available appointments at this time. Please contact the clinic directly."
        )

    try:
        slot_summary = "\n".join([
            f"- {slot.doctor_name}: {slot.date} at {slot.time}"
            for slot in all_slots[:10]
        ])

        recommendation_prompt = f"""Select the best appointment slot based on these criteria:

Urgency Level: {urgency_level}
Available Slots (showing first 10):
{slot_summary}

Preferred Date: {preferred_date or "None specified"}

Select the most appropriate slot considering:
1. Urgency (higher urgency = sooner appointment)
2. User's preferred date if specified
3. Convenient timing (morning slots often preferred)

Return the slot_id of the recommended slot and brief scheduling notes.
Format:
{{
    "recommended_slot_id": "slot_id_here",
    "scheduling_notes": "Brief explanation of why this slot is recommended"
}}
"""

        from pydantic import BaseModel, Field

        class SlotSelection(BaseModel):
            recommended_slot_id: str = Field(..., description="ID of recommended slot")
            scheduling_notes: str = Field(..., description="Scheduling notes")

        selection = llm_generate(
            prompt=recommendation_prompt,
            schema=SlotSelection,
            temperature=0.1,
            client=llm_client
        )

        recommended_slot = next(
            (slot for slot in all_slots if slot.slot_id == selection.recommended_slot_id),
            all_slots[0] if all_slots else None
        )

        logger.info(f"Generated {len(all_slots)} available slots")

        return SchedulingRecommendation(
            available_slots=all_slots[:20],
            recommended_slot=recommended_slot,
            scheduling_notes=selection.scheduling_notes
        )

    except Exception as e:
        logger.error(f"Scheduling agent failed: {e}", exc_info=True)

        return SchedulingRecommendation(
            available_slots=all_slots[:20],
            recommended_slot=all_slots[0] if all_slots else None,
            scheduling_notes=f"First available appointment recommended. Urgency level: {urgency_level}"
        )


async def scheduling_agent_async(
    doctor_recommendation: DoctorRecommendation,
    urgency_level: str,
    llm_client: Optional[LLMClient] = None,
    settings: Optional[Settings] = None,
    preferred_date: Optional[str] = None
) -> SchedulingRecommendation:
    """
    Async version of scheduling_agent.

    Note: Currently wraps synchronous implementation.
    """
    return scheduling_agent(
        doctor_recommendation,
        urgency_level,
        llm_client,
        settings,
        preferred_date
    )
