from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

CATEGORIES = ("invoice", "important", "spam", "other")
_MAX_FILENAME_LEN = 200


@dataclass
class SavedFile:
    original_filename: str
    saved_path: Path
    category: str
    size: int
    checksum: str


@dataclass
class StorageResult:
    saved: list[SavedFile] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class StorageService:
    """
    Manages categorized file storage.

    Layout:
        {base_dir}/invoices/
        {base_dir}/important/
        {base_dir}/spam/
        {base_dir}/other/
    """

    _CATEGORY_DIRS = {
        "invoice": "invoices",
        "important": "important",
        "spam": "spam",
        "other": "other",
    }

    def __init__(self, base_dir: str | Path = "storage") -> None:
        self._base = Path(base_dir)
        self._ensure_dirs()

    # ── Public ────────────────────────────────────────────────────────────────

    def save_attachment(
        self,
        data: bytes,
        filename: str,
        category: str,
        sender: str = "",
        email_date: Optional[datetime] = None,
    ) -> SavedFile | None:
        if not data:
            logger.warning("Empty attachment data for %s — skipping", filename)
            return None

        category = self._normalise_category(category)
        target_dir = self._category_dir(category)
        safe_name = self._sanitise_filename(filename)
        checksum = _sha256(data)

        # Skip exact duplicate (same name + same content)
        if self._is_duplicate(target_dir, safe_name, checksum):
            logger.info("Duplicate file skipped: %s", safe_name)
            return None

        # Resolve name collision (different content, same name)
        final_path = self._resolve_collision(target_dir, safe_name)

        try:
            final_path.write_bytes(data)
        except OSError as exc:
            logger.error("Failed to write %s: %s", final_path, exc)
            raise

        saved = SavedFile(
            original_filename=filename,
            saved_path=final_path,
            category=category,
            size=len(data),
            checksum=checksum,
        )
        logger.info("Saved %s → %s (%d bytes)", filename, final_path, len(data))
        return saved

    def save_attachments(
        self,
        attachments: list[tuple[str, bytes]],
        category: str,
        sender: str = "",
        email_date: Optional[datetime] = None,
    ) -> StorageResult:
        result = StorageResult()
        for filename, data in attachments:
            try:
                saved = self.save_attachment(data, filename, category, sender, email_date)
                if saved is None:
                    result.skipped.append(filename)
                else:
                    result.saved.append(saved)
            except Exception as exc:
                msg = f"{filename}: {exc}"
                result.errors.append(msg)
                logger.error("Error saving attachment %s: %s", filename, exc)
        return result

    def category_path(self, category: str) -> Path:
        return self._category_dir(self._normalise_category(category))

    def list_files(self, category: str) -> list[Path]:
        return sorted(self._category_dir(self._normalise_category(category)).iterdir())

    # ── Private ───────────────────────────────────────────────────────────────

    def _ensure_dirs(self) -> None:
        for dirname in self._CATEGORY_DIRS.values():
            (self._base / dirname).mkdir(parents=True, exist_ok=True)

    def _category_dir(self, category: str) -> Path:
        return self._base / self._CATEGORY_DIRS[category]

    @staticmethod
    def _normalise_category(category: str) -> str:
        cat = category.lower().strip()
        return cat if cat in CATEGORIES else "other"

    @staticmethod
    def _sanitise_filename(name: str) -> str:
        name = re.sub(r'[\\/:*?"<>|]', "_", name)
        name = re.sub(r"\s+", "_", name.strip())
        name = name[:_MAX_FILENAME_LEN]
        return name or "unnamed_file"

    @staticmethod
    def _is_duplicate(directory: Path, filename: str, checksum: str) -> bool:
        target = directory / filename
        if not target.exists():
            return False
        return _sha256(target.read_bytes()) == checksum

    @staticmethod
    def _resolve_collision(directory: Path, filename: str) -> Path:
        target = directory / filename
        if not target.exists():
            return target

        stem = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 1
        while True:
            candidate = directory / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                return candidate
            counter += 1


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
