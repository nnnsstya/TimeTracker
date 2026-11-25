"""Проверка сохранения и восстановления задач для оконного приложения."""
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from task_storage import TaskStorage
from task_system import Priority, Status
from time_tracker import TimeTracker


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "tasks.json"
        self.store = TaskStorage(self.path)

    def test_save_and_load_tasks(self):
        manager = self.store.load()
        task = manager.create_task("Тестовая задача", "Описание", Priority.HIGH,
                                   datetime.now() + timedelta(days=2))
        task.update_status(Status.IN_PROGRESS)
        self.store.save(manager)
        restored = self.store.load()
        self.assertEqual(restored.tasks[1].title, "Тестовая задача")
        self.assertEqual(restored.tasks[1].status, Status.IN_PROGRESS)
        self.assertEqual(restored.tasks[1].priority, Priority.HIGH)

    def test_ids_stable_with_time_records(self):
        manager = self.store.load()
        task = manager.create_task("Время", "", Priority.MEDIUM,
                                   datetime.now() + timedelta(days=2))
        self.store.save(manager)
        db = Path(self.temporary.name) / "time.db"
        with TimeTracker(manager, db) as tracker:
            tracker.start_timer(task.task_id)
            tracker.stop_timer(task.task_id)
        manager2 = self.store.load()
        self.assertIn(task.task_id, manager2.tasks)
        with TimeTracker(manager2, db) as tracker:
            self.assertEqual(tracker.generate_time_report()["tasks"][0]["completed_sessions"], 1)

    def test_next_id_after_restart(self):
        manager = self.store.load()
        manager.create_task("Первая", "", Priority.MEDIUM, datetime.now())
        self.store.save(manager)
        restored = self.store.load()
        task2 = restored.create_task("Вторая", "", Priority.MEDIUM, datetime.now())
        self.assertEqual(task2.task_id, 2)

    def test_invalid_storage_rejected(self):
        self.path.write_text('{"tasks": "wrong"}', encoding="utf-8")
        with self.assertRaises(ValueError):
            self.store.load()


if __name__ == "__main__":
    unittest.main()
