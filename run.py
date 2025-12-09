r"""Run script for local development and production."""

import os
from app import create_app

flask_app = create_app()

if __name__ == '__main__':
    # For Render: use PORT env var and bind to 0.0.0.0
    # For local: use default port 5001 and localhost
    port = int(os.environ.get('PORT', 5001))
    host = '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1'
    debug = not os.environ.get('PORT')  # Only debug locally
    flask_app.run(host=host, port=port, debug=debug)
