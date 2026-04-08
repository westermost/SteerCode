"""Rails (Ruby) complexity rules."""

from .. import register_rules

register_rules(
    frameworks={
        "rails": [
            (r'(?:has_many|belongs_to|has_one|scope|validates)', 0.3),
            (r'(?:includes|joins|where|group|having)\(.*\)\.\w+\(', 1.5),
        ],
    },
    hints={
        "rails": r'(?:class \w+ < Application|ActiveRecord|ActionController)',
    },
)
