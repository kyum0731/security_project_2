"""Tiny, human-labeled inputs. Materialized only in temporary test directories."""

EVALUATION_FILES = {
    "core.py": "def price(items):\n    return sum(items)\n\nclass Service:\n    def run(self):\n        return price([])\n    def forward(self):\n        return self.run()\n",
    "entry.py": "from core import price as calc\nimport core as c\n\ndef main():\n    calc([]); c.price([])\n\ndef dynamic(handler):\n    handler()\n\nif __name__ == '__main__':\n    main()\n",
}
# file, line, UTF-8 start column, expression, status, semantic target (None = no internal target).
# The unsupported self.run() is intentionally in the gold set as a false negative.
EXPECTED_CALLS = [
    ("core.py", 2, 11, "sum(items)", "builtin", None),
    ("core.py", 6, 15, "price([])", "resolved", ("core.py", "price")),
    ("core.py", 8, 15, "self.run()", "unresolved", ("core.py", "Service.run")),
    ("entry.py", 5, 4, "calc([])", "resolved", ("core.py", "price")),
    ("entry.py", 5, 14, "c.price([])", "resolved", ("core.py", "price")),
    ("entry.py", 8, 4, "handler()", "unresolved", None),
    ("entry.py", 11, 4, "main()", "resolved", ("entry.py", "main")),
]
