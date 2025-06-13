"""Enhanced Log Rotation and Archiving

Provides advanced log rotation, compression, and archiving capabilities
with configurable policies and storage options.

Author: CloudWatch Logs AI Agent Team
License: MIT
"""

import gzip
import os
import shutil
import threading
import time
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union
import logging
import logging.handlers
import json
import hashlib
import zipfile


class RotationPolicy(Enum):
    """Log rotation policies"""

    SIZE = "size"
    TIME = "time"
    COMBINED = "combined"


class CompressionType(Enum):
    """Compression types for archived logs"""

    NONE = "none"
    GZIP = "gzip"
    ZIP = "zip"


class ArchivePolicy(Enum):
    """Archive policies for old logs"""

    DELETE = "delete"
    COMPRESS = "compress"
    MOVE = "move"
    CUSTOM = "custom"


class LogRotationConfig:
    """Configuration for log rotation and archiving"""

    def __init__(
        self,
        # Rotation settings
        rotation_policy: RotationPolicy = RotationPolicy.COMBINED,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        rotation_interval: timedelta = timedelta(days=1),
        max_files: int = 30,
        # Compression settings
        compression_type: CompressionType = CompressionType.GZIP,
        compress_after_days: int = 7,
        # Archive settings
        archive_policy: ArchivePolicy = ArchivePolicy.COMPRESS,
        archive_directory: Optional[str] = None,
        delete_after_days: Optional[int] = 90,
        # Metadata settings
        include_metadata: bool = True,
        metadata_file: Optional[str] = None,
        # Performance settings
        async_rotation: bool = True,
        rotation_check_interval: int = 300,  # 5 minutes
    ):
        self.rotation_policy = rotation_policy
        self.max_file_size = max_file_size
        self.rotation_interval = rotation_interval
        self.max_files = max_files

        self.compression_type = compression_type
        self.compress_after_days = compress_after_days

        self.archive_policy = archive_policy
        self.archive_directory = archive_directory
        self.delete_after_days = delete_after_days

        self.include_metadata = include_metadata
        self.metadata_file = metadata_file

        self.async_rotation = async_rotation
        self.rotation_check_interval = rotation_check_interval


class LogMetadata:
    """Metadata for log files"""

    def __init__(
        self,
        filename: str,
        created_at: datetime,
        rotated_at: Optional[datetime] = None,
        size_bytes: Optional[int] = None,
        line_count: Optional[int] = None,
        checksum: Optional[str] = None,
        compression: Optional[CompressionType] = None,
        archived: bool = False,
        archive_location: Optional[str] = None,
    ):
        self.filename = filename
        self.created_at = created_at
        self.rotated_at = rotated_at
        self.size_bytes = size_bytes
        self.line_count = line_count
        self.checksum = checksum
        self.compression = compression
        self.archived = archived
        self.archive_location = archive_location

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "filename": self.filename,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "rotated_at": self.rotated_at.isoformat() if self.rotated_at else None,
            "size_bytes": self.size_bytes,
            "line_count": self.line_count,
            "checksum": self.checksum,
            "compression": self.compression.value if self.compression else None,
            "archived": self.archived,
            "archive_location": self.archive_location,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogMetadata":
        """Create from dictionary"""
        created_at = None
        if data.get("created_at"):
            created_at = datetime.fromisoformat(data["created_at"])

        rotated_at = None
        if data.get("rotated_at"):
            rotated_at = datetime.fromisoformat(data["rotated_at"])

        compression = None
        if data.get("compression"):
            compression = CompressionType(data["compression"])

        return cls(
            filename=data["filename"],
            created_at=created_at,
            rotated_at=rotated_at,
            size_bytes=data.get("size_bytes"),
            line_count=data.get("line_count"),
            checksum=data.get("checksum"),
            compression=compression,
            archived=data.get("archived", False),
            archive_location=data.get("archive_location"),
        )


class EnhancedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Enhanced rotating file handler with advanced features"""

    def __init__(
        self,
        filename: str,
        config: Optional[LogRotationConfig] = None,
        on_rotation_callback: Optional[Callable[[str, str], None]] = None,
        **kwargs,
    ):
        self.config = config or LogRotationConfig()
        self.on_rotation_callback = on_rotation_callback
        self.metadata_store = {}
        self.last_rotation_check = datetime.utcnow()
        self._lock = threading.Lock()

        # Initialize with size-based rotation
        super().__init__(
            filename=filename,
            maxBytes=self.config.max_file_size,
            backupCount=self.config.max_files,
            **kwargs,
        )

        # Create directories
        self._ensure_directories()

        # Load existing metadata
        self._load_metadata()

        # Start background archiver if async rotation is enabled
        if self.config.async_rotation:
            self._start_background_archiver()

    def _ensure_directories(self):
        """Ensure all required directories exist"""
        # Log directory
        log_dir = os.path.dirname(self.baseFilename)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)

        # Archive directory
        if self.config.archive_directory:
            if not os.path.exists(self.config.archive_directory):
                os.makedirs(self.config.archive_directory, exist_ok=True)

    def _load_metadata(self):
        """Load metadata from file"""
        if not self.config.include_metadata:
            return

        metadata_file = (
            self.config.metadata_file or f"{self.baseFilename}.metadata.json"
        )

        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r") as f:
                    data = json.load(f)
                    for filename, metadata_dict in data.items():
                        self.metadata_store[filename] = LogMetadata.from_dict(
                            metadata_dict
                        )
            except Exception as e:
                print(f"Failed to load log metadata: {e}")

    def _save_metadata(self):
        """Save metadata to file"""
        if not self.config.include_metadata:
            return

        metadata_file = (
            self.config.metadata_file or f"{self.baseFilename}.metadata.json"
        )

        try:
            data = {
                filename: metadata.to_dict()
                for filename, metadata in self.metadata_store.items()
            }

            with open(metadata_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to save log metadata: {e}")

    def _calculate_checksum(self, filename: str) -> Optional[str]:
        """Calculate file checksum"""
        try:
            hash_md5 = hashlib.md5()
            with open(filename, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_md5.update(chunk)
            return hash_md5.hexdigest()
        except Exception:
            return None

    def _count_lines(self, filename: str) -> Optional[int]:
        """Count lines in file"""
        try:
            with open(filename, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except Exception:
            return None

    def shouldRollover(self, record: logging.LogRecord) -> bool:
        """Determine if rotation should occur"""
        current_time = datetime.utcnow()

        # Check time-based rotation
        time_rotation = False
        if (
            self.config.rotation_policy
            in [RotationPolicy.TIME, RotationPolicy.COMBINED]
            and current_time - self.last_rotation_check >= self.config.rotation_interval
        ):
            time_rotation = True

        # Check size-based rotation
        size_rotation = super().shouldRollover(record)

        # Determine based on policy
        if self.config.rotation_policy == RotationPolicy.SIZE:
            return size_rotation
        elif self.config.rotation_policy == RotationPolicy.TIME:
            return time_rotation
        else:  # COMBINED
            return size_rotation or time_rotation

    def doRollover(self):
        """Perform log rotation with enhanced features"""
        with self._lock:
            if self.stream:
                self.stream.close()
                self.stream = None

            current_time = datetime.utcnow()

            # Create metadata for current file
            if os.path.exists(self.baseFilename):
                stat = os.stat(self.baseFilename)
                metadata = LogMetadata(
                    filename=os.path.basename(self.baseFilename),
                    created_at=self.last_rotation_check,
                    rotated_at=current_time,
                    size_bytes=stat.st_size,
                    line_count=self._count_lines(self.baseFilename),
                    checksum=self._calculate_checksum(self.baseFilename),
                )

                # Generate timestamped filename
                timestamp = current_time.strftime("%Y%m%d_%H%M%S")
                base_name = os.path.splitext(self.baseFilename)[0]
                extension = os.path.splitext(self.baseFilename)[1]
                rotated_filename = f"{base_name}_{timestamp}{extension}"

                # Move current file to rotated name
                shutil.move(self.baseFilename, rotated_filename)

                # Store metadata
                self.metadata_store[os.path.basename(rotated_filename)] = metadata

                # Trigger callback
                if self.on_rotation_callback:
                    try:
                        self.on_rotation_callback(self.baseFilename, rotated_filename)
                    except Exception as e:
                        print(f"Rotation callback error: {e}")

                # Schedule for archiving if async
                if self.config.async_rotation:
                    self._schedule_archiving(rotated_filename, metadata)
                else:
                    self._process_archiving(rotated_filename, metadata)

            # Update last rotation check
            self.last_rotation_check = current_time

            # Save metadata
            self._save_metadata()

            # Reopen stream
            if not self.delay:
                self.stream = self._open()

    def _schedule_archiving(self, filename: str, metadata: LogMetadata):
        """Schedule file for archiving (async mode)"""
        # This would typically add to a queue processed by background thread
        pass  # Implementation depends on specific archiving requirements

    def _process_archiving(self, filename: str, metadata: LogMetadata):
        """Process file archiving immediately"""

        if self.config.archive_policy == ArchivePolicy.DELETE:
            self._delete_old_files()
        elif self.config.archive_policy == ArchivePolicy.COMPRESS:
            self._compress_file(filename, metadata)
        elif self.config.archive_policy == ArchivePolicy.MOVE:
            self._move_to_archive(filename, metadata)

        # Clean up old files based on retention policy
        self._cleanup_old_files()

    def _compress_file(self, filename: str, metadata: LogMetadata):
        """Compress log file"""
        if not os.path.exists(filename):
            return

        try:
            if self.config.compression_type == CompressionType.GZIP:
                compressed_filename = f"{filename}.gz"
                with open(filename, "rb") as f_in:
                    with gzip.open(compressed_filename, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)

                # Update metadata
                metadata.compression = CompressionType.GZIP
                metadata.checksum = self._calculate_checksum(compressed_filename)
                self.metadata_store[os.path.basename(compressed_filename)] = metadata

                # Remove original
                os.remove(filename)

            elif self.config.compression_type == CompressionType.ZIP:
                compressed_filename = f"{filename}.zip"
                with zipfile.ZipFile(
                    compressed_filename, "w", zipfile.ZIP_DEFLATED
                ) as zipf:
                    zipf.write(filename, os.path.basename(filename))

                # Update metadata
                metadata.compression = CompressionType.ZIP
                metadata.checksum = self._calculate_checksum(compressed_filename)
                self.metadata_store[os.path.basename(compressed_filename)] = metadata

                # Remove original
                os.remove(filename)

        except Exception as e:
            print(f"Compression failed for {filename}: {e}")

    def _move_to_archive(self, filename: str, metadata: LogMetadata):
        """Move file to archive directory"""
        if not self.config.archive_directory or not os.path.exists(filename):
            return

        try:
            archive_filename = os.path.join(
                self.config.archive_directory, os.path.basename(filename)
            )

            shutil.move(filename, archive_filename)

            # Update metadata
            metadata.archived = True
            metadata.archive_location = archive_filename
            self.metadata_store[os.path.basename(filename)] = metadata

        except Exception as e:
            print(f"Archive move failed for {filename}: {e}")

    def _delete_old_files(self):
        """Delete old log files based on retention policy"""
        if not self.config.delete_after_days:
            return

        cutoff_date = datetime.utcnow() - timedelta(days=self.config.delete_after_days)

        files_to_delete = []
        for filename, metadata in self.metadata_store.items():
            if metadata.rotated_at and metadata.rotated_at < cutoff_date:
                files_to_delete.append(filename)

        for filename in files_to_delete:
            try:
                # Determine actual file path
                if self.metadata_store[filename].archived:
                    file_path = self.metadata_store[filename].archive_location
                else:
                    file_path = os.path.join(
                        os.path.dirname(self.baseFilename), filename
                    )

                if file_path and os.path.exists(file_path):
                    os.remove(file_path)

                # Remove from metadata
                del self.metadata_store[filename]

            except Exception as e:
                print(f"Failed to delete old log file {filename}: {e}")

    def _cleanup_old_files(self):
        """Clean up files based on max_files limit"""
        if len(self.metadata_store) <= self.config.max_files:
            return

        # Sort by rotation date (oldest first)
        sorted_files = sorted(
            self.metadata_store.items(), key=lambda x: x[1].rotated_at or datetime.min
        )

        # Remove oldest files
        files_to_remove = len(sorted_files) - self.config.max_files
        for i in range(files_to_remove):
            filename, metadata = sorted_files[i]

            try:
                # Determine actual file path
                if metadata.archived:
                    file_path = metadata.archive_location
                else:
                    file_path = os.path.join(
                        os.path.dirname(self.baseFilename), filename
                    )

                if file_path and os.path.exists(file_path):
                    os.remove(file_path)

                # Remove from metadata
                del self.metadata_store[filename]

            except Exception as e:
                print(f"Failed to cleanup old log file {filename}: {e}")

    def _start_background_archiver(self):
        """Start background thread for archiving operations"""

        def archiver_worker():
            while True:
                try:
                    # Check for files that need compression
                    current_time = datetime.utcnow()
                    compress_cutoff = current_time - timedelta(
                        days=self.config.compress_after_days
                    )

                    for filename, metadata in list(self.metadata_store.items()):
                        if (
                            metadata.rotated_at
                            and metadata.rotated_at < compress_cutoff
                            and not metadata.compression
                            and not metadata.archived
                        ):

                            file_path = os.path.join(
                                os.path.dirname(self.baseFilename), filename
                            )

                            if os.path.exists(file_path):
                                self._compress_file(file_path, metadata)

                    # Clean up old files
                    self._delete_old_files()

                    # Save metadata
                    self._save_metadata()

                    # Sleep until next check
                    time.sleep(self.config.rotation_check_interval)

                except Exception as e:
                    print(f"Background archiver error: {e}")
                    time.sleep(60)  # Wait 1 minute on error

        archiver_thread = threading.Thread(target=archiver_worker, daemon=True)
        archiver_thread.start()

    def get_log_statistics(self) -> Dict[str, Any]:
        """Get statistics about log files"""
        total_files = len(self.metadata_store)
        total_size = sum(
            metadata.size_bytes or 0 for metadata in self.metadata_store.values()
        )

        compressed_files = sum(
            1 for metadata in self.metadata_store.values() if metadata.compression
        )

        archived_files = sum(
            1 for metadata in self.metadata_store.values() if metadata.archived
        )

        oldest_file = None
        newest_file = None

        if self.metadata_store:
            oldest_file = min(
                self.metadata_store.values(), key=lambda x: x.created_at or datetime.max
            ).created_at

            newest_file = max(
                self.metadata_store.values(), key=lambda x: x.rotated_at or datetime.min
            ).rotated_at

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "compressed_files": compressed_files,
            "archived_files": archived_files,
            "oldest_file": oldest_file.isoformat() if oldest_file else None,
            "newest_file": newest_file.isoformat() if newest_file else None,
            "metadata_store": {
                filename: metadata.to_dict()
                for filename, metadata in self.metadata_store.items()
            },
        }
