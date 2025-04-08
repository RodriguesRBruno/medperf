from threading import Lock
import os
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.singularity.operators.singularity import SingularityOperator
from docker.types import Mount
from abc import ABC, abstractmethod
from utils.rano_stage import RANOStage


class _SingletonMeta(type):
    """
    This is a thread-safe implementation of Singleton.
    """

    _instances = {}

    _lock: Lock = Lock()
    """
    We now have a lock object that will be used to synchronize threads during
    first access to the Singleton.
    """

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                instance = super().__call__(*args, **kwargs)
                cls._instances[cls] = instance
        return cls._instances[cls]


class _ContainerOperatorFactory(metaclass=_SingletonMeta):
    value: str = None
    """
    We'll use this property to prove that our Singleton really works.
    """
    _VALID_CONTAINER_TYPES = {"docker", "singularity"}

    def __init__(self, container_type: str, image: str) -> None:
        if container_type not in self.__class__._VALID_CONTAINER_TYPES:
            raise ValueError(
                f"Invalid container type! Must be one of {self.__class__._VALID_CONTAINER_TYPES}!"
            )

        if container_type == "docker":
            self._operator_factory = _DockerOperatorFactory(image)
        elif container_type == "singularity":
            self._operator_factory = _SingularityOperatorFactory(image)

    def get_operator(self, rano_stage: RANOStage):
        return self._operator_factory.get_operator(rano_stage)


class _OperatorFactory(ABC):

    def __init__(self, image_name: str):
        self.image_name = image_name

    @abstractmethod
    def _mount_returner(self, host_dir, container_dir):
        pass

    @abstractmethod
    def _operator_constructor(self, rano_stage: RANOStage, mounts):
        pass

    def _mount_helper(self, host_dirs: list[str], container_dirs: list[str]):
        host_dir = os.path.join(*host_dirs)
        container_dir = os.path.join(*container_dirs)
        return self._mount_returner(host_dir, container_dir)

    def get_operator(self, rano_stage: RANOStage):
        workspace_host_dir = os.getenv("WORKSPACE_DIRECTORY")

        mounts = [
            self._mount_helper(
                host_dirs=[workspace_host_dir], container_dirs=["/", "workspace"]
            )
        ]

        # Uncomment to mount project directory into the DockerOperator images. Used for development and debugging.
        # project_dir = os.getenv("PROJECT_DIRECTORY")
        # mounts.append(
        #     self._mount_helper(host_dirs=[project_dir], container_dirs=["/", "project"])
        # )

        return self._operator_constructor(rano_stage, mounts)


class _DockerOperatorFactory(_OperatorFactory):
    def _mount_returner(self, host_dir: str, container_dir: str) -> Mount:
        return Mount(source=host_dir, target=container_dir, type="bind")

    def _operator_constructor(
        self, rano_stage: RANOStage, mounts: list[Mount]
    ) -> DockerOperator:

        return DockerOperator(
            image=self.image_name,
            command=[rano_stage.command, *rano_stage.command_args],
            mounts=mounts,
            task_id=rano_stage.task_id,
            task_display_name=rano_stage.task_display_name,
            auto_remove="success",
            **rano_stage.operator_kwargs,
        )


class _SingularityOperatorFactory(_OperatorFactory):
    def _mount_returner(self, host_dir: str, container_dir: str) -> Mount:
        return ":".join([host_dir, container_dir])

    def _operator_constructor(
        self, rano_stage: RANOStage, mounts: list[str]
    ) -> SingularityOperator:

        command_args = list(
            rano_stage.command_args
        )  # Must be a list for Airflow's SingularityOperator
        return SingularityOperator(
            image=self.image_name,
            command=rano_stage.command,
            start_command=command_args,
            volumes=mounts,
            task_id=rano_stage.task_id,
            task_display_name=rano_stage.task_display_name,
            auto_remove=True,
            **rano_stage.operator_kwargs,
        )


ContainerOperatorFactory = _ContainerOperatorFactory(
    container_type=os.getenv("CONTAINER_TYPE"),
    image=os.getenv("RANO_DOCKER_IMAGE_NAME"),
)
