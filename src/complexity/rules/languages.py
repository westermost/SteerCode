"""Branch/control-flow patterns for all supported languages."""

from .. import register_rules

register_rules(branches={
    "python":     r'^\s*(?:if |elif |else:|for |while |except |with |try:|finally:|match |case )',
    "javascript": r'(?:(?:if|else if|else|for|while|do|switch|case|catch|finally)\s*[\({]|=>|\?\?|\?\.|[^\s?]\s*\?\s*[^\s?.:>])',
    "typescript": r'(?:(?:if|else if|else|for|while|do|switch|case|catch|finally)\s*[\({]|=>|\?\?|\?\.|[^\s?]\s*\?\s*[^\s?.:>]|(?:as|is|satisfies)\s)',
    "java":       r'(?:(?:if|else if|else|for|while|do|switch|case|catch|finally|throw)\s*[\({]|instanceof|\?)',
    "kotlin":     r'(?:(?:if|else if|else|for|while|do|when|catch|finally|throw)\s*[\({]|\?[.:]|!!|is\s)',
    "swift":      r'(?:(?:if|else if|else|for|while|repeat|switch|case|catch|guard|throw)\s*[\({]|\?\.|try[?!])',
    "go":         r'(?:(?:if|else if|else|for|switch|case|select|defer|go)\s+|:=)',
    "rust":       r'(?:(?:if|else if|else|for|while|loop|match|=>)\s*[\({]|\?|unwrap\(|expect\()',
    "c":          r'(?:(?:if|else if|else|for|while|do|switch|case|goto)\s*[\({]|\?)',
    "cpp":        r'(?:(?:if|else if|else|for|while|do|switch|case|catch|throw|try)\s*[\({]|\?|dynamic_cast|static_cast)',
    "csharp":     r'(?:(?:if|else if|else|for|foreach|while|do|switch|case|catch|finally|throw|try)\s*[\({]|\?\?|\?\.|\bis\s|\bwhen\s)',
    "ruby":       r'(?:(?:if|elsif|else|unless|case|when|while|until|for|begin|rescue|ensure|raise)\s+|\.each|\.map|\.select|\.reject)',
    "php":        r'(?:(?:if|elseif|else|for|foreach|while|do|switch|case|catch|finally|throw|try|match)\s*[\({]|\?\?|\?->|\?:)',
    "scala":      r'(?:(?:if|else if|else|for|while|match|case|catch|finally|throw|try)\s*[\({]|=>)',
    "lua":        r'(?:(?:if|elseif|else|for|while|repeat|until)\s+)',
    "shell":      r'(?:(?:if|elif|else|fi|for|while|until|case|esac|then|do|done)\s+|\|\||&&)',
})
