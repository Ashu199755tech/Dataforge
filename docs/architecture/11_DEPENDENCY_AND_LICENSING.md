# DataFlow Enterprise — Dependency & Licensing Inventory

## 1. Open Source Licensing Policy
DataFlow Enterprise adheres strictly to permissive open source licensing (MIT, Apache 2.0, BSD-3-Clause) to guarantee unencumbered commercial use, redistribution, and proprietary SaaS deployment. Strong copyleft licenses (GPL, AGPL) are prohibited in core platform modules.

---

## 2. Backend Dependency Inventory (Python 3.12+)

| Package | Version | License | Justification |
| :--- | :--- | :--- | :--- |
| `fastapi` | ^0.115.0 | MIT | Modern, high-performance async web framework for REST & WebSockets. |
| `uvicorn` | ^0.31.0 | BSD-3-Clause | Production ASGI server. |
| `pydantic` | ^2.9.0 | MIT | High-speed data validation and settings management. |
| `sqlalchemy` | ^2.0.35 | MIT | Enterprise-grade ORM and SQL toolkit with dialect abstractions. |
| `alembic` | ^1.13.0 | MIT | Database schema migrations for PostgreSQL. |
| `psycopg2-binary` | ^2.9.9 | LGPL w/ exception | Standard PostgreSQL driver. |
| `pymysql` | ^1.1.1 | MIT | Pure-Python MySQL client driver. |
| `cryptography` | ^43.0.0 | Apache 2.0 / BSD | Enterprise encryption for connection secrets (AES-256-GCM / Fernet). |
| `python-jose` | ^3.3.0 | MIT | Cryptographic JWT token generation and verification. |
| `passlib[bcrypt]` | ^1.7.4 | BSD | Industry-standard password hashing. |
| `pytest` | ^8.3.0 | MIT | Automated testing framework. |
| `pytest-asyncio`| ^0.24.0 | Apache 2.0 | Async test harness for FastAPI endpoints. |

---

## 3. Frontend Dependency Inventory (React 18 + TypeScript)

| Package | Version | License | Justification |
| :--- | :--- | :--- | :--- |
| `react` / `react-dom` | ^18.3.1 | MIT | Core UI library. |
| `@xyflow/react` (React Flow) | ^12.3.0 | MIT | Leading drag-and-drop node graph canvas for visual workflow authoring. |
| `vite` | ^5.4.0 | MIT | Next-generation frontend tooling and bundler. |
| `typescript` | ^5.6.0 | Apache 2.0 | Static type safety. |
| `tailwindcss` | ^3.4.0 | MIT | Utility-first CSS framework for enterprise styling. |
| `lucide-react` | ^0.450.0 | ISC | Crisp, neutral, modern icon library (avoids proprietary cloud vendor icons). |
| `zustand` | ^5.0.0 | MIT | Lightweight, boilerplate-free state management. |
| `@tanstack/react-query`| ^5.59.0 | MIT | Server-state management and caching. |
| `axios` | ^1.7.0 | MIT | HTTP client for REST communication. |
| `recharts` | ^2.13.0 | MIT | Enterprise dashboard analytics charts. |
| `clsx` / `tailwind-merge` | ^2.0.0 | MIT | Dynamic Tailwind class utilities. |

---

## 4. IP Protection & Non-Infringement Statement
- **Zero Proprietary Code**: No Microsoft, Azure, or competitor proprietary code, schemas, or assets are utilized.
- **Independent Visual Language**: UI layouts, nodes, connectors, and canvas interactions are designed from scratch using neutral design patterns.
- **Configurable Branding**: The product brand "DataFlow Enterprise" is completely modular and can be rebranded or white-labeled via environment variables.
