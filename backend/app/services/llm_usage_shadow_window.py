"""Qualifying-window check shared by the shadow stamp and the cutover guard"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.core.config.settings import settings

# Shadow must stay healthy this many consecutive days before cutover can turn on
SHADOW_QUALIFYING_WINDOW_DAYS = 7

# Bump whenever a hard gate is added or tightened
GATE_VERSION = 2


def _metric_int(report, key: str, default: int) -> int:
    """Read one integer metric safely from free-form JSONB"""
    metrics = getattr(report, "metrics", None)
    raw = metrics.get(key) if isinstance(metrics, dict) else None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


def is_stale_verdict(report) -> bool:
    return _metric_int(report, "gate_version", 0) < GATE_VERSION


@dataclass
class ShadowWindow:
    """Whether a shadow qualifying window is healthy, 
    with missing/failed/stale days listed separately
    """

    required: list[date]
    missing: list[date] = field(default_factory=list)
    failed: list[date] = field(default_factory=list)
    stale: list[date] = field(default_factory=list)
    capture_runs: int = 0

    @property
    def min_capture_runs(self) -> int:
        return settings.LLM_USAGE_SHADOW_MIN_CAPTURE_RUNS

    @property
    def has_volume(self) -> bool:
        return self.capture_runs >= self.min_capture_runs

    @property
    def passed(self) -> bool:
        return not self.missing and not self.failed and not self.stale and self.has_volume

    def describe(self) -> str:
        parts = []
        if self.missing:
            parts.append(f"missing days: {[d.isoformat() for d in self.missing]}")
        if self.failed:
            parts.append(f"failing days: {[d.isoformat() for d in self.failed]}")
        if self.stale:
            parts.append(f"days awaiting re-check under the current gates: {[d.isoformat() for d in self.stale]}")
        if not self.has_volume:
            parts.append(f"capture runs {self.capture_runs} below minimum {self.min_capture_runs}")
        return "; ".join(parts) or "window is current"


def qualifying_days(today: date) -> list[date]:
    return [today - timedelta(days=SHADOW_QUALIFYING_WINDOW_DAYS - i) for i in range(SHADOW_QUALIFYING_WINDOW_DAYS)]


async def evaluate_window(reconciliation_repo, today: date) -> ShadowWindow:
    """Read the window's reports by exact date and summarize its health"""
    required = qualifying_days(today)
    by_date = {r.report_date: r for r in await reconciliation_repo.reports_between(required[0], required[-1])}

    window = ShadowWindow(required=required)
    for day in required:
        report = by_date.get(day)
        if report is None:
            window.missing.append(day)
        elif not report.passed:
            window.failed.append(day)
        elif is_stale_verdict(report):
            window.stale.append(day)

    window.capture_runs = sum(_metric_int(by_date[day], "capture_runs", 0) for day in required if day in by_date)
    return window
