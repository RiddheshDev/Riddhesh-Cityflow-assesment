# Revised Cityflo MCP design — review draft

**Status:** Reviewed design implemented in `cityflo_mcp/`; this document remains the contract and policy reference. It does not assert that R-14 or R-27 belongs to the 4xx vehicle series.

## 1. Exact ranking policy

### Immutable policy definition

The server should ship one immutable policy document for the primary run, e.g. `cityflo-lateness-v1`. Every analytical tool requires its `policy_id`; the response returns `policy_id`, `policy_version`, `policy_hash`, and `source_snapshot_id`. A policy ID may never be edited in place. Any changed threshold or disposition rule gets a new policy ID. `compare_analysis` creates named derived scenario policies from the immutable base and returns their canonical overrides/hash; it does not mutate the base.

Policy fields for v1:

```json
{
  "policy_id": "cityflo-lateness-v1",
  "service_date_start": "2026-08-03",
  "service_date_end": "2026-08-09",
  "service_timezone": "Asia/Kolkata",
  "late_threshold_min": 5,
  "late_comparison": "strictly_greater_than",
  "primary_rank_metric": "late_share",
  "tie_breakers": ["late_share_desc_unrounded", "median_excess_desc", "mean_excess_desc", "route_code_asc"],
  "minimum_scoreable_trips": 30,
  "minimum_covered_service_dates": 5,
  "minimum_threshold_status": "chosen_policy_threshold_not_cityflo_fact",
  "schedule_scenario": "provided_route_schedule",
  "malformed_arrival_disposition": "UNCERTAIN",
  "negative_duration_disposition": "EXCLUDED",
  "unusual_offset_disposition": "SCORED_WITH_FLAG_IF_VALID_AFTER_NORMALIZATION",
  "extreme_trip_ids_in_primary": ["T1-04521"],
  "primary_disruption_filter": null
}
```

Primary ranking order is exactly:

1. Higher **unrounded** share of scoreable trips where timetable excess is strictly greater than 5 minutes.
2. Higher median timetable excess.
3. Higher mean timetable excess.
4. Route code ascending.

For every route, expose `late_numerator`, `scoreable_denominator`, `late_share_unrounded`, `late_share_display` (percentage rounded to two decimal places), `rank_eligible`, and `ineligibility_reasons`. Ranking uses unrounded values only. Evidence eligibility requires at least 30 scoreable trips and at least five distinct service dates among the seven-day window. These are chosen policy thresholds, not facts supplied by Cityflo. A route failing either condition gets no rank; it may still return descriptive metrics.

All seven days stay in primary scoring. Disruption analyses use explicit exploratory time windows (local date/time interval filters), produce sensitivity scenarios only, and never infer route-level cause from the ops log.

### Timestamp, anomaly, and disposition rules

- Scheduled departures are interpreted as India local wall-clock timestamps. Arrival values are parsed using their preserved source offsets and normalized to India local time; source text and offset remain alongside normalized fields.
- The 24 malformed `08:60` arrival values are `UNCERTAIN` under the primary policy. They are never silently normalized.
- The 18 validly parsed but negative-duration observations are `EXCLUDED` from numeric scoring, kept in the audit ledger.
- `T1-04521` remains scoreable in the primary analysis if no independent validity rule rejects it. It receives an extreme-value flag and is included/excluded only in explicit sensitivity scenarios.
- `T1-02864` is normalized using its recorded `+00:00` offset, remains visible with `UNUSUAL_OFFSET`, and is compared to an explicit local-clock interpretation scenario. The alternative may make it negative and therefore excluded; the source is never changed.
- Each source row receives exactly one primary disposition for each immutable policy/scenario: `SCORED`, `EXCLUDED`, or `UNCERTAIN`. Quality/anomaly flags are a separate zero-or-more list; flags never create additional dispositions.
- Reconcile `source_rows = SCORED + EXCLUDED + UNCERTAIN` for every complete run. Reconcile the same equality by route and service date where applicable. Include counts by disposition and reason. Every transformation is a row-level, trip-ID-keyed record of source values, derived values, rule ID, and disposition reason.

### REC-114 scenarios

Do not claim R-14 or R-27 is a confirmed member of the 4xx vehicle series. `schedule_v2.csv` is route-keyed and contains R-14 (53 min, effective 2026-08-05, note “reconciliation per REC-114”) and R-27 (45 min, same effective date, note “no change”); trips contain two-digit `vehicle_series`, with `40` on R-40. The schedule does not contain R-40.

Support exactly these scenario labels:

| Scenario ID | Deterministic behavior | Required labeling / limitation |
|---|---|---|
| `provided_route_schedule` | Apply a supplied row only to matching route and service date on/after `effective_date`. For routes without a supplied row, retain export runtime only as an explicitly provisional fallback. | “Unconfirmed route-keyed interpretation.” Does not imply R-14/R-27 are 4xx. R-40 gets export fallback only for sensitivity and a `REC114_MAPPING_UNRESOLVED` flag; no revised runtime is invented. Preserve R-27's “no change” note. |
| `export_runtime_baseline` | Use `scheduled_runtime_min` from the export for every row. | Comparison baseline only; it does not satisfy REC-114 for any trip eventually confirmed as 4xx. |
| `strict_rec114` | Until the mapping is resolved, mark rows with `vehicle_series=40` `UNCERTAIN` / `REC114_RUNTIME_UNRESOLVED`, since that is the only possible 4x code in this export and no R-40 schedule is supplied. Use no selected runtime for those rows. Use export runtime for other series only as a provisional non-4xx assumption; preserve this assumption in output. | Conservative scenario, not confirmation that series 40 is the 4xx series. If Ops says the full vehicle membership is not recoverable from this column, strict mode must be revised to mark every potentially affected row uncertain. |

For each row expose `runtime_source`, `original_runtime_min`, `selected_runtime_min` (nullable), `schedule_route_key`, `schedule_effective_date`, `schedule_note`, and `runtime_selection_reason`. No scenario fabricates an R-40 runtime. The consequences of `strict_rec114` cannot be fully known until Ops identifies what “4xx” maps to. The distinction between the note “no change” and the explicit R-27 revised value must be confirmed before treating `provided_route_schedule` as the operational truth.

## 2. Revised MCP contracts

### Shared contract rules

All five tools require `policy_id` and `source_snapshot_id` (or `"latest"` only for an exploratory call, which must resolve and echo an immutable fingerprint set). They return the same `policy_id`, `policy_version`, `policy_hash`, and `source_snapshot_id`. A policy mismatch or unavailable snapshot is an error, not an implicit fallback. Scenario overrides are allowed only through `compare_analysis`; they are canonicalized, validated against allowed fields, hashed, and echoed. No tool mutates source data.

Common errors use `{ "error": {"code": enum, "message": string, "field": string|null, "details": object} }`. Error messages and logs must not embed raw complaint text, phone numbers, or unfiltered source prose. Retention directive remains binding: where complaint metadata ever exists, expose ticket ID and controlled category only.

### `get_data_quality`

**Input**

```json
{
  "policy_id": "cityflo-lateness-v1",
  "source_snapshot_id": "latest",
  "page_size": 100,
  "cursor": null
}
```

**Output**

```json
{
  "policy_id": "...", "policy_version": "...", "policy_hash": "...", "source_snapshot_id": "...",
  "source_fingerprints": {"trips.csv": "...", "schedule_v2.csv": "...", "ops_log.txt": "..."},
  "source_row_counts": {"trips": 5292, "schedule": 2},
  "reconciliation": {
    "source_rows": 5292, "scored": 0, "excluded": 0, "uncertain": 0,
    "disposition_sum_matches_source": true,
    "trip_id_unique_count": 0, "duplicate_trip_ids": 0, "duplicate_full_rows": 0,
    "missing_required_fields": 0, "route_date_reconciliation_passed": true
  },
  "disposition_counts": [{"disposition": "UNCERTAIN", "reason_code": "MALFORMED_ARRIVAL", "count": 24}],
  "quality_counts": [{"quality_flag": "UNUSUAL_OFFSET", "count": 1}],
  "routes": [{"route": "R-14", "source_rows": 0, "disposition_counts": {}, "covered_service_dates": []}],
  "issue_page": [{"trip_id": "...", "disposition": "...", "reason_codes": [], "quality_flags": []}],
  "next_cursor": null
}
```

Counts are computed for the selected policy/scenario, not hard-coded expected values. `issue_page` is paginated; identifiers remain auditable without dumping every row. Reconciliation failures return the report plus `reconciliation_status: FAILED`; malformed source files return `SOURCE_UNAVAILABLE` with filename and safe parser error code. Invalid policy/snapshot/cursor returns `UNKNOWN_POLICY`, `SNAPSHOT_NOT_FOUND`, or `INVALID_CURSOR`.

### `get_route_metrics`

**Input**

```json
{
  "policy_id": "cityflo-lateness-v1",
  "source_snapshot_id": "...",
  "route": null,
  "schedule_scenario": "provided_route_schedule",
  "offset_scenario": "honor_source_offset",
  "time_window_sensitivity": null
}
```

`route=null` requests all routes. `time_window_sensitivity`, when provided, is an explicit list of local start/end date-time intervals and exclusion/inclusion mode; it is exploratory and cannot be passed as the primary policy. Primary calls use all seven service days.

**Output**

```json
{
  "policy_id": "...", "policy_version": "...", "policy_hash": "...", "source_snapshot_id": "...",
  "schedule_scenario": "provided_route_schedule", "scenario_label": "unconfirmed route-keyed interpretation",
  "routes": [{
    "route": "R-14", "disposition_counts": {"SCORED": 0, "EXCLUDED": 0, "UNCERTAIN": 0},
    "daily": [{"service_date": "2026-08-03", "source_n": 0, "scored_n": 0, "late_numerator": 0, "denominator": 0, "late_share_unrounded": null}],
    "late_numerator": 0, "scoreable_denominator": 0,
    "late_share_unrounded": null, "late_share_display_pct": null,
    "median_excess_min": null, "mean_excess_min": null,
    "schedule_resolution": {"status": "RESOLVED|PROVISIONAL|UNRESOLVED", "runtime_sources": [], "notes": []},
    "rank_eligible": false, "ineligibility_reasons": ["MIN_SCOREABLE_TRIPS"], "rank": null,
    "quality_flags": []
  }]
}
```

The response includes all route-level denominators, daily breakdowns, schedule selection evidence, eligibility, and reason codes. Unknown routes return `UNKNOWN_ROUTE`; a route with inadequate evidence returns metrics and `rank_eligible=false` rather than an exception. Strict REC-114 rows without a runtime are uncertain and are not in the score denominator.

### `inspect_trips`

**Input**

```json
{
  "policy_id": "cityflo-lateness-v1", "source_snapshot_id": "...",
  "trip_ids": ["T1-04521"], "route": null,
  "disposition": null, "reason_code": null, "quality_flag": null,
  "schedule_scenario": "provided_route_schedule", "offset_scenario": "honor_source_offset",
  "page_size": 100, "cursor": null
}
```

Require at least one selector: trip IDs, route, disposition, reason, or quality flag.

**Output**

```json
{
  "policy_id": "...", "policy_version": "...", "policy_hash": "...", "source_snapshot_id": "...",
  "rows": [{
    "trip_id": "T1-04521", "primary_disposition": "SCORED", "disposition_reason_code": "VALID_ROW",
    "reason_codes": [], "quality_flags": ["EXTREME_EXCESS_REVIEW"],
    "source": {"route": "...", "vehicle_series": "...", "scheduled_departure": "...", "scheduled_runtime_min": "...", "actual_arrival": "...", "tz_offset": "..."},
    "normalized": {"departure_ist": "...", "arrival_ist": "...", "elapsed_min": 0, "excess_min": 0},
    "schedule": {"scenario": "...", "source": "...", "original_runtime_min": 0, "selected_runtime_min": 0, "effective_date": null, "note": null, "selection_reason": "..."},
    "transformation_ledger": [{"step": "...", "rule_id": "...", "input_fields": [], "output_fields": [], "result": "..."}]
  }], "next_cursor": null
}
```

Source fields are never overwritten by normalized fields. A malformed value has a null normalized value, `UNCERTAIN` disposition, and a specific reason code. Unknown IDs return per-ID `TRIP_NOT_FOUND`; invalid selector combinations return `INVALID_ARGUMENT`; pagination is bounded.

### `compare_analysis`

**Input**

```json
{
  "policy_id": "cityflo-lateness-v1", "source_snapshot_id": "...",
  "scenarios": [{
    "scenario_id": "strict-rec114",
    "overrides": {
      "schedule_scenario": "strict_rec114",
      "offset_scenario": "honor_source_offset",
      "excluded_trip_ids": [],
      "time_window_sensitivity": null
    }
  }],
  "worst_n": 3
}
```

Only declared scenario dimensions are overrideable: schedule scenario, offset interpretation, explicitly listed trip inclusion/exclusion for sensitivity, and local time-window sensitivity. Threshold, primary metric, and tie-breaks come from the immutable policy unless a new policy version is explicitly registered; arbitrary per-call metric changes are rejected.

**Output**

```json
{
  "policy_id": "...", "policy_version": "...", "policy_hash": "...", "source_snapshot_id": "...",
  "scenarios": [{
    "scenario_id": "strict-rec114", "scenario_policy_hash": "...", "exact_overrides": {},
    "disposition_reconciliation": {"source_rows": 5292, "scored": 0, "excluded": 0, "uncertain": 0, "passes": true},
    "complete_route_ranking": [{"route": "...", "rank": 1, "eligible": true, "score_numerator": 0, "score_denominator": 0, "score_unrounded": 0, "score_display_pct": 0, "median_excess_min": 0, "mean_excess_min": 0}],
    "ineligible_routes": [{"route": "...", "reason_codes": []}],
    "worst_three": ["..."], "worst_three_membership_changes": {"entered": [], "left": []}
  }]
}
```

Every scenario returns the complete ranking of eligible routes, not only changed or top routes. Ineligible routes are listed separately with reasons. If fewer than three routes are eligible, `worst_three` contains the available eligible routes and a shortfall field. Invalid or conflicting overrides return `INVALID_SCENARIO`; no source or base policy mutation occurs.

### `explain_route_classification`

**Input**

```json
{
  "policy_id": "cityflo-lateness-v1", "source_snapshot_id": "...",
  "route": "R-35", "schedule_scenario": "provided_route_schedule",
  "near_threshold_min": 2, "competitor_count": 3,
  "sensitivity_scenarios": ["without_T1-04521", "export_runtime_baseline"]
}
```

**Output**

```json
{
  "policy_id": "...", "policy_version": "...", "policy_hash": "...", "source_snapshot_id": "...",
  "route": "R-35", "rank": null, "rank_eligible": true,
  "score_evidence": {"late_numerator": 0, "denominator": 0, "share_unrounded": 0, "share_display_pct": 0, "median_excess_min": 0, "mean_excess_min": 0, "daily": []},
  "nearby_competitors": [{"route": "...", "rank": 0, "share_difference_pp": 0, "median_difference_min": 0, "mean_difference_min": 0}],
  "influential_trips": [{"trip_id": "...", "excess_min": 0, "late_indicator": false, "influence_description": "contribution to route metrics, not causal attribution"}],
  "borderline_trips": [{"trip_id": "...", "excess_min": 0, "distance_from_threshold_min": 0, "primary_disposition": "...", "reason_codes": []}],
  "sensitivity_results": [{"scenario_id": "...", "score_numerator": 0, "score_denominator": 0, "share_unrounded": 0, "median_excess_min": 0, "mean_excess_min": 0, "rank": null, "rank_change": null}],
  "schedule_resolution": {"status": "...", "runtime_source": "...", "note": "..."}
}
```

This tool explains proximity and contribution; “influential” means numerically affects the score or ranking, not that the trip caused a route-level outcome. All trip evidence is linked to dispositions and transformation records through `inspect_trips`.

## 3. Updated focused tests with exact expected outcomes

1. **Timezone normalization:** a +05:30 arrival normalizes to the same local wall time. For `T1-02864`, honoring +00:00 gives 48 elapsed minutes and preserves source offset/text; a `local_clock_text` sensitivity gives -282 minutes, is excluded for negative duration, and changes R-23's denominator by one only.
2. **Malformed timestamps:** each known `08:60` record is `UNCERTAIN/MALFORMED_ARRIVAL`; normalized arrival/excess are null and original source string is unchanged. Assert exactly 24 such rows on the supplied snapshot.
3. **Negative durations:** the 18 known negative rows are `EXCLUDED/NEGATIVE_DURATION`, excluded from scoring denominator, still retrievable by trip ID. Assert exactly 18 under the selected timestamp policy.
4. **Effective date and schedule ambiguity:** Aug 4 uses original runtime and Aug 5 uses schedule row in `provided_route_schedule`; record R-27 note verbatim in a restricted schedule metadata field, not silently reinterpret it. In `strict_rec114`, a synthetic series-40 row is `UNCERTAIN`, selected runtime null, reason `REC114_RUNTIME_UNRESOLVED`; no R-40 runtime is created. In `export_runtime_baseline`, source runtime is selected and labeled baseline only.
5. **Extreme observation:** `T1-04521` remains scored, excess is +61 minutes under export runtime, and is separately flagged. Since it exceeds five minutes, sensitivity excluding it reduces both R-35's late numerator and denominator by one, as well as changing its mean; assert exact before/after numerator, denominator, share, mean, and rank from fixture or current frozen snapshot.
6. **Exact synthetic ranking with ties:** use 32 scoreable rows per route, distributed over all seven dates, repeating each four-value vector eight times: R-A `[0,6,7,8]`, R-B `[0,4,6,8]`, R-C `[1,4,6,10]`, R-D `[0,0,6,7]`, R-E `[0,0,0,0]`, R-F `[0,4,6,8]`. Expected order: **R-A, R-C, R-B, R-F, R-D, R-E**. Scores: R-A 24/32=.75; R-C 16/32=.5, median 5, mean 5.25; R-B/R-F each 16/32=.5, median 5, mean 4.5; R-D 16/32=.5, median 3, mean 3.25; R-E 0/32=0. This exercises share, median, mean, and route-code tie-breaks exactly.
7. **Exact worst-three membership change:** from the same fixture, scenario `remove_R-A_from_late` changes R-A's 32 excess values to all zero. Expected complete order: **R-C, R-B, R-F, R-D, R-A, R-E**. Baseline worst-three is `[R-A,R-C,R-B]`; scenario worst-three is `[R-C,R-B,R-F]`; exact membership delta is `entered=[R-F]`, `left=[R-A]`. All routes retain 32 trips and seven-date coverage, so the change is not caused by eligibility. Assert complete rankings and membership delta.
8. **Row-disposition reconciliation:** synthetic 4-row input: one valid positive duration, one malformed arrival, one negative duration, and one valid unusual-offset row under honor-offset policy. Expected dispositions: 2 `SCORED`, 1 `EXCLUDED`, 1 `UNCERTAIN`; total 4 equals source rows. Quality flag on offset row does not alter its single disposition. Assert reason-count sums and route/date reconciliation.
9. **Duplicates/missing rows:** detect duplicate trip IDs, duplicate full rows, and missing required fields independently; assert current source snapshot has 5,292 unique IDs and no exact duplicate rows. A malformed T1-05210 row remains present, not classified as missing.
10. **Stable ranking:** shuffle input row order repeatedly and assert identical ranks. Compute ties using full precision; display rounding must not change ranks. Reject non-finite metrics.
11. **Privacy-safe logging:** inject a synthetic phone number and complaint sentence in optional test-only input. Assert neither appears in output, exceptions, trace, or logs; ticket ID and controlled category can appear. Current files have no complaint ticket columns.
12. **Disruption sensitivity:** primary run always includes all seven service days. A sensitivity with explicit local windows changes only that scenario's row subset, echoes exact windows, and never attributes effects to routes based on ops-log prose.

The test suite should be focused and local: standard fixtures plus the frozen assignment snapshot. No database, hosted service, or extra observability stack is needed for the 4–6 hour assignment.

## 4. Remaining assumptions and contradictions

- **Unresolved binding instruction:** HANDOFF says 4xx trips must use revised schedule_v2, but neither the full vehicle identifier nor an R-40 schedule row is supplied. The strict scenario can expose uncertainty but cannot satisfy REC-114 for affected trips until Ops clarifies mapping/runtime.
- **Possible scope ambiguity:** this design treats `vehicle_series=40` as potentially affected in `strict_rec114` only because it is the sole 4x-like code present. That is a conservative testable proxy, not confirmed membership. If full vehicle-series membership is absent, affected trips cannot be isolated from this file.
- **R-14/R-27 interpretation:** they are route keys in the supplied schedule, not confirmed 4xx members. `provided_route_schedule` is explicitly an unconfirmed interpretation. R-27's “no change” note conflicts in tone with the supplied revised value and needs Ops confirmation.
- **Schedule granularity:** export runtime varies by trip while schedule_v2 supplies one revised route runtime. Applying it to every matching route trip after its effective date is the route-keyed scenario's assumption.
- **Timestamp meaning:** scheduled departures are local wall-clock; honoring each arrival offset assumes the offset represents the instant correctly. Device clock correctness cannot be proven from this export.
- **Chosen policy thresholds:** >5 minutes and minimum evidence of 30 trips across five dates are policy choices for review, not Cityflo-provided standards. Ops should confirm before the final memo.
- **No route-level disruption join:** ops-log entries support event reporting only. Window sensitivity is not causal route analysis.

## 5. Small implementation scope after review

1. Confirm or explicitly accept the REC-114 uncertainty treatment; keep all three schedule scenarios available regardless.
2. Freeze the policy JSON and source snapshot hashes.
3. Implement a small local loader that emits immutable source values plus a row-level transformation/disposition ledger.
4. Implement the five contracts above over the same analysis functions; use bounded pagination and safe structured errors/logging.
5. Add the focused tests and run the tools on the assignment snapshot; then prepare the final decision memo from those outputs.

The implementation follows these contracts; see `README.md` for launch and test instructions.
