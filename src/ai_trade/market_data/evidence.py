"""Exclusive per-run local evidence files; no credentials or HTTP interception."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pandas as pd

from ai_trade.data_access.models import DuplicateRecordError
from ai_trade.data_access.validation import text_field
from ai_trade.market_data.models import EvidenceWriteError


class EvidenceStore:
    """Preserve SDK-level responses; these are not original HTTP response bytes.

    The directory name is a hash, so an untrusted run_id cannot escape the root.
    Files are create-only. Hashes detect accidental corruption, not malicious edits.
    """

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    @staticmethod
    def _write(path: Path, payload: bytes) -> None:
        with path.open("xb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())

    def begin(self, run_id: str, request: dict[str, Any]) -> Path:
        text_field(run_id, "run_id")
        folder = self.root / hashlib.sha256(run_id.encode()).hexdigest()
        try:
            self.root.mkdir(parents=True, exist_ok=True)
            folder.mkdir()
        except FileExistsError as exc:
            raise DuplicateRecordError(f"evidence run_id already used: {run_id}") from exc
        except OSError as exc:
            raise EvidenceWriteError("cannot reserve ingestion evidence directory") from exc
        try:
            self._write(folder / "request.json", self._json(request))
        except OSError as exc:
            raise EvidenceWriteError(f"cannot write request evidence: {folder}") from exc
        return folder

    @staticmethod
    def _json(value: object) -> bytes:
        return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")

    def response(self, folder: Path, frame: pd.DataFrame) -> str:
        """Archive the SDK frame before mapping; JSON null represents NaN/NaT/None."""
        # A split representation preserves duplicate column names for schema diagnosis.
        try:
            payload = self._json({
                "format": "akshare-sdk-dataframe-v1", "not_raw_http": True,
                "serialization": "pandas split JSON; non-finite and missing scalars may become null",
                "dtypes": [str(dtype) for dtype in frame.dtypes],
                "frame": json.loads(frame.to_json(orient="split", date_format="iso", double_precision=15)),
            })
            self._write(folder / "response.json", payload)
        except (OSError, TypeError, ValueError, OverflowError) as exc:
            raise EvidenceWriteError(f"cannot archive SDK response: {folder}") from exc
        return hashlib.sha256(payload).hexdigest()

    def finish(self, folder: Path, result: dict[str, Any], *, database_committed: bool) -> None:
        try:
            self._write(folder / "result.json", self._json(result))
        except OSError as exc:
            raise EvidenceWriteError(
                f"cannot finalize evidence: {folder}; inspect database before retrying",
                database_committed=database_committed,
            ) from exc
