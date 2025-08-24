#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MerinfoScraper - Robust system för att hämta personuppgifter och fordonsinformation
från Merinfo.se med fullständig felhantering och OpenWebUI pipeline-integration.

Författare: Utvecklad för OpenWebUI pipeline-integration
Version: 1.0.0
"""

import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import time
import random
from typing import Dict, List, Optional, Tuple, Union
import logging
from dataclasses import dataclass, asdict
from functools import lru_cache
import hashlib
import json
import sys
import traceback
import argparse
from pathlib import Path
import os

# Konfigurera loggning med UTF-8 stöd
def setup_logging(log_level=logging.INFO):
    """Konfigurerar strukturerad loggning"""
    handlers = []
    
    # Fil-handler med UTF-8 encoding
    file_handler = logging.FileHandler('merinfo_scraper.log', encoding='utf-8')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    handlers.append(file_handler)
    
    # Console-handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    handlers.append(console_handler)
    
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()

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
    
    def __str__(self) -> str:
        return f"{self.namn} ({self.ålder or 'okänd ålder'}) - {self.adress}"

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
    
    def __str__(self) -> str:
        return f"{self.märke_modell} ({self.år}) - Ägare: {self.ägare}"

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

class MerinfoCache:
    """Enkel cache för att minska antal förfrågningar"""
    def __init__(self, max_size: int = 100, ttl: int = 3600):
        self.cache = {}
        self.max_size = max_size
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Dict]:
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Dict):
        if len(self.cache) >= self.max_size:
            # Ta bort äldsta
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][-1])
            del self.cache[oldest_key]
        
        self.cache[key] = (value, time.time())
    
    def clear(self):
        self.cache.clear()

class RobustMerinfoScraper:
    """Huvudklass för robust skrapning av Merinfo.se"""
    
    def __init__(self, config: Optional[Dict] = None):
        """Initialiserar scraper med konfiguration"""
        self.config = config or {}
        
        # Konfigurationsparametrar
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]
        
        self.user_agent_rotation = self.config.get('user_agent_rotation', True)
        self.min_delay = self.config.get('min_delay', 2.0)
        self.max_delay = self.config.get('max_delay', 5.0)
        self.max_retries = self.config.get('max_retries', 3)
        self.timeout = self.config.get('timeout', 20)
        self.respect_robots = self.config.get('respect_robots', True)
        
        # Skapa session
        self.session = requests.Session()
        self.setup_session()
        
        # Statistik och cache
        self.cache = MerinfoCache()
        self.request_count = 0
        self.last_request_time = 0
        self.error_count = 0
        
        logger.info("MerinfoScraper initialiserad")

    def setup_session(self):
        """Konfigurerar HTTP-session med robusta inställningar"""
        try:
            # Välj User-Agent
            if self.user_agent_rotation:
                user_agent = random.choice(self.user_agents)
            else:
                user_agent = self.user_agents[-0]  # FIX: var tidigare self.user_agents
                
            # Sätt headers
            self.session.headers.update({
                'User-Agent': user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'sv-SE,sv;q=0.9,en-US;q=0.8,en;q=0.7',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Cache-Control': 'max-age=0',
            })
            
            # Konfigurera adapters med retry-logik
            from requests.adapters import HTTPAdapter
            try:
                from urllib3.util.retry import Retry
                
                retry_strategy = Retry(
                    total=3,
                    backoff_factor=1,
                    status_forcelist=[429, 500, 502, 503, 504],
                    allowed_methods=["HEAD", "GET", "OPTIONS"]
                )
                
                adapter = HTTPAdapter(max_retries=retry_strategy)
                self.session.mount("http://", adapter)
                self.session.mount("https://", adapter)
            except ImportError:
                logger.warning("urllib3 Retry inte tillgänglig, använder grundläggande retry")
            
            logger.info(f"Session konfigurerad med User-Agent: {user_agent[:50]}...")
            
        except Exception as e:
            logger.error(f"Fel vid session-setup: {e}")
            raise

    def rate_limit(self):
        """Implementerar intelligent rate limiting"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        # Beräkna fördröjning med adaptiv logik
        base_delay = self.min_delay
        if self.error_count > 0:
            base_delay *= (1 + self.error_count * 0.5)
        
        if time_since_last < base_delay:
            delay = random.uniform(base_delay, self.max_delay)
            logger.debug(f"Rate limiting: väntar {delay:.2f}s")
            time.sleep(delay)
        
        self.last_request_time = time.time()
        self.request_count += 1

    def safe_request(self, url: str, retries: Optional[int] = None) -> Optional[BeautifulSoup]:
        """Gör säker HTTP-förfrågan med felhantering"""
        if retries is None:
            retries = self.max_retries
        
        # Kontrollera cache först
        cache_key = hashlib.md5(url.encode()).hexdigest()
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.debug(f"Cache hit för {url}")
            return BeautifulSoup(cached_result['html'], 'html.parser')
        
        for attempt in range(retries + 1):
            try:
                self.rate_limit()
                
                # Rotera User-Agent vid retry
                if attempt > 0 and self.user_agent_rotation:
                    new_ua = random.choice(self.user_agents)
                    self.session.headers['User-Agent'] = new_ua
                    logger.info(f"Försök {attempt + 1}: Ny User-Agent")
                
                response = self.session.get(url, timeout=self.timeout)
                response.raise_for_status()
                
                # Hantera encoding
                if response.encoding is None:
                    response.encoding = 'utf-8'
                elif response.encoding.lower() in ['iso-8859-1', 'windows-1252']:
                    response.encoding = 'utf-8'
                
                # Parsa HTML
                soup = BeautifulSoup(response.content, 'html.parser', from_encoding='utf-8')
                
                # Cacha resultatet
                self.cache.set(cache_key, {'html': str(soup)})
                
                # Återställ fel-räknare
                self.error_count = max(0, self.error_count - 1)
                
                logger.info(f"Framgångsrik förfrågan till {url}")
                return soup
                
            except requests.exceptions.RequestException as e:
                self.error_count += 1
                logger.warning(f"Försök {attempt + 1}/{retries + 1} misslyckades: {e}")
                
                if attempt < retries:
                    backoff_delay = (2 ** attempt) + random.uniform(1, 3)
                    logger.info(f"Backoff: {backoff_delay:.2f}s")
                    time.sleep(backoff_delay)
                    
            except Exception as e:
                logger.error(f"Oväntat fel: {e}")
                break
        
        logger.error(f"Alla försök misslyckades för {url}")
        return None

    def intelligent_search_builder(self, förnamn: str = None, efternamn: str = None, 
                                 ort: str = None, gata: str = None, 
                                 ålder: int = None) -> List[Tuple[str, float]]:
        """Bygger intelligenta sökfrågor med konfidenspoäng"""
        sökstrategier = []
        
        # Normalisera input
        if förnamn:
            förnamn = self.normalize_svensk_namn(förnamn)
        if efternamn:
            efternamn = self.normalize_svensk_namn(efternamn)
        if ort:
            ort = self.normalize_svensk_namn(ort)
        if gata:
            gata = self.normalize_svensk_namn(gata)
            
        # Bygg strategier med prioritet
        if förnamn and efternamn and ort:
            sökstrategier.append((f"{förnamn}+{efternamn}+{ort}", 1.0))
            
        if gata and ort:
            if förnamn and efternamn:
                sökstrategier.append((f"{förnamn}+{efternamn}+{gata}+{ort}", 0.95))
            elif förnamn:
                sökstrategier.append((f"{förnamn}+{gata}+{ort}", 0.8))
                
        if förnamn and ort:
            sökstrategier.append((f"{förnamn}+{ort}", 0.7))
            
        if efternamn and ort:
            sökstrategier.append((f"{efternamn}+{ort}", 0.6))
            
        if ålder and förnamn and efternamn:
            födelseår = 2025 - ålder
            sökstrategier.append((f"{förnamn}+{efternamn}+{födelseår}", 0.5))
            
        # Sortera efter konfidenspoäng
        sökstrategier.sort(key=lambda x: x[-1], reverse=True)  # FIX: var tidigare x
        return sökstrategier[:4]

    @lru_cache(maxsize=200)
    def normalize_svensk_namn(self, namn: str) -> str:
        """Normaliserar svenska namn och städer"""
        if not namn:
            return ""
            
        namn = namn.strip()
        
        # Svenska tecken normalisering
        namn_mappning = {
            'aa': 'å', 'ae': 'ä', 'oe': 'ö',
            'AA': 'Å', 'AE': 'Ä', 'OE': 'Ö'
        }
        
        for eng, swe in namn_mappning.items():
            namn = namn.replace(eng, swe)
            
        # Rensa och formatera
        namn = re.sub(r'\s+', ' ', namn)
        namn = re.sub(r'[^\w\såäöÅÄÖ-]', '', namn)
        
        return namn.title()

    def extract_person_data_robust(self, container) -> Optional[PersonResult]:
        """Robust extrahering av persondata"""
        try:
            # Hitta namn och länk
            namn_länk = (
                container.find('a', class_='mi-text-primary hover:mi-underline') or
                container.find('a', href=re.compile(r'/person/')) or
                container.find('a', string=re.compile(r'\w+'))
            )
            
            if not namn_länk:
                logger.warning("Kunde inte hitta namn-länk")
                return None
                
            # Extrahera namn
            namn = re.sub(r'\s+', ' ', namn_länk.get_text().strip())
            
            # Extrahera profil-URL
            profil_url = namn_länk.get('href')
            if profil_url and not profil_url.startswith('http'):
                profil_url = 'https://www.merinfo.se' + profil_url
                
            # Extrahera adress
            adress = ""
            gata = ""
            
            adress_element = container.find('address', class_='mi-not-italic mi-flex mi-flex-col')
            if adress_element:
                adress_delar = [span.get_text().strip() for span in adress_element.find_all('span')]
                adress = ', '.join(filter(None, adress_delar))
                if adress_delar:
                    första_del = adress_delar[-0]  # FIX: var tidigare adress_delar
                    gata_match = re.match(r'^([^\d]+)', första_del)
                    if gata_match:
                        gata = gata_match.group(1).strip()
            
            # Fallback för adress
            if not adress:
                address_spans = container.find_all('span', string=re.compile(r'\d{3}\s*\d{2}\s+\w+'))
                if address_spans:
                    adress = address_spans[-0].get_text().strip()  # FIX: var tidigare address_spans
                    
            # Extrahera personnummer
            personnummer = ""
            personnummer_element = container.find('span', string=re.compile(r'\d{8}-'))
            if personnummer_element:
                personnummer = personnummer_element.get_text().strip()
                
            # Extra data
            extra_data = self.extract_additional_person_data(container)
            
            person = PersonResult(
                namn=namn,
                profil_url=profil_url,
                adress=adress,
                gata=gata,
                personnummer=personnummer,
                ålder=extra_data.get('ålder'),
                kön=extra_data.get('kön'),
                bolagsengagemang=extra_data.get('bolagsengagemang', False)
            )
            
            logger.debug(f"Extraherad person: {person.namn}")
            return person
            
        except Exception as e:
            logger.warning(f"Fel vid extrahering av persondata: {e}")
            return None

    def extract_additional_person_data(self, container) -> Dict:
        """Extraherar utökad persondata"""
        extra_data = {}
        
        try:
            # Kön
            if container.find('span', attrs={'data-original-title': re.compile(r'Är man', re.I)}):
                extra_data['kön'] = 'Man'
            elif container.find('span', attrs={'data-original-title': re.compile(r'Är kvinna', re.I)}):
                extra_data['kön'] = 'Kvinna'
            
            # Bolagsengagemang
            if container.find('span', attrs={'data-original-title': re.compile(r'bolagsengagemang', re.I)}):
                extra_data['bolagsengagemang'] = True
            
            # Ålder från personnummer
            personnummer_element = container.find('span', string=re.compile(r'\d{8}-'))
            if personnummer_element:
                personnummer = personnummer_element.get_text().strip()
                if len(personnummer) >= 8:
                    try:
                        if personnummer.startswith('19') or personnummer.startswith('20'):
                            födelseår = int(personnummer[:4])
                        else:
                            två_siffror = int(personnummer[:2])
                            födelseår = 2000 + två_siffror if två_siffror <= 25 else 1900 + två_siffror
                                
                        if 1900 <= födelseår <= 2025:
                            extra_data['ålder'] = 2025 - födelseår
                    except (ValueError, IndexError):
                        pass
                        
        except Exception as e:
            logger.debug(f"Fel vid extra persondata: {e}")
            
        return extra_data

    def extract_all_persons_robust(self, soup) -> List[PersonResult]:
        """Robust extrahering av alla personer"""
        personer = []
        
        # Multipla selektorer
        selektorer = [
            'div.mi-text-sm.mi-bg-white.mi-shadow-dark-blue-20.mi-p-0.mi-mb-6.md\\:mi-rounded-lg',
            'div[class*="mi-text-sm"][class*="mi-bg-white"]',
            'div[class*="result"]',
            '.person-result',
            'div:has(a[href*="/person/"])'
        ]
        
        containers = []
        for selektor in selektorer:
            try:
                found = soup.select(selektor)
                if found:
                    containers = found
                    logger.debug(f"Hittade {len(containers)} containers med: {selektor}")
                    break
            except Exception as e:
                logger.debug(f"Selektor misslyckades: {e}")
                continue
                
        if not containers:
            logger.warning("Inga person-containers hittades")
            return personer
            
        for i, container in enumerate(containers):
            person = self.extract_person_data_robust(container)
            if person:
                personer.append(person)
                
        logger.info(f"Extraherade {len(personer)} personer")
        return personer

    def parse_vehicle_table_robust(self, container) -> List[FordonResult]:
        """Robust parsing av fordonstabeller"""
        fordon = []
        
        try:
            tabell = container.find('table') or container.find('table', class_='table')
            if not tabell:
                logger.warning("Ingen fordons-tabell hittades")
                return fordon
                
            tbody = tabell.find('tbody')
            if not tbody:
                logger.warning("Ingen tbody hittades")
                return fordon
                
            for i, rad in enumerate(tbody.find_all('tr')):
                try:
                    celler = rad.find_all('td')
                    if len(celler) < 1:
                        continue
                        
                    # Märke och modell
                    märke_modell = ""
                    märke_modell_element = celler[-0].find('span')  # FIX: var tidigare celler.find
                    if märke_modell_element:
                        märke_modell = märke_modell_element.get_text().strip()
                    
                    # År
                    år = ""
                    år_element = celler[-0].find('span', string=re.compile(r'\(\d{4}\)'))  # FIX: var tidigare celler.find
                    if år_element:
                        år_match = re.search(r'\((\d{4})\)', år_element.get_text())
                        år = år_match.group(1) if år_match else ""
                    elif len(celler) >= 2:
                        år_text = celler[-1].get_text().strip()  # FIX: var tidigare celler.get_text
                        if re.match(r'^\d{4}$', år_text):
                            år = år_text
                    
                    # Ägare
                    ägare = ""
                    if len(celler) >= 3:
                        ägare = celler[-2].get_text().strip()  # FIX: var tidigare celler.get_text
                    else:
                        ägare_element = celler[-0].find('dd')  # FIX: var tidigare celler.find
                        if ägare_element:
                            ägare = ägare_element.get_text().strip()
                    
                    # Klassificera
                    fordontyp = self.classify_vehicle_type(märke_modell)
                    
                    if märke_modell:
                        fordon_result = FordonResult(
                            märke_modell=märke_modell,
                            år=år,
                            ägare=ägare,
                            fordontyp=fordontyp
                        )
                        fordon.append(fordon_result)
                        logger.debug(f"Fordon: {märke_modell} ({år}) - {ägare}")
                    
                except Exception as e:
                    logger.warning(f"Fel vid parsing av fordonsrad {i+1}: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Fel vid fordons-tabell parsing: {e}")
            
        logger.info(f"Extraherade {len(fordon)} fordon")
        return fordon

    def classify_vehicle_type(self, märke_modell: str) -> str:
        """Klassificerar fordonstyp"""
        if not märke_modell:
            return 'Okänt'
            
        märke_modell_lower = märke_modell.lower()
        
        kategorier = {
            'Motorcykel': ['motorcykel', 'mc', 'moped', 'yamaha', 'honda', 'kawasaki', 'suzuki', 'harley'],
            'Lastbil': ['lastbil', 'truck', 'scania', 'volvo fl', 'volvo fh', 'man tg', 'mercedes actros'],
            'Släpvagn': ['släpvagn', 'trailer', 'kärra', 'släp'],
            'Husbil': ['husbil', 'camping', 'motorhome', 'autocruiser', 'dethleffs'],
            'Traktor': ['traktor', 'john deere', 'massey ferguson', 'valtra'],
            'Buss': ['buss', 'omnibus', 'coach']
        }
        
        for kategori, nyckelord in kategorier.items():
            if any(ord in märke_modell_lower for ord in nyckelord):
                return kategori
                
        return 'Personbil'

    def fetch_vehicle_info_robust(self, profil_url: str) -> List[FordonResult]:
        """Robust hämtning av fordonsinformation"""
        if not profil_url:
            return []
            
        logger.info(f"Hämtar fordonsinfo från: {profil_url}")
        
        soup = self.safe_request(profil_url)
        if not soup:
            return []
            
        # Hitta fordons-container
        selektorer = [
            'div.vue-vehicle-table',
            'div[class*="vehicle"]',
            'div:has(table:has(th:contains("Märke")))',
            '.vehicle-info'
        ]
        
        for selektor in selektorer:
            try:
                container = soup.select_one(selektor)
                if container:
                    logger.debug(f"Hittade fordons-container: {selektor}")
                    return self.parse_vehicle_table_robust(container)
            except Exception as e:
                logger.debug(f"Selektor {selektor} misslyckades: {e}")
                
        logger.warning("Ingen fordons-container hittades")
        return []

    def calculate_quality_score(self, personer: List[PersonResult], 
                              fordon: List[FordonResult], 
                              sökparametrar: Dict) -> float:
        """Beräknar kvalitetspoäng"""
        if not personer:
            return 0.0
            
        poäng = 0.5  # Baspoäng
        
        # Bonus för antal personer
        if len(personer) == 1:
            poäng += 0.3
        elif len(personer) <= 3:
            poäng += 0.1
            
        # Bonus för fordon
        if fordon:
            poäng += 0.2
            
        # Bonus för komplett data
        for person in personer:
            if person.adress:
                poäng += 0.05
            if person.ålder:
                poäng += 0.05
            if person.kön:
                poäng += 0.05
                
        return min(1.0, poäng)

    def generate_suggestions(self, personer: List[PersonResult]) -> List[str]:
        """Genererar förslag för att förbättra sökningen"""
        suggestions = []
        
        if len(personer) > 1:
            # Samla gator
            gator = [p.gata for p in personer if p.gata]
            if gator:
                unika_gator = list(set(gator))
                suggestions.append(f"Specificera gata: {', '.join(unika_gator[:5])}")
            
            # Samla åldrar
            åldrar = [str(p.ålder) for p in personer if p.ålder]
            if åldrar:
                unika_åldrar = list(set(åldrar))
                suggestions.append(f"Specificera ålder: {', '.join(unika_åldrar[:5])}")
        
        return suggestions

    def search_person(self, förnamn: str = None, efternamn: str = None, 
                     ort: str = None, gata: str = None, 
                     ålder: int = None) -> SearchResult:
        """Huvudmetod för personsökning"""
        start_time = time.time()
        
        # Validera input
        if not any([förnamn, efternamn, ort]):
            return SearchResult(
                success=False,
                persons=[],
                vehicles=[],
                quality_score=0.0,
                error_message="Minst ett sökkriterium krävs (förnamn, efternamn eller ort)"
            )
        
        sökparametrar = {
            'förnamn': förnamn, 'efternamn': efternamn, 
            'ort': ort, 'gata': gata, 'ålder': ålder
        }
        
        logger.info(f"Startar sökning: {sökparametrar}")
        
        # Bygg sökstrategier
        strategier = self.intelligent_search_builder(**sökparametrar)
        
        bästa_resultat = None
        bästa_poäng = 0.0
        
        for strategi, konfidenspoäng in strategier:
            try:
                logger.info(f"Testar strategi: {strategi} (konfidenspoäng: {konfidenspoäng})")
                
                url = f"https://www.merinfo.se/search?q={urllib.parse.quote_plus(strategi)}"
                soup = self.safe_request(url)
                
                if not soup:
                    continue
                    
                personer = self.extract_all_persons_robust(soup)
                
                if not personer:
                    logger.info("Inga personer hittades")
                    continue
                    
                logger.info(f"Hittade {len(personer)} personer")
                
                # Hantera olika scenarion
                if len(personer) == 1:
                    # Ett resultat - hämta fordon
                    person = personer[-0]  # FIX: var tidigare personer
                    fordon = self.fetch_vehicle_info_robust(person.profil_url)
                    
                    kvalitetspoäng = self.calculate_quality_score(personer, fordon, sökparametrar)
                    
                    resultat = SearchResult(
                        success=True,
                        persons=personer,
                        vehicles=fordon,
                        quality_score=kvalitetspoäng,
                        search_strategy=strategi,
                        response_time=time.time() - start_time
                    )
                    
                    logger.info(f"Framgång: {len(fordon)} fordon hittades")
                    return resultat
                    
                elif len(personer) <= 3:
                    # Få resultat - spara som fallback
                    kvalitetspoäng = self.calculate_quality_score(personer, [], sökparametrar)
                    
                    if kvalitetspoäng > bästa_poäng:
                        suggestions = self.generate_suggestions(personer)
                        
                        bästa_resultat = SearchResult(
                            success=False,
                            persons=personer,
                            vehicles=[],
                            quality_score=kvalitetspoäng,
                            error_message=f"Flera resultat ({len(personer)}), specificera gata",
                            search_strategy=strategi,
                            response_time=time.time() - start_time,
                            suggestions=suggestions
                        )
                        bästa_poäng = kvalitetspoäng
                        
                else:
                    # Många resultat
                    logger.info(f"För många resultat ({len(personer)})")
                    
            except Exception as e:
                logger.error(f"Fel vid sökning: {e}")
                logger.debug(traceback.format_exc())
                continue
        
        # Returnera resultat
        if bästa_resultat:
            return bästa_resultat
        else:
            return SearchResult(
                success=False,
                persons=[],
                vehicles=[],
                quality_score=0.0,
                error_message="Inga resultat hittades",
                response_time=time.time() - start_time
            )

    def get_stats(self) -> Dict:
        """Returnerar statistik"""
        return {
            'requests_made': self.request_count,
            'errors_encountered': self.error_count,
            'cache_size': len(self.cache.cache),
            'success_rate': (self.request_count - self.error_count) / max(1, self.request_count) * 100
        }

    def close(self):
        """Stänger session"""
        self.session.close()
        logger.info("MerinfoScraper stängd")

# Pipeline-integration för OpenWebUI
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

# CLI-funktionalitet
def main():
    """Huvudfunktion för CLI"""
    parser = argparse.ArgumentParser(
        description='MerinfoScraper - Hämta personuppgifter och fordonsinformation'
    )
    
    parser.add_argument('--förnamn', '-f', help='Förnamn att söka efter')
    parser.add_argument('--efternamn', '-e', help='Efternamn att söka efter')
    parser.add_argument('--ort', '-o', help='Ort att söka i')
    parser.add_argument('--gata', '-g', help='Gata för mer specifik sökning')
    parser.add_argument('--ålder', '-a', type=int, help='Ålder för mer specifik sökning')
    
    parser.add_argument('--output', help='Spara resultat till fil (JSON)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Detaljerad utskrift')
    parser.add_argument('--stats', action='store_true', help='Visa endast statistik')
    parser.add_argument('--demo', action='store_true', help='Kör demo-sökning')
    
    args = parser.parse_args()
    
    # Konfigurera loggning baserat på verbose-flagga
    if args.verbose:
        setup_logging(logging.DEBUG)
    else:
        setup_logging(logging.INFO)
    
    # Skapa scraper
    config = {
        'min_delay': 3.0,
        'max_delay': 6.0,
        'user_agent_rotation': True
    }
    
    scraper = RobustMerinfoScraper(config)
    
    try:
        if args.demo:
            # Demo-sökning
            print("=== MerinfoScraper Demo ===")
            result = scraper.search_person(
                förnamn='Oscar',
                efternamn='Delerud',
                ort='Borlänge'
            )
            print_search_result(result)
            
        elif args.stats:
            # Visa statistik
            stats = scraper.get_stats()
            print("=== Statistik ===")
            for key, value in stats.items():
                print(f"{key}: {value}")
                
        else:
            # Normal sökning
            if not any([args.förnamn, args.efternamn, args.ort]):
                print("Fel: Minst förnamn, efternamn eller ort krävs")
                parser.print_help()
                return 1
            
            result = scraper.search_person(
                förnamn=args.förnamn,
                efternamn=args.efternamn,
                ort=args.ort,
                gata=args.gata,
                ålder=args.ålder
            )
            
            print_search_result(result)
            
            # Spara till fil om begärt
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
                print(f"\nResultat sparat till: {args.output}")
        
        return 0
        
    except KeyboardInterrupt:
        print("\nAvbrutet av användare")
        return 1
    except Exception as e:
        logger.error(f"Fel: {e}")
        return 1
    finally:
        scraper.close()

def print_search_result(result: SearchResult):
    """Skriver ut sökresultat på ett formaterat sätt"""
    print(f"\n=== Sökresultat ===")
    print(f"Status: {'Framgång' if result.success else 'Partiell/Fel'}")
    print(f"Kvalitetspoäng: {result.quality_score:.2f}")
    print(f"Svarstid: {result.response_time:.2f}s")
    
    if result.error_message:
        print(f"Meddelande: {result.error_message}")
    
    if result.persons:
        print(f"\n=== Hittade {len(result.persons)} personer ===")
        for i, person in enumerate(result.persons, 1):
            print(f"{i}. {person}")
    
    if result.vehicles:
        print(f"\n=== Hittade {len(result.vehicles)} fordon ===")
        for i, vehicle in enumerate(result.vehicles, 1):
            print(f"{i}. {vehicle} (Typ: {vehicle.fordontyp})")
    
    if result.suggestions:
        print(f"\n=== Förslag ===")
        for suggestion in result.suggestions:
            print(f"- {suggestion}")

# Installationsscript
def create_install_script():
    """Skapar installationsscript för systemet"""
    install_script = '''#!/bin/bash
# MerinfoScraper Installationsscript

echo "=== MerinfoScraper Installation ==="

# Kontrollera Python
if ! command -v python3 &> /dev/null; then
    echo "Fel: Python 3 krävs men hittades inte"
    exit 1
fi

# Installera dependencies
echo "Installerar Python-paket..."
pip3 install requests beautifulsoup4 lxml

# Skapa logfil
touch merinfo_scraper.log
chmod 664 merinfo_scraper.log

# Gör script körbart
chmod +x merinfo_scraper.py

echo "Installation klar!"
echo ""
echo "Användning:"
echo "  python3 merinfo_scraper.py --demo          # Kör demo"
echo "  python3 merinfo_scraper.py --förnamn Anna --ort Stockholm"
echo "  python3 merinfo_scraper.py --help          # Visa hjälp"
'''
    
    with open('install.sh', 'w') as f:
        f.write(install_script)
    
    os.chmod('install.sh', 0o755)
    print("Installationsscript skapat: install.sh")

if __name__ == '__main__':
    sys.exit(main())