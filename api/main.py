"""HTTP entry point: validate session, load history, run graph, save history."""
import logging
import sys
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from openai import APITimeoutError
from redis.exceptions import LockError, RedisError

from config import ConfigurationError
from graph import chat_workflow
from history import load_history, save_history, turn_lock
from schemas import ChatRequest, ChatResponse, Doctor, SessionResponse
from session import create_session, require_user
from tools import find_doctors, get_booking

# Application logs go to the terminal; no extra logging dependency is needed.
logger = logging.getLogger("healthlink")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
logger.propagate = False


@asynccontextmanager
async def lifespan(app):
    logger.info("API started")
    yield
    logger.info("API stopped")


app = FastAPI(title="HealthLink", version="2.0.0", lifespan=lifespan)


@app.middleware("http")
async def log_request(request: Request, call_next):
    started = perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error("HTTP request failed method=%s error=%s", request.method, type(exc).__name__)
        raise
    # Log the route template, not query strings, request bodies, or headers.
    route = request.scope.get("route")
    path = route.path if route else "unmatched"
    level = logging.ERROR if response.status_code >= 500 else logging.WARNING if response.status_code >= 400 else logging.INFO
    logger.log(level, "%s %s status=%s duration_ms=%.1f", request.method, path,
               response.status_code, (perf_counter() - started) * 1000)
    return response


@app.get("/health")
def health():
    return {"status": "ok", "service": "api", "version": app.version}


@app.post("/session", response_model=SessionResponse)
def start_session():
    try:
        session = create_session()
        logger.info("Session created")
        return session
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
            logger.info("Chat workflow started phase=%s", state["phase"])
            result = chat_workflow.invoke(state)
            logger.info("Chat workflow completed phase=%s", result["phase"])
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
    except Exception as exc:
        logger.error("Chat workflow failed error=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Could not complete this turn. Please retry.") from None
