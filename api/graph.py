"""One graph turn: understand, recommend, schedule, then summarize."""
from langgraph.graph import END, START, StateGraph

from agents.doctor_agent import chat_doctor_agent
from agents.scheduling_agent import chat_scheduling_agent
from agents.summary_agent import chat_summary_agent
from agents.symptom_agent import chat_symptom_agent
from state import ChatState


def next_agent(state):
    if state.get("booking"):
        return "summary"
    if state["phase"] in {"selecting", "name", "confirming"}:
        return "scheduling"
    return "symptom"


def after_symptoms(state):
    return "doctor" if state["phase"] == "selecting" else END


def after_scheduling(state):
    return "summary" if state["phase"] == "booked" else END


builder = StateGraph(ChatState)
builder.add_node("symptom", chat_symptom_agent)
builder.add_node("doctor", chat_doctor_agent)
builder.add_node("scheduling", chat_scheduling_agent)
builder.add_node("summary", chat_summary_agent)
builder.add_conditional_edges(START, next_agent)
builder.add_conditional_edges("symptom", after_symptoms)
builder.add_edge("doctor", "scheduling")
builder.add_conditional_edges("scheduling", after_scheduling)
builder.add_edge("summary", END)
chat_workflow = builder.compile()
