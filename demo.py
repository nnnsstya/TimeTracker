"""Воспроизводимый пример использования модуля по заданию к лекции № 5."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from task_system import Priority, TaskManager
from time_tracker import TimeTracker


class DemonstrationClock:
    """Искусственные часы позволяют показать минуты без реального ожидания."""

    def __init__(self):
        self.value = datetime(2026, 11, 24, 10, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.value

    def advance(self, minutes: int):
        self.value += timedelta(minutes=minutes)


def main():
    manager = TaskManager()
    user = manager.create_user("Тестовый разработчик", "developer@example.com")
    task1 = manager.create_task(
        "Разработать API", "Создать интерфейс для системы задач",
        Priority.HIGH, datetime.now() + timedelta(days=14),
    )
    task2 = manager.create_task(
        "Написать тесты", "Покрыть основные функции тестами",
        Priority.MEDIUM, datetime.now() + timedelta(days=7),
    )
    manager.assign_task(task1.task_id, user.user_id)
    manager.assign_task(task2.task_id, user.user_id)

    clock = DemonstrationClock()
    with TimeTracker(manager, database_path=":memory:", clock=clock) as tracker:
        tracker.start_timer(task1.task_id)
        clock.advance(25)
        tracker.stop_timer(task1.task_id)
        tracker.start_timer(task1.task_id)
        clock.advance(15)
        tracker.stop_timer(task1.task_id)
        tracker.start_timer(task2.task_id)
        clock.advance(30)
        tracker.stop_timer(task2.task_id)

        report = tracker.generate_time_report()
        print("ОТЧЁТ ПО УЧЁТУ ВРЕМЕНИ")
        print("-" * 58)
        for task in report["tasks"]:
            print(f"{task['task_id']}. {task['title']}: {task['total_hhmmss']} "
                  f"(сеансов: {task['completed_sessions']})")
        print("-" * 58)
        print("Итого:", report["total_hhmmss"])
        output_dir = Path("results")
        csv_file = tracker.export_csv(output_dir / "time_report.csv")
        json_file = tracker.export_json(output_dir / "time_report.json")
        print("CSV:", csv_file)
        print("JSON:", json_file)


if __name__ == "__main__":
    main()
