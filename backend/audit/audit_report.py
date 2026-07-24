import json
import datetime
from pathlib import Path
from app.core.logging import logger

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

    # Build Markdown report
    md_content = f"""# AutoHR System Audit Report

Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Status: **{report_data.get('status', 'UNKNOWN')}**

## Summary
- **Total Assertions**: {report_data.get('total_assertions', 0)}
- **Passed Assertions**: {report_data.get('passed_assertions', 0)}
- **Failed Assertions**: {report_data.get('failed_assertions', 0)}
- **Warnings**: {len(report_data.get('warnings', []))}

---

## 1. Environment Audit
Status: **{report_data['environment']['status']}**
- Python Version: `{report_data['environment']['python_version']}`
- Database Connection: `{report_data['environment']['database']}`
- Playwright Installed: `{report_data['environment']['playwright']}`

## 2. Database Audit
Status: **{report_data['database']['status']}**
- Tables Audited: {report_data['database']['tables_count']}
- Migrations Verified: `{report_data['database']['migrations_ok']}`

## 3. Phase Verification Suites
| Phase | Status | Assertions | Duration (ms) |
|---|---|---|---|
| Phase 1: PowerPoint Parsing | {report_data['phases']['phase1']['status']} | {report_data['phases']['phase1']['assertions']} | {report_data['phases']['phase1']['duration_ms']:.2f} |
| Phase 2: Meeting Bot Joining | {report_data['phases']['phase2']['status']} | {report_data['phases']['phase2']['assertions']} | {report_data['phases']['phase2']['duration_ms']:.2f} |
| Phase 3: Semantic Browser | {report_data['phases']['phase3']['status']} | {report_data['phases']['phase3']['assertions']} | {report_data['phases']['phase3']['duration_ms']:.2f} |
| Phase 4: Observer Pipeline | {report_data['phases']['phase4']['status']} | {report_data['phases']['phase4']['assertions']} | {report_data['phases']['phase4']['duration_ms']:.2f} |
| Phase 5: Runtime Conductor | {report_data['phases']['phase5']['status']} | {report_data['phases']['phase5']['assertions']} | {report_data['phases']['phase5']['duration_ms']:.2f} |

## 4. Integration E2E Audit
Status: **{report_data['integration']['status']}**
- Slide observer detected slides: `{report_data['integration']['observer_slides_detected']}`
- Greeting played: `{report_data['integration']['greeting_played']}`
- Q&A answers resolved: `{report_data['integration']['qa_resolved']}`
- Farewell and complete state: `{report_data['integration']['lifecycle_completed']}`

## 5. Performance Audit
- Coordinator Startup: `{report_data['performance']['coordinator_startup_ms']:.2f} ms`
- Welcome Greeting Gen: `{report_data['performance']['greeting_gen_ms']:.2f} ms`
- Slide Change Reaction: `{report_data['performance']['slide_change_reaction_ms']:.2f} ms`

## 6. Stability & Regression
- 100 Poll cycles stability: **{report_data['stability']['status']}**
- Memory leaks check: `{report_data['stability']['memory_leaks']}`
- Negative regression tests: **{report_data['regression']['status']}** (Missing Scripts, Missing FAQs, Voice toggles)

## 7. Resource Cleanup
- Playwright page closed: `{report_data['resources']['playwright_cleaned']}`
- DB sessions closed: `{report_data['resources']['db_sessions_cleaned']}`

---
### System Integrity Verdict
**{report_data.get('verdict', 'INCOMPLETE')}**
"""

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    logger.info(f"AuditReport | Markdown report saved to: {md_path}")

    return json_path, md_path
