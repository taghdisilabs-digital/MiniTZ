"""Active Biella runtime interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict

from .artifact import ArtifactRef as ArtifactRef


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _require_artifact_ref(value: object) -> "ArtifactRef":
    if not isinstance(value, ArtifactRef):
        raise TypeError("Only ArtifactRef may enter runtime reference fields")
    return value


@dataclass(frozen=True)
class ActiveArtifact:
    ref: ArtifactRef
    created_at: str = field(default_factory=_now_utc, init=False)

    def __post_init__(self) -> None:
        _require_artifact_ref(self.ref)


@dataclass(frozen=True)
class TaskContext:
    artifact_ref: ArtifactRef
    created_at: str = field(default_factory=_now_utc, init=False)

    def __post_init__(self) -> None:
        _require_artifact_ref(self.artifact_ref)


@dataclass(frozen=True)
class ProjectKnowledgeRecord:
    artifact_ref: ArtifactRef
    created_at: str = field(default_factory=_now_utc, init=False)

    def __post_init__(self) -> None:
        _require_artifact_ref(self.artifact_ref)


@dataclass(frozen=True)
class EngineKnowledgeRecord:
    artifact_ref: ArtifactRef
    created_at: str = field(default_factory=_now_utc, init=False)

    def __post_init__(self) -> None:
        _require_artifact_ref(self.artifact_ref)


@dataclass(frozen=True)
class RetrievalRecord:
    artifact_ref: ArtifactRef
    created_at: str = field(default_factory=_now_utc, init=False)

    def __post_init__(self) -> None:
        _require_artifact_ref(self.artifact_ref)


class ActiveArtifactStore:
    def __init__(self) -> None:
        self._artifacts: Dict[str, ActiveArtifact] = {}

    def add(self, artifact_ref: ArtifactRef) -> ActiveArtifact:
        _require_artifact_ref(artifact_ref)
        artifact = ActiveArtifact(ref=artifact_ref)
        self._artifacts[artifact_ref.value] = artifact
        return artifact

    def get(self, artifact_ref: ArtifactRef) -> ActiveArtifact:
        _require_artifact_ref(artifact_ref)
        return self._artifacts[artifact_ref.value]


class ProjectMemory:
    def __init__(self) -> None:
        self._records: Dict[str, ProjectKnowledgeRecord] = {}

    def add_record(self, record: ProjectKnowledgeRecord) -> None:
        if not isinstance(record, ProjectKnowledgeRecord):
            raise TypeError("ProjectMemory expects ProjectKnowledgeRecord")
        _require_artifact_ref(record.artifact_ref)
        self._records[record.artifact_ref.value] = record

    def get(self, artifact_ref: ArtifactRef) -> ProjectKnowledgeRecord:
        _require_artifact_ref(artifact_ref)
        return self._records[artifact_ref.value]


class EngineKnowledge:
    def __init__(self) -> None:
        self._facts: Dict[str, EngineKnowledgeRecord] = {}

    def add_fact(self, record: EngineKnowledgeRecord) -> None:
        if not isinstance(record, EngineKnowledgeRecord):
            raise TypeError("EngineKnowledge expects EngineKnowledgeRecord")
        _require_artifact_ref(record.artifact_ref)
        self._facts[record.artifact_ref.value] = record

    def get(self, artifact_ref: ArtifactRef) -> EngineKnowledgeRecord:
        _require_artifact_ref(artifact_ref)
        return self._facts[artifact_ref.value]


class RetrievalIndex:
    def __init__(self) -> None:
        self._index: Dict[str, RetrievalRecord] = {}

    def add(self, record: RetrievalRecord) -> None:
        if not isinstance(record, RetrievalRecord):
            raise TypeError("RetrievalIndex expects RetrievalRecord")
        _require_artifact_ref(record.artifact_ref)
        self._index[record.artifact_ref.value] = record


class ActiveRuntime:
    def __init__(self) -> None:
        self.artifacts = ActiveArtifactStore()
        self.project_memory = ProjectMemory()
        self.engine_knowledge = EngineKnowledge()
        self.retrieval = RetrievalIndex()

    def bind_task_context(self, artifact_ref: ArtifactRef) -> TaskContext:
        _require_artifact_ref(artifact_ref)
        return TaskContext(artifact_ref=artifact_ref)

    def register_artifact(self, artifact_ref: ArtifactRef) -> ActiveArtifact:
        _require_artifact_ref(artifact_ref)
        return self.artifacts.add(artifact_ref)
