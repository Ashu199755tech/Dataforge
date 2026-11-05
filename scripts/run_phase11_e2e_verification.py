#!/usr/bin/env python3
"""
Phase 11 — End-to-End Multi-Engine Integration & Acceptance Verification Runner
Executes all 8 mandatory integration scenarios from Section 16 of the enterprise specification.
"""
import sys
import time
import json
import os

# Add root directory to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy.orm import Session
from backend.app.core.database import SessionLocal
from backend.app.models.user import User
from backend.app.api.scenarios import execute_scenario, SCENARIOS_CATALOG


def main():
    print("=" * 88)
    print("  DATALOW ENTERPRISE — PHASE 11 FULL-SPECTRUM END-TO-END VALIDATION RUNNER")
    print("  Author: DataFlow Enterprise Engineering Team")
    print("  Timestamp:", time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()))
    print("=" * 88)
    print()

    db: Session = SessionLocal()
    admin_user = db.query(User).filter(User.role == "Admin").first()
    if not admin_user:
        admin_user = User(id="admin_cli", email="admin@dataflow.enterprise", role="Admin")

    all_passed = True
    total_start = time.time()
    results = []

    for idx, sc in enumerate(SCENARIOS_CATALOG, start=1):
        print(f"[{idx}/8] Executing {sc['name']}...")
        print(f"     Engine In:  {sc['input_engine']}")
        print(f"     Engine Out: {sc['output_engine']}")

        try:
            res = execute_scenario(sc["id"], db, admin_user)
            results.append(res)
            status_symbol = "✔ PASSED" if res["status"] == "Passed" else "✖ FAILED"
            print(f"     Result: {status_symbol} in {res['duration_ms']}ms")

            for assertion in res.get("assertions", []):
                chk = "  [✓]" if assertion["passed"] else "  [✗]"
                print(f"     {chk} {assertion['name']}: Expected '{assertion['expected']}' -> Got '{assertion['actual']}'")

            if res["status"] != "Passed":
                all_passed = False

        except Exception as e:
            print(f"     ✖ EXCEPTION: {str(e)}")
            results.append({"scenario_id": sc["id"], "name": sc["name"], "status": "Failed", "error": str(e), "duration_ms": 0})
            all_passed = False

        print()

    total_duration = round((time.time() - total_start), 2)
    passed_count = sum(1 for r in results if r["status"] == "Passed")
    failed_count = sum(1 for r in results if r["status"] != "Passed")

    print("=" * 88)
    print("  PHASE 11 END-TO-END VERIFICATION SCORECARD")
    print("=" * 88)
    print(f"  Total Scenarios Executed:  {len(SCENARIOS_CATALOG)}")
    print(f"  Scenarios Passed:          {passed_count} / {len(SCENARIOS_CATALOG)} (100.0%)" if all_passed else f"  Scenarios Passed:          {passed_count} / {len(SCENARIOS_CATALOG)}")
    print(f"  Scenarios Failed:          {failed_count}")
    print(f"  Total Execution Time:      {total_duration}s")
    print(f"  Overall Milestone Status:  {'COMPLETE (100% PARITY)' if all_passed else 'INCOMPLETE'}")
    print("=" * 88)

    db.close()
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
