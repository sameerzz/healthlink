"""
Gradio + FastAPI app for HealthLink.

Routes:
- FastAPI API docs: /docs
- Gradio UI: /gradio
"""

from __future__ import annotations

from typing import Any

import gradio as gr

from config.settings import get_settings
from core.database import get_db_manager, seed_doctors
from core.llm import get_llm_client
from core.orchestrator import orchestrate_health_assessment
from core.schemas import HealthAssessmentRequest
from main import app as fastapi_app


def _ensure_seeded() -> None:
    """Seed doctors once if CSV exists."""
    import pandas as pd
    from pathlib import Path

    settings = get_settings()
    db_manager = get_db_manager(settings)
    doctors_file = Path("data/doctors.csv")
    if doctors_file.exists():
        doctors_data = pd.read_csv(doctors_file).to_dict("records")
        with db_manager.session_scope() as session:
            seed_doctors(session, doctors_data)


def assess(
    user_input: str,
    user_id: str,
    preferred_date: str,
    preferred_location: str,
) -> dict[str, Any]:
    settings = get_settings()
    db_manager = get_db_manager(settings)
    llm_client = get_llm_client(settings)

    request = HealthAssessmentRequest(
        user_input=user_input,
        user_id=user_id or None,
        preferred_date=preferred_date or None,
        preferred_location=preferred_location or None,
    )

    with db_manager.session_scope() as session:
        response = orchestrate_health_assessment(
            request=request,
            db_session=session,
            llm_client=llm_client,
            settings=settings,
        )
    return response.model_dump(mode="json")


def build_gradio() -> gr.Blocks:
    with gr.Blocks(title="HealthLink Gradio") as demo:
        gr.Markdown("# HealthLink")
        gr.Markdown("Symptom assessment, doctor recommendation, and scheduling.")

        with gr.Row():
            user_input = gr.Textbox(
                label="Describe your symptoms",
                placeholder="I have severe headache and fever for 3 days",
                lines=4,
            )
        with gr.Row():
            user_id = gr.Textbox(label="User ID (optional)", placeholder="user123")
            preferred_date = gr.Textbox(label="Preferred Date YYYY-MM-DD (optional)")
            preferred_location = gr.Textbox(label="Preferred Location (optional)")

        submit = gr.Button("Assess")
        output = gr.JSON(label="Assessment Result")

        submit.click(
            fn=assess,
            inputs=[user_input, user_id, preferred_date, preferred_location],
            outputs=output,
        )
    return demo


_ensure_seeded()
gradio_ui = build_gradio()
app = gr.mount_gradio_app(fastapi_app, gradio_ui, path="/gradio")
