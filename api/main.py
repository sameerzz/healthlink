"""HTTP entry point: validate session, load history, run graph, save history."""
from fastapi import Depends, FastAPI, HTTPException, Query
from openai import APITimeoutError
from redis.exceptions import LockError, RedisError

from config import ConfigurationError
from graph import chat_workflow
from history import load_history, save_history, turn_lock
from schemas import ChatRequest, ChatResponse, Doctor, SessionResponse
from session import create_session, require_user
from tools import find_doctors, get_booking

app = FastAPI(title="HealthLink", version="2.0.0")


@app.get("/health")
def health():
    return {"status": "ok", "service": "api", "version": app.version}


@app.post("/session", response_model=SessionResponse)
def start_session():
    try:
        return create_session()
    except (RedisError, ConfigurationError):
        raise HTTPException(status_code=503, detail="Cannot create a session. Check REDIS_URL.") from None


@app.get("/doctors", response_model=list[Doctor])
def doctors(specialty: str | None = Query(default=None, max_length=100)):
    return find_doctors(specialty)


@app.get("/specialties")
def specialties():
    return sorted({doctor.specialty for doctor in find_doctors()})


@app.get("/history")
def history(user_id: str = Depends(require_user)):
    try:
        return {"messages": load_history(user_id)["messages"]}
    except RedisError:
        raise HTTPException(status_code=503, detail="History storage is unavailable.") from None


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, user_id: str = Depends(require_user)):
    try:
        with turn_lock(user_id):
            state = load_history(user_id)
            # A saved booking survives a lost HTTP response or failed Redis write.
            booking = get_booking(user_id)
            if booking:
                state.update(booking=booking, phase="booked")
            state["messages"].append({"role": "user", "content": request.message})
            result = chat_workflow.invoke(state)
            result["messages"].append({"role": "assistant", "content": result["reply"]})
            save_history(user_id, result)
        return ChatResponse(
            reply=result["reply"], phase=result["phase"],
            available_slots=result.get("available_slots", []), booking=result.get("booking"),
        )
    except LockError:
        raise HTTPException(status_code=409, detail="A reply is already being prepared. Please wait.") from None
    except RedisError:
        raise HTTPException(status_code=503, detail="Conversation storage is unavailable. Please retry.") from None
    except ConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except APITimeoutError:
        raise HTTPException(status_code=504, detail="The model timed out. Please resend your message.") from None
    except Exception:
        raise HTTPException(status_code=502, detail="Could not complete this turn. Please retry.") from None
