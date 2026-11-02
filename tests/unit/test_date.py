
from datetime import datetime, timezone, timedelta
from accountsmachine.date import to_isoformat


class TestToIsoformat:

    def test_naive_datetime(self):
        dt = datetime(2024, 3, 15, 10, 30, 0)
        result = to_isoformat(dt)
        assert isinstance(result, str)
        assert "2024-03-15" in result

    def test_aware_datetime_utc(self):
        dt = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        result = to_isoformat(dt)
        assert result == "2024-03-15T10:30:00"

    def test_aware_datetime_offset(self):
        tz = timezone(timedelta(hours=2))
        dt = datetime(2024, 3, 15, 12, 30, 0, tzinfo=tz)
        result = to_isoformat(dt)
        assert result == "2024-03-15T10:30:00"

    def test_isoformat_string_input(self):
        result = to_isoformat("2024-03-15T10:30:00+00:00")
        assert result == "2024-03-15T10:30:00"

    def test_isoformat_string_with_offset(self):
        result = to_isoformat("2024-03-15T12:30:00+02:00")
        assert result == "2024-03-15T10:30:00"
