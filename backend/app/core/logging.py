import logging
from app.core.config import settings

# ANSI color codes
COLORS = {
    'ERROR': '\033[91m',  # Red
    'WARNING': '\033[93m',  # Yellow
    'INFO': '\033[92m',  # Green
    'DEBUG': '\033[94m',  # Blue
    'RESET': '\033[0m'  # Reset
}

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        # Add color to the levelname
        if record.levelname in COLORS:
            record.levelname = f"{COLORS[record.levelname]}{record.levelname}{COLORS['RESET']}"
        return super().format(record)

# Create a custom handler with the colored formatter
handler = logging.StreamHandler()
formatter = ColoredFormatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)

# Configure logging with the custom handler
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    handlers=[handler]
)

# Create a logger for the application
logger = logging.getLogger("app")

# Add a test log message to verify logging is working
logger.info("Logging system initialized")
logger.error("This is a test error message in red")
logger.warning("This is a test warning message in yellow")
logger.debug("This is a test debug message in blue") 