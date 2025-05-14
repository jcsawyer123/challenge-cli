"""Performance metrics tracking for challenge solutions."""

import datetime
import os
from typing import Any, Dict, List, Optional

from challenge_cli.core.data_utils import load_json, save_json


class PerformanceTracker:
    """Tracks performance metrics over time."""

    _PERFORMANCE_DIR_NAME = "performance"

    def __init__(self, history_dir: str, language: str):
        """
        Initialize the performance tracker.

        Args:
            history_dir: Base history directory
            language: Programming language
        """
        self.history_dir = history_dir
        self.language = language
        self.performance_dir = os.path.join(history_dir, self._PERFORMANCE_DIR_NAME)

        # Ensure directory exists
        os.makedirs(self.performance_dir, exist_ok=True)

    def get_performance_history(self) -> List[Dict]:
        """
        Load the performance history for the current language.

        Returns:
            List of performance records
        """
        performance_file_path = self._get_performance_file_path()
        history = load_json(performance_file_path, default=[])
        return history if isinstance(history, list) else []

    def add_performance_record(
        self, case_num: int, metrics: Dict[str, Any], snapshot_id: Optional[str] = None
    ) -> None:
        """
        Add a new performance record to the history.

        Args:
            case_num: Test case number
            metrics: Performance metrics dictionary
            snapshot_id: Optional associated snapshot ID

        Raises:
            HistoryManagerError: If saving fails
        """
        performance_file_path = self._get_performance_file_path()
        records = self.get_performance_history()

        new_record = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "language": self.language,
            "case_num": case_num,
            "metrics": metrics,
            "snapshot_id": snapshot_id,
        }

        records.append(new_record)
        save_json(performance_file_path, records)

    def _get_performance_file_path(self) -> str:
        """Get the path to the performance history file."""
        return os.path.join(self.performance_dir, f"{self.language}.json")
