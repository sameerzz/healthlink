"""Only the data the graph needs to carry between agents and chat turns."""
from typing_extensions import TypedDict


class ChatState(TypedDict, total=False):
    user_id: str
    messages: list[dict]
    phase: str
    intake: dict
    doctors: list[dict]
    available_slots: list[dict]
    selected_slot: dict | None
    booking: dict
    reply: str
