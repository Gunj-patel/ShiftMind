from datetime import date

from app.models.entities import ShiftRecord
from app.services.anomaly import evaluate_record


def rec(**kw):
    base = dict(id=1, shift_date=date(2026, 11, 2), shift="morning", machine="M-1", product="P",
                target_units=500, actual_units=500, downtime_min=0, rejected_units=5,
                raw_material_kg=60, downtime_reason="", quality_issue="", maintenance_status="", notes="")
    base.update(kw)
    return ShiftRecord(**base)


def rules(flags):
    return {f.rule: f for f in flags}


def test_clean_record_has_no_flags():
    assert evaluate_record(rec(), []) == []


def test_issue_example_from_brief():
    # Target 500, actual 320, downtime 95, motor overheating, maintenance pending
    f = rules(evaluate_record(rec(actual_units=320, downtime_min=95, downtime_reason="Motor overheating",
                                  maintenance_status="pending"), []))
    assert f["target_shortfall"].severity == "critical"
    assert "180 units below target" in f["target_shortfall"].message
    assert "64%" in f["target_shortfall"].evidence
    assert f["high_downtime"].severity == "warning"
    assert f["maintenance_pending"].severity == "critical"


def test_data_integrity_rules():
    f = rules(evaluate_record(rec(downtime_min=900, actual_units=10, rejected_units=50, raw_material_kg=-1), []))
    assert "impossible_downtime" in f and "rejects_exceed_output" in f and "negative_value" in f


def test_missing_values():
    f = rules(evaluate_record(rec(actual_units=None, downtime_min=30), []))
    assert "missing_actual" in f and "missing_downtime_reason" in f


def test_reject_rate_thresholds():
    assert rules(evaluate_record(rec(rejected_units=20), []))["high_reject_rate"].severity == "warning"
    assert rules(evaluate_record(rec(rejected_units=60), []))["high_reject_rate"].severity == "critical"


def test_statistical_outlier_needs_history_and_variance():
    hist = [rec(id=10 + i, shift_date=date(2026, 10, 20 + i), actual_units=500 + (i % 3)) for i in range(6)]
    f = rules(evaluate_record(rec(id=99, actual_units=380), hist))
    assert "production_outlier" in f
    assert "production_outlier" not in rules(evaluate_record(rec(id=99, actual_units=380), hist[:3]))


def test_repeat_failure():
    hist = [rec(id=20, shift_date=date(2026, 10, 30), downtime_min=80, downtime_reason="Motor overheating"),
            rec(id=21, shift_date=date(2026, 11, 1), downtime_min=80, downtime_reason="motor overheating")]
    f = rules(evaluate_record(rec(id=30, downtime_min=80, downtime_reason="Motor overheating"), hist))
    assert f["repeat_failure"].severity == "critical"
