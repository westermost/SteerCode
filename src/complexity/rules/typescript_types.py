"""TypeScript advanced type system complexity rules."""

from .. import register_rules

register_rules(
    frameworks={
        "typescript_types": [
            (r'(?:extends\s+.*\?\s*.*:)', 2.0),
            (r'(?:infer\s+\w+)', 2.0),
            (r'(?:keyof\s+|in\s+keyof)', 1.0),
            (r'(?:\[.*\s+in\s+.*\]\s*:)', 1.5),
            (r'(?:Partial|Required|Readonly|Pick|Omit|Record|Exclude|Extract|NonNullable|ReturnType|Parameters)<', 0.3),
            (r'(?:type\s+\w+\s*<[^>]*,[^>]*,[^>]*>)', 1.5),
            (r'(?:as\s+const|satisfies\s+)', 0.5),
            (r'(?:\)\s*:\s*\w+\s+is\s+\w+)', 0.8),
            (r'(?:declare\s+(?:module|global|namespace))', 1.0),
            (r'(?:&\s*\{|{\s*\[)', 0.8),
        ],
    },
    hints={
        "typescript_types": r'(?:type\s+\w+\s*<|interface\s+\w+\s*<|extends\s+.*\?.*:|infer\s+\w+|keyof\s+)',
    },
)
