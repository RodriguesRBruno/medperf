import yaml
from watchdog.events import FileSystemEventHandler, FileMovedEvent, FileCreatedEvent, FileModifiedEvent


class ReportState:
    def __init__(self, report_path: str, app):
        self.report_path = report_path
        self.app = app
        self.report = None

    def update(self):
        with open(self.report_path, "r") as f:
            report_dict = yaml.safe_load(f)

        if report_dict is not None and len(report_dict):
            self.report = report_dict
            self.__update_app()

    def __update_app(self):
        self.app.report = self.report


class ReportHandler(FileSystemEventHandler):
    def __init__(self, report_state: ReportState):
        self.report_state = report_state

    def _possible_report_update(self, possible_report_path: str):
        if possible_report_path == self.report_state.report_path:
            self.report_state.update()

    def on_created(self, event: FileCreatedEvent):
        self._possible_report_update(event.src_path)

    def on_modified(self, event: FileModifiedEvent):
        self._possible_report_update(event.src_path)

    def on_moved(self, event: FileMovedEvent):
        self._possible_report_update(event.dest_path)
