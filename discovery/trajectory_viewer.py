"""
Trajectory viewer - see the complete agent thinking process.

This shows every step the agent took, every tool call, and every observation.
"""

import os
import requests
import json
from typing import Dict
from datetime import datetime


BASE_URL = os.getenv("SCIENCE_OS_API_BASE_URL", "http://localhost:8000").rstrip("/")


def get_full_trajectory(run_id: int):
    """Get the complete trajectory for a run."""
    response = requests.get(f"{BASE_URL}/runs/{run_id}")
    return response.json()


def format_timestamp(ts_str):
    """Format timestamp nicely."""
    if not ts_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
        return dt.strftime("%H:%M:%S")
    except:
        return ts_str


def print_trajectory(run_id: int, show_tool_results=True, show_timing=True):
    """
    Print the complete agent trajectory with formatting.

    Args:
        run_id: Run ID to view
        show_tool_results: Whether to show detailed tool results
        show_timing: Whether to show timestamps
    """
    data = get_full_trajectory(run_id)

    print("\n" + "="*100)
    print(f"AGENT TRAJECTORY - RUN #{run_id}")
    print("="*100)

    print(f"\nOBJECTIVE: {data['spec']['objective']}")
    print(f"DATASETS: {', '.join(data['spec']['datasets'])}")
    print(f"STATUS: {data['status'].upper()}")

    if data.get('trajectory'):
        trajectory = data['trajectory']
        print(f"\nTOTAL STEPS: {len(trajectory)}")
        print("\n" + "-"*100)

        for i, msg in enumerate(trajectory, 1):
            role = msg.get('role', 'unknown').upper()
            content = msg.get('content', '')
            tool_name = msg.get('tool_name')
            timestamp = msg.get('timestamp')

            # Header
            header = f"[{i}] {role}"
            if tool_name:
                header += f" - {tool_name}"
            if show_timing and timestamp:
                header += f" @ {format_timestamp(timestamp)}"

            print(f"\n{header}")
            print("-" * len(header))

            # Content
            if role == "USER":
                print(f"> {content}")

            elif role == "AGENT":
                # Agent's reasoning and decisions
                if len(content) > 500 and not show_tool_results:
                    print(f"{content[:500]}...")
                else:
                    print(content)

            elif role == "TOOL":
                # Tool observations
                if show_tool_results:
                    if len(content) > 300:
                        print(f"> {content[:300]}...")
                    else:
                        print(f"> {content}")
                else:
                    print(f"> [Tool result: {len(content)} chars]")

        print("\n" + "-"*100)

    # Final result
    if data.get('result'):
        result = data['result']
        print(f"\nFINAL STATUS: {result['status'].upper()}")

        if result.get('summary_metrics'):
            print(f"\nMETRICS:")
            for key, value in result['summary_metrics'].items():
                print(f"  {key}: {value}")

        if result.get('error'):
            print(f"\nERROR: {result['error']}")

    print("\n" + "="*100 + "\n")


def compare_trajectories(run_ids: list):
    """
    Compare trajectories of multiple runs side by side.

    Args:
        run_ids: List of run IDs to compare
    """
    print("\n" + "="*100)
    print(f"TRAJECTORY COMPARISON - Runs: {run_ids}")
    print("="*100)

    trajectories = []
    for run_id in run_ids:
        data = get_full_trajectory(run_id)
        trajectories.append({
            'id': run_id,
            'objective': data['spec']['objective'],
            'status': data['status'],
            'steps': len(data.get('trajectory', [])),
            'result': data.get('result', {}).get('status'),
        })

    # Print comparison table
    print(f"\n{'ID':<6} {'Steps':<7} {'Status':<12} {'Objective'}")
    print("-" * 100)

    for t in trajectories:
        obj = t['objective'][:60] + "..." if len(t['objective']) > 60 else t['objective']
        print(f"{t['id']:<6} {t['steps']:<7} {t['status']:<12} {obj}")

    print("\n" + "="*100 + "\n")


def export_trajectory_to_markdown(run_id: int, output_file: str = None):
    """Export trajectory to markdown file for easy reading."""
    if output_file is None:
        output_file = f"discovery/trajectory_{run_id}.md"

    data = get_full_trajectory(run_id)

    md_content = f"""# Agent Trajectory - Run #{run_id}

## Objective
{data['spec']['objective']}

## Configuration
- **Datasets**: {', '.join(data['spec']['datasets'])}
- **Status**: {data['status']}
- **Started**: {data.get('started_at', 'N/A')}
- **Completed**: {data.get('completed_at', 'N/A')}

## Trajectory

"""

    if data.get('trajectory'):
        for i, msg in enumerate(data['trajectory'], 1):
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            tool_name = msg.get('tool_name')

            md_content += f"\n### Step {i}: {role.title()}"
            if tool_name:
                md_content += f" - `{tool_name}`"
            md_content += "\n\n"

            md_content += f"{content}\n"

    # Write to file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)

    print(f"✓ Trajectory exported to {output_file}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python trajectory_viewer.py <run_id> [--export]")
        print("   or: python trajectory_viewer.py --compare <id1> <id2> ...")
        sys.exit(1)

    if sys.argv[1] == "--compare":
        run_ids = [int(x) for x in sys.argv[2:]]
        compare_trajectories(run_ids)
    else:
        run_id = int(sys.argv[1])

        if "--export" in sys.argv:
            export_trajectory_to_markdown(run_id)
        else:
            print_trajectory(run_id, show_tool_results=True, show_timing=True)
