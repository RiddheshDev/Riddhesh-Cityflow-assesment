"""Immutable-input Cityflo scoring and audit functions (standard library only)."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from statistics import mean, median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
POLICY_PATH = Path(__file__).with_name("policy.json")
REQUIRED_TRIP_FIELDS = (
    "trip_id", "route", "vehicle_series", "scheduled_departure",
    "scheduled_runtime_min", "actual_arrival", "tz_offset",
)
SOURCE_TRIP_FIELDS = REQUIRED_TRIP_FIELDS + ("scheduled_lateness_min",)
DISPOSITIONS = ("SCORED", "EXCLUDED", "UNCERTAIN")
SCHEDULE_SCENARIOS = ("provided_route_schedule", "export_runtime_baseline", "strict_rec114")
OFFSET_SCENARIOS = ("honor_source_offset", "local_clock_text")
DATE_FORMAT = "%Y-%m-%d %H:%M"


class AnalysisError(Exception):
    def __init__(self, code: str, message: str, field: str | None = None, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.field = field
        self.details = details or {}

    def as_dict(self) -> dict:
        return {"error": {"code": self.code, "message": str(self), "field": self.field, "details": self.details}}


def canonical_hash(obj: Any) -> str:
    payload = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def strict_datetime(text: str) -> datetime:
    """Parse the documented minute format, rejecting impossible dates/times."""
    if not isinstance(text, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", text):
        raise ValueError("FORMAT")
    return datetime.strptime(text, DATE_FORMAT)


def parse_offset(text: str) -> int:
    if not isinstance(text, str) or not re.fullmatch(r"[+-]\d{2}:\d{2}", text):
        raise ValueError("OFFSET_FORMAT")
    sign = 1 if text[0] == "+" else -1
    hours, minutes = map(int, text[1:].split(":"))
    if hours > 14 or minutes > 59 or (hours == 14 and minutes != 0):
        raise ValueError("OFFSET_RANGE")
    return sign * (hours * 60 + minutes)


def json_number(value: float | int | Fraction | None) -> float | int | None:
    if value is None:
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


class CityfloAnalyzer:
    def __init__(self, data_dir: Path | str = DATA_DIR, policy_path: Path | str = POLICY_PATH):
        self.data_dir = Path(data_dir)
        self.policy_path = Path(policy_path)
        try:
            self.policy = json.loads(self.policy_path.read_text(encoding="utf-8"))
            self.trips_bytes = (self.data_dir / "trips.csv").read_bytes()
            self.schedule_bytes = (self.data_dir / "schedule_v2.csv").read_bytes()
            self.ops_bytes = (self.data_dir / "ops_log.txt").read_bytes()
        except OSError as exc:
            raise AnalysisError("SOURCE_UNAVAILABLE", "A required source file is unavailable.", details={"filename": Path(exc.filename or "").name}) from None
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise AnalysisError("SOURCE_UNAVAILABLE", "A required source file could not be decoded safely.") from None
        self.policy_hash = canonical_hash(self.policy)
        self.fingerprints = {
            "trips.csv": hashlib.sha256(self.trips_bytes).hexdigest(),
            "schedule_v2.csv": hashlib.sha256(self.schedule_bytes).hexdigest(),
            "ops_log.txt": hashlib.sha256(self.ops_bytes).hexdigest(),
            "policy.json": hashlib.sha256(self.policy_path.read_bytes()).hexdigest(),
        }
        self.snapshot_id = canonical_hash(self.fingerprints)
        self.source_rows = self._read_csv(self.trips_bytes, "trips.csv")
        self.schedule = self._read_csv(self.schedule_bytes, "schedule_v2.csv")
        self.ops_line_count = len(self.ops_bytes.decode("utf-8").splitlines())
        self._schedule_by_route: dict[str, dict] = {}
        for row in self.schedule:
            route = row.get("route", "")
            if route in self._schedule_by_route:
                raise AnalysisError("SOURCE_INVALID", "Schedule contains duplicate route keys.", details={"route": route})
            self._schedule_by_route[route] = row
        self._validate_identity()

    @staticmethod
    def _read_csv(payload: bytes, filename: str) -> list[dict[str, str]]:
        try:
            text = payload.decode("utf-8-sig")
            reader = csv.DictReader(text.splitlines())
            if not reader.fieldnames:
                raise ValueError("missing header")
            return [dict(row) for row in reader]
        except (UnicodeDecodeError, csv.Error, ValueError):
            raise AnalysisError("SOURCE_INVALID", "CSV source could not be parsed.", details={"filename": filename}) from None

    def _validate_identity(self) -> None:
        if self.policy.get("policy_id") != "cityflo-lateness-v1" or not self.policy.get("version"):
            raise AnalysisError("POLICY_INVALID", "Policy definition is invalid.")

    def resolve_context(self, policy_id: str, source_snapshot_id: str) -> dict:
        if policy_id != self.policy["policy_id"]:
            raise AnalysisError("UNKNOWN_POLICY", "The requested immutable policy is not available.", "policy_id")
        if source_snapshot_id not in ("latest", self.snapshot_id):
            raise AnalysisError("SNAPSHOT_NOT_FOUND", "The requested source snapshot is not available.", "source_snapshot_id")
        return {
            "policy_id": self.policy["policy_id"],
            "policy_version": self.policy["version"],
            "policy_hash": self.policy_hash,
            "source_snapshot_id": self.snapshot_id,
        }

    def _validate_scenarios(self, schedule_scenario: str, offset_scenario: str) -> None:
        if schedule_scenario not in SCHEDULE_SCENARIOS:
            raise AnalysisError("INVALID_ARGUMENT", "Unsupported schedule scenario.", "schedule_scenario")
        if offset_scenario not in OFFSET_SCENARIOS:
            raise AnalysisError("INVALID_ARGUMENT", "Unsupported offset scenario.", "offset_scenario")

    def _transform(self, source: dict[str, str], source_index: int, schedule_scenario: str,
                   offset_scenario: str) -> dict:
        """Return one immutable audit row and exactly one primary disposition."""
        raw = {k: ("" if v is None else v) for k, v in source.items()}
        trip_id = raw.get("trip_id", "").strip()
        record_key = trip_id or f"source-row-{source_index + 2}"
        result = {
            "trip_id": trip_id or None,
            "record_key": record_key,
            "source_row_number": source_index + 2,
            "source": raw,
            "normalized": {"departure_ist": None, "arrival_ist": None, "elapsed_min": None, "excess_min": None},
            "schedule": {
                "scenario": schedule_scenario, "runtime_source": None,
                "original_runtime_min": None, "selected_runtime_min": None,
                "schedule_route_key": None, "effective_date": None, "note": None,
                "selection_reason": None, "resolution": "UNRESOLVED",
            },
            "primary_disposition": "UNCERTAIN",
            "disposition_reason_code": "UNCLASSIFIED",
            "reason_codes": [], "quality_flags": [],
            "transformation_ledger": [],
        }
        missing = [key for key in REQUIRED_TRIP_FIELDS if not raw.get(key, "").strip()]
        if missing:
            return self._finish(result, "UNCERTAIN", "MISSING_REQUIRED_FIELD", missing)
        if not trip_id:
            return self._finish(result, "UNCERTAIN", "MISSING_TRIP_ID", missing)
        if raw.get("vehicle_series") == "40":
            # This is a potential mapping flag, not confirmation of REC-114 membership.
            result["quality_flags"].append("REC114_MAPPING_UNRESOLVED")

        try:
            departure = strict_datetime(raw["scheduled_departure"])
        except ValueError:
            result["quality_flags"].append("MALFORMED_DEPARTURE")
            return self._finish(result, "UNCERTAIN", "MALFORMED_DEPARTURE")
        result["normalized"]["departure_ist"] = departure.isoformat(timespec="minutes")
        service_date = departure.date()
        policy_start = date.fromisoformat(self.policy["service_date_start"])
        policy_end = date.fromisoformat(self.policy["service_date_end"])
        result["service_date"] = service_date.isoformat()
        if not policy_start <= service_date <= policy_end:
            return self._finish(result, "EXCLUDED", "OUTSIDE_SERVICE_DATE_WINDOW")

        try:
            arrival_wall = strict_datetime(raw["actual_arrival"])
        except ValueError:
            result["quality_flags"].append("MALFORMED_ARRIVAL")
            return self._finish(result, "UNCERTAIN", "MALFORMED_ARRIVAL")
        try:
            source_offset_minutes = parse_offset(raw["tz_offset"])
        except ValueError:
            result["quality_flags"].append("INVALID_OFFSET")
            return self._finish(result, "UNCERTAIN", "INVALID_OFFSET")

        if raw["tz_offset"] != "+05:30":
            result["quality_flags"].append("UNUSUAL_OFFSET")
        if offset_scenario == "local_clock_text":
            arrival_ist = arrival_wall
            result["quality_flags"].append("LOCAL_CLOCK_INTERPRETATION")
        else:
            # Convert source wall timestamp -> UTC -> India local wall timestamp.
            arrival_ist = arrival_wall - timedelta(minutes=source_offset_minutes) + timedelta(minutes=330)
        elapsed = (arrival_ist - departure).total_seconds() / 60
        result["normalized"]["arrival_ist"] = arrival_ist.isoformat(timespec="minutes")
        result["normalized"]["elapsed_min"] = json_number(elapsed)
        result["transformation_ledger"].append({
            "step": "arrival_to_ist_and_elapsed", "rule_id": f"{offset_scenario}",
            "input_fields": ["actual_arrival", "tz_offset", "scheduled_departure"],
            "output_fields": ["normalized.arrival_ist", "normalized.elapsed_min"],
            "result": "computed_without_mutating_source",
        })

        try:
            original_runtime = int(raw["scheduled_runtime_min"])
            if str(original_runtime) != raw["scheduled_runtime_min"].strip() or original_runtime <= 0:
                raise ValueError
        except ValueError:
            result["quality_flags"].append("INVALID_RUNTIME")
            return self._finish(result, "UNCERTAIN", "INVALID_RUNTIME")
        result["schedule"]["original_runtime_min"] = original_runtime
        # Negative elapsed time is conclusive without knowing which schedule applies.
        if elapsed < 0:
            result["schedule"]["runtime_source"] = "not_used_for_invalid_duration"
            result["schedule"]["selection_reason"] = "negative_duration_excluded_before_runtime_scoring"
            result["schedule"]["resolution"] = "UNRESOLVED" if raw["vehicle_series"] == "40" else "NOT_REQUIRED"
            return self._finish(result, "EXCLUDED", "NEGATIVE_DURATION")
        schedule_row = self._schedule_by_route.get(raw["route"])
        series = raw["vehicle_series"]
        schedule = result["schedule"]

        if schedule_scenario == "strict_rec114" and series == "40":
            schedule["runtime_source"] = "unresolved_rec114"
            schedule["selection_reason"] = "4x_like_series_without_confirmed_mapping_or_route_schedule"
            schedule["resolution"] = "UNRESOLVED"
            result["normalized"]["arrival_ist"] = arrival_ist.isoformat(timespec="minutes")
            return self._finish(result, "UNCERTAIN", "REC114_RUNTIME_UNRESOLVED")

        selected_runtime = original_runtime
        schedule["runtime_source"] = "export_runtime"
        schedule["selection_reason"] = "export_runtime_baseline" if schedule_scenario == "export_runtime_baseline" else "no_matching_effective_schedule_row"
        schedule["resolution"] = "RESOLVED"
        if schedule_scenario == "provided_route_schedule" and schedule_row:
            try:
                effective = date.fromisoformat(schedule_row["effective_date"])
                revised = int(schedule_row["revised_runtime_min"])
                if revised <= 0:
                    raise ValueError
            except (ValueError, KeyError):
                result["quality_flags"].append("INVALID_SCHEDULE_ROW")
                return self._finish(result, "UNCERTAIN", "INVALID_SCHEDULE_ROW")
            schedule.update({
                "schedule_route_key": schedule_row.get("route"),
                "effective_date": effective.isoformat(),
                "note": schedule_row.get("note", ""),
            })
            if service_date >= effective:
                selected_runtime = revised
                schedule["runtime_source"] = "schedule_v2"
                schedule["selection_reason"] = "route_key_match_and_effective_date_reached"
            else:
                schedule["selection_reason"] = "route_key_match_before_effective_date"
            schedule["resolution"] = "RESOLVED"

        if schedule_scenario == "provided_route_schedule" and series == "40":
            # Export fallback is visible for sensitivity but cannot support a final route rank.
            schedule["resolution"] = "PROVISIONAL"
            schedule["selection_reason"] = "export_fallback_no_confirmed_rec114_mapping"
        if schedule_scenario == "strict_rec114":
            result["quality_flags"].append("STRICT_REC114_NON40_EXPORT_ASSUMPTION")

        schedule["selected_runtime_min"] = selected_runtime
        result["normalized"]["excess_min"] = json_number(elapsed - selected_runtime)
        result["transformation_ledger"].append({
            "step": "runtime_selection", "rule_id": schedule_scenario,
            "input_fields": ["route", "vehicle_series", "scheduled_runtime_min", "schedule_v2"],
            "output_fields": ["schedule.selected_runtime_min", "schedule.runtime_source"],
            "result": schedule["selection_reason"],
        })
        result["primary_disposition"] = "SCORED"
        result["disposition_reason_code"] = "VALID_ROW"
        result["reason_codes"] = []
        if trip_id == "T1-04521":
            result["quality_flags"].append("EXTREME_EXCESS_REVIEW")
        return result

    @staticmethod
    def _finish(row: dict, disposition: str, reason: str, missing: list | None = None) -> dict:
        row["primary_disposition"] = disposition
        row["disposition_reason_code"] = reason
        row["reason_codes"].append(reason)
        if missing:
            row["missing_fields"] = missing
        return row

    def transform_rows(self, schedule_scenario: str = "provided_route_schedule",
                       offset_scenario: str = "honor_source_offset") -> list[dict]:
        self._validate_scenarios(schedule_scenario, offset_scenario)
        rows = [self._transform(raw, i, schedule_scenario, offset_scenario) for i, raw in enumerate(self.source_rows)]
        # A duplicate identifier is not safe to use as an audit key. Mark every copy uncertain.
        groups: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            if row["trip_id"]:
                groups[row["trip_id"]].append(row)
        for group in groups.values():
            if len(group) > 1:
                for row in group:
                    row["primary_disposition"] = "UNCERTAIN"
                    row["disposition_reason_code"] = "DUPLICATE_TRIP_ID"
                    if "DUPLICATE_TRIP_ID" not in row["reason_codes"]:
                        row["reason_codes"].append("DUPLICATE_TRIP_ID")
                    row["quality_flags"].append("DUPLICATE_TRIP_ID")
        return rows

    def apply_sensitivity(self, rows: list[dict], excluded_trip_ids: list[str] | None = None,
                          time_window_sensitivity: dict | None = None) -> list[dict]:
        excluded_ids = set(excluded_trip_ids or [])
        if time_window_sensitivity is None and not excluded_ids:
            return rows
        if time_window_sensitivity is not None:
            if not isinstance(time_window_sensitivity, dict) or time_window_sensitivity.get("mode") not in ("exclude", "include_only"):
                raise AnalysisError("INVALID_SCENARIO", "Time-window mode must be exclude or include_only.", "time_window_sensitivity")
            windows = time_window_sensitivity.get("windows")
            if not isinstance(windows, list) or not windows:
                raise AnalysisError("INVALID_SCENARIO", "At least one explicit time window is required.", "time_window_sensitivity")
            parsed = []
            for window in windows:
                try:
                    start = datetime.fromisoformat(window["start"])
                    end = datetime.fromisoformat(window["end"])
                except (KeyError, TypeError, ValueError):
                    raise AnalysisError("INVALID_SCENARIO", "Each time window needs ISO local start and end values.", "time_window_sensitivity") from None
                if start.tzinfo is not None or end.tzinfo is not None or end <= start:
                    raise AnalysisError("INVALID_SCENARIO", "Time windows must be ordered local wall-clock values without offsets.", "time_window_sensitivity")
                parsed.append((start, end))
        else:
            parsed = []
        output = []
        for row in rows:
            copied = json.loads(json.dumps(row))
            if copied["trip_id"] in excluded_ids and copied["primary_disposition"] == "SCORED":
                copied["primary_disposition"] = "EXCLUDED"
                copied["disposition_reason_code"] = "SCENARIO_TRIP_EXCLUSION"
                copied["reason_codes"].append("SCENARIO_TRIP_EXCLUSION")
            if parsed:
                try:
                    trip_time = datetime.fromisoformat(copied["normalized"]["departure_ist"])
                except (TypeError, ValueError):
                    trip_time = None
                matched = bool(trip_time and any(start <= trip_time < end for start, end in parsed))
                mode = time_window_sensitivity["mode"]
                selected = matched if mode == "include_only" else not matched
                if not selected and copied["primary_disposition"] == "SCORED":
                    copied["primary_disposition"] = "EXCLUDED"
                    copied["disposition_reason_code"] = "TIME_WINDOW_FILTERED"
                    copied["reason_codes"].append("TIME_WINDOW_FILTERED")
            output.append(copied)
        return output

    @staticmethod
    def _valid_rows(rows: list[dict]) -> list[dict]:
        return [row for row in rows if row["primary_disposition"] == "SCORED"]

    def _route_stats(self, rows: list[dict]) -> dict[str, dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in self._valid_rows(rows):
            grouped[row["source"]["route"]].append(row)
        stats = {}
        for route, trip_rows in grouped.items():
            excess = [float(row["normalized"]["excess_min"]) for row in trip_rows]
            late_n = sum(value > self.policy["late_threshold_min"] for value in excess)
            late_share = Fraction(late_n, len(excess))
            days = sorted({row["service_date"] for row in trip_rows})
            stats[route] = {
                "route": route, "scored_rows": trip_rows, "n": len(excess), "days": days,
                "late_numerator": late_n, "denominator": len(excess),
                "late_share_fraction": late_share,
                "late_share_unrounded": float(late_share),
                "late_share_display_pct": round(float(late_share) * 100, 2),
                "median_excess_min": float(median(excess)),
                "mean_excess_min": sum(excess) / len(excess),
            }
        return stats

    def _route_eligibility(self, route: str, stats: dict | None, rows: list[dict]) -> tuple[bool, list[str], str]:
        reasons = []
        n = stats["n"] if stats else 0
        days = len(stats["days"]) if stats else 0
        if n < int(self.policy["minimum_scoreable_trips"]):
            reasons.append("MIN_SCOREABLE_TRIPS")
        if days < int(self.policy["minimum_covered_service_dates"]):
            reasons.append("MIN_COVERED_SERVICE_DATES")
        if any(row["source"].get("route") == route and "REC114_MAPPING_UNRESOLVED" in row["quality_flags"] for row in rows):
            reasons.append("SCHEDULE_MAPPING_UNRESOLVED")
        return not reasons, reasons, "ELIGIBLE" if not reasons else "INELIGIBLE"

    def route_metrics(self, rows: list[dict], route_filter: str | None = None) -> dict:
        known_routes = sorted({r.get("route", "") for r in self.source_rows if r.get("route")})
        if route_filter is not None and route_filter not in known_routes:
            raise AnalysisError("UNKNOWN_ROUTE", "The requested route is not in this source snapshot.", "route", {"known_routes": known_routes})
        stats = self._route_stats(rows)
        by_route_all: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            route = row["source"].get("route", "")
            if route:
                by_route_all[route].append(row)
        candidates = [route_filter] if route_filter else known_routes
        entries = []
        for route in candidates:
            route_rows = by_route_all.get(route, [])
            stat = stats.get(route)
            eligible, ineligible, status = self._route_eligibility(route, stat, rows)
            schedule_resolutions = Counter(r["schedule"]["resolution"] for r in route_rows)
            runtime_sources = sorted({r["schedule"]["runtime_source"] for r in route_rows if r["schedule"].get("runtime_source")})
            notes = sorted({r["schedule"]["note"] for r in route_rows if r["schedule"].get("note")})
            daily = []
            all_dates = [date.fromisoformat(self.policy["service_date_start"]) + timedelta(days=i) for i in range(7)]
            for service_day in all_dates:
                day_rows = [r for r in route_rows if r.get("service_date") == service_day.isoformat()]
                scored = [r for r in day_rows if r["primary_disposition"] == "SCORED"]
                late_n = sum(float(r["normalized"]["excess_min"]) > self.policy["late_threshold_min"] for r in scored)
                daily.append({
                    "service_date": service_day.isoformat(), "source_n": len(day_rows),
                    "scored_n": len(scored), "late_numerator": late_n,
                    "denominator": len(scored),
                    "late_share_unrounded": (late_n / len(scored)) if scored else None,
                })
            entries.append({
                "route": route,
                "disposition_counts": dict(Counter(r["primary_disposition"] for r in route_rows)),
                "daily": daily,
                "late_numerator": stat["late_numerator"] if stat else 0,
                "scoreable_denominator": stat["denominator"] if stat else 0,
                "late_share_unrounded": stat["late_share_unrounded"] if stat else None,
                "late_share_display_pct": stat["late_share_display_pct"] if stat else None,
                "median_excess_min": stat["median_excess_min"] if stat else None,
                "mean_excess_min": stat["mean_excess_min"] if stat else None,
                "covered_service_dates": stat["days"] if stat else [],
                "covered_service_date_count": len(stat["days"]) if stat else 0,
                "schedule_resolution": {
                    "status": "UNRESOLVED" if "SCHEDULE_MAPPING_UNRESOLVED" in ineligible else ("PROVISIONAL" if schedule_resolutions.get("PROVISIONAL") else "RESOLVED"),
                    "resolution_counts": dict(schedule_resolutions), "runtime_sources": runtime_sources, "notes": notes,
                },
                "rank_eligible": eligible, "ineligibility_reasons": ineligible,
                "rank_eligibility_status": status, "rank": None, "quality_flags": sorted({f for r in route_rows for f in r["quality_flags"]}),
            })
        eligible_entries = [entry for entry in entries if entry["rank_eligible"]]
        eligible_entries.sort(key=lambda e: (
            -e["late_share_unrounded"], -e["median_excess_min"], -e["mean_excess_min"], e["route"]
        ))
        for rank, entry in enumerate(eligible_entries, 1):
            entry["rank"] = rank
        rank_map = {e["route"]: e["rank"] for e in eligible_entries}
        for entry in entries:
            entry["rank"] = rank_map.get(entry["route"])
        return {"routes": entries, "complete_ranking": [{"route": e["route"], "rank": e["rank"]} for e in eligible_entries],
                "ineligible_routes": [{"route": e["route"], "reason_codes": e["ineligibility_reasons"]} for e in entries if not e["rank_eligible"]]}

    def _reconciliation(self, rows: list[dict]) -> dict:
        counts = Counter(r["primary_disposition"] for r in rows)
        reason_counts = Counter((r["primary_disposition"], r["disposition_reason_code"]) for r in rows)
        trip_ids = [r["trip_id"] for r in rows if r["trip_id"]]
        dup_ids = Counter(trip_ids)
        exact_rows = Counter(tuple(sorted(r["source"].items())) for r in rows)
        duplicate_full_rows = sum(count - 1 for count in exact_rows.values() if count > 1)
        by_route_date: dict[tuple[str, str], Counter] = defaultdict(Counter)
        for row in rows:
            route = row["source"].get("route", "")
            day = row.get("service_date", "")
            by_route_date[(route, day)][row["primary_disposition"]] += 1
        route_date_sum = sum(sum(x.values()) for x in by_route_date.values())
        disposition_sum = sum(counts.get(name, 0) for name in DISPOSITIONS)
        missing_fields = sum(1 for r in rows if r["disposition_reason_code"] in ("MISSING_REQUIRED_FIELD", "MISSING_TRIP_ID"))
        return {
            "source_rows": len(rows), "scored": counts.get("SCORED", 0), "excluded": counts.get("EXCLUDED", 0),
            "uncertain": counts.get("UNCERTAIN", 0), "disposition_sum": disposition_sum,
            "disposition_sum_matches_source": disposition_sum == len(rows),
            "trip_id_unique_count": len(set(trip_ids)),
            "duplicate_trip_ids": sum(1 for count in dup_ids.values() if count > 1),
            "duplicate_full_rows": duplicate_full_rows,
            "missing_required_fields": missing_fields,
            "route_date_reconciled_rows": route_date_sum,
            "route_date_reconciliation_passed": route_date_sum == len(rows),
            "counts_by_disposition_reason": [
                {"disposition": disposition, "reason_code": reason, "count": count}
                for (disposition, reason), count in sorted(reason_counts.items())
            ],
        }

    def data_quality(self, context: dict, schedule_scenario: str = "provided_route_schedule",
                     offset_scenario: str = "honor_source_offset", page_size: int = 100, cursor: int = 0) -> dict:
        self._validate_scenarios(schedule_scenario, offset_scenario)
        self._validate_paging(page_size, cursor)
        rows = self.transform_rows(schedule_scenario, offset_scenario)
        routes = sorted({r.get("route", "") for r in self.source_rows if r.get("route")})
        route_stats = []
        for route in routes:
            subset = [r for r in rows if r["source"].get("route") == route]
            route_stats.append({
                "route": route, "source_rows": len(subset),
                "disposition_counts": dict(Counter(r["primary_disposition"] for r in subset)),
                "covered_service_dates": sorted({r["service_date"] for r in subset if r.get("service_date")}),
            })
        issue_rows = [r for r in rows if r["primary_disposition"] != "SCORED" or r["quality_flags"]]
        page = issue_rows[cursor:cursor + page_size]
        return {
            **context, "source_fingerprints": self.fingerprints,
            "schedule_scenario": schedule_scenario, "offset_scenario": offset_scenario,
            "source_row_counts": {"trips": len(self.source_rows), "schedule": len(self.schedule), "ops_log_lines": self.ops_line_count},
            "reconciliation": self._reconciliation(rows),
            "disposition_counts": [
                {"disposition": k, "reason_code": reason, "count": count}
                for (k, reason), count in sorted(Counter((r["primary_disposition"], r["disposition_reason_code"]) for r in rows).items())
            ],
            "quality_counts": [{"quality_flag": flag, "count": count} for flag, count in sorted(Counter(f for r in rows for f in r["quality_flags"]).items())],
            "routes": route_stats,
            "issue_page": [{"trip_id": r["trip_id"], "record_key": r["record_key"], "route": r["source"].get("route"), "disposition": r["primary_disposition"], "reason_codes": r["reason_codes"], "quality_flags": r["quality_flags"]} for r in page],
            "next_cursor": cursor + page_size if cursor + page_size < len(issue_rows) else None,
        }

    @staticmethod
    def _validate_paging(page_size: int, cursor: int) -> None:
        if not isinstance(page_size, int) or page_size < 1 or page_size > 500:
            raise AnalysisError("INVALID_ARGUMENT", "page_size must be from 1 through 500.", "page_size")
        if not isinstance(cursor, int) or cursor < 0:
            raise AnalysisError("INVALID_CURSOR", "Cursor must be a nonnegative integer.", "cursor")

    def inspect_trips(self, rows: list[dict], trip_ids: list[str] | None = None, route: str | None = None,
                      disposition: str | None = None, reason_code: str | None = None,
                      quality_flag: str | None = None, page_size: int = 100, cursor: int = 0) -> dict:
        self._validate_paging(page_size, cursor)
        if not any((trip_ids, route, disposition, reason_code, quality_flag)):
            raise AnalysisError("INVALID_ARGUMENT", "At least one trip, route, disposition, reason, or quality selector is required.")
        if disposition is not None and disposition not in DISPOSITIONS:
            raise AnalysisError("INVALID_ARGUMENT", "Unknown disposition.", "disposition")
        known_ids = {r["trip_id"] for r in rows if r["trip_id"]}
        missing_ids = sorted(set(trip_ids or []) - known_ids)
        selected = []
        for row in rows:
            if trip_ids and row["trip_id"] not in trip_ids:
                continue
            if route and row["source"].get("route") != route:
                continue
            if disposition and row["primary_disposition"] != disposition:
                continue
            if reason_code and reason_code not in row["reason_codes"] and reason_code != row["disposition_reason_code"]:
                continue
            if quality_flag and quality_flag not in row["quality_flags"]:
                continue
            selected.append(row)
        page = selected[cursor:cursor + page_size]
        rows_out = []
        for row in page:
            # Only whitelisted source columns are returned.
            source = {key: row["source"].get(key, "") for key in SOURCE_TRIP_FIELDS}
            rows_out.append({
                "trip_id": row["trip_id"], "record_key": row["record_key"],
                "service_date": row.get("service_date"),
                "primary_disposition": row["primary_disposition"],
                "disposition_reason_code": row["disposition_reason_code"],
                "reason_codes": row["reason_codes"], "quality_flags": row["quality_flags"],
                "source": source, "normalized": row["normalized"], "schedule": row["schedule"],
                "transformation_ledger": row["transformation_ledger"],
            })
        return {"rows": rows_out, "not_found_trip_ids": missing_ids,
                "next_cursor": cursor + page_size if cursor + page_size < len(selected) else None}

    def ranked(self, rows: list[dict]) -> dict:
        return self.route_metrics(rows)

    def compare_analysis(self, context: dict, scenarios: list[dict], worst_n: int = 3) -> dict:
        if not isinstance(scenarios, list) or not scenarios or len(scenarios) > 12:
            raise AnalysisError("INVALID_SCENARIO", "Provide between one and twelve scenarios.", "scenarios")
        if not isinstance(worst_n, int) or not 1 <= worst_n <= 10:
            raise AnalysisError("INVALID_ARGUMENT", "worst_n must be between 1 and 10.", "worst_n")
        base_rows = self.transform_rows()
        base_rank = self.route_metrics(base_rows)["complete_ranking"]
        base_members = [x["route"] for x in base_rank[:worst_n]]
        output = []
        seen = set()
        allowed = {"schedule_scenario", "offset_scenario", "excluded_trip_ids", "time_window_sensitivity"}
        for scenario in scenarios:
            if not isinstance(scenario, dict) or not isinstance(scenario.get("scenario_id"), str):
                raise AnalysisError("INVALID_SCENARIO", "Each scenario needs a string scenario_id.", "scenarios")
            scenario_id = scenario["scenario_id"]
            if scenario_id in seen:
                raise AnalysisError("INVALID_SCENARIO", "Scenario IDs must be unique.", "scenarios")
            seen.add(scenario_id)
            overrides = scenario.get("overrides", {})
            if not isinstance(overrides, dict) or set(overrides) - allowed:
                raise AnalysisError("INVALID_SCENARIO", "Scenario contains unsupported override fields.", "overrides", {"allowed": sorted(allowed)})
            schedule_mode = overrides.get("schedule_scenario", "provided_route_schedule")
            offset_mode = overrides.get("offset_scenario", "honor_source_offset")
            self._validate_scenarios(schedule_mode, offset_mode)
            excluded = overrides.get("excluded_trip_ids", [])
            if not isinstance(excluded, list) or any(not isinstance(x, str) for x in excluded):
                raise AnalysisError("INVALID_SCENARIO", "excluded_trip_ids must be a list of strings.", "excluded_trip_ids")
            rows = self.transform_rows(schedule_mode, offset_mode)
            rows = self.apply_sensitivity(rows, excluded, overrides.get("time_window_sensitivity"))
            metrics = self.route_metrics(rows)
            members = [x["route"] for x in metrics["complete_ranking"][:worst_n]]
            base_set, new_set = set(base_members), set(members)
            scenario_hash = canonical_hash({"base_policy_hash": self.policy_hash, "overrides": overrides})
            output.append({
                "scenario_id": scenario_id, "scenario_policy_hash": scenario_hash,
                "exact_overrides": overrides,
                "disposition_reconciliation": self._reconciliation(rows),
                "complete_route_ranking": [
                    {"route": entry["route"], "rank": entry["rank"], "eligible": True,
                     "score_numerator": entry["late_numerator"], "score_denominator": entry["scoreable_denominator"],
                     "score_unrounded": entry["late_share_unrounded"], "score_display_pct": entry["late_share_display_pct"],
                     "median_excess_min": entry["median_excess_min"], "mean_excess_min": entry["mean_excess_min"]}
                    for entry in sorted(metrics["routes"], key=lambda e: e["rank"] or 10**9) if entry["rank_eligible"]
                ],
                "ineligible_routes": metrics["ineligible_routes"], "worst_n": worst_n,
                "worst_routes": members,
                "worst_membership_changes": {"entered": sorted(new_set - base_set), "left": sorted(base_set - new_set)},
            })
        return {**context, "base_worst_routes": base_members, "scenarios": output}

    def explain_route(self, rows: list[dict], route: str, competitor_count: int = 3,
                      near_threshold_min: float = 2, sensitivity_scenarios: list[str] | None = None) -> dict:
        metrics = self.route_metrics(rows)
        route_entry = next((e for e in metrics["routes"] if e["route"] == route), None)
        if route_entry is None:
            raise AnalysisError("UNKNOWN_ROUTE", "The requested route is not in this source snapshot.", "route")
        ordered = sorted([e for e in metrics["routes"] if e["rank_eligible"]], key=lambda e: e["rank"])
        index = next((i for i, e in enumerate(ordered) if e["route"] == route), None)
        nearby = []
        if index is not None:
            lo, hi = max(0, index - competitor_count), min(len(ordered), index + competitor_count + 1)
            for other in ordered[lo:hi]:
                if other["route"] == route:
                    continue
                nearby.append({
                    "route": other["route"], "rank": other["rank"],
                    "share_difference_pp": round((other["late_share_unrounded"] - route_entry["late_share_unrounded"]) * 100, 6),
                    "median_difference_min": round(other["median_excess_min"] - route_entry["median_excess_min"], 6),
                    "mean_difference_min": round(other["mean_excess_min"] - route_entry["mean_excess_min"], 6),
                })
        scored = [r for r in rows if r["primary_disposition"] == "SCORED" and r["source"].get("route") == route]
        threshold = self.policy["late_threshold_min"]
        boundary = sorted(scored, key=lambda r: abs(float(r["normalized"]["excess_min"]) - threshold))
        extremes = sorted(scored, key=lambda r: abs(float(r["normalized"]["excess_min"])), reverse=True)
        influence_ids = {r["record_key"] for r in boundary if abs(float(r["normalized"]["excess_min"]) - threshold) <= near_threshold_min}
        influence_ids.update(r["record_key"] for r in extremes[:5])
        influential = []
        for row in scored:
            excess = float(row["normalized"]["excess_min"])
            if row["record_key"] in influence_ids:
                why = []
                if abs(excess - threshold) <= near_threshold_min:
                    why.append("near_late_threshold")
                if row["quality_flags"]:
                    why.append("quality_flagged")
                if abs(excess) >= 30:
                    why.append("large_absolute_excess")
                influential.append({"trip_id": row["trip_id"], "excess_min": excess,
                                    "late_indicator": excess > threshold,
                                    "influence_reasons": why or ["largest_absolute_excess_in_route"]})
        influential.sort(key=lambda x: (-abs(x["excess_min"]), x["trip_id"] or ""))
        sensitivities = []
        for scenario_id in sensitivity_scenarios or []:
            if scenario_id == "without_T1-04521":
                sens_rows = self.apply_sensitivity(rows, ["T1-04521"])
            elif scenario_id == "export_runtime_baseline":
                sens_rows = self.transform_rows("export_runtime_baseline")
            elif scenario_id == "strict_rec114":
                sens_rows = self.transform_rows("strict_rec114")
            elif scenario_id == "without_T1-02864":
                sens_rows = self.apply_sensitivity(rows, ["T1-02864"])
            else:
                raise AnalysisError("INVALID_SCENARIO", "Unknown named sensitivity scenario.", "sensitivity_scenarios", {"scenario_id": scenario_id})
            sens = self.route_metrics(sens_rows)
            sens_entry = next((e for e in sens["routes"] if e["route"] == route), None)
            sensitivities.append({
                "scenario_id": scenario_id,
                "score_numerator": sens_entry["late_numerator"] if sens_entry else 0,
                "score_denominator": sens_entry["scoreable_denominator"] if sens_entry else 0,
                "share_unrounded": sens_entry["late_share_unrounded"] if sens_entry else None,
                "median_excess_min": sens_entry["median_excess_min"] if sens_entry else None,
                "mean_excess_min": sens_entry["mean_excess_min"] if sens_entry else None,
                "rank": sens_entry["rank"] if sens_entry else None,
                "rank_change": (sens_entry["rank"] - route_entry["rank"]) if sens_entry and sens_entry["rank"] and route_entry["rank"] else None,
            })
        return {
            "route": route, "rank": route_entry["rank"], "rank_eligible": route_entry["rank_eligible"],
            "ineligibility_reasons": route_entry["ineligibility_reasons"],
            "score_evidence": {"late_numerator": route_entry["late_numerator"],
                               "denominator": route_entry["scoreable_denominator"],
                               "share_unrounded": route_entry["late_share_unrounded"],
                               "share_display_pct": route_entry["late_share_display_pct"],
                               "median_excess_min": route_entry["median_excess_min"],
                               "mean_excess_min": route_entry["mean_excess_min"], "daily": route_entry["daily"]},
            "nearby_competitors": nearby, "influential_trips": influential,
            "borderline_trips": [{"trip_id": r["trip_id"], "excess_min": r["normalized"]["excess_min"],
                                  "distance_from_threshold_min": abs(float(r["normalized"]["excess_min"]) - threshold),
                                  "primary_disposition": r["primary_disposition"], "reason_codes": r["reason_codes"]}
                                 for r in boundary if abs(float(r["normalized"]["excess_min"]) - threshold) <= near_threshold_min],
            "sensitivity_results": sensitivities, "schedule_resolution": route_entry["schedule_resolution"],
        }


def make_tool_schemas() -> list[dict]:
    policy = {"type": "string", "const": "cityflo-lateness-v1"}
    snapshot = {"type": "string", "minLength": 1}
    common = {"policy_id": policy, "source_snapshot_id": snapshot}
    def obj(props: dict, required: list[str], **extra) -> dict:
        return {"type": "object", "properties": props, "required": required, "additionalProperties": False, **extra}
    scenarios = {"type": "string", "enum": list(SCHEDULE_SCENARIOS)}
    offsets = {"type": "string", "enum": list(OFFSET_SCENARIOS)}
    window = obj({
        "mode": {"type": "string", "enum": ["exclude", "include_only"]},
        "windows": {"type": "array", "items": obj({"start": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}$"}, "end": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}$"}}, ["start", "end"]), "minItems": 1},
    }, ["mode", "windows"])
    return [
        {"name": "get_data_quality", "description": "Report source fingerprints, row dispositions, quality flags, and reconciliation.",
         "inputSchema": obj({**common, "schedule_scenario": scenarios, "offset_scenario": offsets,
                              "page_size": {"type": "integer", "minimum": 1, "maximum": 500}, "cursor": {"type": "integer", "minimum": 0}}, ["policy_id", "source_snapshot_id"])},
        {"name": "get_route_metrics", "description": "Compute daily route metrics, schedule resolution, rank eligibility, and ranking.",
         "inputSchema": obj({**common, "route": {"type": ["string", "null"]}, "schedule_scenario": scenarios,
                              "offset_scenario": offsets, "time_window_sensitivity": {"anyOf": [window, {"type": "null"}]}}, ["policy_id", "source_snapshot_id"])},
        {"name": "inspect_trips", "description": "Inspect source and normalized trip values, disposition, reasons, and transformation ledger.",
         "inputSchema": obj({**common, "trip_ids": {"type": ["array", "null"], "items": {"type": "string"}},
                              "route": {"type": ["string", "null"]}, "disposition": {"type": ["string", "null"], "enum": ["SCORED", "EXCLUDED", "UNCERTAIN", None]},
                              "reason_code": {"type": ["string", "null"]}, "quality_flag": {"type": ["string", "null"]},
                              "schedule_scenario": scenarios, "offset_scenario": offsets,
                              "page_size": {"type": "integer", "minimum": 1, "maximum": 500}, "cursor": {"type": "integer", "minimum": 0}}, ["policy_id", "source_snapshot_id"])},
        {"name": "compare_analysis", "description": "Compare explicit scenarios and return complete route rankings and worst-N membership changes.",
         "inputSchema": obj({**common, "scenarios": {"type": "array", "minItems": 1, "maxItems": 12, "items": obj({
             "scenario_id": {"type": "string"}, "overrides": {"type": "object", "additionalProperties": True}}, ["scenario_id", "overrides"])},
                              "worst_n": {"type": "integer", "minimum": 1, "maximum": 10}}, ["policy_id", "source_snapshot_id", "scenarios"])},
        {"name": "explain_route_classification", "description": "Explain route score, nearby competitors, influential trips, borderline observations, and sensitivities.",
         "inputSchema": obj({**common, "route": {"type": "string"}, "schedule_scenario": scenarios,
                              "offset_scenario": offsets, "near_threshold_min": {"type": "number", "minimum": 0},
                              "competitor_count": {"type": "integer", "minimum": 0, "maximum": 10},
                              "sensitivity_scenarios": {"type": "array", "items": {"type": "string", "enum": ["without_T1-04521", "export_runtime_baseline", "strict_rec114", "without_T1-02864"]}}},
                             ["policy_id", "source_snapshot_id", "route"])},
    ]
