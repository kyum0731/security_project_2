"""Read Python source without importing or evaluating it."""

import ast
import hashlib
import io
import tokenize

from .models import SourceFile


def parse_file(file: SourceFile) -> dict | None:
    try:
        raw = file.path.read_bytes()
        file.content_hash = hashlib.sha256(raw).hexdigest()
    except OSError as error:
        return failure(file, "read_error", error)
    try:
        file.encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
        file.source = raw.decode(file.encoding)
    except (SyntaxError, UnicodeError, LookupError) as error:
        return failure(file, "decode_error", error)
    try:
        file.tree = ast.parse(file.source, filename=file.relative)
    except SyntaxError as error:
        return failure(file, "syntax_error", error)
    except (ValueError, RecursionError) as error:
        return failure(file, "parser_error", error)
    file.parse_status = "ok"
    return None


def failure(file, code, error):
    file.parse_status = code
    diagnostic = {"file": file.relative, "code": code, "severity": "error", "message": str(error)}
    if isinstance(error, SyntaxError) and error.lineno:
        line = (error.text or "").rstrip("\r\n")
        diagnostic["range"] = {"start_line": error.lineno,
                               "start_col": len(line[:max(0, (error.offset or 1) - 1)].encode("utf-8")),
                               "end_line": error.lineno,
                               "end_col": len(line[:max(0, (error.offset or 1) - 1)].encode("utf-8"))}
    return diagnostic
