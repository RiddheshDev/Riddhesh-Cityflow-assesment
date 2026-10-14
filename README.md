# Cityflo route review MCP server

This is a read-only, standard-library Python MCP server for the Cityflo take-home dataset. It implements five investigation tools and preserves source CSVs. No external Python packages are required.

## Run

From this `starter` directory, launch:

```powershell
python -m cityflo_mcp.server
```

The process speaks MCP over newline-delimited JSON-RPC on standard input/output. Configure the MCP client to run Python with `-m cityflo_mcp.server` and set the working directory to this directory. Standard output is reserved for protocol messages. The server does not write logs or mutate source files.

For the included dataset, use `policy_id: "cityflo-lateness-v1"` and `source_snapshot_id: "latest"` for an initial call. The tool response resolves `latest` to a content fingerprinted snapshot ID; use that ID for subsequent calls that must remain pinned to the same files.

## Tools

- `get_data_quality` — source fingerprints, coverage, dispositions, quality flags, and reconciliation.
- `get_route_metrics` — route metrics, daily breakdowns, schedule resolution, and rank eligibility.
- `inspect_trips` — trip-level source and normalized values, dispositions, and transformation ledger.
- `compare_analysis` — complete rankings for explicit sensitivity scenarios and worst-N membership changes.
- `explain_route_classification` — score evidence, nearby routes, influential/borderline trips, and sensitivity results.

See [ANALYSIS_AND_MCP_DESIGN.md](ANALYSIS_AND_MCP_DESIGN.md) for the versioned policy, schedule scenarios, tool contracts, assumptions, and test plan. REC-114 membership remains unresolved: R-40 has no supplied revised runtime and is not rank-eligible under the route-keyed interpretation.

## Tests

```powershell
python -m unittest discover -s tests -v
```

Tests cover the assignment snapshot and synthetic ranking, schedule, disposition, timezone, anomaly, privacy, scenario, and MCP stdio cases.
