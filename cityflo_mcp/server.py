"""Minimal MCP stdio server implemented with the Python standard library."""

from __future__ import annotations

import json
import sys
from typing import Any

from .engine import AnalysisError, CityfloAnalyzer, make_tool_schemas


SERVER_INFO = {"name": "cityflo-route-review", "version": "1.0.0"}
PROTOCOL_VERSION = "2025-06-18"


class MCPService:
    def __init__(self, analyzer: CityfloAnalyzer | None = None):
        self.analyzer = analyzer or CityfloAnalyzer()
        self.tools = {tool["name"]: tool for tool in make_tool_schemas()}

    def call(self, name: str, args: dict[str, Any]) -> dict:
        if not isinstance(args, dict):
            raise AnalysisError("INVALID_ARGUMENT", "Tool arguments must be an object.")
        context = self.analyzer.resolve_context(args.get("policy_id"), args.get("source_snapshot_id"))

        if name == "get_data_quality":
            schedule, offset = self._common_scenarios(args)
            result = self.analyzer.data_quality(
                context, schedule, offset,
                args.get("page_size", 100), args.get("cursor", 0),
            )
            return result

        if name == "get_route_metrics":
            schedule, offset = self._common_scenarios(args)
            rows = self.analyzer.transform_rows(schedule, offset)
            time_filter = args.get("time_window_sensitivity")
            if time_filter is not None:
                rows = self.analyzer.apply_sensitivity(rows, time_window_sensitivity=time_filter)
            result = self.analyzer.route_metrics(rows, args.get("route"))
            result.update(context)
            result["schedule_scenario"] = schedule
            result["scenario_label"] = {
                "provided_route_schedule": "unconfirmed route-keyed interpretation",
                "export_runtime_baseline": "comparison baseline only",
                "strict_rec114": "conservative uncertainty scenario; membership not confirmed",
            }[schedule]
            result["time_window_sensitivity"] = time_filter
            result["disposition_reconciliation"] = self.analyzer._reconciliation(rows)
            return result

        if name == "inspect_trips":
            schedule, offset = self._common_scenarios(args)
            rows = self.analyzer.transform_rows(schedule, offset)
            result = self.analyzer.inspect_trips(
                rows, args.get("trip_ids"), args.get("route"), args.get("disposition"),
                args.get("reason_code"), args.get("quality_flag"), args.get("page_size", 100), args.get("cursor", 0),
            )
            return {**context, "schedule_scenario": schedule, "offset_scenario": offset, **result}

        if name == "compare_analysis":
            return self.analyzer.compare_analysis(context, args.get("scenarios"), args.get("worst_n", 3))

        if name == "explain_route_classification":
            schedule, offset = self._common_scenarios(args)
            rows = self.analyzer.transform_rows(schedule, offset)
            result = self.analyzer.explain_route(
                rows, args.get("route"), args.get("competitor_count", 3),
                args.get("near_threshold_min", 2), args.get("sensitivity_scenarios", []),
            )
            return {**context, **result, "schedule_scenario": schedule, "offset_scenario": offset}

        raise AnalysisError("UNKNOWN_TOOL", "The requested tool is not available.", "name", {"available": sorted(self.tools)})

    @staticmethod
    def _common_scenarios(args: dict) -> tuple[str, str]:
        return args.get("schedule_scenario", "provided_route_schedule"), args.get("offset_scenario", "honor_source_offset")

    def handle(self, message: dict) -> dict | None:
        if not isinstance(message, dict):
            return {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid JSON-RPC request."}}
        method = message.get("method")
        request_id = message.get("id")
        if not isinstance(method, str):
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32600, "message": "Missing method."}}
        if method.startswith("notifications/"):
            return None
        params = message.get("params") or {}
        try:
            if method == "initialize":
                requested = params.get("protocolVersion", PROTOCOL_VERSION)
                return {"jsonrpc": "2.0", "id": request_id, "result": {
                    "protocolVersion": requested,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": SERVER_INFO,
                    "instructions": "Read-only route analysis. Data rows receive one SCORED, EXCLUDED, or UNCERTAIN disposition. No source files are modified.",
                }}
            if method == "ping":
                return {"jsonrpc": "2.0", "id": request_id, "result": {}}
            if method == "tools/list":
                return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": list(self.tools.values())}}
            if method == "tools/call":
                name = params.get("name")
                if name not in self.tools:
                    raise AnalysisError("UNKNOWN_TOOL", "The requested tool is not available.", "name", {"available": sorted(self.tools)})
                try:
                    data = self.call(name, params.get("arguments", {}))
                    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
                    return {"jsonrpc": "2.0", "id": request_id, "result": {
                        "content": [{"type": "text", "text": text}], "structuredContent": data, "isError": False,
                    }}
                except AnalysisError as exc:
                    data = exc.as_dict()
                    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                    return {"jsonrpc": "2.0", "id": request_id, "result": {
                        "content": [{"type": "text", "text": text}], "structuredContent": data, "isError": True,
                    }}
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32601, "message": "Method not found."}}
        except Exception:
            # Keep tracebacks and raw request data off stdout and logs. Return a generic safe error.
            if request_id is None:
                return None
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": -32603, "message": "Internal server error."}}


def serve() -> None:
    service = MCPService()
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            request = json.loads(line)
            response = service.handle(request)
        except json.JSONDecodeError:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error."}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    serve()
