"""Spring (Java) complexity rules."""

from .. import register_rules

register_rules(
    frameworks={
        "spring": [
            (r'@(?:Transactional|Async|Scheduled|Retryable)', 1.0),
            (r'@(?:GetMapping|PostMapping|RequestMapping)', 0.3),
        ],
    },
    hints={
        "spring": r'(?:@Controller|@Service|@Repository|@SpringBoot|import org\.springframework)',
    },
)
