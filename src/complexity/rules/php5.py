"""PHP 5.x legacy code complexity rules."""

from .. import register_rules

register_rules(
    frameworks={
        "php5": [
            (r'(?:global\s+\$|GLOBALS\[)', 2.0),
            (r'(?:__call|__callStatic|__get|__set|__isset|__unset)\s*\(', 1.5),
            (r'(?:__toString|__invoke|__clone)\s*\(', 0.8),
            (r'(?:eval\s*\(|create_function\s*\()', 2.5),
            (r'(?:extract\s*\(|compact\s*\()', 1.5),
            (r'(?:mysql_|ereg|eregi|split\()', 1.0),
            (r'(?:\$this\s*->\s*\$|->{\$|\$\$)', 1.5),
            (r'(?:@\s*(?:mysql_|file_|fopen|include|require))', 1.0),
            (r'(?:(?:include|require)(?:_once)?\s+\$)', 1.5),
            (r'(?:array_walk|array_map|array_filter|usort)\(.*function\s*\(', 0.8),
        ],
    },
    hints={
        "php5": r'(?:mysql_connect|mysql_query|ereg\(|create_function|global\s+\$|\$GLOBALS)',
    },
)
