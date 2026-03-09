#!/usr/bin/env python
"""
Live monitoring dashboard for discovery runs.

Beautiful terminal interface showing real-time agent activity.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import requests
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich import box

BASE_URL = os.getenv("SCIENCE_OS_API_BASE_URL", "http://localhost:8000").rstrip("/")


class DiscoveryMonitor:
    """Real-time monitoring for discovery runs."""

    def __init__(self, base_url: Optional[str] = None):
        self.console = Console()
        self.base_url = (base_url or BASE_URL).rstrip("/")
        self.runs: Dict[int, Dict] = {}
        self.start_time = datetime.now()

    def fetch_run_status(self, run_id: int) -> Dict:
        """Fetch current status of a run."""
        try:
            response = requests.get(f"{self.base_url}/runs/{run_id}", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"id": run_id, "status": "error", "error": str(e)}

    def parse_trajectory(self, trajectory: List[Dict]) -> Dict:
        """Extract useful metrics from trajectory."""
        if not trajectory:
            return {
                "tool_calls": 0,
                "reflections": 0,
                "last_action": "Initializing...",
                "findings_preview": "",
            }

        tool_calls = sum(1 for msg in trajectory if msg.get("role") == "tool")
        agent_msgs = [msg for msg in trajectory if msg.get("role") == "agent"]

        reflections = sum(1 for msg in agent_msgs
                         if "reflect" in msg.get("content", "").lower()[:100])

        # Get last meaningful action
        last_action = "Thinking..."
        if trajectory:
            last_msg = trajectory[-1]
            role = last_msg.get("role", "")
            content = last_msg.get("content", "")

            if role == "tool":
                tool_name = last_msg.get("tool_name", "unknown")
                last_action = f"🔧 {tool_name}: {content[:60]}..."
            elif role == "agent":
                if "finish" in content.lower()[:50]:
                    last_action = "✅ Finalizing findings"
                elif "tool_call" in content.lower()[:100]:
                    last_action = "🎯 Planning next tool call"
                else:
                    last_action = f"💭 {content[:60]}..."

        # Extract findings preview if finished
        findings_preview = ""
        for msg in reversed(agent_msgs):
            content = msg.get("content", "")
            if "findings:" in content.lower() or "discovery summary" in content.lower():
                findings_preview = content[:200] + "..."
                break

        return {
            "tool_calls": tool_calls,
            "reflections": reflections,
            "last_action": last_action,
            "findings_preview": findings_preview,
        }

    def create_header(self) -> Panel:
        """Create header panel."""
        elapsed = datetime.now() - self.start_time
        elapsed_str = str(elapsed).split('.')[0]

        # Try to get model from first run
        model_name = None
        for run_id, data in self.runs.items():
            spec = data.get("spec", {})
            if spec and isinstance(spec, dict):
                model_name = spec.get("model")
                if model_name:
                    break

        header_text = Text()
        header_text.append("🔭 ", style="bold cyan")
        header_text.append("JWST Deep Discovery Monitor", style="bold white")
        header_text.append(f"\n⏱️  Session time: {elapsed_str}", style="dim")
        header_text.append(f" | Runs: {len(self.runs)}", style="dim")
        if model_name:
            header_text.append(f" | Model: {model_name}", style="bold yellow")

        return Panel(header_text, border_style="cyan", box=box.DOUBLE)

    def create_run_table(self) -> Table:
        """Create table showing all runs."""
        table = Table(
            title="Active Discovery Runs",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            border_style="blue",
        )

        table.add_column("ID", style="cyan", width=6)
        table.add_column("Status", width=12)
        table.add_column("Tools", justify="right", width=8)
        table.add_column("Reflect", justify="right", width=8)
        table.add_column("Duration", width=10)
        table.add_column("Last Action", style="dim", width=50)

        for run_id in sorted(self.runs.keys()):
            data = self.runs[run_id]
            status = data.get("status", "unknown")

            # Status styling
            if status == "completed":
                status_text = Text("✅ DONE", style="bold green")
            elif status == "failed":
                status_text = Text("❌ FAIL", style="bold red")
            elif status == "running":
                status_text = Text("🔄 RUN", style="bold yellow")
            else:
                status_text = Text(f"⏸️  {status.upper()}", style="dim")

            # Parse trajectory
            trajectory = data.get("trajectory", [])
            metrics = self.parse_trajectory(trajectory)

            # Calculate duration
            created = data.get("created_at", "")
            updated = data.get("updated_at", "")
            if created and updated:
                try:
                    duration = (datetime.fromisoformat(updated) -
                              datetime.fromisoformat(created)).total_seconds()
                    duration_str = f"{duration:.1f}s"
                except:
                    duration_str = "—"
            else:
                duration_str = "—"

            table.add_row(
                str(run_id),
                status_text,
                str(metrics["tool_calls"]),
                str(metrics["reflections"]),
                duration_str,
                metrics["last_action"][:50],
            )

        return table

    def create_findings_panel(self) -> Panel:
        """Create panel showing recent findings."""
        findings_text = Text()

        completed_runs = [
            (run_id, data) for run_id, data in self.runs.items()
            if data.get("status") == "completed"
        ]

        if not completed_runs:
            findings_text.append("No completed runs yet...", style="dim italic")
        else:
            for run_id, data in completed_runs[-3:]:  # Last 3 completed
                trajectory = data.get("trajectory", [])
                metrics = self.parse_trajectory(trajectory)

                findings_text.append(f"Run {run_id}: ", style="bold cyan")
                findings_text.append(f"{metrics['tool_calls']} tools, ", style="dim")

                if metrics["findings_preview"]:
                    findings_text.append(f"\n  {metrics['findings_preview']}\n\n", style="white")
                else:
                    findings_text.append("(extracting findings...)\n\n", style="dim italic")

        return Panel(
            findings_text,
            title="Recent Findings",
            border_style="green",
            box=box.ROUNDED,
        )

    def create_stats_panel(self) -> Panel:
        """Create statistics panel."""
        total_runs = len(self.runs)
        completed = sum(1 for data in self.runs.values() if data.get("status") == "completed")
        failed = sum(1 for data in self.runs.values() if data.get("status") == "failed")
        running = sum(1 for data in self.runs.values() if data.get("status") == "running")

        total_tools = sum(
            self.parse_trajectory(data.get("trajectory", []))["tool_calls"]
            for data in self.runs.values()
        )

        stats_text = Text()
        stats_text.append(f"📊 Total Runs: {total_runs}\n", style="bold white")
        stats_text.append(f"✅ Completed: {completed}\n", style="green")
        stats_text.append(f"🔄 Running: {running}\n", style="yellow")
        stats_text.append(f"❌ Failed: {failed}\n", style="red")
        stats_text.append(f"🔧 Total Tool Calls: {total_tools}\n", style="cyan")

        return Panel(
            stats_text,
            title="Session Statistics",
            border_style="magenta",
            box=box.ROUNDED,
        )

    def create_layout(self) -> Layout:
        """Create the full dashboard layout."""
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="main", ratio=2),
            Layout(name="footer", ratio=1),
        )

        layout["main"].split_row(
            Layout(name="runs", ratio=2),
            Layout(name="stats", ratio=1),
        )

        layout["header"].update(self.create_header())
        layout["runs"].update(self.create_run_table())
        layout["stats"].update(self.create_stats_panel())
        layout["footer"].update(self.create_findings_panel())

        return layout

    def monitor(
        self,
        run_ids: List[int],
        refresh_rate: float = 2.0,
        timeout: int = 1800,
    ):
        """
        Monitor multiple runs with live updates.

        Args:
            run_ids: List of run IDs to monitor
            refresh_rate: Update interval in seconds
            timeout: Maximum monitoring time
        """
        self.start_time = datetime.now()
        self.console.clear()

        # Initial fetch
        for run_id in run_ids:
            self.runs[run_id] = self.fetch_run_status(run_id)

        with Live(
            self.create_layout(),
            console=self.console,
            refresh_per_second=1.0 / refresh_rate,
            screen=True,
        ) as live:
            start = time.time()

            while True:
                # Check timeout
                if time.time() - start > timeout:
                    break

                # Update all runs
                for run_id in run_ids:
                    self.runs[run_id] = self.fetch_run_status(run_id)

                # Check if all completed or failed
                all_done = all(
                    data.get("status") in ["completed", "failed"]
                    for data in self.runs.values()
                )

                # Update display
                live.update(self.create_layout())

                if all_done:
                    time.sleep(2)  # Show final state briefly
                    break

                time.sleep(refresh_rate)

        # Final summary
        self.print_final_summary()

    def print_final_summary(self):
        """Print final summary after monitoring."""
        self.console.print("\n")
        self.console.rule("[bold cyan]Final Summary", style="cyan")
        self.console.print()

        for run_id, data in sorted(self.runs.items()):
            status = data.get("status", "unknown")
            trajectory = data.get("trajectory", [])
            metrics = self.parse_trajectory(trajectory)

            # Status icon
            if status == "completed":
                icon = "✅"
                style = "green"
            elif status == "failed":
                icon = "❌"
                style = "red"
            else:
                icon = "⚠️"
                style = "yellow"

            self.console.print(f"{icon} [bold]Run {run_id}[/bold] [{style}]{status}[/{style}]")
            self.console.print(f"   Tool calls: {metrics['tool_calls']}")
            self.console.print(f"   Reflections: {metrics['reflections']}")

            if metrics["findings_preview"]:
                self.console.print(f"   Findings: {metrics['findings_preview'][:150]}...")

            self.console.print()


def monitor_runs(run_ids: List[int], refresh_rate: float = 2.0):
    """
    Monitor discovery runs with live dashboard.

    Args:
        run_ids: List of run IDs to track
        refresh_rate: Update interval in seconds
    """
    monitor = DiscoveryMonitor()

    try:
        monitor.monitor(run_ids, refresh_rate=refresh_rate)
    except KeyboardInterrupt:
        monitor.console.print("\n[yellow]⚠️  Monitoring interrupted by user[/yellow]\n")
        monitor.print_final_summary()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python discovery_monitor.py <run_id> [run_id2 run_id3 ...]")
        print("\nExample:")
        print("  python discovery_monitor.py 42")
        print("  python discovery_monitor.py 42 43 44")
        sys.exit(1)

    run_ids = [int(rid) for rid in sys.argv[1:]]
    monitor_runs(run_ids, refresh_rate=2.0)
