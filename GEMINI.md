# DataForge – Project-Level Development Governance & Quality Guardrails

This document establishes mandatory engineering rules and quality guardrails for all current and future development work on the DataForge platform.

These instructions take precedence over convenience, implementation speed, and unapproved feature expansion. Every Antigravity / Gemini development session must strictly comply with these rules.

---

## 1. Existing Functionality Protection
- **Inspect Before Modifying:** Always inspect and understand existing implementations, contracts, and dependencies before touching code.
- **Component Reuse:** Reuse existing components, services, models, connectors, activities, and abstractions. Never generate redundant parallel implementations for existing responsibilities.
- **Preserve Functionality & Compatibility:** Never break backward compatibility for existing pipelines, database schemas, connectors, or API contracts.
- **No Unapproved Destructive Actions:** Do not delete, rewrite, or refactor working code or modules without explicit user authorization.
- **Unrelated Files:** Do not modify unrelated files or screens outside the active milestone scope.

---

## 2. Strict Scope Control
- **Milestone Gating:** Work only on the single milestone and feature scope currently approved by the user.
- **No Early Implementation:** Never implement future phases or unapproved features ahead of time.
- **No Unapproved Technology Introductions:** Do not introduce new third-party libraries, frameworks, or architectural layers without justification and user consent.
- **Dependency Escalation:** If an architectural dependency requires touching modules outside the current milestone:
  1. Clearly explain why the dependency is necessary.
  2. Identify all affected modules and potential regression risks.
  3. Propose the smallest safe, isolated change.
  4. Wait for explicit user approval before proceeding.

---

## 3. Architecture & Code Quality Standards
- **Architectural Planes:** Maintain strict separation of concerns between:
  - **Control Plane:** Metadata, scheduling, REST APIs, user authentication, and DAG orchestration.
  - **Execution Plane:** Runtime workers, task runners, and compute execution.
  - **Execution Engines:** 
    - *Copy Engine:* Parallel, streaming, bounded-memory data movement; strictly independent of Spark.
    - *Spark Engine:* Distributed compute and PySpark compilation for massive workloads (>10 GB).
    - *SQL Pushdown Engine:* Native in-database ELT compilation for zero network egress.
    - *Execution Planner:* Cost- and heuristic-based engine selection coordinator.
- **Clean Code Standards:**
  - Strict type annotations on functions, methods, and Pydantic/SQLAlchemy models.
  - Clear, domain-specific naming conventions conforming to existing patterns.
  - Centralized configuration, structured logging, and explicit service interfaces.
  - Avoid circular imports, business logic in UI components, and business logic in API routes.
  - Remove dead code or temporary debug statements before completing a milestone.
- **Zero Incomplete Code:** Never leave `TODO`, `FIXME`, mock endpoints, hardcoded successful returns, or placeholder implementations for functionality declared complete.

---

## 4. Database & API Backward Compatibility
- **Database Migrations:**
  - Every schema modification must have an Alembic migration script.
  - Never manually alter production database schemas.
  - Preserve all existing records, indexes, foreign keys, and constraints.
  - Plan for migration reversibility (clean downgrade paths).
- **API Contracts:**
  - Adhere to RESTful conventions and versioned routing (`/api/v1/...`).
  - Validate all incoming requests and outgoing payloads using strict Pydantic schemas.
  - Maintain backward compatibility for existing request/response contracts.
  - Implement pagination for all queries returning collections.
  - Return standardized error responses with structured error codes and descriptive messages.

---

## 5. Security Requirements
- **Zero Plaintext Secrets:** Never hardcode, commit, or return credentials, passwords, tokens, connection strings, or cloud access keys in plaintext.
- **Encryption at Rest:** All sensitive credentials must be encrypted using AES-256 Fernet cryptography (`backend/app/core/security.py`).
- **Secret Masking:** Ensure all REST APIs mask sensitive linked-service configurations before sending responses to clients.
- **Sandboxed Execution:** Custom script execution (e.g. Python scripts) must execute inside isolated child processes (`IsolatedSubprocessWorker`) with strict timeouts, restricted environments, and resource limits.
- **Input Sanitization & Injection Defense:** Parameterize all database queries to prevent SQL injection; sanitize and validate all user-supplied file paths and expressions.
- **Audit Logging:** Maintain tamper-evident audit logs for sensitive operations, pipeline mutations, secret access, and environment promotions.

---

## 6. Data Engineering & Execution Safeguards
- **Bounded-Memory Streaming:** Never load entire large datasets into application memory. All data movement must utilize streaming chunks with bounded transfer buffers (`BoundedTransferBuffer`) and hard memory caps ($\le 64\text{ MB}$ per partition) with backpressure.
- **Resource Cleanup:** Always guarantee safe closure of file handles, database cursors, and network sockets using context managers or explicit `finally` blocks.
- **Idempotency & Duplicate Prevention:** Ensure writes use transactional staging tables (`_df_stage_<run_id>`), deterministic file manifests (`_SUCCESS`), or database merge/upsert operations to prevent duplicate records during retries.
- **Fault-Tolerant Checkpointing:** Track partition progress in `PartitionCheckpointLedger`. Retried runs must resume only incomplete partitions. Never advance watermarks prior to verified destination commits.
- **Engine Affinity:** Never invoke Apache Spark for simple copy operations. Never force SQL Pushdown when transformations contain unsupported non-SQL operations.

---

## 7. Frontend Development Standards
- **Design System Adherence:** Follow the unified DataForge visual design system, dark/light themes, typography, and layout standards.
- **Component Reuse:** Reuse existing UI components (buttons, modals, inputs, tables, cards, icons) instead of creating duplicate ad-hoc styles.
- **State Integrity:** Implement true loading states, meaningful empty states, and user-friendly error banners displaying actual backend error messages.
- **Functional Interactivity:** Every button, tab, and control must perform a real, working action connected to the backend. Never produce non-functional cosmetic controls.
- **Separation of Concerns:** Keep business logic, query translation, and data manipulation out of React UI components; delegate to state stores and API service clients.

---

## 8. Mandatory Testing Requirements
- **Verification Pyramid:** Every feature must be validated through appropriate automated tests:
  - Unit tests for isolated business logic, AST parsers, and utilities.
  - API integration tests for route handlers, request validation, and error codes.
  - Execution tests for data movement, streaming buffers, and pushdown queries.
  - Regression tests to verify existing features remain intact.
- **Boundary & Chaos Scenarios:**
  - Empty datasets, small datasets, and large-scale datasets.
  - Malformed schemas and unexpected data types.
  - Interrupted connections, worker crashes (SIGKILL), and retry resumption.
  - Idempotency and zero-duplicate guarantees across retries.
  - Memory leak checks using continuous streaming under memory profiling (`tracemalloc`).
- **Truthfulness in Benchmarks:**
  - Never fabricate, estimate, or hardcode benchmark numbers. All reported throughputs, execution latencies, and row counts must come from empirical test runs.
  - Clearly classify status: `Implemented`, `Unit Tested`, `Integration Tested`, `Benchmarked`, or `Production Ready`.

---

## 9. Phase-Wise Implementation & Approval Gates
- **Sequential Execution:** Follow approved milestone sequences step-by-step.
- **Strict Stop Condition:** Stop immediately upon completing the currently approved milestone.
- **No Automatic Next Steps:** Never automatically proceed to the next milestone without explicit user approval.
- **Phase Completion Verification:** Run the full test suite and verify frontend build cleanliness before declaring a milestone complete.

---

## 10. Git & File Change Management
- **Pre-Change Inspection:** Check `git status` and inspect existing diffs before making modifications.
- **Preserve User Modifications:** Never overwrite or discard uncommitted user changes.
- **Non-Destructive Operations:** Never run destructive commands (e.g. dropping production databases, deleting directories recursively without verification, or resetting Git history) without explicit user authorization.
- **Minimal Diffs:** Keep changes focused only on files required for the approved milestone. Review diffs before committing. Never commit `.env` files or secrets.

---

## 11. Error Handling & Recovery
- **Granular Diagnostics:** Capture meaningful, structured errors with full context (activity ID, run ID, node type).
- **Error Classification:** Classify exceptions into standard domains (`ConnectionError`, `TimeoutError`, `DataQualityError`, `UserError`, `SystemError`).
- **Stack Trace Preservation:** Preserve original exception stack traces in `ActivityRun.error_stack_trace` for debugging.
- **Honest Status Reporting:** Never report success if any unhandled partition or child activity failed. Suppressing exceptions or returning fake 200 responses is strictly forbidden.

---

## 12. Documentation & Session Continuity
- **Living Documentation:** Continuously update and maintain core documentation:
  - `MASTER_ARCHITECTURE.md`: Platform architecture, engine boundaries, and components.
  - `TECHNICAL_DECISIONS.md`: Architectural Decision Records (ADRs).
  - `IMPLEMENTATION_ROADMAP.md`: Phased roadmaps and upcoming features.
  - `MILESTONE_TRACKER.md`: Historical and active milestone completion ledger.
  - `TESTING_REPORT.md`: Test suite coverage and empirical benchmark reports.
  - `KNOWN_LIMITATIONS.md`: Operational boundaries and rate limits.
  - `CHANGELOG.md`: Chronological log of changes.
- **Session Start Protocol:**
  At the beginning of every development session, the agent must:
  1. Read this `GEMINI.md` governance file.
  2. Inspect `git status` to verify working tree hygiene.
  3. Inspect `MILESTONE_TRACKER.md` to identify the last completed milestone.
  4. Await user instruction on the next milestone before creating or modifying code.

---

## 13. Mandatory Milestone Completion Reports
Upon completing any approved milestone, provide a structured completion report containing:
1. **Milestone Completed:** Phase number, title, and commit hash.
2. **Features Implemented:** Concrete list of capabilities delivered.
3. **Files Created:** Full paths to new files.
4. **Files Modified:** Full paths to modified files.
5. **Database Changes:** Migrations created and schema updates.
6. **API Changes:** New or updated endpoints and schemas.
7. **Tests Executed:** Test suites run, total tests passed, skipped, or failed.
8. **Empirical Results:** Actual benchmark measurements and resource metrics.
9. **Regression Verification:** Proof that existing functionality remains unbroken.
10. **Security Considerations:** Secret handling, encryption, and authorization verified.
11. **Known Limitations:** Edge cases or boundaries discovered.
12. **Remaining Work:** Pending tasks in the overall project plan.
13. **Next Milestone Recommendation:** Specific proposal for the next user-approved step.

---

## Final Governance Rule
DataForge is designed as an enterprise-grade platform. Engineering priorities must always follow this strict hierarchy:
$$\textbf{1. Correctness} \;\longrightarrow\; \textbf{2. Data Integrity} \;\longrightarrow\; \textbf{3. Security} \;\longrightarrow\; \textbf{4. Reliability} \;\longrightarrow\; \textbf{5. Performance} \;\longrightarrow\; \textbf{6. Maintainability} \;\longrightarrow\; \textbf{7. User Experience} \;\longrightarrow\; \textbf{8. Speed}$$

Never sacrifice correctness, security, or data integrity for convenience or speed.
