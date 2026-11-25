"""Учебная система управления задачами по структуре лекции № 5.

Сохранены основные классы и методы примера: User, Task, TaskManager,
Priority, Status, create_user, create_task, assign_task, generate_report.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class Priority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class Status(Enum):
    TODO = "To Do"
    IN_PROGRESS = "In Progress"
    REVIEW = "Review"
    DONE = "Done"


class User:
    def __init__(self, user_id: int, name: str, email: str):
        self.user_id = user_id
        self.name = name
        self.email = email


class Task:
    def __init__(self, task_id: int, title: str, description: str,
                 priority: Priority, due_date: datetime):
        self.task_id = task_id
        self.title = title
        self.description = description
        self.priority = priority
        self.due_date = due_date
        self.status = Status.TODO
        self.assignee: Optional[User] = None
        self.created_at = datetime.now()

    def assign_to(self, user: User) -> None:
        self.assignee = user
        self.status = Status.IN_PROGRESS

    def update_status(self, status: Status) -> None:
        self.status = status

    def is_overdue(self) -> bool:
        return datetime.now() > self.due_date


class TaskManager:
    """Минимальная реализация менеджера из лекции для запуска практики."""

    def __init__(self):
        self.tasks: Dict[int, Task] = {}
        self.users: Dict[int, User] = {}
        self.next_task_id = 1
        self.next_user_id = 1

    def create_user(self, name: str, email: str) -> User:
        user = User(self.next_user_id, name, email)
        self.users[user.user_id] = user
        self.next_user_id += 1
        return user

    def create_task(self, title: str, description: str,
                    priority: Priority, due_date: datetime) -> Task:
        if not title.strip():
            raise ValueError("Название задачи не может быть пустым")
        task = Task(self.next_task_id, title, description, priority, due_date)
        self.tasks[task.task_id] = task
        self.next_task_id += 1
        return task

    def assign_task(self, task_id: int, user_id: int) -> bool:
        task = self.tasks.get(task_id)
        user = self.users.get(user_id)
        if task is None or user is None:
            return False
        task.assign_to(user)
        return True

    def get_overdue_tasks(self) -> List[Task]:
        return [task for task in self.tasks.values() if task.is_overdue()]

    def get_user_tasks(self, user_id: int) -> List[Task]:
        return [task for task in self.tasks.values()
                if task.assignee and task.assignee.user_id == user_id]

    def generate_report(self) -> dict:
        distribution: Dict[str, int] = {}
        for task in self.tasks.values():
            distribution[task.status.value] = distribution.get(task.status.value, 0) + 1
        return {
            "total_tasks": len(self.tasks),
            "overdue_tasks": len(self.get_overdue_tasks()),
            "status_distribution": distribution,
            "report_generated_at": datetime.now().isoformat(),
        }
