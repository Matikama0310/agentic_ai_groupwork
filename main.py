"""
NorthStar Underwriting System - CLI Entry Point.

Usage:
    python main.py              # Run demo submission
    python main.py --server     # Start FastAPI server
    streamlit run app.py        # Start Streamlit workbench
"""

import argparse
import json
import logging
import sys
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


def run_demo():
    """Run a demo submission through the full workflow."""
    from src.orchestration.supervisor_agent import SupervisorAgent
    from src.core.state_manager import get_state_manager

    print("\n" + "=" * 70)
    print("  NorthStar Insurance - Agentic Underwriting System (MVP Demo)")
    print("=" * 70)

    supervisor = SupervisorAgent()
    sm = get_state_manager()

    # Demo submission: happy path (should result in QUOTED)
    sub_id = f"DEMO-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
    print(f"\n[1/3] Submitting application: {sub_id}")
    print("      Applicant: Acme Restaurant Inc.")
    print("      Broker: John Smith (broker@example.com)")
    print("-" * 70)

    state = supervisor.process_submission(
        submission_id=sub_id,
        email_subject="Application for Acme Restaurant Inc.",
        email_body=(
            "We are submitting an application for general liability coverage "
            "for Acme Restaurant Inc., a full-service restaurant located at "
            "123 Main St, Springfield, IL. The business has been operating "
            "since 2015 with 12 employees and $500,000 annual revenue."
        ),
        broker_email="broker@example.com",
        broker_name="John Smith",
        attachments=[],
    )

    print(f"\n[2/3] Processing complete!")
    print(f"      Status:   {state.status}")
    print(f"      Decision: {state.decision}")
    if state.risk_metrics:
        print(f"      Premium:  ${state.risk_metrics.get('annual_premium', 0):,.2f}")
        print(f"      Risk:     {state.risk_metrics.get('risk_score', 0):.1f}/100")
    if state.drafted_email:
        print(f"\n      Email Subject: {state.drafted_email.get('subject', '')}")
    if state.quote_pdf_url:
        print(f"      Quote PDF: {state.quote_pdf_url}")

    # Show audit trail
    print(f"\n[3/3] Audit Trail ({len(state.audit_trail)} entries):")
    print("-" * 70)
    for entry in state.audit_trail:
        if hasattr(entry, "timestamp"):
            print(f"  {entry.timestamp} | {entry.component:25s} | {entry.action}")
        else:
            print(f"  {entry.get('timestamp', '')} | {entry.get('component', ''):25s} | {entry.get('action', '')}")

    print("\n" + "=" * 70)
    print("  Demo complete. Run 'streamlit run app.py' for the full workbench.")
    print("=" * 70 + "\n")

    return state


def run_server():
    """Start the FastAPI server."""
    import uvicorn
    from src.api.handlers import create_app

    app = create_app()
    print("\nStarting NorthStar Underwriting API server...")
    print("  Docs: http://localhost:8000/docs")
    print("  Submit: POST http://localhost:8000/submit")
    print("  Status: GET  http://localhost:8000/status/{submission_id}")
    print("  Override: POST http://localhost:8000/override\n")
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NorthStar Underwriting System")
    parser.add_argument("--server", action="store_true", help="Start FastAPI server")
    parser.add_argument("--demo", action="store_true", help="Run demo submission (default)")
    args = parser.parse_args()

    if args.server:
        run_server()
    else:
        run_demo()
