import json
import datetime
from pathlib import Path
from app.core.logging import logger


def _fmt_ms(value) -> str:
    try:
        return f"{float(value):.2f} ms"
    except (TypeError, ValueError):
        return "n/a"


def generate_reports(report_data: dict, reports_dir: Path) -> tuple[Path, Path]:
    """
    Generates human-readable Markdown and CI-friendly JSON reports.
    """
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = reports_dir / f"audit_{timestamp}.json"
    md_path = reports_dir / f"audit_{timestamp}.md"

    # Save JSON report
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    logger.info(f"AuditReport | JSON report saved to: {json_path}")

    perf = report_data.get("performance", {})
    phase_durations = perf.get("phase_durations_ms", {})
    integration = report_data.get("integration", {})
    resources = report_data.get("resources", {})
    stability = report_data.get("stability", {})

    phase_rows = []
    phase_names = {
        "phase1": "Phase 1: PowerPoint Parsing",
        "phase2": "Phase 2: Meeting Bot Joining",
        "phase3": "Phase 3: Semantic Browser",
        "phase4": "Phase 4: Observer Pipeline",
        "phase5": "Phase 5: Runtime Conductor",
    }
    for key, label in phase_names.items():
        phase = report_data["phases"].get(key, {})
        phase_rows.append(
            f"| {label} | {phase.get('status', 'UNKNOWN')} | "
            f"{phase.get('passed_assertions', phase.get('assertions', 0))} | "
            f"{phase.get('failed_assertions', 0)} | "
            f"{float(phase.get('duration_ms', 0)):.2f} |"
        )

    phase_duration_lines = "\n".join(
        f"- {key}: `{_fmt_ms(value)}`" for key, value in phase_durations.items()
    ) or "- No phase timings recorded."

    md_content = f"""# AutoHR System Audit Report

Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Status: **{report_data.get('status', 'UNKNOWN')}**

## Summary
- **Total Checks**: {report_data.get('total_assertions', 0)}
- **Passed Checks**: {report_data.get('passed_assertions', 0)}
- **Failed Checks**: {report_data.get('failed_assertions', 0)}
- **Warnings**: {len(report_data.get('warnings', []))}
- **Verdict**: {report_data.get('verdict', 'INCOMPLETE')}

---

## 1. Environment Audit
Status: **{report_data['environment']['status']}**
- Python Version: `{report_data['environment']['python_version']}`
- Database Connection: `{report_data['environment']['database']}`
- Playwright Installed: `{report_data['environment']['playwright']}`
- PPTX Support: `{report_data['environment'].get('pptx_support', 'UNKNOWN')}`

## 2. Database Audit
Status: **{report_data['database']['status']}**
- Tables Audited: {report_data['database']['tables_count']}
- Migrations Verified: `{report_data['database']['migrations_ok']}`
- Missing Tables: `{report_data['database'].get('missing_tables', [])}`

## 3. Phase Verification Suites
| Phase | Status | Passed | Failed | Duration (ms) |
|---|---|---:|---:|---:|
{chr(10).join(phase_rows)}

## 4. Integration E2E Audit
Status: **{integration.get('status', 'UNKNOWN')}**
- Semantic browser snapshots verified: `{integration.get('semantic_browser_snapshots_verified')}`
- Slide observer detected slides: `{integration.get('observer_slides_detected')}`
- Greeting played: `{integration.get('greeting_played')}`
- Q&A answers resolved: `{integration.get('qa_resolved')}`
- Farewell and complete state: `{integration.get('lifecycle_completed')}`
- Basis: {integration.get('basis', 'n/a')}

## 5. Performance Audit
Status: **{perf.get('status', 'UNKNOWN')}**
- Source: {perf.get('source', 'n/a')}
- Coordinator and pipeline: `{_fmt_ms(perf.get('coordinator_and_pipeline_ms'))}`
- Semantic browser: `{_fmt_ms(perf.get('semantic_browser_ms'))}`
- Observer pipeline: `{_fmt_ms(perf.get('observer_pipeline_ms'))}`
- Runtime cycle average: `{_fmt_ms(perf.get('runtime_cycle_avg_ms'))}`

### Phase Timings
{phase_duration_lines}

## 6. Stability & Regression
- Runtime cycles stability: **{stability.get('status', 'UNKNOWN')}**
- Cycles run: `{stability.get('poll_cycles_run', 0)}`
- Component exercised: `{stability.get('component', 'n/a')}`
- Transitions verified: `{stability.get('transitions_verified', 0)}`
- Invalid transitions blocked: `{stability.get('invalid_transitions_blocked', 0)}`
- Memory leaks check: `{stability.get('memory_leaks', 'UNKNOWN')}`
- Negative regression tests: **{report_data['regression']['status']}**
- Regression basis: {report_data['regression'].get('basis', 'n/a')}

## 7. Resource Cleanup
Status: **{resources.get('status', 'UNKNOWN')}**
- Playwright/browser child processes cleaned: `{resources.get('playwright_cleaned')}`
- Runtime processes before: `{resources.get('runtime_processes_before', [])}`
- Runtime processes after: `{resources.get('runtime_processes_after', [])}`
- Leaked runtime processes: `{resources.get('leaked_runtime_processes', [])}`
- DB sessions closed: `{resources.get('db_sessions_cleaned')}`

---
### System Integrity Verdict
**{report_data.get('verdict', 'INCOMPLETE')}**
"""

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info(f"AuditReport | Markdown report saved to: {md_path}")

    return json_path, md_path
