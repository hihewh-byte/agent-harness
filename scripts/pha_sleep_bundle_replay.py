#!/usr/bin/env python3
"""T0 offline replay: PHA_SLEEP_V1 → overlap / duplicate / sum-vs-union report.

Does not write the production DB. Read a captured shortcut body or the latest
dump under data/local_shortcuts/.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ASLEEP = frozenset({"sleep_core", "sleep_deep", "sleep_rem", "sleep_asleep"})
DEFAULT_TZ = "Asia/Shanghai"
DEFAULT_PATHS = (
    ROOT / "data" / "local_shortcuts" / "sleep_body_2026-09-07.txt",
    ROOT / "data" / "local_shortcuts" / "sleep_body_latest.txt",
)


def _hours(seconds: float) -> float:
    return seconds / 3600.0


def _fmt_h(hours: float) -> str:
    return f"{hours:.3f}h ({int(hours)}h {round((hours % 1) * 60)}m)"


def _load_text(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    if "PHA_SLEEP_V1" in raw and "preview='" in raw:
        start = raw.find("PHA_SLEEP_V1")
        end = raw.rfind("'")
        if end > start:
            raw = raw[start:end].encode("utf-8").decode("unicode_escape")
    return raw


def _pair_segments(text: str, *, tz_name: str, now: datetime, window_hours: float):
    from pha.healthkit_ingest import (
        _as_str_list,
        ingest_tz_name,
        normalize_timestamp,
        parse_sleep_bundle_text,
        resolve_sleep_stage_metric,
    )

    tz = tz_name or ingest_tz_name()
    bundle = parse_sleep_bundle_text(text)
    if bundle is None:
        raise SystemExit("not a PHA_SLEEP_V1 body")
    values = _as_str_list(bundle["sleep_values"])
    starts = _as_str_list(bundle["sleep_starts"])
    ends = _as_str_list(bundle["sleep_ends"])
    if not values or len(values) != len(starts) or len(values) != len(ends):
        raise SystemExit(
            f"list mismatch values={len(values)} starts={len(starts)} ends={len(ends)}"
        )
    window_start = now - timedelta(hours=window_hours)
    segments: list[dict] = []
    skipped_zero = 0
    unknown = 0
    for idx, (label, start_raw, end_raw) in enumerate(zip(values, starts, ends)):
        metric = resolve_sleep_stage_metric(label)
        if metric is None:
            unknown += 1
            continue
        start = normalize_timestamp(start_raw, tz)
        end = normalize_timestamp(end_raw, tz)
        delta = (end - start).total_seconds()
        if delta <= 0:
            if delta >= -120:
                skipped_zero += 1
                continue
            raise SystemExit(f"end before start idx={idx} {start_raw!r}..{end_raw!r}")
        clip_start = max(start, window_start)
        clip_end = min(end, now)
        if clip_end <= clip_start:
            continue
        segments.append(
            {
                "idx": idx,
                "label": label,
                "metric": metric,
                "start": clip_start,
                "end": clip_end,
                "hours": _hours((clip_end - clip_start).total_seconds()),
                "start_raw": start_raw,
                "end_raw": end_raw,
            }
        )
    return segments, skipped_zero, unknown


def _union_hours(intervals: list[tuple[datetime, datetime]]) -> float:
    from pha.healthkit_ingest import _union_hours

    return _union_hours(intervals)


def _overlaps(segments: list[dict]) -> list[tuple[dict, dict, float]]:
    pairs: list[tuple[dict, dict, float]] = []
    ordered = sorted(segments, key=lambda item: (item["start"], item["end"], item["idx"]))
    for i, left in enumerate(ordered):
        for right in ordered[i + 1 :]:
            if right["start"] >= left["end"]:
                break
            if right["end"] <= left["start"]:
                continue
            overlap = (
                min(left["end"], right["end"]) - max(left["start"], right["start"])
            ).total_seconds()
            if overlap > 0:
                pairs.append((left, right, _hours(overlap)))
    return pairs


def report(path: Path, *, tz_name: str, now: datetime, window_hours: float) -> int:
    text = _load_text(path)
    if "---ENDS---" not in text:
        print(f"INCOMPLETE body at {path}: missing ---ENDS--- (log preview only)")
        return 2
    segments, skipped_zero, unknown = _pair_segments(
        text, tz_name=tz_name, now=now, window_hours=window_hours
    )
    print(f"file={path}")
    print(f"kept={len(segments)} skipped_zero={skipped_zero} unknown_label={unknown}")
    print(f"window={window_hours}h now={now.isoformat()} tz={tz_name}")
    print()
    print("segments")
    for item in segments:
        print(
            f"  [{item['idx']:03d}] {item['metric']:16s} "
            f"{item['start'].isoformat()} → {item['end'].isoformat()} "
            f"{item['hours']:.3f}h"
        )

    by_metric: dict[str, list[tuple[datetime, datetime]]] = defaultdict(list)
    sums: dict[str, float] = defaultdict(float)
    for item in segments:
        by_metric[item["metric"]].append((item["start"], item["end"]))
        sums[item["metric"]] += item["hours"]

    print()
    print("per-stage sum vs union")
    asleep_intervals: list[tuple[datetime, datetime]] = []
    all_intervals: list[tuple[datetime, datetime]] = []
    for metric in sorted(by_metric):
        union = _union_hours(by_metric[metric])
        extra = sums[metric] - union
        print(
            f"  {metric:16s} n={len(by_metric[metric]):3d} "
            f"sum={_fmt_h(sums[metric])} union={_fmt_h(union)} extra={_fmt_h(extra)}"
        )
        all_intervals.extend(by_metric[metric])
        if metric in ASLEEP:
            asleep_intervals.extend(by_metric[metric])

    asleep_sum = sum(sums[m] for m in ASLEEP if m in sums)
    asleep_union = _union_hours(asleep_intervals)
    awake_union = _union_hours(by_metric.get("sleep_awake", []))
    labeled_union = _union_hours(all_intervals)
    print()
    print(f"asleep Σ分期      {_fmt_h(asleep_sum)}")
    print(f"asleep 一次总并集  {_fmt_h(asleep_union)}")
    print(f"asleep extra       {_fmt_h(asleep_sum - asleep_union)}")
    print(f"awake union        {_fmt_h(awake_union)}")
    print(f"asleep∪awake 并集  {_fmt_h(labeled_union)}")
    print(f"asleep∪awake Σ并集 {_fmt_h(asleep_union + awake_union)}")
    print(
        f"cross-stage extra  {_fmt_h((asleep_union + awake_union) - labeled_union)}"
    )

    if segments:
        span_start = min(item["start"] for item in segments)
        span_end = max(item["end"] for item in segments)
        span = _hours((span_end - span_start).total_seconds())
        print()
        print(f"session span {span_start.isoformat()} → {span_end.isoformat()} {_fmt_h(span)}")
        print(f"Σ(asleep∪ + awake∪) − span {_fmt_h(asleep_union + awake_union - span)}")

    exact = [
        (a, b)
        for a, b, hours in _overlaps(segments)
        if a["metric"] == b["metric"]
        and a["start"] == b["start"]
        and a["end"] == b["end"]
    ]
    same_stage = [
        (a, b, hours)
        for a, b, hours in _overlaps(segments)
        if a["metric"] == b["metric"] and (a["start"], a["end"]) != (b["start"], b["end"])
    ]
    cross = [
        (a, b, hours)
        for a, b, hours in _overlaps(segments)
        if a["metric"] != b["metric"]
    ]
    print()
    print(f"exact duplicate pairs {len(exact)}")
    for left, right in exact[:40]:
        print(
            f"  {left['metric']} {left['start'].isoformat()}–{left['end'].isoformat()} "
            f"idx {left['idx']}+{right['idx']}"
        )
    print(f"same-stage overlap pairs {len(same_stage)}")
    for left, right, hours in same_stage[:40]:
        print(
            f"  {left['metric']} idx {left['idx']}+{right['idx']} overlap {_fmt_h(hours)}"
        )
    print(f"cross-stage overlap pairs {len(cross)}")
    for left, right, hours in cross[:40]:
        print(
            f"  {left['metric']}/{right['metric']} "
            f"idx {left['idx']}+{right['idx']} overlap {_fmt_h(hours)}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", nargs="?", type=Path, help="PHA_SLEEP_V1 text file")
    parser.add_argument("--tz", default=DEFAULT_TZ)
    parser.add_argument("--now", default="", help="naive local ISO, default now")
    parser.add_argument("--window-hours", type=float, default=24.0)
    args = parser.parse_args()
    path = args.path
    if path is None:
        for candidate in DEFAULT_PATHS:
            if candidate.is_file() and "---ENDS---" in candidate.read_text(encoding="utf-8"):
                path = candidate
                break
        else:
            print("Need a complete PHA_SLEEP_V1 file. Tried:")
            for candidate in DEFAULT_PATHS:
                print(f"  {candidate} exists={candidate.is_file()}")
            print(
                "Copy the iPhone Show Result sleep bundle, or re-run the shortcut "
                "after ingest dump is live, then:"
            )
            print("  python3 scripts/pha_sleep_bundle_replay.py data/local_shortcuts/sleep_body_latest.txt")
            return 2
    tz = ZoneInfo(args.tz)
    if args.now:
        now = datetime.fromisoformat(args.now)
    else:
        now = datetime.now(tz).replace(tzinfo=None)
    return report(path, tz_name=args.tz, now=now, window_hours=args.window_hours)


if __name__ == "__main__":
    raise SystemExit(main())
