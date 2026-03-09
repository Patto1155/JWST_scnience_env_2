#!/usr/bin/env python
"""
Stream discovery runs in real-time - watch agent thinking live!

Polls the API for trajectory updates and displays them as they happen.
"""

import requests
import time
import sys
import os
import sys
import time
from datetime import datetime
from typing import Dict, Optional, Set

import requests
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich import box

BASE_URL = os.getenv("SCIENCE_OS_API_BASE_URL", "http://localhost:8000").rstrip("/")


class DiscoveryStreamer:
    """Streams discovery run output in real-time."""

    def __init__(self, run_id: int, base_url: Optional[str] = None):
        self.run_id = run_id
        self.base_url = (base_url or BASE_URL).rstrip("/")
        self.console = Console()
        self.seen_messages: Set[str] = set()  # Track which messages we've printed
        self.last_message_count = 0

    def fetch_trajectory(self) -> Dict:
        """Fetch current run trajectory."""
        try:
            response = requests.get(f"{self.base_url}/runs/{self.run_id}", timeout=5)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def print_message(self, msg: Dict, index: int):
        """Print a single message from trajectory."""
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        tool_name = msg.get("tool_name")
        timestamp = msg.get("timestamp", "")

        # Create unique ID for message
        msg_id = f"{index}:{role}:{content[:50]}"
        if msg_id in self.seen_messages:
            return  # Already printed
        self.seen_messages.add(msg_id)

        # Format timestamp
        try:
            ts = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
        except:
            ts = "??:??:??"

        if role == "user":
            # User/system message
            text = Text()
            text.append(f"[{ts}] ", style="dim")
            text.append("📋 OBJECTIVE: ", style="bold cyan")
            text.append(content[:300])
            panel = Panel(
                text,
                border_style="cyan",
                box=box.ROUNDED,
                title="Research Objective",
            )
            self.console.print(panel)

        elif role == "agent":
            # Agent thinking/response
            if "Final Findings:" in content:
                # Final findings - special treatment
                text = Text()
                text.append(f"[{ts}] ", style="dim")
                text.append("🎯 FINAL FINDINGS: ", style="bold green")
                text.append(content.replace("Final Findings:", "").strip())
                panel = Panel(
                    text,
                    border_style="green",
                    box=box.DOUBLE,
                    title="✅ Discovery Complete",
                )
                self.console.print(panel)
            elif "reflect" in content.lower()[:100]:
                # Reflection
                text = Text()
                text.append(f"[{ts}] ", style="dim")
                text.append("💭 REFLECTION: ", style="bold magenta")
                text.append(content[:400])
                panel = Panel(
                    text,
                    border_style="magenta",
                    box=box.ROUNDED,
                    title="Deep Thinking",
                )
                self.console.print(panel)
            else:
                # Regular agent response
                text = Text()
                text.append(f"[{ts}] ", style="dim")
                text.append("🤖 AGENT: ", style="bold blue")
                text.append(content[:500])
                panel = Panel(
                    text,
                    border_style="blue",
                    box=box.ROUNDED,
                )
                self.console.print(panel)

        elif role == "tool":
            # Tool result
            if tool_name:
                if "Error:" in content:
                    # Tool error
                    self.console.print(f"[{ts}] [bold red]❌ {tool_name} ERROR:[/bold red] {content[:200]}")
                else:
                    # Tool success
                    self.console.print(f"[{ts}] [bold yellow]🔧 {tool_name}:[/bold yellow]")
                    text = Text()
                    text.append(f"   ", style="dim")
                    text.append("📊 ", style="green")
                    text.append(content[:400])
                    self.console.print(text)

    def stream(self, poll_interval: float = 2.0, timeout: int = 1800):
        """
        Stream the discovery run in real-time.

        Args:
            poll_interval: Seconds between polls
            timeout: Maximum time to wait
        """
        start_time = time.time()

        # Print header
        self.console.clear()
        self.console.rule("[bold cyan]🔭 JWST Discovery - Live Stream[/bold cyan]", style="cyan")
        self.console.print(f"\n[bold]Run ID:[/bold] {self.run_id}\n")

        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed > timeout:
                    self.console.print("\n[yellow]⏱️  Timeout reached[/yellow]\n")
                    break

                # Fetch current state
                data = self.fetch_trajectory()

                if "error" in data:
                    self.console.print(f"[red]Error fetching data: {data['error']}[/red]")
                    time.sleep(poll_interval)
                    continue

                # Get trajectory
                trajectory = data.get("trajectory", [])

                # Print new messages
                if len(trajectory) > self.last_message_count:
                    for i in range(self.last_message_count, len(trajectory)):
                        self.print_message(trajectory[i], i)

                    self.last_message_count = len(trajectory)

                # Check if done
                status = data.get("status", "unknown")
                if status in ["completed", "failed"]:
                    self.console.print()
                    if status == "completed":
                        self.console.rule("[bold green]✅ Discovery Completed Successfully[/bold green]", style="green")
                    else:
                        error = data.get("error", "Unknown error")
                        self.console.print(f"[bold red]❌ Discovery Failed:[/bold red] {error}")
                        self.console.rule("[bold red]Discovery Failed[/bold red]", style="red")
                    break

                # Show status update
                if elapsed > 0 and int(elapsed) % 10 == 0:  # Every 10 seconds
                    self.console.print(
                        f"[dim]⏳ Running... ({int(elapsed)}s elapsed, {len(trajectory)} messages)[/dim]",
                        end="\r"
                    )

                time.sleep(poll_interval)

        except KeyboardInterrupt:
            self.console.print("\n\n[yellow]⚠️  Streaming interrupted by user[/yellow]")
            self.console.print("[dim]Run continues in background...[/dim]\n")


def stream_run(run_id: int, poll_interval: float = 2.0, base_url: Optional[str] = None):
    """
    Stream a discovery run to terminal.

    Args:
        run_id: Run ID to stream
        poll_interval: Seconds between polls
    """
    streamer = DiscoveryStreamer(run_id, base_url=base_url)
    streamer.stream(poll_interval=poll_interval)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python stream_discovery.py <run_id>")
        print("\nExample:")
        print("  python stream_discovery.py 42")
        sys.exit(1)

    run_id = int(sys.argv[1])
    stream_run(run_id, poll_interval=2.0)
