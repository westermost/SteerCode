"""Stimulus (Hotwire) complexity rules."""

from .. import register_rules

register_rules(
    frameworks={
        "stimulus": [
            (r'static\s+targets\s*=\s*\[', 0.3),
            (r'static\s+values\s*=\s*\{', 0.5),
            (r'static\s+outlets\s*=\s*\[', 1.5),
            (r'(?:connect|disconnect|initialize)\s*\(\)', 0.3),
            (r'this\.\w+Outlet(?:s|Element)?', 1.2),
            (r'this\.(?:dispatch|application\.getControllerForElementAndIdentifier)', 1.5),
            (r'(?:\w+TargetConnected|\w+TargetDisconnected)\s*\(', 1.0),
            (r'(?:\w+ValueChanged)\s*\(', 0.8),
            (r'this\.element\.querySelector', 0.5),
        ],
    },
    hints={
        "stimulus": r'(?:import\s+.*Controller.*stimulus|extends\s+Controller|static\s+targets\s*=|data-controller)',
    },
)
