from dataclasses import dataclass, field
@dataclass
class SearchResult:
 id: int = field(default=0)
 name: str = field(default='')
 description: str = field(default='')
