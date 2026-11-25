"""Модульные и интеграционные тесты TimeTracker (стандартный unittest)."""
import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from task_system import Priority, TaskManager, Status
from time_tracker import TimeTracker, format_duration


class FakeClock:
    def __init__(self):
        self.value = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


class TimeTrackerTests(unittest.TestCase):
    def setUp(self):
        self.manager = TaskManager()
        self.user = self.manager.create_user("Тестер", "test@example.org")
        self.first = self.manager.create_task(
            "Сделать API", "", Priority.HIGH, datetime.now() + timedelta(days=2)
        )
        self.second = self.manager.create_task(
            "Написать тесты", "", Priority.MEDIUM, datetime.now() + timedelta(days=3)
        )
        self.clock = FakeClock()
        self.tracker = TimeTracker(self.manager, database_path=":memory:", clock=self.clock)
        self.addCleanup(self.tracker.close)

    def test_timer_start_and_stop(self):
        self.tracker.start_timer(self.first.task_id)
        self.assertTrue(self.tracker.is_running(self.first.task_id))
        self.clock.advance(90)
        self.assertEqual(self.tracker.stop_timer(self.first.task_id), 90)
        self.assertFalse(self.tracker.is_running(self.first.task_id))

    def test_total_time_from_several_sessions(self):
        for seconds in (600, 1200, 300):
            self.tracker.start_timer(self.first.task_id)
            self.clock.advance(seconds)
            self.tracker.stop_timer(self.first.task_id)
        self.assertEqual(self.tracker.get_total_time(self.first.task_id), 2100)
        self.assertEqual(self.tracker.generate_time_report()["tasks"][0]["completed_sessions"], 3)

    def test_running_time_included(self):
        self.tracker.start_timer(self.first.task_id)
        self.clock.advance(75)
        self.assertEqual(self.tracker.get_total_time(self.first.task_id), 75)
        self.assertTrue(self.tracker.generate_time_report()["tasks"][0]["timer_running"])

    def test_two_tasks_are_counted_separately(self):
        self.tracker.start_timer(self.first.task_id)
        self.clock.advance(30)
        self.tracker.start_timer(self.second.task_id)
        self.clock.advance(60)
        self.tracker.stop_timer(self.first.task_id)
        self.clock.advance(10)
        self.tracker.stop_timer(self.second.task_id)
        self.assertEqual(self.tracker.get_total_time(self.first.task_id), 90)
        self.assertEqual(self.tracker.get_total_time(self.second.task_id), 70)

    def test_double_start_for_same_task_forbidden(self):
        self.tracker.start_timer(self.first.task_id)
        with self.assertRaisesRegex(ValueError, "уже запущен"):
            self.tracker.start_timer(self.first.task_id)

    def test_stop_without_start_forbidden(self):
        with self.assertRaisesRegex(ValueError, "нет запущенного"):
            self.tracker.stop_timer(self.first.task_id)

    def test_unknown_task_forbidden(self):
        with self.assertRaisesRegex(ValueError, "не найдена"):
            self.tracker.start_timer(999)
        with self.assertRaisesRegex(ValueError, "не найдена"):
            self.tracker.get_total_time(999)

    def test_negative_duration_forbidden(self):
        self.tracker.start_timer(self.first.task_id)
        self.clock.advance(-2)
        with self.assertRaisesRegex(ValueError, "раньше"):
            self.tracker.stop_timer(self.first.task_id)
        self.assertTrue(self.tracker.is_running(self.first.task_id))

    def test_generated_report_totals(self):
        self.tracker.start_timer(self.first.task_id)
        self.clock.advance(3600)
        self.tracker.stop_timer(self.first.task_id)
        report = self.tracker.generate_time_report()
        self.assertEqual(report["total_tasks"], 2)
        self.assertEqual(report["total_hhmmss"], "01:00:00")
        self.assertEqual(report["tasks"][1]["total_seconds"], 0)

    def test_csv_and_json_exports(self):
        self.tracker.start_timer(self.first.task_id)
        self.clock.advance(150)
        self.tracker.stop_timer(self.first.task_id)
        with tempfile.TemporaryDirectory() as temp_dir:
            csv_path = self.tracker.export_csv(Path(temp_dir) / "report.csv")
            json_path = self.tracker.export_json(Path(temp_dir) / "report.json")
            with csv_path.open(encoding="utf-8-sig", newline="") as file:
                rows = list(csv.reader(file, delimiter=";"))
            self.assertEqual(rows[1][3], "00:02:30")
            self.assertEqual(rows[-1][1], "ИТОГО")
            with json_path.open(encoding="utf-8") as file:
                data = json.load(file)
            self.assertEqual(data["total_seconds"], 150)

    def test_sqlite_persists_entries_after_reopen(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "sessions.db"
            with TimeTracker(self.manager, db_path, self.clock) as first:
                first.start_timer(self.first.task_id)
                self.clock.advance(180)
                first.stop_timer(self.first.task_id)
            with TimeTracker(self.manager, db_path, self.clock) as reopened:
                self.assertEqual(reopened.get_total_time(self.first.task_id), 180)

    def test_integration_with_task_manager_from_lecture(self):
        self.assertTrue(self.manager.assign_task(self.first.task_id, self.user.user_id))
        self.assertEqual(self.first.status, Status.IN_PROGRESS)
        self.tracker.start_timer(self.first.task_id)
        self.clock.advance(30)
        self.tracker.stop_timer(self.first.task_id)
        self.assertEqual(self.manager.generate_report()["total_tasks"], 2)
        self.assertEqual(self.tracker.generate_time_report()["tasks"][0]["total_seconds"], 30)

    def test_duration_formatting(self):
        self.assertEqual(format_duration(3661), "01:01:01")
        self.assertEqual(format_duration(25 * 3600), "25:00:00")
        with self.assertRaises(ValueError):
            format_duration(-1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
