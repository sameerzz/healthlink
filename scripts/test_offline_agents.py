"""
Run all HealthLink agents locally with one command.

Usage:
  python scripts/test_offline_agents.py
  python scripts/test_offline_agents.py "I have chest pain and shortness of breath since morning"
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pandas as pd

from config.settings import get_settings
from core.database import get_db_manager, seed_doctors
from agents.symptom_agent import symptom_agent
from agents.doctor_agent import doctor_agent
from agents.scheduling_agent import scheduling_agent
from agents.summary_agent import summary_agent


def pretty(title: str, data: dict) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(data, indent=2, default=str))


def main() -> None:
    user_input = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "I have severe headache and fever for 3 days"
    )

    settings = get_settings()

    db_manager = get_db_manager(settings)
    doctors_csv = ROOT_DIR / "data" / "doctors.csv"
    if doctors_csv.exists():
        doctors_data = pd.read_csv(doctors_csv).to_dict("records")
        with db_manager.session_scope() as session:
            seed_doctors(session, doctors_data)

    symptom_result = symptom_agent(user_input=user_input, settings=settings, use_rag=False)

    with db_manager.session_scope() as session:
        doctor_result = doctor_agent(
            symptom_analysis=symptom_result,
            db_session=session,
            settings=settings,
        )

    scheduling_result = scheduling_agent(
        doctor_recommendation=doctor_result,
        urgency_level=symptom_result.urgency_level,
        settings=settings,
    )

    summary_result = summary_agent(
        symptom_analysis=symptom_result,
        doctor_recommendation=doctor_result,
        scheduling_recommendation=scheduling_result,
        settings=settings,
    )

    print(f"LLM_PROVIDER={settings.llm_provider}")
    print(f"INPUT={user_input}")
    pretty("Symptom Agent", symptom_result.model_dump())
    pretty("Doctor Agent", doctor_result.model_dump())
    pretty("Scheduling Agent", scheduling_result.model_dump())
    pretty("Summary Agent", summary_result.model_dump())


if __name__ == "__main__":
    main()
