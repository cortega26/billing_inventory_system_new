from datetime import datetime

from utils.dates import parse_date_cell, parse_datetime_cell


def test_parse_datetime_cell_parses_iso_string():
    value = "2026-08-17T10:30:00"
    assert parse_datetime_cell({"created_at": value}, "created_at") == datetime(
        2026, 8, 17, 10, 30, 0
    )


def test_parse_datetime_cell_falls_back_to_now_when_empty():
    parsed = parse_datetime_cell({"created_at": ""}, "created_at")
    assert isinstance(parsed, datetime)
    assert (datetime.now() - parsed).total_seconds() < 5


def test_parse_datetime_cell_falls_back_when_key_missing():
    parsed = parse_datetime_cell({}, "created_at")
    assert isinstance(parsed, datetime)
    assert (datetime.now() - parsed).total_seconds() < 5


def test_parse_date_cell_parses_date_only_string():
    assert parse_date_cell({"date": "2026-08-17"}, "date") == datetime(2026, 8, 17)


def test_parse_date_cell_parses_iso_timestamp():
    assert parse_date_cell({"date": "2026-08-17T10:30:00"}, "date") == datetime(
        2026, 8, 17, 10, 30, 0
    )


def test_parse_date_cell_falls_back_when_empty():
    parsed = parse_date_cell({"date": None}, "date")
    assert isinstance(parsed, datetime)
    assert (datetime.now() - parsed).total_seconds() < 5
