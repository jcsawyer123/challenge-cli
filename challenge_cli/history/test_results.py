"""Test results tracking for challenge solutions."""

import datetime
import os
from typing import Dict, List, Optional

from challenge_cli.core.data_utils import load_json, save_json


class TestResultsTracker:
    """Tracks test results history."""

    _TEST_RESULTS_DIR_NAME = "test_results"

    def __init__(self, history_dir: str, language: str):
        """
        Initialize the test results tracker.

        Args:
            history_dir: Base history directory
            language: Programming language
        """
        self.history_dir = history_dir
        self.language = language
        self.test_results_dir = os.path.join(history_dir, self._TEST_RESULTS_DIR_NAME)

        # Ensure directory exists
        os.makedirs(self.test_results_dir, exist_ok=True)

    def get_test_history(self) -> List[Dict]:
        """
        Load the test result history for the current language.

        Returns:
            List of test result records
        """
        test_results_file_path = self._get_test_results_file_path()
        history = load_json(test_results_file_path, default=[])
        return history if isinstance(history, list) else []

    def add_test_results(
        self, results: List[Dict], snapshot_id: Optional[str] = None
    ) -> None:
        """
        Add a new set of test results to the history.

        Args:
            results: List of test result dictionaries
            snapshot_id: Optional associated snapshot ID

        Raises:
            HistoryManagerError: If saving fails
        """
        test_results_file_path = self._get_test_results_file_path()
        records = self.get_test_history()

        # Calculate summary
        passed_count = sum(1 for r in results if r.get("passed", False))
        summary = {
            "total": len(results),
            "passed": passed_count,
            "failed": len(results) - passed_count,
        }

        new_record = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "language": self.language,
            "results": results,
            "snapshot_id": snapshot_id,
            "summary": summary,
        }

        records.append(new_record)
        save_json(test_results_file_path, records)

    def _get_test_results_file_path(self) -> str:
        """Get the path to the test results history file."""
        return os.path.join(self.test_results_dir, f"{self.language}.json")
