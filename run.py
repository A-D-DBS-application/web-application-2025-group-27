"""Run script voor lokale development en productie."""

import os

from app import create_app

flask_app = create_app()

if __name__ == '__main__':
    # Voor Render (productie): gebruik PORT env var en bind aan 0.0.0.0
    # Voor lokaal: gebruik default poort 5001 en localhost
    # Dit zorgt ervoor dat dezelfde code werkt in beide omgevingen
    port = int(os.environ.get('PORT', 5001))
    host = '0.0.0.0' if os.environ.get('PORT') else '127.0.0.1'
    debug = not os.environ.get('PORT')  # Alleen debug mode lokaal (veiliger)
    flask_app.run(host=host, port=port, debug=debug)
