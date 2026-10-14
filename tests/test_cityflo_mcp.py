import csv
import json
import random
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from cityflo_mcp.engine import AnalysisError, CityfloAnalyzer, make_tool_schemas
from cityflo_mcp.server import MCPService


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "cityflo_mcp" / "policy.json"


def write_fixture(rows, schedule_rows=None, extra_columns=None):
    # Keep temporary test data inside the writable project sandbox rather than OS temp.
    temp = tempfile.TemporaryDirectory(dir=ROOT / "tests")
    folder = Path(temp.name)
    fields = ["trip_id", "route", "vehicle_series", "scheduled_departure", "scheduled_runtime_min", "actual_arrival", "tz_offset", "scheduled_lateness_min"]
    fields.extend(extra_columns or [])
    with (folder / "trips.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    with (folder / "schedule_v2.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["route", "revised_runtime_min", "effective_date", "note"])
        writer.writeheader()
        for row in schedule_rows or []:
            writer.writerow(row)
    (folder / "ops_log.txt").write_text("test event only\n", encoding="utf-8")
    return temp, CityfloAnalyzer(folder, POLICY)


def trip(trip_id, route, day="2026-08-03", runtime=30, excess=0, series="01", arrival=None, offset="+05:30", **extra):
    departure = datetime.fromisoformat(day + "T06:00")
    actual = arrival or (departure + timedelta(minutes=runtime + excess)).strftime("%Y-%m-%d %H:%M")
    row = {
        "trip_id": trip_id, "route": route, "vehicle_series": series,
        "scheduled_departure": departure.strftime("%Y-%m-%d %H:%M"),
        "scheduled_runtime_min": str(runtime), "actual_arrival": actual,
        "tz_offset": offset, "scheduled_lateness_min": "",
    }
    row.update(extra)
    return row


def ranking_fixture():
    vectors = {
        "R-A": [0, 6, 7, 8], "R-B": [0, 4, 6, 8],
        "R-C": [1, 4, 6, 10], "R-D": [0, 0, 6, 7],
        "R-E": [0, 0, 0, 0], "R-F": [0, 4, 6, 8],
    }
    rows = []
    for route, values in vectors.items():
        seq = values * 8
        for i, excess in enumerate(seq):
            day = (datetime(2026, 8, 3) + timedelta(days=i % 7)).date().isoformat()
            rows.append(trip(f"{route}-{i:03}", route, day=day, excess=excess))
    return vectors, rows


class CityfloMCPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.real = CityfloAnalyzer()
        cls.context = cls.real.resolve_context("cityflo-lateness-v1", "latest")

    def test_assignment_snapshot_reconciliation_and_expected_anomalies(self):
        report = self.real.data_quality(self.context)
        rec = report["reconciliation"]
        self.assertEqual(report["source_row_counts"]["trips"], 5292)
        self.assertEqual((rec["scored"], rec["excluded"], rec["uncertain"]), (5250, 18, 24))
        self.assertTrue(rec["disposition_sum_matches_source"])
        self.assertTrue(rec["route_date_reconciliation_passed"])
        self.assertEqual(rec["duplicate_trip_ids"], 0)
        self.assertEqual(rec["duplicate_full_rows"], 0)
        self.assertEqual(report["quality_counts"], [
            {"quality_flag": "EXTREME_EXCESS_REVIEW", "count": 1},
            {"quality_flag": "MALFORMED_ARRIVAL", "count": 24},
            {"quality_flag": "REC114_MAPPING_UNRESOLVED", "count": 154},
            {"quality_flag": "UNUSUAL_OFFSET", "count": 1},
        ])

    def test_primary_snapshot_top_order_is_conditional_and_r40_unranked(self):
        result = self.real.route_metrics(self.real.transform_rows())
        ranking = result["complete_ranking"]
        self.assertEqual([row["route"] for row in ranking[:3]], ["R-33", "R-27", "R-14"])
        by_route = {row["route"]: row for row in result["routes"]}
        self.assertEqual((by_route["R-33"]["late_numerator"], by_route["R-33"]["scoreable_denominator"]), (49, 104))
        self.assertAlmostEqual(by_route["R-33"]["late_share_unrounded"], 49 / 104)
        self.assertFalse(by_route["R-40"]["rank_eligible"])
        self.assertIn("SCHEDULE_MAPPING_UNRESOLVED", by_route["R-40"]["ineligibility_reasons"])

    def test_strict_rec114_rows_reconcile_as_uncertain(self):
        rows = self.real.transform_rows("strict_rec114")
        rec = self.real._reconciliation(rows)
        self.assertEqual((rec["scored"], rec["excluded"], rec["uncertain"]), (5098, 18, 176))
        self.assertTrue(rec["disposition_sum_matches_source"])
        self.assertEqual(sum(1 for r in rows if r["disposition_reason_code"] == "REC114_RUNTIME_UNRESOLVED"), 152)
        self.assertEqual(sum(1 for r in rows if r["source"].get("vehicle_series") == "40" and r["primary_disposition"] == "UNCERTAIN"), 153)

    def test_known_invalid_and_impossible_trip_ids(self):
        rows = self.real.transform_rows()
        by_id = {r["trip_id"]: r for r in rows}
        self.assertEqual(by_id["T1-00136"]["primary_disposition"], "UNCERTAIN")
        self.assertEqual(by_id["T1-00136"]["disposition_reason_code"], "MALFORMED_ARRIVAL")
        self.assertIsNone(by_id["T1-00136"]["normalized"]["arrival_ist"])
        self.assertEqual(by_id["T1-00361"]["primary_disposition"], "EXCLUDED")
        self.assertEqual(by_id["T1-00361"]["disposition_reason_code"], "NEGATIVE_DURATION")
        self.assertEqual(by_id["T1-04521"]["primary_disposition"], "SCORED")
        self.assertEqual(by_id["T1-04521"]["normalized"]["excess_min"], 61)

    def test_unusual_utc_offset_and_alternative_local_clock(self):
        rows = self.real.transform_rows()
        row = next(r for r in rows if r["trip_id"] == "T1-02864")
        self.assertEqual(row["normalized"]["elapsed_min"], 48)
        self.assertIn("UNUSUAL_OFFSET", row["quality_flags"])
        local_rows = self.real.transform_rows(offset_scenario="local_clock_text")
        local = next(r for r in local_rows if r["trip_id"] == "T1-02864")
        self.assertEqual(local["normalized"]["elapsed_min"], -282)
        self.assertEqual(local["primary_disposition"], "EXCLUDED")
        self.assertEqual(local["source"]["tz_offset"], "+00:00")
        primary_route = self.real.route_metrics(rows, "R-23")["routes"][0]
        local_route = self.real.route_metrics(local_rows, "R-23")["routes"][0]
        self.assertEqual(primary_route["scoreable_denominator"] - local_route["scoreable_denominator"], 1)

    def test_extreme_trip_influence_is_visible_in_sensitivity(self):
        rows = self.real.transform_rows()
        explained = self.real.explain_route(rows, "R-35", sensitivity_scenarios=["without_T1-04521"])
        sensitivity = explained["sensitivity_results"][0]
        self.assertEqual(sensitivity["scenario_id"], "without_T1-04521")
        self.assertEqual(sensitivity["score_numerator"], explained["score_evidence"]["late_numerator"] - 1)
        self.assertEqual(sensitivity["score_denominator"], explained["score_evidence"]["denominator"] - 1)
        self.assertLess(sensitivity["mean_excess_min"], explained["score_evidence"]["mean_excess_min"])
        self.assertIn("T1-04521", [row["trip_id"] for row in explained["influential_trips"]])

    def test_schedule_effective_date_runtime_provenance_and_note(self):
        temp, analyzer = write_fixture([
            trip("before", "R-14", day="2026-08-04", runtime=40, excess=10),
            trip("effective", "R-14", day="2026-08-05", runtime=40, excess=10),
            trip("r27", "R-27", day="2026-08-05", runtime=40, excess=10),
        ], [
            {"route": "R-14", "revised_runtime_min": "53", "effective_date": "2026-08-05", "note": "reconciliation per REC-114"},
            {"route": "R-27", "revised_runtime_min": "45", "effective_date": "2026-08-05", "note": "no change"},
        ])
        try:
            rows = {r["trip_id"]: r for r in analyzer.transform_rows()}
            self.assertEqual(rows["before"]["schedule"]["selected_runtime_min"], 40)
            self.assertEqual(rows["before"]["schedule"]["runtime_source"], "export_runtime")
            self.assertEqual(rows["effective"]["schedule"]["selected_runtime_min"], 53)
            self.assertEqual(rows["effective"]["schedule"]["runtime_source"], "schedule_v2")
            self.assertEqual(rows["r27"]["schedule"]["selected_runtime_min"], 45)
            self.assertEqual(rows["r27"]["schedule"]["note"], "no change")
        finally:
            temp.cleanup()

    def test_rec114_scenarios_never_invent_r40_runtime(self):
        temp, analyzer = write_fixture([trip("r40", "R-40", series="40", runtime=44, excess=20)])
        try:
            provided = analyzer.transform_rows("provided_route_schedule")[0]
            self.assertEqual(provided["primary_disposition"], "SCORED")
            self.assertEqual(provided["schedule"]["selected_runtime_min"], 44)
            self.assertEqual(provided["schedule"]["resolution"], "PROVISIONAL")
            metrics = analyzer.route_metrics([provided])["routes"][0]
            self.assertFalse(metrics["rank_eligible"])
            self.assertIn("SCHEDULE_MAPPING_UNRESOLVED", metrics["ineligibility_reasons"])
            strict = analyzer.transform_rows("strict_rec114")[0]
            self.assertEqual(strict["primary_disposition"], "UNCERTAIN")
            self.assertEqual(strict["disposition_reason_code"], "REC114_RUNTIME_UNRESOLVED")
            self.assertIsNone(strict["schedule"]["selected_runtime_min"])
            self.assertEqual(strict["schedule"]["original_runtime_min"], 44)
        finally:
            temp.cleanup()

    def test_exact_synthetic_ranking_and_tie_breaks(self):
        _, fixture = ranking_fixture()
        temp, analyzer = write_fixture(fixture)
        try:
            result = analyzer.route_metrics(analyzer.transform_rows())
            self.assertEqual([r["route"] for r in result["complete_ranking"]], ["R-A", "R-C", "R-B", "R-F", "R-D", "R-E"])
            stats = {r["route"]: r for r in result["routes"]}
            self.assertEqual((stats["R-A"]["late_numerator"], stats["R-A"]["scoreable_denominator"]), (24, 32))
            self.assertEqual(stats["R-A"]["late_share_unrounded"], 0.75)
            self.assertEqual(stats["R-C"]["median_excess_min"], 5)
            self.assertEqual(stats["R-C"]["mean_excess_min"], 5.25)
            self.assertEqual(stats["R-B"]["rank"], 3)
            self.assertEqual(stats["R-F"]["rank"], 4)
            self.assertEqual(stats["R-A"]["covered_service_date_count"], 7)
        finally:
            temp.cleanup()

    def test_ranking_is_stable_under_source_row_permutation(self):
        _, fixture = ranking_fixture()
        temp, analyzer = write_fixture(fixture)
        try:
            first = [r["route"] for r in analyzer.route_metrics(analyzer.transform_rows())["complete_ranking"]]
            shuffled = list(reversed(fixture))
            temp2, analyzer2 = write_fixture(shuffled)
            try:
                second = [r["route"] for r in analyzer2.route_metrics(analyzer2.transform_rows())["complete_ranking"]]
                self.assertEqual(first, second)
            finally:
                temp2.cleanup()
        finally:
            temp.cleanup()

    def test_minimum_evidence_thresholds_are_policy_enforced(self):
        rows = [trip(f"few-{i}", "R-01", day=f"2026-08-0{3 + (i % 5)}", excess=7) for i in range(29)]
        rows += [trip(f"days-{i}", "R-02", day=f"2026-08-0{3 + (i % 4)}", excess=7) for i in range(32)]
        temp, analyzer = write_fixture(rows)
        try:
            entries = {r["route"]: r for r in analyzer.route_metrics(analyzer.transform_rows())["routes"]}
            self.assertFalse(entries["R-01"]["rank_eligible"])
            self.assertIn("MIN_SCOREABLE_TRIPS", entries["R-01"]["ineligibility_reasons"])
            self.assertFalse(entries["R-02"]["rank_eligible"])
            self.assertIn("MIN_COVERED_SERVICE_DATES", entries["R-02"]["ineligibility_reasons"])
        finally:
            temp.cleanup()

    def test_exact_worst_three_membership_change(self):
        vectors, fixture = ranking_fixture()
        temp, analyzer = write_fixture(fixture)
        try:
            a_ids = [f"R-A-{i:03}" for i, v in enumerate(vectors["R-A"] * 8) if v > 5]
            context = analyzer.resolve_context("cityflo-lateness-v1", "latest")
            result = analyzer.compare_analysis(context, [{"scenario_id": "remove_R-A_from_late", "overrides": {"excluded_trip_ids": a_ids}}])
            scenario = result["scenarios"][0]
            self.assertEqual(result["base_worst_routes"], ["R-A", "R-C", "R-B"])
            self.assertEqual(scenario["worst_routes"], ["R-C", "R-B", "R-F"])
            self.assertEqual(scenario["worst_membership_changes"], {"entered": ["R-F"], "left": ["R-A"]})
            self.assertEqual(len(scenario["complete_route_ranking"]), 5)
            self.assertTrue(scenario["disposition_reconciliation"]["disposition_sum_matches_source"])
        finally:
            temp.cleanup()

    def test_row_disposition_reconciliation_and_anomaly_flags_are_separate(self):
        rows = [
            trip("ok", "R-01", excess=0),
            trip("bad", "R-01", arrival="2026-08-03 08:60"),
            trip("negative", "R-01", runtime=50, arrival="2026-08-03 05:55"),
            trip("offset", "R-01", day="2026-08-03", runtime=50, arrival="2026-08-03 01:32", offset="+00:00"),
        ]
        temp, analyzer = write_fixture(rows)
        try:
            transformed = analyzer.transform_rows()
            rec = analyzer._reconciliation(transformed)
            self.assertEqual((rec["scored"], rec["excluded"], rec["uncertain"]), (2, 1, 1))
            self.assertEqual(rec["disposition_sum"], 4)
            self.assertTrue(rec["disposition_sum_matches_source"])
            offset_row = next(r for r in transformed if r["trip_id"] == "offset")
            self.assertEqual(offset_row["primary_disposition"], "SCORED")
            self.assertIn("UNUSUAL_OFFSET", offset_row["quality_flags"])
        finally:
            temp.cleanup()

    def test_duplicate_rows_and_ids_are_uncertain_and_reconciled(self):
        row = trip("duplicate", "R-01")
        temp, analyzer = write_fixture([row, dict(row)])
        try:
            rows = analyzer.transform_rows()
            self.assertTrue(all(r["primary_disposition"] == "UNCERTAIN" for r in rows))
            rec = analyzer._reconciliation(rows)
            self.assertEqual(rec["duplicate_trip_ids"], 1)
            self.assertEqual(rec["duplicate_full_rows"], 1)
            self.assertEqual(rec["uncertain"], 2)
            self.assertTrue(rec["disposition_sum_matches_source"])
        finally:
            temp.cleanup()

    def test_missing_required_fields_have_one_disposition_and_reason(self):
        row = trip("missing-route", "R-01")
        row["route"] = ""
        temp, analyzer = write_fixture([row])
        try:
            result = analyzer.transform_rows()[0]
            self.assertEqual(result["primary_disposition"], "UNCERTAIN")
            self.assertEqual(result["disposition_reason_code"], "MISSING_REQUIRED_FIELD")
            self.assertEqual(result["missing_fields"], ["route"])
            reconciliation = analyzer._reconciliation([result])
            self.assertEqual(reconciliation["uncertain"], 1)
            self.assertTrue(reconciliation["disposition_sum_matches_source"])
        finally:
            temp.cleanup()

    def test_explicit_time_window_sensitivity_does_not_change_primary(self):
        rows = [trip(f"d{i}", "R-01", day=f"2026-08-0{i}", excess=8) for i in range(3, 10)]
        temp, analyzer = write_fixture(rows)
        try:
            primary = analyzer.transform_rows()
            self.assertEqual(sum(r["primary_disposition"] == "SCORED" for r in primary), 7)
            sensitivity = analyzer.apply_sensitivity(primary, time_window_sensitivity={
                "mode": "exclude", "windows": [{"start": "2026-08-05T00:00", "end": "2026-08-06T00:00"}],
            })
            self.assertEqual(sum(r["primary_disposition"] == "SCORED" for r in sensitivity), 6)
            self.assertEqual(sum(r["disposition_reason_code"] == "TIME_WINDOW_FILTERED" for r in sensitivity), 1)
            self.assertEqual(sum(r["primary_disposition"] == "SCORED" for r in primary), 7)
        finally:
            temp.cleanup()

    def test_privacy_whitelist_does_not_return_extra_complaint_fields(self):
        phone = "+91-9999999999"
        complaint = "SYNTHETIC_PRIVATE_COMPLAINT_SENTENCE"
        temp, analyzer = write_fixture([trip("private", "R-01", phone=phone, complaint_text=complaint)], extra_columns=["phone", "complaint_text"])
        try:
            service = MCPService(analyzer)
            ctx = analyzer.resolve_context("cityflo-lateness-v1", "latest")
            rows = analyzer.transform_rows()
            output = analyzer.inspect_trips(rows, trip_ids=["private"])
            serialized = json.dumps(output)
            self.assertNotIn(phone, serialized)
            self.assertNotIn(complaint, serialized)
            response = service.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
                "name": "inspect_trips", "arguments": {**ctx, "trip_ids": ["private"]}}})
            text = response["result"]["content"][0]["text"]
            self.assertNotIn(phone, text)
            self.assertNotIn(complaint, text)
        finally:
            temp.cleanup()

    def test_mcp_protocol_tool_registry_and_safe_errors(self):
        service = MCPService(self.real)
        initialized = service.handle({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertIn("tools", initialized["result"]["capabilities"])
        listed = service.handle({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        self.assertEqual({t["name"] for t in listed["result"]["tools"]}, {
            "get_data_quality", "get_route_metrics", "inspect_trips", "compare_analysis", "explain_route_classification",
        })
        bad = service.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "get_data_quality", "arguments": {}}})
        self.assertTrue(bad["result"]["isError"])
        self.assertIn("UNKNOWN_POLICY", bad["result"]["content"][0]["text"])
        self.assertEqual(len(make_tool_schemas()), 5)

    def test_all_five_tools_execute_with_shared_policy_snapshot(self):
        service = MCPService(self.real)
        base = {"policy_id": "cityflo-lateness-v1", "source_snapshot_id": self.real.snapshot_id}
        calls = [
            ("get_data_quality", {}),
            ("get_route_metrics", {"route": "R-35"}),
            ("inspect_trips", {"trip_ids": ["T1-04521"]}),
            ("compare_analysis", {"scenarios": [{"scenario_id": "strict", "overrides": {"schedule_scenario": "strict_rec114"}}]}),
            ("explain_route_classification", {"route": "R-35", "sensitivity_scenarios": ["without_T1-04521"]}),
        ]
        for request_id, (name, args) in enumerate(calls, 1):
            with self.subTest(tool=name):
                response = service.handle({"jsonrpc": "2.0", "id": request_id, "method": "tools/call", "params": {"name": name, "arguments": {**base, **args}}})
                self.assertFalse(response["result"]["isError"])
                result = response["result"]["structuredContent"]
                self.assertEqual(result["policy_id"], "cityflo-lateness-v1")
                self.assertEqual(result["policy_hash"], self.real.policy_hash)
                self.assertEqual(result["source_snapshot_id"], self.real.snapshot_id)

    def test_stdio_process_handshake_and_tools_list(self):
        request = "\n".join([
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}}),
            json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "get_data_quality", "arguments": self.context}}),
            "",
        ])
        proc = subprocess.run([sys.executable, "-m", "cityflo_mcp.server"], input=request, text=True,
                              capture_output=True, cwd=ROOT, timeout=20, check=False)
        self.assertEqual(proc.returncode, 0, msg=proc.stderr)
        messages = [json.loads(line) for line in proc.stdout.splitlines() if line.startswith("{")]
        self.assertEqual([m["id"] for m in messages], [1, 2, 3])
        self.assertEqual(len(messages[1]["result"]["tools"]), 5)
        tool_result = messages[2]["result"]["structuredContent"]
        self.assertEqual(tool_result["reconciliation"]["source_rows"], 5292)
        self.assertEqual(tool_result["reconciliation"]["scored"], 5250)


if __name__ == "__main__":
    unittest.main()
