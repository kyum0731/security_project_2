"""CPython monitoring collector. Stores locations and types, never runtime values."""

import ast
import hashlib
import inspect
import io
import json
from pathlib import Path
import sys
import threading
import tokenize
import types


class Collector:
    def __init__(self, analysis, stream, max_events):
        self.analysis, self.stream, self.max_events = analysis, stream, max_events
        self.root = Path(analysis["metadata"]["project_root"])
        self.thread = threading.get_ident()
        self.lock = threading.RLock()
        self.seq = 0
        self.active = False
        self.reasons = set()
        self.expected, self.cache, self.positions = {}, {}, {}
        self.tool_id = None
        self.nodes = {n["id"]: n for n in analysis["nodes"]}
        self.files = {str((self.root / f["path"]).resolve()): f for f in analysis["files"]}
        self.internal_files = {str(Path(__file__).resolve()), str(Path(__file__).with_name("_runtime_worker.py").resolve())}
        self.prepare()

    def prepare(self):
        """Compile but never execute snapshot-matching source to identify code objects."""
        for filename, file in self.files.items():
            if file["parse_status"] != "ok":
                continue
            path = Path(filename)
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != file["sha256"]:
                raise ValueError("실행 전 원문이 변경되었습니다: " + file["path"])
            encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
            source = raw.decode(encoding)
            tree = ast.parse(source, filename=filename)
            starts = {n.lineno: min([n.lineno] + [d.lineno for d in n.decorator_list])
                      for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
            definitions = [n for n in self.analysis["nodes"] if n["file"] == file["path"] and n["range"] and n["type"] != "variable"]
            compiled = compile(source, filename, "exec", dont_inherit=True)
            pending, expected = [compiled], []
            while pending:
                code = pending.pop()
                pending.extend(c for c in code.co_consts if isinstance(c, types.CodeType))
                qualname = code.co_qualname.replace(".<locals>.", ".")
                matches = [n for n in definitions if
                           (code.co_name == "<module>" and n["type"] == "file") or
                           (n["type"] != "file" and n["qualified_name"] == qualname and
                            starts.get(n["range"]["start_line"], n["range"]["start_line"]) <= code.co_firstlineno <= n["range"]["start_line"])]
                if len(matches) == 1:
                    expected.append((code, matches[0]["id"]))
            self.expected[filename] = expected

    def identify(self, code):
        key = (code.co_filename, code)
        if key in self.cache:
            return self.cache[key]
        if len(self.cache) >= 20000:
            self.notice("code_cache_limit")
            self.stop_events()
            return None
        try:
            filename = str(Path(code.co_filename).resolve())
        except (OSError, ValueError):
            filename = ""
        found = None
        if filename in self.files and filename not in self.internal_files:
            if code.co_flags & (inspect.CO_COROUTINE | inspect.CO_GENERATOR | inspect.CO_ASYNC_GENERATOR):
                self.notice("async_or_generator_not_traced")
            else:
                # Code equality compares structure/constants/positions, not just a name.
                matches = [nid for expected, nid in self.expected.get(filename, []) if code == expected]
                if len(matches) == 1:
                    found = matches[0]
                else:
                    self.notice("unmapped_project_code")
        self.cache[key] = found
        return found

    def location(self, frame, node_id, offset=None):
        code = frame.f_code
        key = (code.co_filename, code)
        if key not in self.positions:
            self.positions[key] = tuple(code.co_positions())
        offset = frame.f_lasti if offset is None else offset
        index = max(0, offset // 2)  # CPython 3.13 wordcode includes cache entries.
        positions = self.positions[key]
        pos = positions[index] if index < len(positions) else (None,) * 4
        r = None
        if all(p is not None for p in pos) and pos[0] > 0:
            r = dict(start_line=pos[0], end_line=pos[1], start_col=pos[2], end_col=pos[3])
        return {"file": self.nodes[node_id]["file"], "range": r}

    def write(self, event):
        if self.seq >= self.max_events:
            if "event_limit" not in self.reasons:
                self.reasons.add("event_limit")
                self.seq += 1
                self.stream.write(json.dumps({"seq": self.seq, "event": "limitation", "reason": "event_limit"}) + "\n")
                self.stream.flush()
            self.stop_events()
            return
        self.seq += 1
        event["seq"] = self.seq
        self.stream.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.stream.flush()

    def notice(self, reason):
        with self.lock:
            if reason not in self.reasons:
                self.reasons.add(reason)
                self.write({"event": "limitation", "reason": reason})

    def handle(self, event, code, offset, frame, exception=None):
        with self.lock:
            self._handle(event, code, offset, frame, exception)

    def _handle(self, event, code, offset, frame, exception=None):
        if not self.active:
            return
        try:
            node_id = self.identify(code)
            if not node_id or not self.active:
                return
            if threading.get_ident() != self.thread:
                self.notice("other_thread_not_traced")
                return
            if frame.f_code is not code:
                self.notice("frame_unavailable")
                return
            item = {"event": event, "node_id": node_id, "location": self.location(frame, node_id, offset)}
            if event == "start":
                caller = frame.f_back
                caller_id = self.identify(caller.f_code) if caller else None
                item["caller_id"] = caller_id
                item["caller_relation"] = "python_frame_parent"
                item["caller_location"] = self.location(caller, caller_id) if caller_id else None
                item["entry_kind"] = self.nodes[node_id]["type"]
            if exception is not None:
                cls = type(exception)
                item["exception_type"] = type.__getattribute__(cls, "__module__") + "." + type.__getattribute__(cls, "__qualname__")
            if self.active:
                self.write(item)
        except BaseException:
            self.reasons.add("collector_error")
            self.stop_events()

    def on_start(self, code, offset):
        self.handle("start", code, offset, sys._getframe(1))

    def on_return(self, code, offset, value):
        self.handle("return", code, offset, sys._getframe(1))

    def on_raise(self, code, offset, exception):
        self.handle("raise", code, offset, sys._getframe(1), exception)

    def on_unwind(self, code, offset, exception):
        self.handle("unwind", code, offset, sys._getframe(1), exception)

    def on_resume(self, code, offset):
        self.handle("resume", code, offset, sys._getframe(1))

    def audit(self, event, args):
        if self.active and event in {"subprocess.Popen", "os.system", "os.fork", "os.posix_spawn", "os.spawn"}:
            try:
                self.notice("child_process_not_traced")
            except BaseException:
                self.reasons.add("collector_error")
                self.stop_events()

    def start(self):
        mon = sys.monitoring
        for tool_id in range(6):
            if mon.get_tool(tool_id) is None:
                mon.use_tool_id(tool_id, "knitcode-runtime")
                self.tool_id = tool_id
                break
        if self.tool_id is None:
            raise ValueError("사용 가능한 sys.monitoring 도구 ID가 없습니다.")
        events = {"PY_START": self.on_start, "PY_RETURN": self.on_return, "RAISE": self.on_raise,
                  "PY_UNWIND": self.on_unwind, "PY_RESUME": self.on_resume}
        mask = 0
        for name, callback in events.items():
            event = getattr(mon.events, name)
            mon.register_callback(self.tool_id, event, callback)
            mask |= event
        sys.addaudithook(self.audit)
        self.active = True
        mon.set_events(self.tool_id, mask)

    def stop_events(self):
        self.active = False
        if self.tool_id is not None:
            sys.monitoring.set_events(self.tool_id, 0)

    def close(self):
        with self.lock:
            self.stop_events()
            if self.tool_id is not None:
                for name in ("PY_START", "PY_RETURN", "RAISE", "PY_UNWIND", "PY_RESUME"):
                    sys.monitoring.register_callback(self.tool_id, getattr(sys.monitoring.events, name), None)
                sys.monitoring.free_tool_id(self.tool_id)


def summarize(analysis, events):
    """Only observed function/method entries create runtime call relationships."""
    from .models import digest
    nodes = {n["id"]: n for n in analysis["nodes"]}
    calls, entries, exceptions, reasons = {}, {}, [], set()
    for event in events:
        if event["event"] == "limitation":
            reasons.add(event["reason"])
            continue
        nid = event.get("node_id")
        if nid not in nodes:
            reasons.add("invalid_event_node")
            continue
        if event["event"] == "start":
            entries[nid] = entries.get(nid, 0) + 1
            source, location = event.get("caller_id"), event.get("caller_location")
            if source in nodes and location and nodes[nid]["type"] in {"function", "method"}:
                key = digest([source, nid, location])
                if key not in calls:
                    calls[key] = {"id": "runtime:" + key, "source": source, "target": nid,
                                  "type": "observed_calls", "count": 0, "evidence": location,
                                  "caller_relation": "python_frame_parent",
                                  "event_sequences": []}
                calls[key]["count"] += 1
                calls[key]["event_sequences"].append(event["seq"])
        if event["event"] in {"raise", "unwind"}:
            exceptions.append(event)
    return {"runtime_schema_version": "1.0", "snapshot_id": analysis["metadata"]["snapshot_id"],
            "observed_calls": list(calls.values()), "node_entries": entries,
            "exceptions": exceptions, "event_count": len(events), "limitations": sorted(reasons)}
