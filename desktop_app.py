"""Графическое приложение учёта времени. Запуск: python desktop_app.py.

Окно использует Tkinter (стандартная библиотека). Бизнес-логика таймера
остаётся в TimeTracker, интегрированном с TaskManager из лекции № 5.
"""
from __future__ import annotations

import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox, ttk

from task_storage import TaskStorage
from task_system import Priority, Status
from time_tracker import TimeTracker, format_duration

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"

COLORS = {
    "bg": "#f3f5f9", "surface": "#ffffff", "navy": "#14213d",
    "body": "#31405a", "muted": "#78849b", "accent": "#3759df",
    "accent_hover": "#2945b9", "green": "#098a62", "line": "#e3e8f1",
    "orange": "#ad6617", "light": "#edf1ff",
}


class TimeTrackerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Учёт времени по задачам | Практическая работа № 5")
        self.geometry("1080x720")
        self.minsize(970, 680)
        self.configure(bg=COLORS["bg"])
        self.storage = TaskStorage(DATA_DIR / "tasks.json")
        try:
            self.manager = self.storage.load()
        except (ValueError, KeyError, OSError, TypeError) as exc:
            messagebox.showerror("Ошибка загрузки задач", f"Не удалось загрузить задачи:\n{exc}")
            self.destroy()
            return
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.tracker = TimeTracker(self.manager, database_path=DATA_DIR / "time_tracking.db")
        self._timer_job = None
        self._build_styles()
        self._build_window()
        self._refresh()
        self.protocol("WM_DELETE_WINDOW", self._close_app)
        self._schedule_refresh()

    def _build_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Task.Treeview", font=("Segoe UI", 11), rowheight=34,
                        background="white", fieldbackground="white", foreground=COLORS["body"],
                        borderwidth=0)
        style.configure("Task.Treeview.Heading", font=("Segoe UI", 10, "bold"),
                        foreground=COLORS["muted"], background=COLORS["bg"],
                        borderwidth=0, padding=(7, 12))
        style.map("Task.Treeview", background=[("selected", "#e6ecff")],
                  foreground=[("selected", COLORS["navy"])])

    def _make_label(self, parent, text, size=11, color="body", bold=False, bg=None):
        return tk.Label(parent, text=text, font=("Segoe UI", size, "bold" if bold else "normal"),
                        fg=COLORS.get(color, color), bg=bg or COLORS["surface"], anchor="w")

    def _button(self, parent, label, command, kind="main"):
        if kind == "main":
            bg, fg = COLORS["accent"], "#ffffff"
        elif kind == "success":
            bg, fg = COLORS["green"], "#ffffff"
        else:
            bg, fg = COLORS["light"], COLORS["navy"]
        return tk.Button(parent, text=label, command=command, bg=bg, fg=fg,
                         activebackground=bg, activeforeground=fg, font=("Segoe UI", 10, "bold"),
                         cursor="hand2", relief="flat", borderwidth=0, padx=19, pady=12)

    def _build_window(self):
        header = tk.Frame(self, bg=COLORS["navy"], padx=37, pady=17)
        header.pack(fill="x")
        self._make_label(header, "TASK TIME", 12, "#b8c8ff", True, COLORS["navy"]).pack(anchor="w")
        self._make_label(header, "Учёт времени по задачам", 23, "#ffffff", True,
                         COLORS["navy"]).pack(anchor="w", pady=(3, 2))
        self._make_label(header, "Практическая работа № 5 · Модуль для системы управления задачами",
                         10, "#c4cee0", False, COLORS["navy"]).pack(anchor="w")

        content = tk.Frame(self, bg=COLORS["bg"], padx=35, pady=15)
        content.pack(fill="both", expand=True)

        cards = tk.Frame(content, bg=COLORS["bg"])
        cards.pack(fill="x", pady=(0, 15))
        self.summary_values = {}
        for ix, (name, label) in enumerate([("tasks", "Задач"),
                                             ("running", "Активных таймеров"),
                                             ("time", "Общее время")]):
            card = tk.Frame(cards, bg=COLORS["surface"], padx=20, pady=15,
                            highlightbackground=COLORS["line"], highlightthickness=1)
            card.pack(side="left", fill="both", expand=True,
                      padx=(0, 12) if ix < 2 else (0, 0))
            self._make_label(card, label, 10, "muted").pack(anchor="w")
            value = self._make_label(card, "0", 24, "navy", True)
            value.pack(anchor="w", pady=(3, 0))
            self.summary_values[name] = value

        panel = tk.Frame(content, bg=COLORS["surface"], padx=17, pady=17,
                         highlightbackground=COLORS["line"], highlightthickness=1)
        panel.pack(fill="both", expand=True)
        titlebar = tk.Frame(panel, bg=COLORS["surface"])
        titlebar.pack(fill="x", pady=(0, 13))
        self._make_label(titlebar, "Мои задачи", 16, "navy", True).pack(side="left")
        self._button(titlebar, "+ Добавить задачу", self._add_task).pack(side="right")

        table_area = tk.Frame(panel, bg=COLORS["surface"])
        table_area.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_area, style="Task.Treeview", show="headings",
                                   columns=("id", "title", "status", "time", "sessions", "timer"),
                                   height=6, selectmode="browse")
        headings = {"id": "ID", "title": "Задача", "status": "Статус",
                    "time": "Затрачено", "sessions": "Сеансов", "timer": "Таймер"}
        widths = {"id": 46, "title": 355, "status": 120,
                  "time": 114, "sessions": 83, "timer": 145}
        for key, label in headings.items():
            self.table.heading(key, text=label, anchor="w")
            self.table.column(key, width=widths[key], minwidth=50, stretch=(key == "title"), anchor="w")
        scrollbar = ttk.Scrollbar(table_area, orient="vertical", command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        self.table.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.table.tag_configure("running", foreground=COLORS["green"])
        self.table.bind("<<TreeviewSelect>>", lambda _event: self._selection_changed())
        self.table.bind("<Double-1>", lambda _event: self._toggle_selected())
        self.table.focus_set()

        actions = tk.Frame(panel, bg=COLORS["surface"])
        actions.pack(fill="x", pady=(13, 0))
        self.start_btn = self._button(actions, "▶  Старт", self._start, "success")
        self.start_btn.pack(side="left", padx=(0, 10))
        self.stop_btn = self._button(actions, "■  Стоп", self._stop, "secondary")
        self.stop_btn.pack(side="left", padx=(0, 10))
        self.done_btn = self._button(actions, "✓  Завершить задачу", self._complete, "secondary")
        self.done_btn.pack(side="left")
        self._button(actions, "Экспорт CSV + JSON", self._export, "secondary").pack(side="right")
        self._button(actions, "Показать отчёт", self._show_report, "secondary").pack(side="right", padx=(0, 10))

        self.status_label = self._make_label(content,
            "Выбери задачу и нажми «Старт». Время сохраняется автоматически.", 10, "muted", bg=COLORS["bg"])
        self.status_label.pack(anchor="w", pady=(12, 0))
        self._selection_changed()

    def _schedule_refresh(self):
        self._timer_job = self.after(1000, self._tick)

    def _tick(self):
        self._timer_job = None
        self._refresh()
        self._schedule_refresh()

    def _refresh(self):
        report = self.tracker.generate_time_report()
        self.summary_values["tasks"].config(text=str(report["total_tasks"]))
        self.summary_values["running"].config(text=str(sum(t["timer_running"] for t in report["tasks"])))
        self.summary_values["time"].config(text=report["total_hhmmss"])
        selected = self.table.selection()
        selection_id = selected[0] if selected else None
        existing = set(self.table.get_children())
        status_map = {Status.TODO: "К выполнению", Status.IN_PROGRESS: "В работе",
                      Status.REVIEW: "Проверка", Status.DONE: "Завершена"}
        for item in report["tasks"]:
            key = str(item["task_id"])
            task = self.manager.tasks[item["task_id"]]
            values = (task.task_id, task.title, status_map[task.status], item["total_hhmmss"],
                      item["completed_sessions"], "● Работает" if item["timer_running"] else "Остановлен")
            tags = ("running",) if item["timer_running"] else ()
            if key in existing:
                self.table.item(key, values=values, tags=tags)
            else:
                self.table.insert("", "end", iid=key, values=values, tags=tags)
        if selection_id and self.table.exists(selection_id):
            self.table.selection_set(selection_id)
        self._selection_changed()

    def _selected_task_id(self):
        selection = self.table.selection()
        return int(selection[0]) if selection else None

    def _selection_changed(self):
        task_id = self._selected_task_id()
        if task_id is None:
            self.start_btn.config(state="disabled")
            self.stop_btn.config(state="disabled")
            self.done_btn.config(state="disabled")
            return
        running = self.tracker.is_running(task_id)
        self.start_btn.config(state="disabled" if running else "normal")
        self.stop_btn.config(state="normal" if running else "disabled")
        self.done_btn.config(state="normal")

    def _toggle_selected(self):
        task_id = self._selected_task_id()
        if task_id is not None:
            if self.tracker.is_running(task_id):
                self._stop()
            else:
                self._start()

    def _add_task(self):
        window = tk.Toplevel(self)
        window.title("Новая задача")
        window.geometry("480x260")
        window.resizable(False, False)
        window.configure(bg=COLORS["surface"])
        window.transient(self)
        window.grab_set()
        body = tk.Frame(window, bg=COLORS["surface"], padx=23, pady=19)
        body.pack(fill="both", expand=True)
        self._make_label(body, "Создать задачу", 18, "navy", True).pack(anchor="w", pady=(0, 14))
        self._make_label(body, "Название задачи", 10, "muted").pack(anchor="w")
        text = tk.StringVar()
        field = tk.Entry(body, textvariable=text, font=("Segoe UI", 13),
                         relief="solid", bd=1, highlightthickness=0)
        field.pack(fill="x", pady=(6, 16), ipady=7)
        field.focus_set()

        def save():
            title = text.get().strip()
            if not title:
                messagebox.showwarning("Название задачи", "Введите название задачи.", parent=window)
                return
            task = self.manager.create_task(title, "", Priority.MEDIUM,
                                            datetime.now() + timedelta(days=30))
            try:
                self.storage.save(self.manager)
            except OSError as exc:
                del self.manager.tasks[task.task_id]
                messagebox.showerror("Ошибка сохранения", str(exc), parent=window)
                return
            window.destroy()
            self._refresh()
            key = str(task.task_id)
            self.table.selection_set(key)
            self.table.see(key)
            self.status_label.config(text=f"Создана задача «{title}».")

        self._button(body, "Сохранить задачу", save).pack(anchor="e")
        window.bind("<Return>", lambda _event: save())

    def _start(self):
        task_id = self._selected_task_id()
        if task_id is None:
            return
        try:
            self.tracker.start_timer(task_id)
            self.manager.tasks[task_id].update_status(Status.IN_PROGRESS)
            self.storage.save(self.manager)
            self.status_label.config(text=f"Таймер запущен для задачи № {task_id}.")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Не удалось запустить таймер", str(exc))
        self._refresh()

    def _stop(self):
        task_id = self._selected_task_id()
        if task_id is None:
            return
        try:
            seconds = self.tracker.stop_timer(task_id)
            self.status_label.config(text=f"Сеанс задачи № {task_id} сохранён: {format_duration(seconds)}.")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Не удалось остановить таймер", str(exc))
        self._refresh()

    def _complete(self):
        task_id = self._selected_task_id()
        if task_id is None:
            return
        try:
            if self.tracker.is_running(task_id):
                messagebox.showwarning("Сначала останови таймер",
                                       "Чтобы завершить задачу, сначала нажми «Стоп».")
                return
            self.manager.tasks[task_id].update_status(Status.DONE)
            self.storage.save(self.manager)
            self.status_label.config(text=f"Задача № {task_id} завершена.")
        except OSError as exc:
            messagebox.showerror("Ошибка сохранения", str(exc))
        self._refresh()

    def _export(self):
        try:
            csv_path = self.tracker.export_csv(RESULTS_DIR / "time_report.csv")
            json_path = self.tracker.export_json(RESULTS_DIR / "time_report.json")
        except OSError as exc:
            messagebox.showerror("Ошибка экспорта", str(exc))
            return
        messagebox.showinfo("Отчёт сохранён",
                            f"Сохранены два файла:\n{csv_path}\n{json_path}")
        self.status_label.config(text="Экспорт выполнен. Файлы находятся в папке results.")

    def _show_report(self):
        report = self.tracker.generate_time_report()
        window = tk.Toplevel(self)
        window.title("Отчёт по затраченному времени")
        window.geometry("680x450")
        window.configure(bg=COLORS["surface"])
        content = tk.Frame(window, bg=COLORS["surface"], padx=23, pady=20)
        content.pack(fill="both", expand=True)
        self._make_label(content, "Отчёт по времени", 19, "navy", True).pack(anchor="w")
        self._make_label(content, f"Итого по {report['total_tasks']} задачам: {report['total_hhmmss']}",
                         12, "body").pack(anchor="w", pady=(7, 17))
        table = ttk.Treeview(content, style="Task.Treeview", show="headings",
                             columns=("name", "duration", "count", "active"))
        for key, text, width in [("name", "Задача", 350), ("duration", "Время", 100),
                                  ("count", "Сеансов", 90), ("active", "Таймер", 90)]:
            table.heading(key, text=text, anchor="w")
            table.column(key, width=width, anchor="w", stretch=(key == "name"))
        for item in report["tasks"]:
            table.insert("", "end", values=(item["title"], item["total_hhmmss"],
                                            item["completed_sessions"],
                                            "Работает" if item["timer_running"] else "Нет"))
        table.pack(fill="both", expand=True)
        self._button(content, "Сохранить CSV и JSON", self._export).pack(anchor="e", pady=(13, 0))

    def _close_app(self):
        if any(self.tracker.is_running(task_id) for task_id in self.manager.tasks):
            if not messagebox.askyesno("Таймер продолжит идти",
                    "Есть работающие таймеры. Даже после закрытия окна их время "
                    "будет учитываться до остановки при следующем запуске.\n\nЗакрыть приложение?"):
                return
        if self._timer_job is not None:
            self.after_cancel(self._timer_job)
        self.tracker.close()
        self.destroy()


def main():
    app = TimeTrackerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
