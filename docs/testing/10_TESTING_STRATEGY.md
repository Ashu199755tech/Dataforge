# DataFlow Enterprise — Testing Strategy & Verification Plan

## 1. Testing Pyramid
DataFlow Enterprise employs an automated, multi-tiered testing strategy:

1. **Unit Tests (Fast, Isolated)**:
   - DAG engine topological sorting, cycle detection, dependency satisfaction.
   - Pydantic schema validation for complex pipeline JSON models.
   - Symmetric cryptographic encryption/decryption of connection configs.
   - Column mapping and data type casting logic.

2. **Integration Tests (Subsystem Verification)**:
   - Pluggable connector test suite: PostgreSQL, MySQL, and SQLite drivers.
   - Live schema discovery (catalog discovery, table listing, column type inference).
   - Execution state machine transitions and retry policy triggers.

3. **End-to-End Functional Tests (Full Lifecycle Pipeline Execution)**:
   - Seed test source database (MySQL) with mock customer order records.
   - Create and save pipeline with `CopyData` activity via API.
   - Trigger manual execution and observe activity runs, logs, and row counters.
   - Verify that destination database (PostgreSQL) contains exact row count and matching checksums.
   - Test incremental loading: insert new records in MySQL, re-run with watermark filter, verify only delta records are transferred.

4. **Frontend Verification**:
   - TypeScript compile-time type verification (`tsc --noEmit`).
   - Vite production bundle build verification (`vite build`).
   - Component rendering and visual workflow layout checks.

---

## 2. Test Execution Commands
- Backend Pytest Suite:
  ```bash
  pytest backend/tests/ -v
  ```
- End-to-End Ingestion Verification Script:
  ```bash
  python3 scripts/run_mvp_verification.py
  ```
- Frontend Production Build:
  ```bash
  cd frontend && npm run build
  ```
