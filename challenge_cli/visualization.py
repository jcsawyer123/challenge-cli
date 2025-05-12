import os
import json
import datetime
import tempfile
import webbrowser
import subprocess
from typing import Dict, List, Optional

class HistoryVisualizer:
    """
    Visualizes history data with interactive charts using HTML/JavaScript.
    """
    
    def __init__(self, challenge_dir: str, language: str):
        """
        Initialize the visualizer.
        
        Args:
            challenge_dir: Path to the challenge directory
            language: Programming language to visualize
        """
        self.challenge_dir = challenge_dir
        self.language = language
        self.history_dir = os.path.join(challenge_dir, '.history')
        self.performance_file = os.path.join(self.history_dir, 'performance', f"{language}.json")
        self.test_results_file = os.path.join(self.history_dir, 'test_results', f"{language}.json")
        
    def _load_performance_data(self) -> List[Dict]:
        """Load performance history data."""
        if not os.path.exists(self.performance_file):
            return []
            
        with open(self.performance_file, 'r') as f:
            return json.load(f)
            
    def _load_test_results_data(self) -> List[Dict]:
        """Load test results history data."""
        if not os.path.exists(self.test_results_file):
            return []
            
        with open(self.test_results_file, 'r') as f:
            return json.load(f)
            
    def _load_snapshots_metadata(self) -> Dict[str, Dict]:
        """Load metadata for all snapshots."""
        snapshots_dir = os.path.join(self.history_dir, 'snapshots')
        if not os.path.exists(snapshots_dir):
            return {}
            
        snapshots = {}
        for item in os.listdir(snapshots_dir):
            if item.endswith(f"_{self.language}"):
                metadata_file = os.path.join(snapshots_dir, item, 'metadata.json')
                if os.path.exists(metadata_file):
                    with open(metadata_file, 'r') as f:
                        snapshots[item] = json.load(f)
        
        return snapshots
        
    def _generate_performance_chart_data(self, case_filter: Optional[List[int]] = None) -> Dict:
        """
        Generate data for performance chart.
        
        Args:
            case_filter: List of test cases to include (None for all)
            
        Returns:
            Dict with chart data
        """
        performance_data = self._load_performance_data()
        if not performance_data:
            return {"timestamps": [], "series": []}
            
        # Group by snapshot and timestamp
        grouped_data = {}
        for record in performance_data:
            case_num = record.get("case_num")
            if case_filter and case_num not in case_filter:
                continue
                
            timestamp = record.get("timestamp")
            snapshot_id = record.get("snapshot_id")
            metrics = record.get("metrics", {})
            
            if not timestamp or not metrics:
                continue
                
            # Convert timestamp to datetime object for sorting
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                # Format to shorter string for display
                display_timestamp = dt.strftime("%Y-%m-%d %H:%M")
            except:
                display_timestamp = timestamp
                
            # Create key for sorting and grouping
            if snapshot_id:
                key = f"{snapshot_id}_{display_timestamp}"
            else:
                key = f"unknown_{display_timestamp}"
                
            if key not in grouped_data:
                grouped_data[key] = {
                    "timestamp": display_timestamp,
                    "snapshot_id": snapshot_id,
                    "cases": {}
                }
                
            grouped_data[key]["cases"][case_num] = {
                "time_ms": metrics.get("time_ms"),
                "mem_bytes": metrics.get("mem_bytes")
            }
            
        # Sort by timestamp
        sorted_keys = sorted(grouped_data.keys())
        
        # Get unique case numbers
        all_cases = set()
        for key in sorted_keys:
            all_cases.update(grouped_data[key]["cases"].keys())
        
        # Prepare chart data
        timestamps = []
        time_series = {}
        memory_series = {}
        
        for case_num in sorted(all_cases):
            time_series[case_num] = []
            memory_series[case_num] = []
            
        for key in sorted_keys:
            data = grouped_data[key]
            timestamps.append(data["timestamp"])
            
            for case_num in all_cases:
                case_data = data["cases"].get(case_num, {})
                time_ms = case_data.get("time_ms")
                mem_bytes = case_data.get("mem_bytes")
                
                time_series[case_num].append(time_ms)
                memory_series[case_num].append(mem_bytes)
                
        return {
            "timestamps": timestamps,
            "time_series": time_series,
            "memory_series": memory_series
        }
        
    def _generate_test_results_chart_data(self) -> Dict:
        """
        Generate data for test results chart.
        
        Returns:
            Dict with chart data
        """
        test_data = self._load_test_results_data()
        if not test_data:
            return {"timestamps": [], "passed": [], "failed": []}
            
        # Prepare chart data
        timestamps = []
        passed = []
        failed = []
        
        for record in sorted(test_data, key=lambda x: x.get("timestamp", "")):
            timestamp = record.get("timestamp")
            summary = record.get("summary", {})
            
            if not timestamp or not summary:
                continue
                
            # Convert timestamp to datetime object for sorting
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                # Format to shorter string for display
                display_timestamp = dt.strftime("%Y-%m-%d %H:%M")
            except:
                display_timestamp = timestamp
                
            total = summary.get("total", 0)
            passed_count = summary.get("passed", 0)
            failed_count = total - passed_count
            
            timestamps.append(display_timestamp)
            passed.append(passed_count)
            failed.append(failed_count)
            
        return {
            "timestamps": timestamps,
            "passed": passed,
            "failed": failed
        }
        
    def generate_html(self, title: str = "Challenge Performance Visualization") -> str:
        """
        Generate HTML for visualization.
        
        Args:
            title: Chart title
            
        Returns:
            HTML content as string
        """
        performance_data = self._generate_performance_chart_data()
        test_results_data = self._generate_test_results_chart_data()
        snapshots_metadata = self._load_snapshots_metadata()
        
        # Convert data to JSON for JavaScript
        performance_json = json.dumps(performance_data)
        test_results_json = json.dumps(test_results_data)
        snapshots_json = json.dumps(snapshots_metadata)
        
        html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .chart-container {{ position: relative; height: 400px; margin-bottom: 30px; }}
        .header {{ margin-bottom: 20px; }}
        .tab {{ overflow: hidden; border: 1px solid #ccc; background-color: #f1f1f1; }}
        .tab button {{ background-color: inherit; float: left; border: none; outline: none; cursor: pointer; padding: 14px 16px; transition: 0.3s; }}
        .tab button:hover {{ background-color: #ddd; }}
        .tab button.active {{ background-color: #ccc; }}
        .tabcontent {{ display: none; padding: 6px 12px; border: 1px solid #ccc; border-top: none; }}
        .visible {{ display: block; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{title}</h1>
        <p>Language: {self.language}</p>
    </div>
    
    <div class="tab">
        <button class="tablinks active" onclick="openTab(event, 'performance')">Performance History</button>
        <button class="tablinks" onclick="openTab(event, 'memory')">Memory Usage</button>
        <button class="tablinks" onclick="openTab(event, 'tests')">Test Results</button>
    </div>
    
    <div id="performance" class="tabcontent visible">
        <h2>Execution Time History</h2>
        <div class="chart-container">
            <canvas id="performanceChart"></canvas>
        </div>
    </div>
    
    <div id="memory" class="tabcontent">
        <h2>Memory Usage History</h2>
        <div class="chart-container">
            <canvas id="memoryChart"></canvas>
        </div>
    </div>
    
    <div id="tests" class="tabcontent">
        <h2>Test Results History</h2>
        <div class="chart-container">
            <canvas id="testsChart"></canvas>
        </div>
    </div>
    
    <script>
        // Performance data
        const performanceData = {performance_json};
        
        // Test results data
        const testResultsData = {test_results_json};
        
        // Snapshots metadata
        const snapshotsMetadata = {snapshots_json};
        
        // Tab functionality
        function openTab(evt, tabName) {{
            const tabcontent = document.getElementsByClassName("tabcontent");
            for (let i = 0; i < tabcontent.length; i++) {{
                tabcontent[i].classList.remove("visible");
            }}
            
            const tablinks = document.getElementsByClassName("tablinks");
            for (let i = 0; i < tablinks.length; i++) {{
                tablinks[i].classList.remove("active");
            }}
            
            document.getElementById(tabName).classList.add("visible");
            evt.currentTarget.classList.add("active");
        }}
        
        // Generate random colors for chart series
        function getRandomColor(index) {{
            const colors = [
                'rgba(255, 99, 132, 0.7)',
                'rgba(54, 162, 235, 0.7)',
                'rgba(255, 206, 86, 0.7)',
                'rgba(75, 192, 192, 0.7)',
                'rgba(153, 102, 255, 0.7)',
                'rgba(255, 159, 64, 0.7)',
                'rgba(201, 203, 207, 0.7)',
                'rgba(255, 99, 255, 0.7)',
                'rgba(99, 255, 132, 0.7)',
                'rgba(86, 142, 255, 0.7)'
            ];
            
            if (index < colors.length) {{
                return colors[index];
            }}
            
            // Generate random color if we run out of predefined colors
            return `rgba(${{Math.floor(Math.random() * 255)}}, ${{Math.floor(Math.random() * 255)}}, ${{Math.floor(Math.random() * 255)}}, 0.7)`;
        }}
        
        // Initialize charts
        document.addEventListener('DOMContentLoaded', function() {{
            // Performance Chart
            const performanceCtx = document.getElementById('performanceChart').getContext('2d');
            
            const performanceDatasets = [];
            let caseIndex = 0;
            
            // Create datasets for each test case
            for (const [caseNum, values] of Object.entries(performanceData.time_series)) {{
                performanceDatasets.push({{
                    label: `Case ${{caseNum}}`,
                    data: values,
                    backgroundColor: getRandomColor(caseIndex),
                    borderColor: getRandomColor(caseIndex).replace('0.7', '1.0'),
                    borderWidth: 2,
                    fill: false,
                    tension: 0.1
                }});
                caseIndex++;
            }}
            
            const performanceChart = new Chart(performanceCtx, {{
                type: 'line',
                data: {{
                    labels: performanceData.timestamps,
                    datasets: performanceDatasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            title: {{
                                display: true,
                                text: 'Execution Time (ms)'
                            }},
                            beginAtZero: true
                        }},
                        x: {{
                            title: {{
                                display: true,
                                text: 'Timestamp'
                            }}
                        }}
                    }},
                    plugins: {{
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    const label = context.dataset.label || '';
                                    const value = context.parsed.y || 0;
                                    return `${{label}}: ${{value.toFixed(2)}} ms`;
                                }}
                            }}
                        }}
                    }}
                }}
            }});
            
            // Memory Chart
            const memoryCtx = document.getElementById('memoryChart').getContext('2d');
            
            const memoryDatasets = [];
            caseIndex = 0;
            
            // Create datasets for each test case
            for (const [caseNum, values] of Object.entries(performanceData.memory_series)) {{
                memoryDatasets.push({{
                    label: `Case ${{caseNum}}`,
                    data: values,
                    backgroundColor: getRandomColor(caseIndex),
                    borderColor: getRandomColor(caseIndex).replace('0.7', '1.0'),
                    borderWidth: 2,
                    fill: false,
                    tension: 0.1
                }});
                caseIndex++;
            }}
            
            const memoryChart = new Chart(memoryCtx, {{
                type: 'line',
                data: {{
                    labels: performanceData.timestamps,
                    datasets: memoryDatasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            title: {{
                                display: true,
                                text: 'Memory Usage (bytes)'
                            }},
                            beginAtZero: true
                        }},
                        x: {{
                            title: {{
                                display: true,
                                text: 'Timestamp'
                            }}
                        }}
                    }},
                    plugins: {{
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    const label = context.dataset.label || '';
                                    const value = context.parsed.y || 0;
                                    
                                    // Format bytes to KB/MB if large
                                    let formattedValue;
                                    if (value > 1024 * 1024) {{
                                        formattedValue = `${{(value / (1024 * 1024)).toFixed(2)}} MB`;
                                    }} else if (value > 1024) {{
                                        formattedValue = `${{(value / 1024).toFixed(2)}} KB`;
                                    }} else {{
                                        formattedValue = `${{value.toFixed(2)}} bytes`;
                                    }}
                                    
                                    return `${{label}}: ${{formattedValue}}`;
                                }}
                            }}
                        }}
                    }}
                }}
            }});
            
            // Test Results Chart
            const testsCtx = document.getElementById('testsChart').getContext('2d');
            
            const testsChart = new Chart(testsCtx, {{
                type: 'bar',
                data: {{
                    labels: testResultsData.timestamps,
                    datasets: [
                        {{
                            label: 'Passed',
                            data: testResultsData.passed,
                            backgroundColor: 'rgba(75, 192, 192, 0.7)',
                            borderColor: 'rgba(75, 192, 192, 1)',
                            borderWidth: 1
                        }},
                        {{
                            label: 'Failed',
                            data: testResultsData.failed,
                            backgroundColor: 'rgba(255, 99, 132, 0.7)',
                            borderColor: 'rgba(255, 99, 132, 1)',
                            borderWidth: 1
                        }}
                    ]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            title: {{
                                display: true,
                                text: 'Number of Test Cases'
                            }},
                            beginAtZero: true,
                            stacked: true
                        }},
                        x: {{
                            title: {{
                                display: true,
                                text: 'Timestamp'
                            }},
                            stacked: true
                        }}
                    }},
                    plugins: {{
                        tooltip: {{
                            callbacks: {{
                                footer: function(tooltipItems) {{
                                    let total = 0;
                                    tooltipItems.forEach(function(tooltipItem) {{
                                        total += tooltipItem.parsed.y;
                                    }});
                                    return `Total: ${{total}}`;
                                }}
                            }}
                        }}
                    }}
                }}
            }});
        }});
    </script>
</body>
</html>
"""
        return html_template
    
    def visualize(self, output_path: Optional[str] = None) -> str:
        """
        Generate visualization and open in browser.
        
        Args:
            output_path: Path to save the HTML file (optional, uses temp file if None)
            
        Returns:
            Path to the generated HTML file
        """
        html_content = self.generate_html()
        
        if output_path:
            html_file = output_path
        else:
            # Create a temporary file
            fd, html_file = tempfile.mkstemp(suffix='.html', prefix='challenge_viz_')
            os.close(fd)
        
        with open(html_file, 'w') as f:
            f.write(html_content)
        
        # Open the HTML file in the default browser
        try:
            webbrowser.open('file://' + os.path.abspath(html_file))
            print(f"Visualization opened in browser: {html_file}")
        except Exception as e:
            print(f"Failed to open browser: {e}")
            print(f"Visualization saved to: {html_file}")
        
        return html_file