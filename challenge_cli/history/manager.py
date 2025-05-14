"""Main history manager that orchestrates the various history components."""

import datetime
import os
from typing import Any, Dict, List, Optional

from challenge_cli.core.config import HISTORY_DIR_NAME
from challenge_cli.core.data_utils import load_json, save_json
from challenge_cli.history.peformance import PerformanceTracker

from .snapshots import SnapshotManager
from .test_results import TestResultsTracker


class HistoryManager:
    """
    Manages the history of solutions, test results, and performance metrics
    for a specific challenge and language.
    """

    _METADATA_FILENAME = "metadata.json"

    def __init__(self, challenge_dir: str, language: str, max_snapshots: int = 50):
        """
        Initialize the history manager.

        Args:
            challenge_dir: Path to the challenge directory
            language: Programming language
            max_snapshots: Maximum number of snapshots to keep
        """
        if not os.path.isdir(challenge_dir):
            raise FileNotFoundError(f"Challenge directory not found: {challenge_dir}")

        self.challenge_dir = challenge_dir
        self.language = language
        self.max_snapshots = max_snapshots

        # Define base history directory
        self.history_dir = os.path.join(self.challenge_dir, HISTORY_DIR_NAME)
        self.metadata_file_path = os.path.join(
            self.history_dir, self._METADATA_FILENAME
        )

        # Ensure history directory exists
        os.makedirs(self.history_dir, exist_ok=True)

        # Initialize components
        self.snapshots = SnapshotManager(self.history_dir, language, max_snapshots)
        self.performance = PerformanceTracker(self.history_dir, language)
        self.test_results = TestResultsTracker(self.history_dir, language)

        # Initialize metadata
        self._initialize_metadata_if_needed()

    def create_snapshot(
        self,
        solution_file_path: str,
        function_name: str,
        tag: Optional[str] = None,
        comment: Optional[str] = None,
    ) -> str:
        """Create a new snapshot of the current solution."""
        snapshot_id = self.snapshots.create_snapshot(
            solution_file_path, function_name, tag, comment
        )
        self._update_language_metadata(snapshot_id)
        return snapshot_id

    def get_snapshot_solution(self, snapshot_id: str) -> str:
        """Retrieve the solution code from a specific snapshot."""
        return self.snapshots.get_snapshot_solution(snapshot_id)

    def get_snapshot_info(self, snapshot_id: str) -> Dict:
        """Retrieve metadata for a specific snapshot."""
        return self.snapshots.get_snapshot_info(snapshot_id)

    def get_snapshot_language(self, snapshot_id: str) -> Optional[str]:
        """Get the language from a snapshot's metadata."""
        return self.snapshots.get_snapshot_language(snapshot_id)

    def add_performance_record(
        self, case_num: int, metrics: Dict[str, Any], snapshot_id: Optional[str] = None
    ) -> None:
        """Add a new performance record to the history."""
        self.performance.add_performance_record(case_num, metrics, snapshot_id)

    def get_performance_history(self) -> List[Dict]:
        """Load the performance history for the current language."""
        return self.performance.get_performance_history()

    def add_test_results(
        self, results: List[Dict], snapshot_id: Optional[str] = None
    ) -> None:
        """Add a new set of test results to the history."""
        self.test_results.add_test_results(results, snapshot_id)

    def get_test_history(self) -> List[Dict]:
        """Load the test result history for the current language."""
        return self.test_results.get_test_history()

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
            save_json(self.metadata_file_path, initial_metadata)

    def _load_metadata(self) -> Dict:
        """Load the main history metadata."""
        self._initialize_metadata_if_needed()
        return load_json(self.metadata_file_path, default={})

    def _save_metadata(self, metadata: Dict) -> None:
        """Save the main history metadata."""
        save_json(self.metadata_file_path, metadata)

    def _update_language_metadata(self, snapshot_id: Optional[str] = None) -> None:
        """Update language-specific metadata."""
        metadata = self._load_metadata()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        if self.language not in metadata.setdefault("languages", {}):
            metadata["languages"][self.language] = {
                "first_snapshot_at": now_iso,
                "snapshot_count": 0,
                "latest_snapshot_id": None,
                "latest_snapshot_at": None,
            }

        lang_meta = metadata["languages"][self.language]
        lang_meta["snapshot_count"] = lang_meta.get("snapshot_count", 0) + 1
        lang_meta["latest_snapshot_at"] = now_iso
        if snapshot_id:
            lang_meta["latest_snapshot_id"] = snapshot_id

        self._save_metadata(metadata)

    # Delegate to SnapshotManager for backward compatibility
    def _get_language_snapshot_ids(self, limit: Optional[int] = None) -> List[str]:
        """Get snapshot IDs for the current language."""
        return self.snapshots.get_language_snapshot_ids(limit)
