from enum import Enum


class Role(Enum):
    BENCHMARK_OWNER = "BenchmarkOwner"
    DATA_OWNER = "DataOwner"
    MODEL_OWNER = "ModelOwner"
    NONE = None


class Status(Enum):
    APPROVED = "APPROVED"
    PENDING = "PENDING"
    REJECTED = "REJECTED"


class CaseInsensitiveEnum(str, Enum):
    @classmethod
    def _missing_(cls, value):
        """
        Example from Enum's documentation to make it case insensitive:
        https://docs.python.org/3/library/enum.html#enum.Enum._missing_
        """
        value = value.lower()
        for member in cls:
            if member.value == value:
                return member
        return None


class WorkflowTypes(CaseInsensitiveEnum):
    CWL = "cwl"


class ContainerRuntimes(CaseInsensitiveEnum):
    docker = "docker"
    singularity = "singularity"
