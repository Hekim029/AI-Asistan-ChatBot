from memory.user_memory import UserMemory
from services.reminder_manager import ReminderManager
from services.shared_workspace import SharedWorkspace
from services.task_manager import TaskManager


class SharedAssistantState:
    """Pencereler arasında paylaşılması gereken kalıcı servisleri tek yerde tutar."""

    def __init__(self):
        self.user_memory = UserMemory()
        self.reminders = ReminderManager()
        self.tasks = TaskManager()
        self.workspace = SharedWorkspace()
