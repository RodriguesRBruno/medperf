class RANOStage:
    def __init__(
        self,
        command: str,
        *command_args,
        task_id: str = None,
        task_display_name: str = None,
        **operator_kwargs,
    ):
        self.command = command
        self.command_args = command_args
        self.task_id = task_id or self.command
        self.task_display_name = (task_display_name or self.task_id) or self.command
        self.operator_kwargs = operator_kwargs
