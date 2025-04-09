from threading import Lock
import os
from airflow.providers.docker.operators.docker import DockerOperator
from airflow.providers.singularity.operators.singularity import SingularityOperator
from docker.types import Mount
from abc import ABC, abstractmethod


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

    def get_operator(self, *commands, **kwargs):
        return self._operator_factory.get_operator(*commands, **kwargs)


class _OperatorFactory(ABC):

    def __init__(self, image_name: str):
        self.image_name = image_name

    @abstractmethod
    def _mount_returner(self, host_di: str, container_dir: str):
        pass

    @abstractmethod
    def _operator_constructor(
        self, *commands: str, mounts: list[Mount | str], **kwargs
    ):
        pass

    def _mount_helper(self, host_dirs: list[str], container_dirs: list[str]):
        host_dir = os.path.join(*host_dirs)
        container_dir = os.path.join(*container_dirs)
        return self._mount_returner(host_dir, container_dir)

    def get_operator(self, *commands: str, **kwargs):
        workspace_host_dir = os.getenv("HOST_WORKSPACE_DIRECTORY")
        data_host_dir = os.getenv("HOST_DATA_DIRECTORY")
        input_data_host_dir = os.getenv("HOST_INPUT_DATA_DIRECTORY")
        mounts = [
            self._mount_helper(
                host_dirs=[workspace_host_dir], container_dirs=["/", "workspace"]
            ),
            self._mount_helper(
                host_dirs=[data_host_dir], container_dirs=["/", "workspace", "data"]
            ),
            self._mount_helper(
                host_dirs=[input_data_host_dir],
                container_dirs=["/", "workspace", "input_data"],
            ),
        ]

        # Uncomment to mount project directory into the DockerOperator images. Used for development and debugging.
        # project_dir = os.getenv("PROJECT_DIRECTORY")
        # mounts.append(
        #     self._mount_helper(host_dirs=[project_dir], container_dirs=["/", "project"])
        # )

        return self._operator_constructor(*commands, mounts=mounts, **kwargs)


class _DockerOperatorFactory(_OperatorFactory):
    def _mount_returner(self, host_dir: str, container_dir: str) -> Mount:
        return Mount(source=host_dir, target=container_dir, type="bind")

    def _operator_constructor(
        self, *commands: str, mounts: list[Mount | str], **kwargs
    ) -> DockerOperator:

        return DockerOperator(
            image=self.image_name,
            command=list(commands),
            mounts=mounts,
            auto_remove="success",
            **kwargs,
        )


class _SingularityOperatorFactory(_OperatorFactory):
    def _mount_returner(self, host_dir: str, container_dir: str) -> Mount:
        return ":".join([host_dir, container_dir])

    def _operator_constructor(
        self, *commands: str, mounts: list[Mount | str], **kwargs
    ) -> SingularityOperator:

        command_args = list(
            commands[1:]
        )  # Must be a list for Airflow's SingularityOperator
        return SingularityOperator(
            image=self.image_name,
            command=commands[0],
            start_command=command_args,
            auto_remove=True,
            volumes=mounts,
            **kwargs,
        )


ContainerOperatorFactory = _ContainerOperatorFactory(
    container_type=os.getenv("CONTAINER_TYPE"),
    image=os.getenv("RANO_DOCKER_IMAGE_NAME"),
)
