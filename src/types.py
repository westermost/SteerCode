from dataclasses import dataclass, field
from typing import List, Tuple, Optional

@dataclass
class SideEffect:
    type: str              # e.g. "db_write:transactions", "external_api:stripe"
    confidence: float = 0.8
    source: str = "regex"  # regex | import_inference | ast

@dataclass
class SemanticInfo:
    side_effects: List[SideEffect] = field(default_factory=list)
    control_flow: List[str] = field(default_factory=list)   # branching, loop, try_catch, async
    domain_hint: str = ""                                    # payment, auth, user, ...
    execution_role: str = ""                                 # entry_point, orchestrator, validator, data_access, adapter
    importance: float = 0.0                                  # 0-1 percentile

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
    semantics: Optional[SemanticInfo] = None

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

@dataclass
class FileSummary:
    file_path: str
    summary: str = ""
    facts: dict = field(default_factory=dict)  # {external_apis:[], db_tables:[], domains:[], side_effects:[]}

@dataclass
class ModuleSummary:
    name: str
    file_paths: List[str] = field(default_factory=list)
    summary: str = ""
    facts: dict = field(default_factory=dict)
