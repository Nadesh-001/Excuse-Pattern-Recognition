import os
import logging
from app import create_app

# Set up logging early
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the Flask application using the factory
app = create_app()

if __name__ == '__main__':
    # Configuration from environment
    _debug = os.getenv("FLASK_ENV", "development").lower() == "development"
    _port  = int(os.getenv("PORT", 5000))
    _host  = "0.0.0.0"

    logger.info(f"🚀 Starting Neural_Protocol on {_host}:{_port} (debug={_debug})")
    app.run(debug=_debug, host=_host, port=_port)
