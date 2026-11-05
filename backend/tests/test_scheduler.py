from datetime import datetime, timezone
from backend.app.orchestration.scheduler import scheduler


def test_scheduler_cron_calculation():
    # Test calculating next run for hourly cron "0 * * * *"
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    next_time = scheduler.calculate_next_fire("0 * * * *", base)
    assert next_time == datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)

    # Test daily at midnight "0 0 * * *"
    next_midnight = scheduler.calculate_next_fire("0 0 * * *", base)
    assert next_midnight == datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
