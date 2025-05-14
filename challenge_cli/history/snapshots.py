import datetime
import os
import shutil
import uuid
from typing import Dict, List, Optional

from challenge_cli.core.data_utils import load_json, save_json
from challenge_cli.core.exceptions import HistoryManagerError, SnapshotNotFoundError


class SnapshotManager:
    """Manages solution snapshots."""

    _SNAPSHOT_METADATA_FILENAME = "metadata.json"
    _SNAPSHOTS_DIR_NAME = "snapshots"

    def __init__(self, history_dir: str, language: str, max_snapshots: int = 50):
        """
        Initialize the snapshot manager.

        Args:
            history_dir: Base history directory
            language: Programming language
            max_snapshots: Maximum number of snapshots to keep
        """
        self.history_dir = history_dir
        self.language = language
        self.max_snapshots = max_snapshots
        self.snapshots_dir = os.path.join(history_dir, self._SNAPSHOTS_DIR_NAME)

        # Ensure directory exists
        os.makedirs(self.snapshots_dir, exist_ok=True)

    def create_snapshot(
        self,
        solution_file_path: str,
        function_name: str,
        tag: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> str:
        """
        Create a new snapshot of the current solution file.

        Args:
            solution_file_path: Absolute path to the solution file
            function_name: Name of the primary function/method
            tag: Optional tag for categorizing the snapshot
            comment: Optional comment about the snapshot

        Returns:
            The unique ID of the created snapshot

        Raises:
            FileNotFoundError: If solution file doesn't exist
            HistoryManagerError: If snapshot creation fails
        """
        if not os.path.isfile(solution_file_path):
            raise FileNotFoundError(f"Solution file not found: {solution_file_path}")

        # Generate unique snapshot ID
        snapshot_id = self._generate_snapshot_id()
        snapshot_dir = self._get_snapshot_path(snapshot_id)

        try:
            # Create snapshot directory
            os.makedirs(snapshot_dir, exist_ok=True)

            # Copy solution file
            solution_filename = os.path.basename(solution_file_path)
            snapshot_solution_path = os.path.join(snapshot_dir, solution_filename)
            shutil.copy2(solution_file_path, snapshot_solution_path)

            # Create snapshot metadata
            snapshot_metadata = {
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "language": self.language,
                "original_filename": solution_filename,
                "function_name": function_name,
                "tag": tag,
                "comment": comment,
            }

            # Save metadata
            metadata_path = self._get_snapshot_metadata_path(snapshot_id)
            save_json(metadata_path, snapshot_metadata)

        except (IOError, OSError) as e:
            # Clean up on failure
            if os.path.exists(snapshot_dir):
                try:
                    shutil.rmtree(snapshot_dir)
                except OSError:
                    pass
            raise HistoryManagerError(
                f"Failed to create snapshot {snapshot_id}: {e}"
            ) from e

        # Prune old snapshots
        self._prune_old_snapshots()

        return snapshot_id

    def get_snapshot_solution(self, snapshot_id: str) -> str:
        """
        Retrieve the solution code from a specific snapshot.

        Args:
            snapshot_id: The ID of the snapshot

        Returns:
            The content of the solution file

        Raises:
            SnapshotNotFoundError: If snapshot doesn't exist
            HistoryManagerError: If there's an error reading the file
        """
        snapshot_dir = self._get_snapshot_path(snapshot_id)
        metadata_path = self._get_snapshot_metadata_path(snapshot_id)

        if not os.path.isdir(snapshot_dir):
            raise SnapshotNotFoundError(
                f"Snapshot directory not found for ID: {snapshot_id}"
            )

        try:
            # Load metadata to get filename
            metadata = load_json(metadata_path)
            if not metadata or "original_filename" not in metadata:
                # Fallback: find first non-metadata file
                for filename in os.listdir(snapshot_dir):
                    if filename != self._SNAPSHOT_METADATA_FILENAME:
                        solution_filename = filename
                        break
                else:
                    raise HistoryManagerError(
                        f"Could not determine solution filename in snapshot {snapshot_id}"
                    )
            else:
                solution_filename = metadata["original_filename"]

            solution_path = os.path.join(snapshot_dir, solution_filename)

            if not os.path.isfile(solution_path):
                raise SnapshotNotFoundError(
                    f"Solution file not found in snapshot {snapshot_id}"
                )

            with open(solution_path, "r", encoding="utf-8") as f:
                return f.read()

        except FileNotFoundError as e:
            raise SnapshotNotFoundError(
                f"Solution file not found for snapshot {snapshot_id}: {e}"
            ) from e
        except (IOError, OSError) as e:
            raise HistoryManagerError(
                f"Error reading solution file for snapshot {snapshot_id}: {e}"
            ) from e

    def get_snapshot_info(self, snapshot_id: str) -> Dict:
        """
        Retrieve metadata for a specific snapshot.

        Args:
            snapshot_id: The ID of the snapshot

        Returns:
            Snapshot metadata dictionary

        Raises:
            SnapshotNotFoundError: If snapshot doesn't exist
            HistoryManagerError: If there's an error reading metadata
        """
        metadata_path = self._get_snapshot_metadata_path(snapshot_id)

        try:
            metadata = load_json(metadata_path)
            if not metadata:
                if not os.path.exists(metadata_path):
                    raise SnapshotNotFoundError(
                        f"Metadata file not found for snapshot ID: {snapshot_id}"
                    )
                else:
                    raise HistoryManagerError(
                        f"Metadata file for snapshot {snapshot_id} is empty or corrupt."
                    )
            return metadata
        except SnapshotNotFoundError:
            raise
        except HistoryManagerError:
            raise
        except Exception as e:
            raise HistoryManagerError(
                f"Unexpected error loading metadata for snapshot {snapshot_id}: {e}"
            ) from e

    def get_language_snapshot_ids(self, limit: Optional[int] = None) -> List[str]:
        """
        Get a list of snapshot IDs for the current language.

        Args:
            limit: Maximum number of snapshot IDs to return

        Returns:
            List of snapshot IDs, newest first
        """
        try:
            all_items = os.listdir(self.snapshots_dir)
        except FileNotFoundError:
            return []

        # Filter snapshots by language
        language_snapshots_with_time = []
        for item_id in all_items:
            snapshot_path = self._get_snapshot_path(item_id)
            if not os.path.isdir(snapshot_path):
                continue

            metadata_path = self._get_snapshot_metadata_path(item_id)
            try:
                metadata = load_json(metadata_path, default=None)
                if metadata and metadata.get("language") == self.language:
                    created_at_iso = metadata.get("created_at", "")
                    if created_at_iso:
                        language_snapshots_with_time.append((created_at_iso, item_id))
            except Exception:
                continue

        # Sort by timestamp (newest first)
        language_snapshots_with_time.sort(key=lambda x: x[0], reverse=True)
        language_snapshot_ids = [item_id for _, item_id in language_snapshots_with_time]

        return (
            language_snapshot_ids[:limit]
            if limit is not None
            else language_snapshot_ids
        )

    def get_snapshot_language(self, snapshot_id: str) -> Optional[str]:
        """Get the language from a snapshot's metadata."""
        try:
            metadata = self.get_snapshot_info(snapshot_id)
            return metadata.get("language")
        except (SnapshotNotFoundError, HistoryManagerError):
            return None

    def _generate_snapshot_id(self) -> str:
        """Generate a short, unique snapshot ID."""
        return uuid.uuid4().hex[:8]

    def _get_snapshot_path(self, snapshot_id: str) -> str:
        """Get the absolute path to a snapshot directory."""
        return os.path.join(self.snapshots_dir, snapshot_id)

    def _get_snapshot_metadata_path(self, snapshot_id: str) -> str:
        """Get the absolute path to a snapshot's metadata file."""
        return os.path.join(
            self._get_snapshot_path(snapshot_id), self._SNAPSHOT_METADATA_FILENAME
        )

    def _prune_old_snapshots(self) -> None:
        """Remove the oldest snapshots if count exceeds max_snapshots."""
        snapshot_ids = self.get_language_snapshot_ids()

        if len(snapshot_ids) > self.max_snapshots:
            snapshots_to_remove = snapshot_ids[self.max_snapshots :]

            for snapshot_id in snapshots_to_remove:
                snapshot_path = self._get_snapshot_path(snapshot_id)
                try:
                    if os.path.isdir(snapshot_path):
                        shutil.rmtree(snapshot_path)
                except OSError as e:
                    print(f"Warning: Failed to remove old snapshot {snapshot_id}: {e}")
