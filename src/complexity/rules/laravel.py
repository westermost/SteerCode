"""Laravel (PHP) complexity rules."""

from .. import register_rules

register_rules(
    frameworks={
        "laravel": [
            (r'(?:whereHas|with|whereIn|orWhere)\(', 1.0),
            (r'(?:Facade|Pipeline|Middleware)', 0.5),
        ],
    },
    hints={
        "laravel": r'(?:use Illuminate|namespace App\\|Eloquent|Artisan)',
    },
)
