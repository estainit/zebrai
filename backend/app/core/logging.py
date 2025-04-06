import logging
from app.core.config import settings

# Configure logging to show all levels and use a simple format
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()  # This ensures logs go to stdout
    ]
)

# Create a logger for the application
logger = logging.getLogger("app")

# Add a test log message to verify logging is working
logger.info("Logging system initialized") 