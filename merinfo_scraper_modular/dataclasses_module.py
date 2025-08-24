from dataclasses import dataclass, asdict
from typing import Dict, List, Optional

@dataclass
class PersonResult:
    """Datastruktur för personinformation"""
    namn: str
    profil_url: str
    adress: str
    gata: str
    personnummer: str
    ålder: Optional[int] = None
    kön: Optional[str] = None
    bolagsengagemang: bool = False

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class FordonResult:
    """Datastruktur för fordonsinformation"""
    märke_modell: str
    år: str
    ägare: str
    fordontyp: Optional[str] = None
    registreringsnummer: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class SearchResult:
    """Datastruktur för sökresultat"""
    success: bool
    persons: List[PersonResult]
    vehicles: List[FordonResult]
    quality_score: float
    error_message: Optional[str] = None
    search_strategy: Optional[str] = None
    response_time: Optional[float] = None
    suggestions: Optional[List[str]] = None

    def to_dict(self) -> Dict:
        return {
            'success': self.success,
            'persons': [p.to_dict() for p in self.persons],
            'vehicles': [v.to_dict() for v in self.vehicles],
            'quality_score': self.quality_score,
            'error_message': self.error_message,
            'search_strategy': self.search_strategy,
            'response_time': self.response_time,
            'suggestions': self.suggestions or []
        }
