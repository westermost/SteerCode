"""React complexity rules."""

from .. import register_rules

register_rules(
    frameworks={
        "react": [
            (r'useState|useEffect|useCallback|useMemo|useRef|useReducer|useContext', 0.5),
            (r'useEffect\([^)]*\[.*\]', 1.5),
        ],
    },
    hints={
        "react": r'(?:import.*react|from\s+["\']react|useState|useEffect|jsx)',
    },
)
