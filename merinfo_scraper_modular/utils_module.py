from merinfo_scraper_modular.dataclasses_module import SearchResult
from typing import Optional, Dict
import logging
from merinfo_scraper import RobustMerinfoScraper

# Module-level logger to avoid NameError if logging_module isn't imported here
logger = logging.getLogger(__name__)

# Auto-generated hjälpfunktioner
def setup_logging(log_level=logging.INFO):
    """Konfigurerar strukturerad loggning"""
    handlers = []

def pipeline_hämta_fordonsinfo(användarfråga: str, pipeline_kontext: Optional[Dict] = None) -> Dict:
    """Pipeline-wrapper för OpenWebUI integration"""
    try:
        # Parsa användarfråga
        ord = användarfråga.lower().split()
        
        # Extrahera parametrar
        förnamn = None
        efternamn = None
        ort = None
        gata = None
        
        # Enkel NLP för att identifiera parametrar
        svenska_orter = ['stockholm', 'göteborg', 'malmö', 'uppsala', 'västerås', 'örebro', 
                        'linköping', 'helsingborg', 'jönköping', 'norrköping', 'lund', 
                        'umeå', 'gävle', 'borlänge', 'sundsvall', 'borås', 'eskilstuna']
        
        # Hitta ort
        for i, ord_item in enumerate(ord):
            if ord_item in svenska_orter:
                ort = ord_item
                # Ord före ort kan vara namn
                if i > 0:
                    if förnamn is None:
                        förnamn = ord[i-1]
                    elif efternamn is None:
                        efternamn = ord[i-1]
                break
        
        # Använd pipeline-kontext om tillgängligt
        if pipeline_kontext:
            förnamn = pipeline_kontext.get('förnamn', förnamn)
            efternamn = pipeline_kontext.get('efternamn', efternamn)
            ort = pipeline_kontext.get('ort', ort)
            gata = pipeline_kontext.get('gata', gata)
        
        # Skapa scraper med konservativa inställningar för pipeline
        config = {
            'min_delay': 5.0,
            'max_delay': 10.0,
            'user_agent_rotation': True,
            'max_retries': 2
        }
        
        scraper = RobustMerinfoScraper(config)
        
        try:
            result = scraper.search_person(
                förnamn=förnamn,
                efternamn=efternamn,
                ort=ort,
                gata=gata
            )
            
            # Formatera för pipeline
            return {
                'status': 'success' if result.success else 'partial',
                'meddelande': result.error_message or f"Hittade {len(result.persons)} personer",
                'personer': len(result.persons),
                'fordon': [
                    {
                        'märke_modell': v.märke_modell,
                        'år': v.år,
                        'ägare': v.ägare,
                        'typ': v.fordontyp
                    }
                    for v in result.vehicles
                ],
                'kvalitetspoäng': result.quality_score,
                'svarstid': result.response_time,
                'förslag': result.suggestions or []
            }
            
        finally:
            scraper.close()
            
    except Exception as e:
        logger.error(f"Pipeline-fel: {e}")
        return {
            'status': 'error',
            'meddelande': f"Fel vid sökning: {str(e)}",
            'personer': 0,
            'fordon': [],
            'kvalitetspoäng': 0.0
        }

def print_search_result(result: SearchResult):
    """Skriver ut sökresultat på ett formaterat sätt"""
    print(f"\n=== Sökresultat ===")
    print(f"Status: {'Framgång' if result.success else 'Partiell/Fel'}")
    print(f"Kvalitetspoäng: {result.quality_score:.2f}")
    print(f"Svarstid: {result.response_time:.2f}s")

def create_install_script():
    """Skapar installationsscript för systemet"""
    install_script = '''#!/bin/bash'''
