from __future__ import annotations

import os
from pathlib import Path
import shutil

from huggingface_hub import snapshot_download


MODEL_REPO = os.getenv("HF_MODEL_REPO", "openai/privacy-filter")
MODEL_REVISION = os.getenv(
    "HF_MODEL_REVISION",
    "57b51f4cffdc93db3fa5ed7065e362ca88e8e7e7",
)
TARGET = Path(os.getenv("OPF_MODEL_PATH", "/models/privacy-filter"))


def checkpoint_is_complete(path: Path) -> bool:
    return (
        (path / "config.json").is_file()
        and any(path.glob("*.safetensors"))
        and (path / ".model-revision").is_file()
        and (path / ".model-revision").read_text(encoding="utf-8").strip() == MODEL_REVISION
    )


def main() -> None:
    if checkpoint_is_complete(TARGET):
        print(f"Model checkpoint is ready at {TARGET}")
        return
    if TARGET.exists() and any(TARGET.iterdir()):
        raise RuntimeError(
            f"Checkpoint directory {TARGET} is incomplete or has a different revision; "
            "move it aside before retrying"
        )

    TARGET.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=MODEL_REPO,
        revision=MODEL_REVISION,
        local_dir=str(TARGET),
        allow_patterns=["original/*"],
    )
    original = TARGET / "original"
    if not original.is_dir():
        raise RuntimeError("Downloaded checkpoint does not contain original/")
    for source in original.iterdir():
        shutil.move(str(source), str(TARGET / source.name))
    original.rmdir()
    (TARGET / ".model-revision").write_text(MODEL_REVISION + "\n", encoding="utf-8")
    if not checkpoint_is_complete(TARGET):
        raise RuntimeError("Downloaded checkpoint failed validation")
    print(f"Downloaded pinned model revision {MODEL_REVISION} to {TARGET}")


if __name__ == "__main__":
    main()

