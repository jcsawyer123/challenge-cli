import os
import json
import time
import shutil
import datetime
from typing import Dict, List, Any, Optional

class HistoryManager:
    """
    Manages the history of solutions, test results, and performance metrics.
    Handles versioning, pruning, and data retrieval for visualization.
    """
    
    def __init__(self, challenge_dir: str, language: str, max_snapshots: int = 50):
        """
        Initialize the history manager.
        
        Args:
            challenge_dir: Path to the challenge directory
            language: Programming language (python, go, javascript)
            max_snapshots: Maximum number of snapshots to keep (per language)
        """
        self.challenge_dir = challenge_dir
        self.language = language
        self.max_snapshots = max_snapshots
        
        # Create history directory structure if it doesn't exist
        self.history_dir = os.path.join(challenge_dir, '.history')
        self.snapshots_dir = os.path.join(self.history_dir, 'snapshots')
        self.performance_dir = os.path.join(self.history_dir, 'performance')
        self.test_results_dir = os.path.join(self.history_dir, 'test_results')
        
        # Ensure directories exist
        for directory in [self.history_dir, self.snapshots_dir, 
                          self.performance_dir, self.test_results_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Initialize metadata file if it doesn't exist
        self.metadata_file = os.path.join(self.history_dir, 'metadata.json')
        if not os.path.exists(self.metadata_file):
            self._initialize_metadata()
    
    def _initialize_metadata(self) -> None:
        """Initialize history metadata file with default settings."""
        metadata = {
            "created_at": datetime.datetime.now().isoformat(),
            "settings": {
                "max_snapshots": self.max_snapshots,
            },
            "languages": {}
        }
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _load_metadata(self) -> Dict:
        """Load history metadata."""
        if not os.path.exists(self.metadata_file):
            self._initialize_metadata()
        
        with open(self.metadata_file, 'r') as f:
            return json.load(f)
    
    def _save_metadata(self, metadata: Dict) -> None:
        """Save history metadata."""
        with open(self.metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
    
    def _update_language_metadata(self, snapshot_id: str = None) -> None:
        """Update language-specific metadata after taking a snapshot."""
        metadata = self._load_metadata()
        
        if self.language not in metadata["languages"]:
            metadata["languages"][self.language] = {
                "first_snapshot_at": datetime.datetime.now().isoformat(),
                "snapshot_count": 0,
                "latest_snapshot_id": None
            }
        
        lang_meta = metadata["languages"][self.language]
        lang_meta["snapshot_count"] += 1
        lang_meta["latest_snapshot_at"] = datetime.datetime.now().isoformat()
        if snapshot_id:
            lang_meta["latest_snapshot_id"] = snapshot_id
        
        self._save_metadata(metadata)
    
    def _get_snapshot_path(self, snapshot_id: str) -> str:
        """Get path to a specific snapshot directory."""
        return os.path.join(self.snapshots_dir, snapshot_id)
    
    def _get_latest_snapshots(self, limit: int = None) -> List[str]:
        """Get a list of snapshot IDs sorted by creation time (newest first)."""
        all_snapshots = []
        
        # Filter snapshots for current language
        for item in os.listdir(self.snapshots_dir):
            if item.endswith(f"_{self.language}"):
                all_snapshots.append(item)
        
        # Sort by timestamp (snapshot ID format: YYYYMMDD_HHMMSS_language)
        all_snapshots.sort(reverse=True)
        
        if limit is not None:
            return all_snapshots[:limit]
        return all_snapshots
    
    def create_snapshot(self, solution_file: str, function_name: str, 
                        tag: str = None, comment: str = None) -> str:
        """
        Create a new snapshot of the current solution.
        
        Args:
            solution_file: Path to the solution file
            function_name: Name of the solution function/method
            tag: Optional tag for this snapshot (e.g., "optimized", "initial")
            comment: Optional comment about this snapshot
        
        Returns:
            str: ID of the created snapshot
        """
        if not os.path.exists(solution_file):
            raise FileNotFoundError(f"Solution file not found: {solution_file}")
        
        # Generate timestamp and snapshot ID
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        snapshot_id = f"{timestamp}_{self.language}"
        snapshot_dir = self._get_snapshot_path(snapshot_id)
        
        # Create snapshot directory
        os.makedirs(snapshot_dir, exist_ok=True)
        
        # Copy solution file
        solution_filename = os.path.basename(solution_file)
        snapshot_solution_path = os.path.join(snapshot_dir, solution_filename)
        shutil.copy2(solution_file, snapshot_solution_path)
        
        # Create snapshot metadata
        snapshot_metadata = {
            "created_at": datetime.datetime.now().isoformat(),
            "function_name": function_name,
            "tag": tag,
            "comment": comment
        }
        
        # Save snapshot metadata
        with open(os.path.join(snapshot_dir, 'metadata.json'), 'w') as f:
            json.dump(snapshot_metadata, f, indent=2)
        
        # Update history metadata
        self._update_language_metadata(snapshot_id)
        
        # Prune old snapshots if necessary
        self._prune_old_snapshots()
        
        return snapshot_id
    
    def _prune_old_snapshots(self) -> None:
        """Remove old snapshots if exceeding max_snapshots limit."""
        snapshots = self._get_latest_snapshots()
        
        if len(snapshots) > self.max_snapshots:
            # Remove oldest snapshots
            for snapshot_id in snapshots[self.max_snapshots:]:
                snapshot_path = self._get_snapshot_path(snapshot_id)
                try:
                    shutil.rmtree(snapshot_path)
                except Exception as e:
                    print(f"Warning: Failed to remove old snapshot {snapshot_id}: {e}")
    
    def get_performance_history(self) -> List[Dict]:
        """
        Load performance history for the current language.
        
        Returns:
            List of performance records.
        """
        performance_file = os.path.join(self.performance_dir, f"{self.language}.json")
        
        if not os.path.exists(performance_file):
            return []
        
        with open(performance_file, 'r') as f:
            return json.load(f)
    
    def add_performance_record(self, case_num: int, metrics: Dict[str, Any], 
                               snapshot_id: str = None) -> None:
        """
        Add a new performance record.
        
        Args:
            case_num: Test case number
            metrics: Performance metrics (time_ms, mem_bytes, etc.)
            snapshot_id: Optional ID of associated snapshot
        """
        performance_file = os.path.join(self.performance_dir, f"{self.language}.json")
        
        # Load existing records or create empty list
        if os.path.exists(performance_file):
            with open(performance_file, 'r') as f:
                records = json.load(f)
        else:
            records = []
        
        # Create new record
        new_record = {
            "timestamp": datetime.datetime.now().isoformat(),
            "case_num": case_num,
            "metrics": metrics,
            "snapshot_id": snapshot_id
        }
        
        records.append(new_record)
        
        # Save updated records
        with open(performance_file, 'w') as f:
            json.dump(records, f, indent=2)
    
    def get_test_history(self) -> List[Dict]:
        """
        Load test result history for the current language.
        
        Returns:
            List of test result records.
        """
        test_file = os.path.join(self.test_results_dir, f"{self.language}.json")
        
        if not os.path.exists(test_file):
            return []
        
        with open(test_file, 'r') as f:
            return json.load(f)
    
    def add_test_results(self, results: List[Dict], snapshot_id: str = None) -> None:
        """
        Add new test results.
        
        Args:
            results: List of test results (case_num, passed, etc.)
            snapshot_id: Optional ID of associated snapshot
        """
        test_file = os.path.join(self.test_results_dir, f"{self.language}.json")
        
        # Load existing records or create empty list
        if os.path.exists(test_file):
            with open(test_file, 'r') as f:
                records = json.load(f)
        else:
            records = []
        
        # Create new record
        new_record = {
            "timestamp": datetime.datetime.now().isoformat(),
            "results": results,
            "snapshot_id": snapshot_id,
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.get("passed", False))
            }
        }
        
        records.append(new_record)
        
        # Save updated records
        with open(test_file, 'w') as f:
            json.dump(records, f, indent=2)
    
    def get_snapshot_solution(self, snapshot_id: str) -> Optional[str]:
        """
        Get the solution code from a specific snapshot.
        
        Args:
            snapshot_id: ID of the snapshot
            
        Returns:
            Solution code as a string, or None if not found
        """
        snapshot_dir = self._get_snapshot_path(snapshot_id)
        
        if not os.path.exists(snapshot_dir):
            return None
        
        # Find solution file in the snapshot directory
        for filename in os.listdir(snapshot_dir):
            if filename != 'metadata.json':
                solution_path = os.path.join(snapshot_dir, filename)
                with open(solution_path, 'r') as f:
                    return f.read()
        
        return None
    
    def get_snapshot_info(self, snapshot_id: str) -> Optional[Dict]:
        """
        Get metadata for a specific snapshot.
        
        Args:
            snapshot_id: ID of the snapshot
            
        Returns:
            Dictionary with snapshot metadata, or None if not found
        """
        snapshot_dir = self._get_snapshot_path(snapshot_id)
        metadata_path = os.path.join(snapshot_dir, 'metadata.json')
        
        if not os.path.exists(metadata_path):
            return None
        
        with open(metadata_path, 'r') as f:
            return json.load(f)