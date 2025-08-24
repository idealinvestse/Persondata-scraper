# Auto-generated logghantering
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
