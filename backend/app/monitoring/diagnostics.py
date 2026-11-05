import os
import socket
import platform
import threading
import traceback
from typing import Dict, Any, Optional


def get_worker_telemetry() -> Dict[str, Any]:
    """Collects current process and host environment metrics for the execution worker."""
    hostname = socket.gethostname()
    try:
        host_ip = socket.gethostbyname(hostname)
    except Exception:
        host_ip = "127.0.0.1"

    return {
        "hostname": hostname,
        "host_ip": host_ip,
        "pid": os.getpid(),
        "thread_id": threading.get_ident(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "process_title": "DataFlow-Worker-Runner"
    }


def classify_error(err: Any) -> str:
    """
    Classifies errors into standard enterprise diagnostic categories:
    - ConnectionError: Database connection failures, socket resets, network timeouts.
    - TimeoutError: SLA exceeded, query execution or HTTP request timeout.
    - DataQualityError: Threshold violations, null/duplicate check failures, schema drift.
    - UserError: Syntax errors, missing parameters, invalid expressions, invalid file paths.
    - SystemError: Unhandled runtime errors, out-of-memory, engine crashes.
    """
    if err is None:
        return "Unknown"

    err_str = str(err).lower()
    err_type = type(err).__name__ if isinstance(err, Exception) else ""

    # Timeout
    if "timeout" in err_str or "timed out" in err_str or "timeouterror" in err_type.lower():
        return "TimeoutError"

    # Connection
    if any(k in err_str for k in [
        "connection refused", "connect error", "connection reset", "could not connect",
        "operationalerror", "socket", "network is unreachable", "failed to establish a new connection",
        "name or service not known", "psycopg2.operationalerror", "pymysql.err.operationalerror"
    ]):
        return "ConnectionError"

    # Data Quality
    if any(k in err_str for k in [
        "data quality", "dq check failed", "quarantine threshold", "assertionerror",
        "reconciliation mismatch", "schema drift detected", "validation failed"
    ]):
        return "DataQualityError"

    # User / Configuration
    if any(k in err_str for k in [
        "syntaxerror", "expressionerror", "keyerror", "filenotfounderror",
        "parameter", "missing required", "invalid argument", "dagvalidationerror",
        "valueerror", "typeerror", "bad request", "404 not found", "400 bad request"
    ]):
        return "UserError"

    # System
    return "SystemError"


def extract_stack_trace(err: Any) -> Optional[str]:
    """Extracts a clean, formatted stack trace string from an exception."""
    if isinstance(err, Exception):
        return "".join(traceback.format_exception(type(err), err, err.__traceback__))
    elif isinstance(err, str) and "Traceback" in err:
        return err
    return None
