"""Django complexity rules."""

from .. import register_rules

register_rules(
    frameworks={
        "django": [
            (r'class\s+\w+\(.*(?:View|ModelAdmin|Serializer|Form|Model)\)', 0.5),
            (r'(?:filter|exclude|annotate|aggregate)\(.*Q\(', 2.0),
        ],
    },
    hints={
        "django": r'(?:from django|import django|models\.Model|views\.View)',
    },
)
