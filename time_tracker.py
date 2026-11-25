"""Модуль учёта времени для TaskManager из лекции № 5.

Возможности:
- запуск и остановка секундомера для задачи;
- накопление времени по нескольким сеансам;
- учёт текущего (ещё не остановленного) сеанса;
- отчёты по всем задачам, экспорт CSV и JSON;
- хранение сеансов в SQLite без сторонних библиотек.
"""
from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Union


DatabasePath = Union[str, Path]


def format_duration(seconds: float) -> str:
    """Переводит длительность в ЧЧ:ММ:СС (часы могут быть > 24)."""
    if seconds < 0:
        raise ValueError("Время не может быть отрицательным")
    total = round(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, remaining_seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}"


class TimeTracker:
    """Работает с любым менеджером задач, у которого есть словарь tasks.

    Экземпляр менеджера из лекции подходит без изменения его методов:
        tracker = TimeTracker(manager)
        tracker.start_timer(task.task_id)
        tracker.stop_timer(task.task_id)
    """

    def __init__(self, task_manager: object,
                 database_path: DatabasePath = "time_tracking.db",
                 clock: Optional[Callable[[], datetime]] = None):
        if not hasattr(task_manager, "tasks") or not isinstance(task_manager.tasks, dict):
            raise TypeError("Необходим TaskManager со словарём tasks")
        self.task_manager = task_manager
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._conn = sqlite3.connect(str(database_path))
        self._conn.row_factory = sqlite3.Row
        with self._conn:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS time_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    stopped_at TEXT,
                    duration_seconds REAL,
                    CHECK (duration_seconds IS NULL OR duration_seconds >= 0)
                )
            """)
            self._conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS one_running_timer_per_task
                ON time_entries(task_id) WHERE stopped_at IS NULL
            """)

    def close(self) -> None:
        """Закрывает соединение с хранилищем."""
        self._conn.close()

    def __enter__(self) -> "TimeTracker":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def _now(self) -> datetime:
        result = self._clock()
        if not isinstance(result, datetime):
            raise TypeError("Функция clock должна возвращать datetime")
        if result.tzinfo is None or result.utcoffset() is None:
            # Для совместимости с учебным кодом разрешаем наивный datetime:
            # интерпретируем его в UTC.
            result = result.replace(tzinfo=timezone.utc)
        return result.astimezone(timezone.utc)

    def _check_task(self, task_id: int) -> None:
        if isinstance(task_id, bool) or not isinstance(task_id, int):
            raise TypeError("ID задачи должен быть целым числом")
        if task_id not in self.task_manager.tasks:
            raise ValueError(f"Задача с ID {task_id} не найдена")

    def _running_entry(self, task_id: int) -> Optional[sqlite3.Row]:
        return self._conn.execute(
            "SELECT * FROM time_entries WHERE task_id = ? AND stopped_at IS NULL",
            (task_id,),
        ).fetchone()

    def is_running(self, task_id: int) -> bool:
        """Проверяет, запущен ли таймер конкретной задачи."""
        self._check_task(task_id)
        return self._running_entry(task_id) is not None

    def start_timer(self, task_id: int) -> int:
        """Запускает таймер и возвращает ID сеанса.

        Не разрешает запуск двух таймеров для одной задачи одновременно.
        """
        self._check_task(task_id)
        if self._running_entry(task_id) is not None:
            raise ValueError(f"Таймер задачи {task_id} уже запущен")
        started_at = self._now().isoformat()
        with self._conn:
            cursor = self._conn.execute(
                "INSERT INTO time_entries (task_id, started_at) VALUES (?, ?)",
                (task_id, started_at),
            )
        return int(cursor.lastrowid)

    def stop_timer(self, task_id: int) -> float:
        """Останавливает таймер; возвращает секунды завершённого сеанса."""
        self._check_task(task_id)
        entry = self._running_entry(task_id)
        if entry is None:
            raise ValueError(f"У задачи {task_id} нет запущенного таймера")
        stopped_at = self._now()
        started_at = datetime.fromisoformat(entry["started_at"])
        duration = (stopped_at - started_at).total_seconds()
        if duration < 0:
            raise ValueError("Время остановки раньше времени запуска")
        with self._conn:
            self._conn.execute(
                """UPDATE time_entries
                   SET stopped_at = ?, duration_seconds = ?
                   WHERE id = ?""",
                (stopped_at.isoformat(), duration, entry["id"]),
            )
        return duration

    def _totals(self, task_id: int, current_time: datetime) -> tuple[float, int, bool]:
        rows = self._conn.execute(
            "SELECT started_at, stopped_at, duration_seconds "
            "FROM time_entries WHERE task_id = ? ORDER BY id",
            (task_id,),
        ).fetchall()
        seconds = 0.0
        completed = 0
        running = False
        for entry in rows:
            if entry["stopped_at"] is None:
                running = True
                current_duration = (current_time - datetime.fromisoformat(entry["started_at"])).total_seconds()
                seconds += max(0.0, current_duration)
            else:
                completed += 1
                seconds += float(entry["duration_seconds"])
        return seconds, completed, running

    def get_total_time(self, task_id: int) -> float:
        """Возвращает секунды по задаче, включая работающий таймер."""
        self._check_task(task_id)
        return self._totals(task_id, self._now())[0]

    def generate_time_report(self) -> dict:
        """Формирует сводку по всем задачам, включая задачи с нулевым временем."""
        now = self._now()
        items = []
        total_seconds = 0.0
        for task_id, task in sorted(self.task_manager.tasks.items()):
            seconds, completed, running = self._totals(task_id, now)
            total_seconds += seconds
            items.append({
                "task_id": task_id,
                "title": task.title,
                "total_seconds": round(seconds, 2),
                "total_hhmmss": format_duration(seconds),
                "completed_sessions": completed,
                "timer_running": running,
            })
        return {
            "generated_at": now.isoformat(),
            "total_tasks": len(items),
            "total_seconds": round(total_seconds, 2),
            "total_hhmmss": format_duration(total_seconds),
            "tasks": items,
        }

    def export_csv(self, path: DatabasePath = "time_report.csv") -> Path:
        """Сохраняет отчёт в CSV с UTF-8 BOM для корректного открытия в Excel."""
        report = self.generate_time_report()
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8-sig", newline="") as output:
            writer = csv.writer(output, delimiter=";")
            writer.writerow(["ID задачи", "Название", "Затрачено, сек.",
                             "Всего (ч:м:с)", "Завершённых сеансов", "Таймер работает"])
            for task in report["tasks"]:
                writer.writerow([task["task_id"], task["title"],
                                 task["total_seconds"], task["total_hhmmss"],
                                 task["completed_sessions"],
                                 "Да" if task["timer_running"] else "Нет"])
            writer.writerow(["", "ИТОГО", report["total_seconds"],
                             report["total_hhmmss"], "", ""])
        return file_path

    def export_json(self, path: DatabasePath = "time_report.json") -> Path:
        """Сохраняет структурированный отчёт в JSON."""
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with file_path.open("w", encoding="utf-8") as output:
            json.dump(self.generate_time_report(), output,
                      ensure_ascii=False, indent=2)
        return file_path
