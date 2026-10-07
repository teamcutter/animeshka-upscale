from pathlib import Path
from uuid import UUID


class LocalFileStorage:
    def __init__(self, root: Path) -> None:
        self._inputs = root / "inputs"
        self._outputs = root / "outputs"
        self._inputs.mkdir(parents=True, exist_ok=True)
        self._outputs.mkdir(parents=True, exist_ok=True)

    def save_input(self, job_id: UUID, filename: str, data: bytes) -> Path:
        # Never trust the client filename: keep only its extension.
        path = self._inputs / f"{job_id}{Path(filename).suffix.lower()}"
        path.write_bytes(data)
        return path

    def output_path(self, job_id: UUID, suffix: str) -> Path:
        return self._outputs / f"{job_id}{suffix}"
