"""Tooltip definitions for metric labels shown on the dashboard.

Keep this in sync with the metric cards and frontier table headers so that a
visitor who hovers any label sees a short, concrete definition.
"""

from __future__ import annotations

METRIC_TITLES: dict[str, str] = {
    "Headline score": "The versioned weighted total of abstract operations across the full suite. Lower is better. Only valid full-suite runs appear here.",
    "Runtime": "Sum of wall-clock seconds spent solving every instance in the suite.",
    "Peak memory": "Largest single-instance peak memory observed during the run, in mebibytes.",
    "Solution quality": "Median absolute size of the recovered coefficient vector across instances. Smaller is a tighter solution.",
    "Score": "The versioned weighted total of abstract operations across the full suite. Lower is better. Only valid full-suite runs appear here.",
    "Memory": "Largest single-instance peak memory observed during the run, in mebibytes.",
    "Quality": "Median absolute size of the recovered coefficient vector across instances. Smaller is a tighter solution.",
    "Baseline score": "Score of the baseline experiment in this cohort — the starting reference point for comparison.",
    "Current score": "Score of the best-ranked experiment currently on the leaderboard for this cohort.",
    "Improvement": "Percent change from baseline to current score. A positive number means the best score dropped (improved) relative to baseline.",
}
