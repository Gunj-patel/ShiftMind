from datetime import date

from app.services.parser import (normalize_shift, parse_csv, parse_date, parse_excel, parse_number,
                                 parse_pdf, parse_text)

from conftest import SAMPLES


def test_parse_number_units_and_junk():
    assert parse_number("1.5 hrs") == 90
    assert parse_number("95 min") == 95
    assert parse_number("1,200") == 1200
    assert parse_number("n/a") is None
    assert parse_number("") is None


def test_parse_date_formats():
    assert parse_date("02/11/2026") == date(2026, 11, 2)
    assert parse_date("2026-11-02") == date(2026, 11, 2)
    assert parse_date("garbage") is None


def test_shift_aliases():
    assert normalize_shift("Morning") == "morning"
    assert normalize_shift("B") == "evening"
    assert normalize_shift("3") == "night"
    assert normalize_shift("weekend") is None


def test_csv_history():
    res = parse_csv((SAMPLES / "history_week.csv").read_bytes(), "h.csv")
    assert len(res.rows) == 7 * 3 * 5
    assert not res.rejected


def test_excel_messy_headers_and_units():
    res = parse_excel((SAMPLES / "daily_report_morning.xlsx").read_bytes(), "d.xlsx")
    assert len(res.rows) == 5
    m102 = next(r for r in res.rows if r["machine"] == "M-102")  # lower-case id normalised
    assert m102["downtime_min"] == 90  # "1.5 hrs"
    assert m102["maintenance_status"] == "pending"
    assert m102["shift"] == "morning" and m102["shift_date"] == date(2026, 11, 2)
    assert m102["rejected_units"] == 6  # "Scrap" alias


def test_text_blocks_carry_date_and_shift():
    res = parse_text((SAMPLES / "evening_notes.txt").read_text(), "e.txt")
    assert len(res.rows) == 4
    assert {r["shift"] for r in res.rows} == {"evening"}


def test_pdf():
    res = parse_pdf((SAMPLES / "night_report.pdf").read_bytes(), "n.pdf")
    assert res.kind == "pdf" and len(res.rows) == 5
    m104 = next(r for r in res.rows if r["machine"] == "M-104")
    assert m104["rejected_units"] == 35 and "Viscosity" in m104["quality_issue"]


def test_bad_rows_are_rejected_not_guessed():
    res = parse_text("Machine: M-1\nShift: purple\nDate: 2026-01-01\nActual: 5", "x")
    assert not res.rows and res.rejected and "shift" in res.rejected[0]["reason"]
