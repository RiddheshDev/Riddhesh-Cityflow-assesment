# Cityflo route lateness decision record

**Decision date:** 2026-10-14  
**Analysis window:** 2026-08-03 through 2026-08-09 (India service dates)  
**Policy:** `cityflo-lateness-v1` v1.0.0; policy hash `abde3e798fd85b840a75ed4776137edc7274cb6ccab4ff464bf131aa9e18e61c`  
**Source snapshot:** `6794282bfc2b7f2d53a9bc754c415b7c909874db17fd45c1b596a3cbbc76082f`  
**Supporting evidence:** [DECISION_EVIDENCE.json](DECISION_EVIDENCE.json) contains exact MCP tool inputs and structured results for all 55 calls, including all-route daily metrics, route explanations, trip-level audit rows, and scenario rankings.

## Verdict

I use **share of scoreable trips with timetable excess strictly greater than five minutes** as the primary ranking metric. Under the declared `provided_route_schedule` route-keyed interpretation, the computed worst three are:

| Conditional rank | Route | Trips >5 min / scoreable trips | Unrounded share | Display share | Median excess | Mean excess |
|---:|---|---:|---:|---:|---:|---:|
| 1 | R-33 | 49/104 | 0.471153846154 | 47.12% | 5.00 min | 5.36 min |
| 2 | R-27 | 62/143 | 0.433566433566 | 43.36% | 4.00 min | 4.14 min |
| 3 | R-14 | 51/118 | 0.432203389831 | 43.22% | 4.00 min | 2.47 min |

This is a **conditional analytical verdict**, not confirmation that R-14 or R-27 belongs to REC-114’s 4xx series. R-14 and R-27 use supplied route-keyed schedule rows in the primary scenario, as the reviewed policy specifies, but that interpretation is unconfirmed. R-40 receives no rank or definitive route verdict because its required runtime cannot be established from the supplied mapping. The table is an evidence-based ranking under the stated assumption; it must not be used as proof of REC-114 membership or as automatic evidence of depot fault.

## Ranking and one verdict per route

The verdict labels below are relative to this week’s ranked comparison. “Outside worst three” is not a finding that a route met schedule or was on time. Exact score numerators, denominators, unrounded values, daily counts, eligibility reasons, and schedule resolution are in the linked tool evidence.

| Rank | Route | >5 min / scoreable | Unrounded share | Display | Median excess (min) | Mean excess (min) | Days covered | Eligibility | Verdict |
|---:|---|---:|---:|---:|---:|---:|---:|---|---|
| 1 | R-33 | 49/104 | 0.471153846154 | 47.12% | 5.00 | 5.36 | 7/7 | Eligible | Worst-three |
| 2 | R-27 | 62/143 | 0.433566433566 | 43.36% | 4.00 | 4.14 | 7/7 | Eligible | Worst-three; schedule-conditional |
| 3 | R-14 | 51/118 | 0.432203389831 | 43.22% | 4.00 | 2.47 | 7/7 | Eligible | Worst-three; schedule-conditional |
| 4 | R-26 | 44/103 | 0.427184466019 | 42.72% | 4.00 | 4.51 | 7/7 | Eligible | Outside worst three; no clearance |
| 5 | R-37 | 42/105 | 0.400000000000 | 40.00% | 4.00 | 4.13 | 7/7 | Eligible | Outside worst three; no clearance |
| 6 | R-31 | 37/112 | 0.330357142857 | 33.04% | 4.00 | 3.59 | 7/7 | Eligible | Outside worst three; no clearance |
| 7 | R-17 | 41/147 | 0.278911564626 | 27.89% | 3.00 | 2.98 | 7/7 | Eligible | Outside worst three; no clearance |
| 8 | R-35 | 32/132 | 0.242424242424 | 24.24% | 2.00 | 8.05 | 7/7 | Eligible | Outside worst three; no clearance |
| 9 | R-09 | 33/146 | 0.226027397260 | 22.60% | 2.00 | 2.31 | 7/7 | Eligible | Outside worst three; no clearance |
| 10 | R-34 | 28/124 | 0.225806451613 | 22.58% | 3.00 | 2.51 | 7/7 | Eligible | Outside worst three; no clearance |
| 11 | R-07 | 32/147 | 0.217687074830 | 21.77% | 3.00 | 2.73 | 7/7 | Eligible | Outside worst three; no clearance |
| 12 | R-15 | 25/119 | 0.210084033613 | 21.01% | 3.00 | 2.67 | 7/7 | Eligible | Outside worst three; no clearance |
| 13 | R-21 | 26/124 | 0.209677419355 | 20.97% | 2.00 | 1.82 | 7/7 | Eligible | Outside worst three; no clearance |
| 14 | R-18 | 32/154 | 0.207792207792 | 20.78% | 2.00 | 2.03 | 7/7 | Eligible | Outside worst three; no clearance |
| 15 | R-08 | 26/126 | 0.206349206349 | 20.63% | 3.00 | 2.36 | 7/7 | Eligible | Outside worst three; no clearance |
| 16 | R-03 | 21/103 | 0.203883495146 | 20.39% | 2.00 | 1.70 | 7/7 | Eligible | Outside worst three; no clearance |
| 17 | R-05 | 20/105 | 0.190476190476 | 19.05% | 2.00 | 2.34 | 7/7 | Eligible | Outside worst three; no clearance |
| 18 | R-19 | 23/125 | 0.184000000000 | 18.40% | 3.00 | 2.33 | 7/7 | Eligible | Outside worst three; no clearance |
| 19 | R-11 | 23/137 | 0.167883211679 | 16.79% | 2.00 | 2.26 | 7/7 | Eligible | Outside worst three; no clearance |
| 20 | R-20 | 24/145 | 0.165517241379 | 16.55% | 2.00 | 1.97 | 7/7 | Eligible | Outside worst three; no clearance |
| 21 | R-38 | 24/146 | 0.164383561644 | 16.44% | 1.00 | 1.49 | 7/7 | Eligible | Outside worst three; no clearance |
| 22 | R-39 | 25/154 | 0.162337662338 | 16.23% | 2.00 | 1.81 | 7/7 | Eligible | Outside worst three; no clearance |
| 23 | R-22 | 18/112 | 0.160714285714 | 16.07% | 2.00 | 1.82 | 7/7 | Eligible | Outside worst three; no clearance |
| 24 | R-32 | 21/133 | 0.157894736842 | 15.79% | 1.00 | 1.17 | 7/7 | Eligible | Outside worst three; no clearance |
| 25 | R-25 | 20/139 | 0.143884892086 | 14.39% | 1.00 | 1.45 | 7/7 | Eligible | Outside worst three; no clearance |
| 26 | R-02 | 15/105 | 0.142857142857 | 14.29% | 2.00 | 1.34 | 7/7 | Eligible | Outside worst three; no clearance |
| 27 | R-10 | 18/126 | 0.142857142857 | 14.29% | 1.00 | 1.07 | 7/7 | Eligible | Outside worst three; no clearance |
| 28 | R-12 | 15/112 | 0.133928571429 | 13.39% | 2.00 | 1.79 | 7/7 | Eligible | Outside worst three; no clearance |
| 29 | R-24 | 16/146 | 0.109589041096 | 10.96% | 1.00 | 0.84 | 7/7 | Eligible | Outside worst three; no clearance |
| 30 | R-28 | 15/151 | 0.099337748344 | 9.93% | 1.00 | 0.62 | 7/7 | Eligible | Outside worst three; no clearance |
| 31 | R-36 | 13/132 | 0.098484848485 | 9.85% | 1.00 | 0.22 | 7/7 | Eligible | Outside worst three; no clearance |
| 32 | R-04 | 14/144 | 0.097222222222 | 9.72% | 0.00 | 0.17 | 7/7 | Eligible | Outside worst three; no clearance |
| 33 | R-01 | 13/153 | 0.084967320261 | 8.50% | 1.00 | 0.82 | 7/7 | Eligible | Outside worst three; no clearance |
| 34 | R-30 | 11/147 | 0.074829931973 | 7.48% | -1.00 | -0.38 | 7/7 | Eligible | Outside worst three; no clearance |
| 35 | R-23 | 8/132 | 0.060606060606 | 6.06% | 0.00 | 0.11 | 7/7 | Eligible | Outside worst three; no clearance |
| 36 | R-13 | 8/133 | 0.060150375940 | 6.02% | -1.00 | -0.93 | 7/7 | Eligible | Outside worst three; no clearance |
| 37 | R-06 | 6/117 | 0.051282051282 | 5.13% | -2.00 | -1.45 | 7/7 | Eligible | Outside worst three; no clearance |
| 38 | R-16 | 7/146 | 0.047945205479 | 4.79% | 0.00 | -0.19 | 7/7 | Eligible | Outside worst three; no clearance |
| 39 | R-29 | 6/151 | 0.039735099338 | 3.97% | -1.00 | -0.93 | 7/7 | Eligible | Outside worst three; no clearance |
| — | R-40 | 33/152* | 0.217105263158* | 21.71%* | 3.00* | 2.61* | 7/7* | Ineligible: SCHEDULE_MAPPING_UNRESOLVED | Withhold definitive verdict; conditional fallback only |

*R-40 values are provisional diagnostics under an exported-runtime fallback, not a score against an established REC-114 timetable. Its 152 parseable, nonnegative rows under that fallback yield 33/152 = 0.217105263158 (21.71%), median 3 min, mean 2.61 min. The strict scenario leaves those 152 rows uncertain and unranked. The remaining R-40 source rows include one malformed arrival (uncertain) and one negative duration (excluded). No revised R-40 runtime is invented.*

### Evidence and reproducible rule

For each row, arrival is interpreted using its supplied UTC offset and converted to Asia/Kolkata; scheduled departure is the documented local wall-clock. `elapsed_min = arrival_IST - scheduled_departure`; `timetable_excess_min = elapsed_min - selected_runtime_min`. A late trip is **excess > 5.0**, not `>= 5`. The route score is `late_numerator / scoreable_denominator`. Scores are sorted using the unrounded ratio, then higher median excess, then higher mean excess, then route code ascending. Display percentage is rounded to two decimal places only after sorting.

The minimum evidence gate is a chosen policy threshold, not a Cityflo-supplied fact: at least 30 scoreable trips and at least five of the seven service dates. All 39 ranked routes pass; each has seven covered dates. R-40 would pass the volume and coverage tests under the fallback but fails schedule resolution, so it remains ineligible. No primary-score tie changes the top-three order; unrounded values remain the sorting input.

The 39-route rank list is a relative prioritization. It does not establish departure punctuality (actual departure is absent), passenger-weighted exposure, individual rider impact, or fault. The dataset records trips, not affected rider counts or financial outcomes.

## Alternative ranking rules considered

These are derived directly from the returned route metrics, not additional policy overrides in the MCP tool. For a median-first comparison, ties are resolved by higher unrounded late-trip share, then mean excess, then route code. For a mean-first comparison, ties are resolved by higher unrounded late-trip share, then median excess, then route code.

| Rule | First three under the route-keyed primary schedule | Consequence |
|---|---|---|
| Late-trip share (chosen primary) | R-33 (49/104, 47.12%); R-27 (62/143, 43.36%); R-14 (51/118, 43.22%) | Prioritizes how often the material-delay threshold is crossed. |
| Median excess (supporting) | R-33 (5 min); R-27 (4 min); R-14 (4 min) | Same first three with the stated secondary tie-breaks; R-14 beats R-26/R-37/R-31 on share among routes with a 4-minute median. |
| Mean excess (supporting) | R-35 (8.05 min); R-33 (5.36 min); R-26 (4.51 min) | Elevates severity and is more sensitive to the single +61-minute R-35 observation. |

The frequency rule trades away severity detail: R-35’s mean is highest but its share rank is eighth. Conversely, a high share does not say how far beyond five minutes each trip ran. Reporting median and mean beside the primary share preserves both perspectives without silently changing the ranking objective. The schedule caveat still applies to R-14/R-27.

## Why this rule, and the counterexample it breaks on

I choose incidence of trips more than five minutes over timetable runtime because the review asks which routes repeatedly expose service trips to material arrival delay. It is less dominated by one extreme than a mean and directly encodes the five-minute tolerance. The counterexample is **T1-04521 on R-35**: elapsed 96 minutes against 35 scheduled, or **+61 minutes**. It remains scored because its timestamp parses, duration is positive, and the supplied files do not prove its GPS value false. It carries `EXTREME_EXCESS_REVIEW`; excluding it is reported as a sensitivity, not done silently. R-35’s primary late share is 32/132 = 24.24% (rank 8), while its mean is 8.05 minutes—the highest mean among routes. Removing T1-04521 changes R-35 to 31/131 = 23.66% and mean 7.65 minutes; it does **not** change the worst-three membership. The chosen frequency rule therefore accepts that a severe event can be understated in the main ordering; the mean and trip-level evidence preserve its severity.

The strict boundary has a second practical edge: trips at exactly +5 minutes are not counted. The server’s route explanations expose trips at, below, and above the threshold, so a reviewer can inspect the cutoff. That is the consequence of choosing a strict five-minute tolerance rather than any positive delay; it is deliberate and reproducible.

## REC-114 and the schedule decision

The handoff says the revised timetable applies to trips on the 4xx vehicle series. The supplied trip field is only a two-digit series value; the only value beginning with 4 is `40`, on R-40 (154 source rows). `schedule_v2.csv` instead has R-14 = 53 minutes effective 2026-08-05 and R-27 = 45 minutes effective 2026-08-05, with no R-40 row. Nothing supplied confirms that R-14 or R-27 belongs to the 4xx series or maps series `40` to a different route.

I use `provided_route_schedule` as the declared primary *route-keyed* interpretation: apply each supplied route row on or after its effective service date, retain the R-27 note, and leave export runtimes before the effective date. This is an explicit assumption selected for a runnable primary analysis, not a claim of confirmed REC-114 applicability. The MCP audit rows preserve runtime source, original runtime, selected runtime, effective date, note, and selection reason.

| Route | Route-keyed primary | Export-runtime comparison | Effect |
|---|---|---|---|
| R-14 | 51/118 (43.2203%), rank 3 | 85/118 (72.0339%), rank 1 | Route-keyed interpretation lowers excess by using 53 min from Aug 5; top-three membership remains, rank changes materially. |
| R-27 | 62/143 (43.3566%), rank 2 | 32/143 (22.3776%), rank 10 | Route-keyed interpretation materially raises the share and brings R-27 into the top three. |
| R-40 | 33/152 (21.7105%), not rank-eligible* | 33/152 (21.7105%), not rank-eligible* | Export fallback is only a provisional comparison; strict REC-114 yields no score for the 152 rows whose runtime cannot be established. |

The R-27 schedule row says “no change,” but its raw `scheduled_runtime_min` values in the inspected route rows range from 35 to 55 minutes; the revised route-keyed runtime is 45 minutes from Aug 5. The supplied files do not explain what “no change” refers to or reconcile a single revised 45-minute route runtime with those per-trip export values. The route-keyed scenario applies 45 because the reviewed policy says to use supplied rows by effective date; I preserve the note and treat this as a material unresolved contradiction. It is not safe to say the revised value made no change to each trip’s exported value.

Under `export_runtime_baseline`, the worst three are **R-14, R-33, R-26**. Under `strict_rec114`, the ranked 39-route list and worst-three are the same as export baseline; R-40’s 152 runtime-unresolved rows become UNCERTAIN. Compared with the route-keyed primary, R-26 enters and R-27 leaves when the R-14/R-27 schedule rows are not applied. Thus the worst-three membership is not robust to the schedule interpretation. There is no justified definitive REC-114-adjusted ranking for routes whose actual series mapping is unknown; the committed list above is conditional on route-keyed schedule use. No runtime is assigned to R-40.

## Data quality and dispositions

The trip source has 5,292 rows across 40 routes (R-01–R-40) and all seven service dates; each service date has 756 source rows. The supplied schedule has two route-keyed rows, and the ops log has six entries. `scheduled_lateness_min` is empty by design on all trip rows. The primary scenario reconciles 5,292 input rows to exactly one primary disposition each: **5,250 SCORED, 18 EXCLUDED for negative duration, and 24 UNCERTAIN for malformed arrivals**. The reconciliation sums to 5,292, all 5,292 trip IDs are unique, and the tool found no duplicate full rows or missing required fields. All 24 malformed arrivals are the impossible clock string `08:60`. The policy never normalizes it; all such rows remain auditable by trip ID. Each of the 18 negative durations is excluded from numeric scoring but preserved in trip audit output.

Quality flags are separate from dispositions and may overlap: 154 `REC114_MAPPING_UNRESOLVED` flags on R-40 rows; 24 malformed arrival flags; one unusual-offset flag (`T1-02864`); and one extreme-excess flag (`T1-04521`). Do not add flag totals as if they were disjoint row counts. Source fingerprints and reconciliation details are in `get_data_quality`’s exact result in the evidence file.

For `T1-02864` (R-23), the primary policy honors `+00:00`: arrival 01:32 UTC converts to 07:02 India time, yielding 48 minutes elapsed and -2 minutes excess against the 50-minute runtime. Treating the clock text as local instead yields -282 minutes elapsed and EXCLUDED disposition. That sensitivity reduces R-23 from 8/132 (6.06%) to 7/131 (5.34%); it does not change the primary worst three. I retain the source offset as stated while flagging it, because the file does not prove it is misconfigured; device metadata would resolve the concern.

## Operational disruption sensitivity

All seven days remain in the primary score. The ops log supports that the following events were reported, but it has no trip/route join key: Monday yard release, Tuesday covered evening no-show, Wednesday morning SV Road flooding/diversion, Wednesday evening festival crowd slowdown, Thursday vehicle swap after an AC complaint, and Friday described as normal. It does not establish which trips or routes were affected.

For exploration only, the MCP scenarios excluded trips departing within these analyst-defined local windows: Mon 06:00–08:00; Tue 21:00–22:30; Wed 06:00–12:00; Wed 17:00–22:00; Thu 09:00–15:00. These are not event durations established by the log. Individual windows filtered respectively 103, 45, 290, 238, and 306 scoreable trips; the combined windows filtered 982 scoreable trips, leaving 4,268 scored (the 18 negative-duration exclusions and 24 malformed uncertainties remain). None of these filters justifies route-level causal attribution.

| Sensitivity-only filter | Worst-three order | Membership change vs primary |
|---|---|---|
| Mon 06:00–08:00 yard-release window | R-33, R-27, R-14 | none |
| Tue 21:00–22:30 driver-event window | R-33, R-14, R-27 | none |
| Wed 06:00–12:00 flooding/AM window | R-33, R-14, R-27 | none |
| Wed 17:00–22:00 festival window | R-33, R-14, R-27 | none |
| Thu 09:00–15:00 vehicle-swap window | R-33, R-14, R-26 | enter R-26; leave R-27 |
| All five windows combined | R-14, R-33, R-27 | none |

Individual and combined scenario rankings, denominators, exact overrides, and disposition reconciliations are in `compare_analysis` results in the evidence file. Excluding the Thursday analyst window changes membership: R-26 replaces R-27 by a very small unrounded share margin. The combined windows preserve membership but reverse R-14/R-33 order (R-14 45/93 = 48.3871%; R-33 42/87 = 48.2759%). This demonstrates that removing broad time windows can alter accountability even without route-specific evidence; I therefore retain all days in the primary score.

## Costs, decision risks, and what would change my mind

The measurable exposure is a count of trips over the five-minute rule: R-33 49/104, R-27 62/143, and R-14 51/118 under the conditional primary. These are trip counts, not affected riders or unique passenger journeys. The files contain no incentive amounts, passenger loads, refund claims, or cost data, so I do not assign monetary costs. As Priya’s handoff describes, a false positive puts the on-time incentive and depot relationship at risk for the depot head; a false clear leaves riders and the refund queue carrying the harm. The data cannot price either risk or establish a specific rider loss.

I would change the schedule-dependent verdicts with an authoritative full-vehicle-ID-to-route/series crosswalk and the signed REC-114 schedule showing which routes/vehicles each row covers, including a clarified R-27 “no change” note and an R-40 runtime if applicable. I would reconsider T1-02864 with device timezone configuration or independent arrival evidence; T1-04521 with GPS trace/device health or a corroborating dispatch record; and disruption sensitivity with trip-level incident/route identifiers. Rider counts, refund outcomes, and incentive rules would be needed to quantify the cost trade-off.

## Limitations

- The primary route-keyed schedule interpretation is unconfirmed and changes the worst-three membership versus export runtimes. It is suitable only as a clearly labelled conditional analysis until REC-114 mapping is resolved.
- R-40 cannot receive a definitive score or rank under strict REC-114 from the available schedule. Its fallback values are displayed for sensitivity only.
- Timestamp consistency does not prove GPS location or device clock trust. The +00:00 row and +61-minute row are flagged and sensitivity-tested, but their correctness cannot be established from these files.
- Ops notes have no route/trip join key; sensitivity windows are analyst-chosen and do not prove route-level impact.
- Scores are trip-weighted. Passenger-weighted delay, actual departure lateness, causal attribution, and monetary costs are unavailable.
- The 30-trip/five-date eligibility thresholds are our selected policy, not Cityflo requirements. The supplied week has seven dates; no inference beyond this slice is made.

## Reproducibility and MCP verification

The route-analysis server returned all five tools: `compare_analysis, explain_route_classification, get_data_quality, get_route_metrics, inspect_trips`. A fresh Codex CLI agent session successfully called each tool (`get_data_quality`, `get_route_metrics`, `inspect_trips`, `compare_analysis`, `explain_route_classification`) on the registered `cityflo-route-review` integration. The Codex desktop session that started this work had a static tool inventory; registration is in the user-level Codex config and a refreshed session is needed for the tools to appear there. This does not affect the verified tool results stored here.

The 55 captured tool calls are pinned to the source snapshot and policy hash above. `DECISION_EVIDENCE.json` contains tool names, exact inputs, structured outputs, complete scenario rankings, route daily breakdowns, and trip audit values. The server’s trip output is allow-listed and contains no phone numbers or complaint text. The source CSVs were not changed.
