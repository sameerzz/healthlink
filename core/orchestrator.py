"""
Orchestrator for HealthLink agents.
Coordinates execution of all agents in the correct sequence.
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from core.llm import LLMClient
from core.schemas import HealthAssessmentRequest, HealthAssessmentResponse
from agents.symptom_agent import symptom_agent
from agents.doctor_agent import doctor_agent
from agents.scheduling_agent import scheduling_agent
from agents.summary_agent import summary_agent
from config.settings import Settings


logger = logging.getLogger("healthlink.orchestrator")


def _resolve_settings(settings: Optional[Settings]) -> Settings:
    if settings is not None:
        return settings
    from config.settings import get_settings
    return get_settings()


def _build_response(
    request_id: str,
    request: HealthAssessmentRequest,
    symptom_analysis,
    doctor_recommendation,
    scheduling_recommendation,
    health_summary,
) -> HealthAssessmentResponse:
    return HealthAssessmentResponse(
        request_id=request_id,
        timestamp=datetime.utcnow(),
        symptom_analysis=symptom_analysis,
        doctor_recommendations=doctor_recommendation,
        scheduling_options=scheduling_recommendation,
        health_summary=health_summary,
        metadata={
            "user_id": request.user_id,
            "preferred_location": request.preferred_location,
            "processing_time_ms": 0,
        },
    )


def orchestrate_health_assessment(
    request: HealthAssessmentRequest,
    db_session: Session,
    llm_client: Optional[LLMClient] = None,
    settings: Optional[Settings] = None
) -> HealthAssessmentResponse:
    request_id = str(uuid.uuid4())
    logger.info(f"Starting health assessment orchestration [request_id={request_id}]")
    resolved_settings = _resolve_settings(settings)

    try:
        logger.info(f"[{request_id}] Step 1/4: Analyzing symptoms")
        symptom_analysis = symptom_agent(
            user_input=request.user_input,
            llm_client=llm_client,
            settings=resolved_settings,
            use_rag=True,
        )
        logger.info(
            f"[{request_id}] Symptom analysis complete: "
            f"urgency={symptom_analysis.urgency_level}, "
            f"symptoms={len(symptom_analysis.symptoms)}"
        )

        logger.info(f"[{request_id}] Step 2/4: Recommending doctors")
        doctor_recommendation = doctor_agent(
            symptom_analysis=symptom_analysis,
            db_session=db_session,
            llm_client=llm_client,
            settings=resolved_settings,
            max_recommendations=3,
        )
        logger.info(
            f"[{request_id}] Doctor recommendation complete: "
            f"doctors={len(doctor_recommendation.recommended_doctors)}"
        )

        logger.info(f"[{request_id}] Step 3/4: Generating scheduling options")
        scheduling_recommendation = scheduling_agent(
            doctor_recommendation=doctor_recommendation,
            urgency_level=symptom_analysis.urgency_level,
            llm_client=llm_client,
            settings=resolved_settings,
            preferred_date=request.preferred_date,
        )
        logger.info(
            f"[{request_id}] Scheduling complete: "
            f"slots={len(scheduling_recommendation.available_slots)}"
        )

        logger.info(f"[{request_id}] Step 4/4: Generating health summary")
        health_summary = summary_agent(
            symptom_analysis=symptom_analysis,
            doctor_recommendation=doctor_recommendation,
            scheduling_recommendation=scheduling_recommendation,
            llm_client=llm_client,
            settings=resolved_settings,
        )
        logger.info(f"[{request_id}] Summary generation complete")

        response = _build_response(
            request_id=request_id,
            request=request,
            symptom_analysis=symptom_analysis,
            doctor_recommendation=doctor_recommendation,
            scheduling_recommendation=scheduling_recommendation,
            health_summary=health_summary,
        )
        logger.info(f"[{request_id}] Health assessment orchestration complete")
        return response

    except Exception as e:
        logger.error(f"[{request_id}] Orchestration failed: {e}", exc_info=True)
        raise


async def orchestrate_health_assessment_async(
    request: HealthAssessmentRequest,
    db_session: Session,
    llm_client: Optional[LLMClient] = None,
    settings: Optional[Settings] = None
) -> HealthAssessmentResponse:
    """
    Async version of orchestrate_health_assessment.

    Note: Currently wraps synchronous implementation.
    For true async, all agent functions would need async implementations.
    """
    return orchestrate_health_assessment(request, db_session, llm_client, settings)


def validate_assessment_request(request: HealthAssessmentRequest) -> tuple[bool, str]:
    """Validate user-provided assessment request."""
    if len(request.user_input.strip()) < 10:
        return False, "Health concern description too short. Please provide more details."

    prohibited_keywords = ["test", "demo", "fake"]
    lower_input = request.user_input.lower()
    if any(keyword in lower_input for keyword in prohibited_keywords):
        logger.warning(f"Suspicious input detected: {request.user_input[:50]}")

    if request.preferred_date:
        try:
            datetime.strptime(request.preferred_date, "%Y-%m-%d")
        except ValueError:
            return False, "Invalid preferred_date format. Use YYYY-MM-DD."

    return True, ""
