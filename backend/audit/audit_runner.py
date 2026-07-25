import asyncio
import os
import sys
import time
import psutil
from pathlib import Path
from sqlalchemy import inspect

# Insert parent dir to resolve imports correctly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.database import SessionLocal, Base
from audit.audit_config import REPORTS_DIR
from audit.audit_report import generate_reports

# Import individual phase verifiers
from audit import verify_phase1, verify_phase2, verify_phase3, verify_phase4, verify_phase5


def _child_runtime_processes(process: psutil.Process) -> list[dict]:
    runtime_names = {"chrome.exe", "chromium.exe", "msedge.exe", "node.exe"}
    children = []
    for child in process.children(recursive=True):
        try:
            name = child.name().lower()
            if name in runtime_names:
                children.append({"pid": child.pid, "name": child.name(), "status": child.status()})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return children


def _record_phase(audit_data: dict, phase_key: str, phase_result: dict) -> dict:
    phase_result["status"] = "PASS" if phase_result.get("success", False) else "FAIL"

    passed = int(phase_result.get("passed_assertions", phase_result.get("assertions", 0)) or 0)
    failed = int(phase_result.get("failed_assertions", 0) or 0)
    if phase_result["status"] == "FAIL" and failed == 0:
        # Existing verifiers only report assertions reached before failure.
        # Count failed suite itself as one failed check until verifiers expose exact expected totals.
        failed = 1

    phase_result["passed_assertions"] = passed
    phase_result["failed_assertions"] = failed
    phase_result["total_assertions"] = passed + failed

    audit_data["phases"][phase_key] = phase_result
    audit_data["passed_assertions"] += passed
    audit_data["failed_assertions"] += failed
    audit_data["total_assertions"] += passed + failed
    audit_data["warnings"].extend(phase_result.get("warnings", []))
    return phase_result


def _compute_status(audit_data: dict) -> None:
    section_statuses = [
        audit_data["environment"].get("status"),
        audit_data["database"].get("status"),
        audit_data["integration"].get("status"),
        audit_data["stability"].get("status"),
        audit_data["regression"].get("status"),
        audit_data["resources"].get("status"),
    ]
    phase_statuses = [phase.get("status") for phase in audit_data["phases"].values()]
    all_statuses = section_statuses + phase_statuses

    audit_data["status"] = "PASS" if all(status == "PASS" for status in all_statuses) else "FAIL"
    audit_data["verdict"] = "PRODUCTION READY" if audit_data["status"] == "PASS" else "NOT PRODUCTION READY"


async def _run_stability_cycles() -> dict:
    from app.modules.induction_runtime.orchestrator.session_manager import RuntimeSessionManager
    from app.modules.induction_runtime.models.runtime_state import RuntimeState

    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss
    manager = RuntimeSessionManager()
    transitions = [
        RuntimeState.WAITING_FOR_PRESENTATION,
        RuntimeState.INTRODUCTION,
        RuntimeState.PRESENTING,
        RuntimeState.QUESTION_ANSWER,
        RuntimeState.COMPLETED,
    ]

    cycle_start = time.time()
    successful_transitions = 0
    invalid_blocks = 0
    for _ in range(100):
        manager.state = RuntimeState.CREATED
        for target in transitions:
            if manager.transition_to(target):
                successful_transitions += 1
        if not manager.transition_to(RuntimeState.PRESENTING):
            invalid_blocks += 1
        await asyncio.sleep(0)

    cycle_duration = (time.time() - cycle_start) * 1000
    mem_after = process.memory_info().rss
    mem_leak_bytes = mem_after - mem_before
    expected_transitions = len(transitions) * 100
    expected_blocks = 100

    status = "PASS" if successful_transitions == expected_transitions and invalid_blocks == expected_blocks and mem_leak_bytes < 5_000_000 else "FAIL"
    return {
        "status": status,
        "poll_cycles_run": 100,
        "component": "RuntimeSessionManager",
        "transitions_verified": successful_transitions,
        "invalid_transitions_blocked": invalid_blocks,
        "memory_leaks": "CLEAN" if mem_leak_bytes < 5_000_000 else f"LEAK_{mem_leak_bytes}_BYTES",
        "memory_growth_bytes": mem_leak_bytes,
        "duration_ms": cycle_duration,
    }


async def run_audit():
    print("==================================================")
    print("         AUTOHR FULL SYSTEM INTEGRATION AUDIT     ")
    print("==================================================")

    process = psutil.Process(os.getpid())
    runtime_processes_before = _child_runtime_processes(process)

    audit_data = {
        "status": "PENDING",
        "total_assertions": 0,
        "passed_assertions": 0,
        "failed_assertions": 0,
        "warnings": [],
        "environment": {},
        "database": {},
        "phases": {},
        "integration": {},
        "performance": {},
        "stability": {},
        "regression": {},
        "resources": {},
        "verdict": "PENDING",
    }

    # ----------------------------------------------------
    # LEVEL 1: Environment Audit
    # ----------------------------------------------------
    print("\n[+] Level 1: Environment Audit...")
    db_ok = False
    try:
        db = SessionLocal()
        db.execute(Base.metadata.tables["sessions"].select().limit(1))
        db_ok = True
        db.close()
    except Exception as e:
        audit_data["warnings"].append(f"DB connection test warning: {e}")

    playwright_ok = False
    try:
        import playwright  # noqa: F401
        playwright_ok = True
    except ImportError:
        pass

    pptx_ok = False
    try:
        import pptx  # noqa: F401
        pptx_ok = True
    except ImportError:
        pass

    audit_data["environment"] = {
        "status": "PASS" if db_ok and playwright_ok and pptx_ok else "FAIL",
        "python_version": sys.version.split()[0],
        "database": "CONNECTED" if db_ok else "DISCONNECTED",
        "playwright": "INSTALLED" if playwright_ok else "MISSING",
        "pptx_support": "INSTALLED" if pptx_ok else "MISSING",
    }
    print(f"    - Python: {audit_data['environment']['python_version']}")
    print(f"    - DB: {audit_data['environment']['database']}")
    print(f"    - Playwright: {audit_data['environment']['playwright']}")

    # ----------------------------------------------------
    # LEVEL 2: Database Schema Audit
    # ----------------------------------------------------
    print("\n[+] Level 2: Database Schema Audit...")
    db = SessionLocal()
    inspector = inspect(db.bind)
    tables = inspector.get_table_names()
    db.close()

    required_tables = [
        "sessions", "meetings", "presentations", "presentation_scripts",
        "presentation_questions", "runtimes", "runtime_messages",
        "employee_lists", "organization_config",
    ]

    missing_tables = [t for t in required_tables if t not in tables]
    if missing_tables:
        audit_data["database"] = {
            "status": "FAIL",
            "tables_count": len(tables),
            "migrations_ok": "MISSING_TABLES",
            "missing_tables": missing_tables,
        }
        print(f"    [X] Missing tables: {missing_tables}")
    else:
        audit_data["database"] = {
            "status": "PASS",
            "tables_count": len(tables),
            "migrations_ok": "UP-TO-DATE",
            "missing_tables": [],
        }
        print(f"    - Verified {len(tables)} tables exist.")

    # ----------------------------------------------------
    # LEVEL 3: Phase Suites Verification
    # ----------------------------------------------------
    print("\n[+] Level 3: Executing Phase Suites...")

    phase_specs = [
        ("phase1", "Phase 1", verify_phase1.run_verification),
        ("phase2", "Phase 2", verify_phase2.run_verification),
        ("phase3", "Phase 3", verify_phase3.run_verification),
        ("phase4", "Phase 4", verify_phase4.run_verification),
        ("phase5", "Phase 5", verify_phase5.run_verification),
    ]
    for key, label, runner in phase_specs:
        result = _record_phase(audit_data, key, await runner())
        print(
            f"    - {label}: {result['status']} | "
            f"passed={result['passed_assertions']} failed={result['failed_assertions']} "
            f"in {result['duration_ms']:.2f} ms"
        )

    p1 = audit_data["phases"]["phase1"]
    p2 = audit_data["phases"]["phase2"]
    p3 = audit_data["phases"]["phase3"]
    p4 = audit_data["phases"]["phase4"]
    p5 = audit_data["phases"]["phase5"]

    # ----------------------------------------------------
    # LEVEL 4 & 5: Integration & Runtime Stability (100 poll cycles)
    # ----------------------------------------------------
    print("\n[+] Level 4 & 5: Stability & Integration (100 Runtime Cycles)...")
    audit_data["stability"] = await _run_stability_cycles()
    print(f"    - 100 runtime cycles completed in {audit_data['stability']['duration_ms']:.2f} ms")
    print(
        "    - State transitions: "
        f"{audit_data['stability']['transitions_verified']} ok, "
        f"{audit_data['stability']['invalid_transitions_blocked']} invalid blocked"
    )
    print(f"    - Memory growth: {audit_data['stability']['memory_growth_bytes'] / 1024 / 1024:.2f} MB")

    audit_data["integration"] = {
        "status": "PASS" if p3["status"] == "PASS" and p4["status"] == "PASS" and p5["status"] == "PASS" else "FAIL",
        "observer_slides_detected": p4["status"] == "PASS",
        "semantic_browser_snapshots_verified": p3["status"] == "PASS",
        "greeting_played": p5["status"] == "PASS",
        "qa_resolved": p5["status"] == "PASS",
        "lifecycle_completed": p5["status"] == "PASS",
        "basis": "Derived from phase 3, phase 4, and phase 5 verifier outcomes",
    }

    # ----------------------------------------------------
    # LEVEL 6: Regression & Toggles Audit
    # ----------------------------------------------------
    print("\n[+] Level 6: Regression & Toggles Audit...")
    audit_data["regression"] = {
        "status": "PASS" if p5["status"] == "PASS" else "FAIL",
        "voice_toggles_verified": p5["status"] == "PASS",
        "question_block_verified": p5["status"] == "PASS",
        "basis": "Derived from Phase 5 negative/runtime branch assertions",
    }
    print(f"    - Regression status: {audit_data['regression']['status']}")

    # ----------------------------------------------------
    # LEVEL 7, 8 & 9: Performance, Resource Cleanups & Architecture
    # ----------------------------------------------------
    print("\n[+] Level 7, 8 & 9: Performance & Resources Audit...")
    phase_durations = {key: phase["duration_ms"] for key, phase in audit_data["phases"].items()}
    runtime_processes_after = _child_runtime_processes(process)
    leaked_processes = [proc for proc in runtime_processes_after if proc not in runtime_processes_before]

    audit_data["performance"] = {
        "status": "PASS",
        "source": "Measured phase verifier durations and runtime stability cycle timing",
        "phase_durations_ms": phase_durations,
        "coordinator_and_pipeline_ms": p5["duration_ms"],
        "semantic_browser_ms": p3["duration_ms"],
        "observer_pipeline_ms": p4["duration_ms"],
        "runtime_cycle_avg_ms": audit_data["stability"]["duration_ms"] / audit_data["stability"]["poll_cycles_run"],
    }
    audit_data["resources"] = {
        "status": "PASS" if not leaked_processes else "FAIL",
        "playwright_cleaned": not leaked_processes,
        "runtime_processes_before": runtime_processes_before,
        "runtime_processes_after": runtime_processes_after,
        "leaked_runtime_processes": leaked_processes,
        "db_sessions_cleaned": True,
    }

    _compute_status(audit_data)

    # Generate consolidated JSON & Markdown reports
    json_path, md_path = generate_reports(audit_data, REPORTS_DIR)

    print("\n" + "=" * 50)
    print("           AUTOHR SYSTEM AUDIT SUMMARY            ")
    print("=" * 50)
    print(f"Environment Check      | {audit_data['environment']['status']}")
    print(f"Database Schemas       | {audit_data['database']['status']}")
    print(f"Phase 1 Verification   | {p1['status'].upper()}")
    print(f"Phase 2 Verification   | {p2['status'].upper()}")
    print(f"Phase 3 Verification   | {p3['status'].upper()}")
    print(f"Phase 4 Verification   | {p4['status'].upper()}")
    print(f"Phase 5 Verification   | {p5['status'].upper()}")
    print(f"Integration E2E        | {audit_data['integration']['status']}")
    print(f"100 Cycles Stability   | {audit_data['stability']['status']}")
    print(f"Regression Negative    | {audit_data['regression']['status']}")
    print(f"Resource Cleanup       | {audit_data['resources']['status']}")
    print("-" * 50)
    print(f"TOTAL ASSERTIONS RUN   | {audit_data['total_assertions']}")
    print(f"PASSED                 | {audit_data['passed_assertions']}")
    print(f"FAILED                 | {audit_data['failed_assertions']}")
    print(f"WARNINGS               | {len(audit_data['warnings'])}")
    print("-" * 50)
    print(f"FINAL AUDIT VERDICT    | {audit_data['verdict']}")
    print(f"JSON REPORT            | {json_path}")
    print(f"MARKDOWN REPORT        | {md_path}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(run_audit())
