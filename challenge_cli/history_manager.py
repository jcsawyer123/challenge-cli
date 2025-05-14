import datetime
import json
import os
import shutil
import uuid  # Add uuid import
from typing import Any, Dict, List, Optional

# Import the consolidated helpers from utils
from challenge_cli.utils import load_json, save_json

HISTORY_DIR_NAME = ".history"  # Public constant for use elsewhere (e.g., cli.py)


class HistoryManagerError(Exception):
    """Base exception for HistoryManager errors."""

    pass


class SnapshotNotFoundError(HistoryManagerError):
    """Raised when a snapshot ID is not found."""

    pass


class HistoryManager:
    """
    Manages the history of solutions, test results, and performance metrics
    for a specific challenge and language.

    Handles creating snapshots, storing test/performance data, pruning old
    snapshots, and retrieving historical information.
    """

    _METADATA_FILENAME = "metadata.json"  # Internal detail for top-level metadata
    _SNAPSHOT_METADATA_FILENAME = (
        "metadata.json"  # Internal detail for snapshot metadata
    )
    _SNAPSHOTS_DIR_NAME = "snapshots"  # Internal detail
    _PERFORMANCE_DIR_NAME = "performance"  # Internal detail
    _TEST_RESULTS_DIR_NAME = "test_results"

    def __init__(self, challenge_dir: str, language: str, max_snapshots: int = 50):
        """
        Initialize the history manager.

        Args:
            challenge_dir: Path to the root directory of the challenge.
            language: Programming language (e.g., 'python', 'go', 'javascript').
            max_snapshots: Maximum number of snapshots to keep per language.
                           Older snapshots will be pruned.
        """
        if not os.path.isdir(challenge_dir):
            # Consider creating it or raising a more specific error
            raise FileNotFoundError(f"Challenge directory not found: {challenge_dir}")

        self.challenge_dir = challenge_dir
        self.language = language
        self.max_snapshots = max_snapshots

        # Define base history directory using the public constant
        self.history_dir = os.path.join(self.challenge_dir, HISTORY_DIR_NAME)

        # Define specific subdirectories (using internal names)
        self.snapshots_dir = os.path.join(self.history_dir, self._SNAPSHOTS_DIR_NAME)
        self.performance_dir = os.path.join(
            self.history_dir, self._PERFORMANCE_DIR_NAME
        )
        self.test_results_dir = os.path.join(
            self.history_dir, self._TEST_RESULTS_DIR_NAME
        )

        # Define file paths (using internal name for top-level metadata)
        self.metadata_file_path = os.path.join(
            self.history_dir, self._METADATA_FILENAME
        )

        self._ensure_directories_exist()
        self._initialize_metadata_if_needed()

    # --- Private Helper Methods ---

    def _ensure_directories_exist(self) -> None:
        """Ensure all required history directories exist."""
        for directory in [
            self.history_dir,
            self.snapshots_dir,
            self.performance_dir,
            self.test_results_dir,
        ]:
            os.makedirs(directory, exist_ok=True)

    # _load_json and _save_json were removed in the previous (partial) application

    def _get_performance_file_path(self) -> str:
        """Get the path to the performance history file for the current language."""
        return os.path.join(self.performance_dir, f"{self.language}.json")

    def _get_test_results_file_path(self) -> str:
        """Get the path to the test results history file for the current language."""
        return os.path.join(self.test_results_dir, f"{self.language}.json")

    def _get_snapshot_path(self, snapshot_id: str) -> str:
        """Get the absolute path to a specific snapshot directory."""
        return os.path.join(self.snapshots_dir, snapshot_id)

    def _get_snapshot_metadata_path(self, snapshot_id: str) -> str:
        """Get the absolute path to the metadata file of a specific snapshot."""
        # Use internal constant for snapshot metadata filename
        return os.path.join(
            self._get_snapshot_path(snapshot_id), self._SNAPSHOT_METADATA_FILENAME
        )

    # --- Metadata Management ---

    def _initialize_metadata_if_needed(self) -> None:
        """Initialize the main metadata file if it doesn't exist."""
        if not os.path.exists(self.metadata_file_path):
            initial_metadata = {
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "settings": {
                    "max_snapshots": self.max_snapshots,
                },
                "languages": {},
            }
            save_json(self.metadata_file_path, initial_metadata)  # Use util function

    def _load_metadata(self) -> Dict:
        """Load the main history metadata."""
        # Ensure initialization check happens before loading
        self._initialize_metadata_if_needed()
        # Use util function, default should not be hit due to check
        return load_json(self.metadata_file_path, default={})

    def _save_metadata(self, metadata: Dict) -> None:
        """Save the main history metadata."""
        save_json(self.metadata_file_path, metadata)  # Use util function

    def _update_language_metadata(self, snapshot_id: Optional[str] = None) -> None:
        """Update language-specific metadata, typically after taking a snapshot."""
        metadata = self._load_metadata()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if self.language not in metadata.setdefault("languages", {}):
            metadata["languages"][self.language] = {
                "first_snapshot_at": now_iso,
                "snapshot_count": 0,
                "latest_snapshot_id": None,
                "latest_snapshot_at": None,  # Initialize explicitly
            }

        lang_meta = metadata["languages"][self.language]
        lang_meta["snapshot_count"] = lang_meta.get("snapshot_count", 0) + 1
        lang_meta["latest_snapshot_at"] = now_iso
        if snapshot_id:
            lang_meta["latest_snapshot_id"] = snapshot_id

        self._save_metadata(metadata)

    # --- Snapshot Management ---

    def _generate_snapshot_id(self) -> str:
        """Generates a short, unique snapshot ID."""
        # Generate a UUID and take the first 8 hex characters
        return uuid.uuid4().hex[:8]

    def _get_language_snapshot_ids(self, limit: Optional[int] = None) -> List[str]:
        """
        Get a list of snapshot IDs for the current language, sorted by
        creation time (newest first).

        Args:
            limit: Optional maximum number of snapshot IDs to return.

        Returns:
            A list of snapshot IDs.
        """
        try:
            all_items = os.listdir(self.snapshots_dir)
        except FileNotFoundError:
            return []  # Snapshots directory might not exist yet if no snapshots made

        # Filter snapshots by checking language in metadata and sort by creation time
        language_snapshots_with_time = []
        for item_id in all_items:
            snapshot_path = self._get_snapshot_path(item_id)
            if not os.path.isdir(snapshot_path):
                continue

            metadata_path = self._get_snapshot_metadata_path(item_id)
            try:
                # Use the utility function to load metadata safely
                metadata = load_json(
                    metadata_path, default=None
                )  # Default to None to distinguish missing/corrupt
                if metadata and metadata.get("language") == self.language:
                    # Use ISO format timestamp from metadata for reliable sorting
                    created_at_iso = metadata.get("created_at", "")
                    if created_at_iso:  # Only include if timestamp exists
                        language_snapshots_with_time.append((created_at_iso, item_id))
            except Exception:
                # Log or print warning about issues reading metadata? For now, just skip.
                # print(f"Warning: Could not process metadata for {item_id}: {e}")
                continue

        # Sort by timestamp (ISO format string comparison works correctly here)
        language_snapshots_with_time.sort(key=lambda x: x[0], reverse=True)

        # Extract just the IDs after sorting
        language_snapshot_ids = [item_id for _, item_id in language_snapshots_with_time]

        return (
            language_snapshot_ids[:limit]
            if limit is not None
            else language_snapshot_ids
        )

    def create_snapshot(
        self,
        solution_file_path: str,
        function_name: str,
        tag: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> str:
        """
        Create a new snapshot of the current solution file.

        Copies the solution file and creates metadata for the snapshot.

        Args:
            solution_file_path: Absolute path to the solution file to snapshot.
            function_name: Name of the primary function/method in the solution.
            tag: Optional tag for categorizing the snapshot (e.g., "optimized").
            comment: Optional free-text comment about the snapshot.

        Returns:
            The unique ID string of the created snapshot.

        Raises:
            FileNotFoundError: If the solution_file_path does not exist.
            HistoryManagerError: If snapshot creation fails (e.g., I/O error).
        """
        if not os.path.isfile(solution_file_path):
            raise FileNotFoundError(f"Solution file not found: {solution_file_path}")

        # Generate snapshot ID using the new method
        snapshot_id = self._generate_snapshot_id()
        snapshot_dir = self._get_snapshot_path(snapshot_id)

        try:
            # Create snapshot directory
            os.makedirs(snapshot_dir, exist_ok=True)

            # Copy solution file, preserving metadata (like modification time)
            solution_filename = os.path.basename(solution_file_path)
            snapshot_solution_path = os.path.join(snapshot_dir, solution_filename)
            shutil.copy2(
                solution_file_path, snapshot_solution_path
            )  # copy2 preserves metadata

            # Create snapshot metadata
            snapshot_metadata = {
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "language": self.language,
                "original_filename": solution_filename,
                "function_name": function_name,
                "tag": tag,
                "comment": comment,
            }

            # Save snapshot metadata using the util function
            metadata_path = self._get_snapshot_metadata_path(snapshot_id)
            save_json(metadata_path, snapshot_metadata)

        except (IOError, OSError) as e:
            # Clean up partially created snapshot directory if something went wrong
            if os.path.exists(snapshot_dir):
                try:
                    shutil.rmtree(snapshot_dir)
                except OSError:
                    # Log this cleanup failure, but prioritize the original error
                    print(
                        f"Warning: Failed to clean up partially created snapshot directory {snapshot_dir}"
                    )
            raise HistoryManagerError(
                f"Failed to create snapshot {snapshot_id}: {e}"
            ) from e

        # Update overall history metadata
        self._update_language_metadata(snapshot_id)

        # Prune old snapshots after successfully creating the new one
        self._prune_old_snapshots()

        return snapshot_id

    def _prune_old_snapshots(self) -> None:
        """Remove the oldest snapshots if the count exceeds max_snapshots."""
        # Get all snapshot IDs for the current language, sorted newest first
        snapshot_ids = self._get_language_snapshot_ids()

        if len(snapshot_ids) > self.max_snapshots:
            # Identify snapshots to remove (the oldest ones)
            snapshots_to_remove = snapshot_ids[self.max_snapshots :]

            for snapshot_id in snapshots_to_remove:
                snapshot_path = self._get_snapshot_path(snapshot_id)
                try:
                    if os.path.isdir(snapshot_path):  # Double check it's a directory
                        shutil.rmtree(snapshot_path)
                        # print(f"Pruned old snapshot: {snapshot_id}") # Optional: for debugging/verbose output
                except OSError as e:
                    # Log the error but continue pruning others
                    print(
                        f"Warning: Failed to remove old snapshot {snapshot_id} at {snapshot_path}: {e}"
                    )
                    # Consider logging this error more formally

    # --- Performance History ---

    def get_performance_history(self) -> List[Dict]:
        """
        Load the performance history records for the current language.

        Returns:
            A list of performance records (dictionaries), or an empty list
            if no history exists or the file is invalid.
        """
        performance_file_path = self._get_performance_file_path()
        # Load JSON using util function, defaulting to an empty list
        history = load_json(performance_file_path, default=[])
        # Basic validation: ensure it's a list
        return history if isinstance(history, list) else []

    def add_performance_record(
        self, case_num: int, metrics: Dict[str, Any], snapshot_id: Optional[str] = None
    ) -> None:
        """
        Add a new performance record to the history for the current language.

        Args:
            case_num: The test case number this record corresponds to.
            metrics: A dictionary containing performance metrics
                     (e.g., {'time_ms': 10.5, 'mem_bytes': 512000}).
            snapshot_id: Optional ID of the snapshot associated with this run.

        Raises:
            HistoryManagerError: If saving the performance data fails.
        """
        performance_file_path = self._get_performance_file_path()
        records = self.get_performance_history()  # Use the getter to load safely

        # Create new record
        new_record = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "language": self.language,
            "case_num": case_num,
            "metrics": metrics,
            "snapshot_id": snapshot_id,
        }

        records.append(new_record)

        # Save updated records using the util function
        save_json(performance_file_path, records)

    # --- Test Result History ---

    def get_test_history(self) -> List[Dict]:
        """
        Load the test result history for the current language.

        Returns:
            A list of test result records (dictionaries), or an empty list
            if no history exists or the file is invalid.
        """
        test_results_file_path = self._get_test_results_file_path()
        # Load JSON using util function, defaulting to an empty list
        history = load_json(test_results_file_path, default=[])
        # Basic validation: ensure it's a list
        return history if isinstance(history, list) else []

    def add_test_results(
        self, results: List[Dict], snapshot_id: Optional[str] = None
    ) -> None:
        """
        Add a new set of test results to the history for the current language.

        Args:
            results: A list of dictionaries, where each dictionary represents
                     the result of a single test case (e.g.,
                     {'case_num': 1, 'passed': True, 'output': '...', 'expected': '...'}).
            snapshot_id: Optional ID of the snapshot associated with these results.

        Raises:
            HistoryManagerError: If saving the test results fails.
        """
        test_results_file_path = self._get_test_results_file_path()
        records = self.get_test_history()  # Use the getter to load safely

        # Calculate summary within the new record
        passed_count = sum(1 for r in results if r.get("passed", False))
        summary = {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
        }

        # Create new record for this test run
        new_record = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "language": self.language,
            "results": results,
            "snapshot_id": snapshot_id,
            "summary": summary,
        }

        records.append(new_record)

        # Save updated records using the util function
        save_json(test_results_file_path, records)

    # --- Snapshot Data Retrieval ---

    def get_snapshot_language(self, snapshot_id: str) -> Optional[str]:
        """Retrieve the language from a snapshot's metadata."""
        try:
            metadata = self.get_snapshot_info(snapshot_id)
            return metadata.get("language")
        except SnapshotNotFoundError:
            return None
        except HistoryManagerError:
            # Handle cases where metadata might be corrupt but file exists
            return None

    def get_snapshot_solution(self, snapshot_id: str) -> str:
        """
        Retrieve the solution code content from a specific snapshot.

        Args:
            snapshot_id: The ID of the snapshot.

        Returns:
            The content of the solution file as a string.

        Raises:
            SnapshotNotFoundError: If the snapshot ID or its solution file doesn't exist.
            HistoryManagerError: If there's an error reading the file.
        """
        snapshot_dir = self._get_snapshot_path(snapshot_id)
        metadata_path = self._get_snapshot_metadata_path(snapshot_id)

        if not os.path.isdir(snapshot_dir):
            raise SnapshotNotFoundError(
                f"Snapshot directory not found for ID: {snapshot_id}"
            )

        try:
            # Load snapshot metadata using util function
            metadata = load_json(metadata_path)
            if not metadata or "original_filename" not in metadata:
                # Fallback: find the first non-metadata file if metadata is missing/corrupt
                for filename in os.listdir(snapshot_dir):
                    # Use internal constant for snapshot metadata filename
                    if filename != self._SNAPSHOT_METADATA_FILENAME:
                        solution_filename = filename
                        break
                else:  # No non-metadata file found
                    raise HistoryManagerError(
                        f"Could not determine solution filename in snapshot {snapshot_id}"
                    )
            else:
                solution_filename = metadata["original_filename"]

            solution_path = os.path.join(snapshot_dir, solution_filename)

            if not os.path.isfile(solution_path):
                raise SnapshotNotFoundError(
                    f"Solution file '{solution_filename}' not found in snapshot {snapshot_id}"
                )

            with open(solution_path, "r", encoding="utf-8") as f:
                return f.read()

        except (
            FileNotFoundError
        ) as e:  # Handles case where metadata exists but file doesn't
            raise SnapshotNotFoundError(
                f"Solution file not found for snapshot {snapshot_id}: {e}"
            ) from e
        except (IOError, OSError) as e:
            raise HistoryManagerError(
                f"Error reading solution file for snapshot {snapshot_id}: {e}"
            ) from e
        except json.JSONDecodeError as e:
            # Handle case where snapshot metadata is corrupt
            raise HistoryManagerError(
                f"Error reading metadata for snapshot {snapshot_id}: {e}"
            ) from e

    def get_snapshot_info(self, snapshot_id: str) -> Dict:
        """
        Retrieve the metadata for a specific snapshot.

        Args:
            snapshot_id: The ID of the snapshot.

        Returns:
            A dictionary containing the snapshot's metadata.

        Raises:
            SnapshotNotFoundError: If the snapshot ID or its metadata file doesn't exist.
            HistoryManagerError: If there's an error reading the metadata file.
        """
        metadata_path = self._get_snapshot_metadata_path(snapshot_id)

        try:
            metadata = load_json(metadata_path)  # Use util function
            if (
                not metadata
            ):  # Check if load_json returned empty dict due to FileNotFoundError or decode error
                if not os.path.exists(metadata_path):
                    raise SnapshotNotFoundError(
                        f"Metadata file not found for snapshot ID: {snapshot_id}"
                    )
                else:
                    # File exists but couldn't be decoded or is empty
                    raise HistoryManagerError(
                        f"Metadata file for snapshot {snapshot_id} is empty or corrupt."
                    )
            return metadata
        except SnapshotNotFoundError:  # Re-raise specific error
            raise
        except HistoryManagerError:  # Re-raise specific error
            raise
        except Exception as e:  # Catch unexpected errors during loading
            raise HistoryManagerError(
                f"Unexpected error loading metadata for snapshot {snapshot_id}: {e}"
            ) from e
