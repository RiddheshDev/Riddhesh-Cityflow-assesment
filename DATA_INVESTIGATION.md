# Data investigation report

Scope: `BRIEF.md`, `HANDOFF.md`, `DATA_GUIDE.md`, `data/trips.csv`, `data/schedule_v2.csv`, and `data/ops_log.txt`. This is an investigation only; it makes no final route verdict or worst-three recommendation. The source files were not modified.

## Observed facts

### Dataset shape and coverage

| File | Rows (excluding header) | Schema |
|---|---:|---|
| `trips.csv` | 5,292 | `trip_id`, `route`, `vehicle_series`, `scheduled_departure`, `scheduled_runtime_min`, `actual_arrival`, `tz_offset`, `scheduled_lateness_min` |
| `schedule_v2.csv` | 2 | `route`, `revised_runtime_min`, `effective_date`, `note` |
| `ops_log.txt` | 6 entries | Free-text operational notes; no trip or route key |

The trip file has 40 routes, R-01 through R-40, all observed every day from 2026-08-03 through 2026-08-09 (seven days). Each day has 756 rows. Route volumes range from 105 (R-02, R-03, R-05, R-26, R-33, R-37) to 154 (R-01, R-18, R-28, R-29, R-39, R-40). There are 5,292 unique, nonempty `trip_id`s and no exact duplicate rows. The scheduled-lateness field is intentionally empty on all 5,292 rows. The other fields are nonempty in the raw CSV.

Values for `scheduled_runtime_min` are numeric integers (35, 40, 45, 50, 55). Routes and vehicle-series codes are complete. The `vehicle_series` values are `01`–`40`, and match their route suffix in the supplied rows. The only value beginning with `4` is `40`, on R-40 (154 rows). The handoff describes a “4xx vehicle series,” but the guide defines this column only as the last two digits of vehicle class; the data provides no full vehicle ID.

Schedule rows are R-14 = 53 minutes from 2026-08-05 and R-27 = 45 minutes from 2026-08-05. Their `note`s are “reconciliation per REC-114” and “no change,” respectively. R-14 has 34 rows before and 85 on/after that effective date; R-27 has 40 before and 104 on/after. There is no R-40 row in this schedule.

### Parsing, timestamps, and anomaly inventory

All 5,292 departure values match the documented minute format and parse as valid dates. Twenty-four arrival values match the superficial shape but are impossible calendar times: each is `08:60`. A strict timestamp parser rejects these 24 values. They should remain visible as uncertain records, with no silent normalization.

Invalid-arrival trip IDs: `T1-00136`, `T1-00352`, `T1-00470`, `T1-00734`, `T1-01372`, `T1-02034`, `T1-02470`, `T1-02585`, `T1-02930`, `T1-03274`, `T1-03297`, `T1-03396`, `T1-03414`, `T1-03490`, `T1-03641`, `T1-03669`, `T1-03716`, `T1-03733`, `T1-03822`, `T1-04337`, `T1-04466`, `T1-04646`, `T1-04846`, `T1-05210`.

`tz_offset` is `+05:30` on 5,291 rows and `+00:00` on one: `T1-02864` (R-23; departure 2026-08-03 06:14, arrival string 01:32). If the offset is honored as an instant and converted to India time (+05:30), its calculated elapsed runtime is 48 minutes (2 minutes below the listed 50). If the arrival clock text is treated as local time while ignoring the offset, it appears 282 minutes before departure. This is a high-impact example of why device offset handling must be explicit. Its offset may be correct or misconfigured; the file alone cannot decide.

For timestamp calculations below, I interpreted scheduled departure as India local wall-clock (+05:30), parsed `actual_arrival` as a timestamp in its stated `tz_offset`, converted it to India local time, then compared elapsed time from departure. This keeps the normal +05:30 records unchanged and makes the +00:00 row interpretable. On the 5,268 strictly parseable arrivals, calculated elapsed times range from -5 to 110 minutes, with median 47 minutes. Eighteen records imply arrival five minutes before scheduled departure, which is impossible as a trip duration and suspiciously identical in size:

`T1-00361`, `T1-00392`, `T1-00417`, `T1-00673`, `T1-01111`, `T1-01303`, `T1-01419`, `T1-01691`, `T1-02488`, `T1-02697`, `T1-02730`, `T1-03142`, `T1-03377`, `T1-03491`, `T1-03636`, `T1-04381`, `T1-04540`, `T1-05264`.

One additional positive-duration anomaly is `T1-04521` (R-35): 96-minute elapsed runtime against a 35-minute planned runtime, or +61 minutes. It is parseable, so not evidence by itself that the GPS is false. No other parseable row exceeds its export runtime by more than 60 minutes. No trip-level location trace or clock-drift evidence is included, so GPS plausibility beyond these timestamp checks cannot be established.

### REC-114 applicability issue

The handoff says trips on the 4xx vehicle series use `schedule_v2.csv`, but the file contains only route-keyed records for R-14 and R-27. Meanwhile, trip `vehicle_series` codes are only two digits, the only 4x code is `40`, and it occurs on R-40. Applying the schedule file by route would change R-14/R-27 from Aug 5 onward, but there is no schedule entry for R-40. Applying it to “4xx” by vehicle series cannot be mapped from the documented field without an assumption. The instructions do not say whether the 4xx reference means full vehicle numbers not present in the export, series code 40, or a different category. This must be reconciled before production calculations. R-27’s “no change” note further means its revised value should not automatically be read as a runtime increase.

### Operations log: what it supports

The log says:

- Monday 06:10: two buses left the depot late; described as normal.
- Tuesday 21:40: an evening driver no-show was covered.
- Wednesday 06:40: SV Road was waterlogged; the western corridor was diverted by about 35 minutes for all AM service.
- Wednesday 18:20: a festival crowd surge slowed the city generally.
- Thursday 09:05: an AC complaint led to a vehicle swap around midday.
- Friday 07:30: all normal, “good day.”

These notes support that those events were reported by ops, not that any particular trip in the CSV experienced them: there is no join key. A Wednesday AM delay near 35 minutes on the western corridor is consistent with the diversion note, but route attribution and causal effect remain unverified. City-wide Wednesday evening delay is likewise a plausible confounder, not proof that any route was affected. The late depot departures, covered no-show, vehicle swap, and “good day” description have no trip-level linkage or quantified impact. They must not be used as factual corrections to individual GPS rows.

## Candidate definitions and ranking consequences

Let elapsed runtime be arrival (after offset normalization) minus scheduled departure. Let timetable excess be elapsed runtime minus applicable planned runtime. “Late” can mean any positive excess, excess over a tolerance (for example 5 minutes), fraction of trips over tolerance, or a typical trip’s excess (median). This dataset contains no actual departure timestamp, so it cannot measure departure punctuality. A pure arrival lateness against the scheduled arrival is exactly the runtime-excess measure only if the scheduled departure and runtime are the intended schedule reference.

An exploratory pass used export runtime for all routes because REC-114 applicability could not be resolved. It retained all 5,268 parseable arrivals and did not exclude the 18 impossible negative-duration records. Results below are therefore diagnostic, not final route scores:

| Route score / rule | Top five (score; valid denominator) | Bottom three | Interpretation |
|---|---|---|---|
| Mean timetable excess (min) | R-35 7.58/133; R-33 5.36/104; R-37 4.13/105; R-26 3.94/104; R-27 3.76/144 | R-29 -0.93/151; R-13 -0.93/133; R-06 -1.91/118 | Very sensitive to high positive observations; R-35’s single +61-minute record is influential. |
| Median timetable excess (min) | R-33 5/104; R-37 4/105; R-31 4/112; R-27 4/144; R-26 4/104 | Needs complete ranked output and tie-break rule | More robust to isolated extremes; minute rounding causes ties. |
| Share with excess >5 min | R-33 47.1%/104; R-27 43.1%/144; R-14 42.9%/119; R-26 42.3%/104; R-37 40.0%/105 | Needs complete ranked output and denominator policy | Prioritizes frequency over severity; R-35 falls out of the top five despite its largest mean. |

The top three thus change depending on whether severity (mean) or frequency/typical performance is prioritized. A median and a frequency rate answer different operational questions; neither can be called the uniquely correct “actually late” measure without a chosen tolerance and cost tradeoff. Route sampling is uneven (105–154 rows), which also affects uncertainty and should be reported with route scores.

## Proposed row-treatment scenarios (not adopted)

Counts use 5,292 source rows. Categories below are mutually exclusive within each scenario; “uncertain” means kept visible but not treated as valid numeric evidence.

| Proposed treatment | Retain for numeric scoring | Exclude from scoring | Uncertain / quarantined | Notes |
|---|---:|---:|---:|---|
| A. Strict parse only | 5,268 | 0 | 24 | Only invalid `08:60` arrivals are uncertain; includes impossible negative durations and the unusual offset. |
| B. Hard physical-validity gate | 5,250 | 42 | 0 | Exclude 24 malformed arrivals and 18 negative durations; still scores the +61-minute R-35 record and interprets the +00:00 offset using its stated offset. |
| C. Conservative review queue | 5,249 | 0 | 43 | Retain only parseable, nonnegative durations except the +61-minute extreme; quarantine 24 malformed, 18 negative-duration, and `T1-04521` as uncertain. Separately flag `T1-02864` for offset review; if uncertainty is defined as “must be manually resolved before use,” then quarantine it too, yielding 5,248 numeric, 0 excluded, 44 uncertain. |

Scenario C is deliberately shown in both readings because there is a real policy distinction between excluding an outlier and marking it uncertain. Neither is an adopted rule. To preserve auditability, any later filter/correction should emit a row ledger keyed by every `trip_id`, with source values, normalized values, rule ID, and reason. For example, never overwrite `08:60` with `09:00` absent confirmation; preserve the source string and store any proposed normalization separately.

## Assumptions and proposed decisions to resolve

### Assumptions used only for this investigation

- The week is the seven local service dates Aug 3–9, 2026, inclusive.
- Scheduled departure is India local time (+05:30), following the documented “local wall-clock” description and predominant device offset.
- A stated arrival offset identifies the timestamp’s offset; it is converted to +05:30 for elapsed-time comparison.
- Exploratory route comparisons use the export runtime uniformly, because REC-114 cannot yet be mapped cleanly to the supplied vehicle-series values.

### Decisions not yet made

1. Define exactly which values identify a “4xx vehicle” and resolve why the revised schedule has R-14/R-27 but no R-40. Obtain the full vehicle identifier or a corrected schedule if necessary. Apply Aug 5 effective date only after deciding whether it applies to service date on/after Aug 5 (the natural reading) and whether R-27’s “no change” note means retain the old value.
2. Choose a trust policy for `T1-02864`: honor `+00:00`, treat it as misconfigured and use the local string, or quarantine pending device metadata. The first two produce radically different elapsed times.
3. Choose hard exclusion versus uncertainty for the 24 invalid arrivals, 18 negative durations, and R-35’s `T1-04521`; do not silently drop any. Determine whether the 18 repeated -5-minute cases indicate systematic clock/reporting behavior.
4. Define “late”: zero-minute threshold, a tolerance such as >5 minutes, mean excess, median excess, late-trip share, or a composite. Decide whether route-level “worst” means most severe average impact or most frequent lateness, and how to handle ties and small denominators.
5. Decide whether to report all service days or exclude/stratify known disruption windows. The log has no route/trip join; excluding Wednesday AM or evening would require an explicit inference and would transfer the cost of a documented disruption differently between ops/depot incentives and riders.
6. Decide minimum evidence for a route verdict, including sample count and day coverage, and how to expose uncertain trip IDs in the drill-down.

## Most consequential questions before implementation

1. What exact source field/value maps to “4xx,” and is R-40 (series `40`) supposed to receive a revised runtime? Where is its REC-114 runtime row?
2. Should the review measure actual arrival against scheduled arrival, and what late threshold should determine a positive verdict?
3. Should the 18 impossible negative durations and `T1-04521` be excluded or quarantined, and what evidence is sufficient to trust `T1-02864`’s `+00:00` offset?
4. Should Wednesday disruption trips remain in route accountability, be separately reported, or be excluded? The ops log cannot identify affected trip IDs.
5. Which cost takes precedence at the borderline: a false late flag and depot incentive loss, or a false clear and rider harm—and what uncertainty/volume is acceptable in the ranked worst-three?
