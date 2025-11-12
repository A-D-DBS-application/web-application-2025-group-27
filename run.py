"""Run script for local development.

Imports the application factory and starts the Flask development server when invoked
directly. The factory pattern ensures extensions and blueprints initialize cleanly.

Networking:
- By default, the development server binds to 127.0.0.1:5000 (loopback over TCP).
- You can change host/port (e.g., `flask_app.run(host='0.0.0.0', port=8000)`) to listen on all interfaces.

Migrations (schema change workflow reminder):
- After editing models (schemas), run:
    flask db migrate -m "describe schema change"
    flask db upgrade
    (flask db init only needs to be run once to initialize the migration environment)
    When you use a new database the commands are:
    flask db init
"""

from app import create_app

flask_app = create_app()

if __name__ == '__main__':
    flask_app.run(debug=True) 