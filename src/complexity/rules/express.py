"""Express (Node.js) complexity rules."""

from .. import register_rules

register_rules(
    frameworks={
        "express": [
            (r'(?:app|router)\.\s*(?:get|post|put|delete|use)\(', 0.3),
            (r'(?:async|await)\s', 0.3),
        ],
    },
    hints={
        "express": r'(?:require\(["\']express|from\s+["\']express|app\.listen)',
    },
)
