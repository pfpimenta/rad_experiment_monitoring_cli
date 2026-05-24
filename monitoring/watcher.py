from pathlib import Path
from watchdog.events import FileSystemEventHandler

class LogChangeHandler(FileSystemEventHandler):
    """Listens for file updates and queues them for the monitor."""
    def __init__(self, monitor):
        self.monitor = monitor

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith('.log'):
            self.monitor.queue_update(Path(event.src_path))

    def on_created(self, event):
        if not event.is_directory and event.src_path.endswith('.log'):
            self.monitor.queue_update(Path(event.src_path))
