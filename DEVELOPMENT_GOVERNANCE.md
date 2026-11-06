# DATAFORGE – DEVELOPMENT GOVERNANCE, ENGINEERING GUARDRAILS AND QUALITY CONTROL

## 1. Purpose

This document defines mandatory development rules for all current and future development work on DataForge.

These rules apply to every module, feature, API, database change, frontend component, execution engine, connector, integration and deployment.

You must follow these rules in every Antigravity development session.

These instructions take priority over convenience, implementation speed and unnecessary feature expansion.

---

# 2. EXISTING FUNCTIONALITY PROTECTION

DataForge is an actively developed application with multiple existing modules.

You MUST:

1. Inspect existing implementations before modifying them.
2. Reuse existing components, APIs, services and abstractions wherever possible.
3. Preserve existing functionality.
4. Maintain backward compatibility.
5. Understand dependencies before modifying shared components.
6. Avoid changing unrelated files.
7. Avoid replacing working implementations with newly generated alternatives.
8. Preserve existing database records and pipeline definitions.

You MUST NOT:

- Rebuild an already implemented module.
- Delete existing functionality without explicit approval.
- Replace an existing connector unnecessarily.
- Introduce duplicate services for the same responsibility.
- Rename existing APIs or database fields without a migration and compatibility plan.
- Perform large-scale refactoring without approval.

Before every significant modification, identify potential regressions.

---

# 3. STRICT SCOPE CONTROL

Work only on the feature and milestone currently approved by the user.

Do not:
- Implement future phases early.
- Introduce unrelated features.
- Expand the scope without approval.
- Modify unrelated UI screens.
- Introduce new technologies without justification.

If an architectural dependency requires changes outside the current milestone:

1. Explain why the dependency is necessary.
2. Identify affected modules.
3. Propose the smallest safe change.
4. Wait for approval if the change is substantial.

---

# 4. ARCHITECTURAL GUARDRAILS

Maintain:

- Separation of concerns.
- Modular architecture.
- Clear service boundaries.
- Reusable connector abstractions.
- Centralized configuration.
- Consistent exception handling.
- Structured logging.
- Explicit interfaces.
- Dependency injection where appropriate.

Avoid:
- Circular dependencies.
- Business logic inside frontend components.
- Business logic inside API route handlers.
- Excessive microservices.
- Unnecessary abstraction layers.
- Hardcoded credentials.
- Duplicate implementations.

For DataForge execution architecture:

- Control plane manages metadata, scheduling and orchestration.
- Execution plane performs actual workloads.
- Runtime workers execute data movement and transformations.
- Copy Engine remains independent of Spark.
- Spark executes distributed transformation workloads.
- SQL Pushdown executes supported database-side operations.
- Execution Planner coordinates engine selection.

Do not violate these architectural boundaries.

---

# 5. CODE QUALITY GUARDRAILS

Every implementation must:

1. Follow existing coding conventions.
2. Use meaningful names.
3. Include appropriate type definitions.
4. Validate inputs.
5. Handle exceptions properly.
6. Avoid unnecessary complexity.
7. Avoid repeated code.
8. Use appropriate logging.
9. Include comments for complex business logic.
10. Remove dead code introduced during implementation.

Never:
- Leave TODOs for functionality claimed as complete.
- Leave placeholder implementations.
- Use hardcoded successful API responses.
- Suppress exceptions without justification.
- Use empty catch blocks.
- Return success when execution failed.
- Hide errors from users.

---

# 6. DATABASE AND API GUARDRAILS

## Database

- Use migrations for every schema change.
- Never modify production schemas manually.
- Preserve existing records.
- Add appropriate indexes.
- Define foreign keys and constraints where appropriate.
- Avoid unnecessary schema duplication.
- Consider migration rollback and recovery.
- Test migrations against representative existing data.

## APIs

- Follow existing API conventions.
- Validate request and response schemas.
- Maintain API compatibility.
- Implement authentication and authorization.
- Return consistent error responses.
- Add pagination for large result sets.
- Avoid exposing internal secrets or sensitive information.

---

# 7. SECURITY GUARDRAILS

Security must be considered in every module.

Mandatory requirements:

- Never hardcode credentials.
- Never expose secrets in API responses.
- Never log passwords, tokens, access keys or connection strings.
- Use secure secret references.
- Validate authorization at the backend.
- Apply least-privilege access.
- Secure runtime-to-control-plane communication.
- Validate user-supplied file paths and expressions.
- Protect against SQL injection.
- Isolate user-submitted code execution.
- Apply execution timeouts and resource limits.
- Audit sensitive operations.

Do not claim that a feature is secure without testing the relevant security controls.

---

# 8. DATA ENGINEERING AND EXECUTION GUARDRAILS

These rules are especially important for DataForge.

## Memory Management

- Never load entire large datasets into application memory unnecessarily.
- Prefer bounded-memory streaming.
- Use configurable batch sizes.
- Implement backpressure where required.
- Close file handles, database cursors and network connections correctly.

## Data Integrity

- Prevent duplicate writes during retries.
- Implement idempotency where required.
- Maintain checkpoint consistency.
- Do not advance watermarks before successful destination commits.
- Handle partial failures.
- Validate source and destination record counts where applicable.
- Preserve data types and schema semantics.

## Parallel Processing

- Avoid unbounded concurrency.
- Respect source and destination connection limits.
- Implement concurrency controls.
- Handle partition-level failures.
- Avoid duplicate or missing records between partitions.

## Execution Engines

- Do not use Spark for ordinary Copy Activity execution.
- Do not force SQL Pushdown where unsupported.
- Do not select execution engines using data volume alone.
- Respect connector capabilities.
- Measure actual throughput and resource utilization.

---

# 9. FRONTEND GUARDRAILS

- Follow the existing DataForge design system.
- Maintain consistent navigation.
- Reuse existing components.
- Ensure responsive behavior.
- Implement real loading states.
- Implement meaningful empty states.
- Display backend errors correctly.
- Validate user input.
- Ensure buttons perform actual actions.
- Do not create non-functional UI controls.
- Do not introduce unnecessary visual changes to unrelated modules.

Every new screen must integrate with actual backend functionality.

---

# 10. TESTING GUARDRAILS

No feature can be declared complete without appropriate testing.

Required testing where applicable:

- Unit tests.
- API tests.
- Integration tests.
- Database migration tests.
- Frontend tests.
- End-to-end tests.
- Regression tests.
- Security tests.
- Performance tests.
- Failure recovery tests.

For data movement features, test:

- Empty datasets.
- Small datasets.
- Large datasets.
- Invalid schemas.
- Interrupted connections.
- Destination failures.
- Retry scenarios.
- Duplicate prevention.
- Memory utilization.

For performance claims, use actual measurements.

Never fabricate test results or benchmarks.

Clearly distinguish:
- Implemented.
- Unit tested.
- Integration tested.
- Manually verified.
- Tested against real infrastructure.
- Production ready.

---

# 11. PHASE AND MILESTONE CONTROL

All development must follow approved phases.

For every milestone:

1. Inspect existing implementation.
2. Define exact scope.
3. Identify affected files.
4. Identify dependencies.
5. Implement the smallest complete solution.
6. Run tests.
7. Fix issues.
8. Perform regression testing.
9. Update documentation.
10. Report results.

Stop after completing the approved milestone.

Never automatically start the next milestone.

Wait for explicit user approval.

---

# 12. FILE AND CHANGE MANAGEMENT

Before significant changes:

- Inspect Git status.
- Identify existing user modifications.
- Avoid overwriting uncommitted work.
- Do not delete files unnecessarily.
- Review the final diff.
- Identify generated files.
- Avoid committing secrets or local environment files.

Never run destructive commands without explicit approval.

Examples include:
- Dropping databases.
- Deleting production records.
- Removing directories recursively.
- Replacing environment configuration.
- Resetting Git history.

---

# 13. ERROR HANDLING AND RECOVERY

For every execution feature:

- Capture meaningful errors.
- Preserve execution context.
- Use correlation IDs.
- Implement retry policies carefully.
- Distinguish retryable and non-retryable errors.
- Prevent duplicate execution.
- Persist execution state.
- Support safe recovery.

Do not report success when only part of an operation completed.

---

# 14. DOCUMENTATION AND SESSION CONTINUITY

Maintain the following documentation:

- MASTER_ARCHITECTURE.md
- TECHNICAL_DECISIONS.md
- IMPLEMENTATION_ROADMAP.md
- MILESTONE_TRACKER.md
- TESTING_REPORT.md
- KNOWN_LIMITATIONS.md
- CHANGELOG.md

At the start of each development session:

1. Read this guardrails document.
2. Read the current implementation tracker.
3. Read technical decisions.
4. Inspect Git status.
5. Identify the last approved milestone.
6. Resume only from that milestone.

Update relevant documents after implementation.

---

# 15. MANDATORY COMPLETION REPORT

After every milestone, provide:

1. Milestone completed.
2. Features implemented.
3. Files created.
4. Files modified.
5. Database changes.
6. API changes.
7. Tests executed.
8. Actual test results.
9. Regression results.
10. Security considerations.
11. Known limitations.
12. Remaining work.
13. Recommendation for the next milestone.

Do not hide failed tests or incomplete work.

---

# 16. FINAL GOVERNANCE RULE

DataForge is intended to become an enterprise-grade product.

Prioritize:

1. Correctness.
2. Data integrity.
3. Security.
4. Reliability.
5. Performance.
6. Maintainability.
7. User experience.
8. Development speed.

Never sacrifice correctness or reliability to finish a milestone faster.

If requirements are unclear, inspect the existing architecture and ask for clarification rather than making risky assumptions.

These guardrails are mandatory for every future development task.
