from dataclasses import dataclass, field
from typing import List, Tuple

@dataclass
class GraphNode:
    id: str
    type: str          # file | function | class | module
    name: str
    file_path: str = ""
    line_range: Tuple[int, int] = (0, 0)
    summary: str = ""
    tags: List[str] = field(default_factory=list)
    language: str = ""
    complexity: str = "simple"  # simple | moderate | complex

@dataclass
class GraphEdge:
    source: str
    target: str
    type: str          # imports | contains | calls | inherits | implements
    weight: float = 0.5

@dataclass
class Layer:
    id: str
    name: str
    description: str = ""
    node_ids: List[str] = field(default_factory=list)

@dataclass
class ParseResult:
    functions: List[dict] = field(default_factory=list)
    classes: List[dict] = field(default_factory=list)
    imports: List[dict] = field(default_factory=list)
    exports: List[dict] = field(default_factory=list)
