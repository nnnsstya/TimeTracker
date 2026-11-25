"""Сохранение задач интерфейса в JSON с сохранением исходных идентификаторов.

Это адаптер для учебного TaskManager. Сам класс TaskManager и интерфейс
TimeTracker менять не требуется.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from task_system import Priority, Status, TaskManager


class TaskStorage:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> TaskManager:
        manager = TaskManager()
        if not self.path.exists():
            return manager
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("tasks"), list):
            raise ValueError("Некорректный формат файла задач")
        for item in data["tasks"]:
            task_id = int(item["id"])
            if task_id <= 0 or task_id in manager.tasks:
                raise ValueError("Повторяющийся или неверный ID задачи")
            priority = Priority[item.get("priority", "MEDIUM")]
            due_date = datetime.fromisoformat(item["due_date"])
            task = manager.create_task(str(item["title"]),
                                       str(item.get("description", "")),
                                       priority, due_date)
            # Система из лекции выдаёт последовательные ID. Здесь сохраняем ID
            # из файла, чтобы сеансы в базе SQLite остались связаны с задачами.
            if task.task_id != task_id:
                del manager.tasks[task.task_id]
                task.task_id = task_id
                manager.tasks[task_id] = task
                manager.next_task_id = max(manager.next_task_id, task_id + 1)
            task.status = Status[item.get("status", "TODO")]
        manager.next_task_id = max(manager.tasks, default=0) + 1
        return manager

    def save(self, manager: TaskManager) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "tasks": [{
                "id": task.task_id,
                "title": task.title,
                "description": task.description,
                "priority": task.priority.name,
                "due_date": task.due_date.isoformat(),
                "status": task.status.name,
            } for task in sorted(manager.tasks.values(), key=lambda task: task.task_id)]
        }
        temp_file = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            temp_file.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                 encoding="utf-8")
            os.replace(temp_file, self.path)
        finally:
            if temp_file.exists():
                temp_file.unlink()
