## Flask + SQLAlchemy + Migrations: How this project is structured and how it runs

This mini-project demonstrates a clean Flask application layout using the application factory pattern, SQLAlchemy ORM, and Alembic migrations (via Flask-Migrate). It also shows how to avoid circular import problems and how the app communicates over the network with the database and HTTP clients.

### Why these files exist and what each does

- `app.py`: Creates the Flask app in a factory function `create_app()`, initializes the SQLAlchemy extension (`db`) and migration support (`Migrate`), and registers routes. This file is the central wiring point for the app and extensions.
- `config.py`: Holds configuration, such as `SECRET_KEY` and `SQLALCHEMY_DATABASE_URI`. The database URI includes networking details (scheme, user, password, host, port, database) that let SQLAlchemy connect to the DB server over TCP.
- `routes.py`: Defines HTTP endpoints (routes) attached to the Flask app. Routes call into models to query data and render templates.
- `models.py`: Declares ORM models (classes) that map to database table schemas. Each class describes the table name and columns/types.
- `run.py`: Entry point for local development. Imports `create_app()` from `app.py`, creates the app, and runs the development server (by default on `127.0.0.1:5000`).
- `templates/`: Jinja2 templates for rendering responses (e.g., `index.html`).
- `migrations/`: Alembic migration environment and versioned migration scripts. These capture schema changes over time.

### Avoiding circular imports (import loops)

Circular imports typically happen when two modules import each other at import time. In Flask apps, a common pitfall is:
- `models.py` imports `db` from `app.py`
- `app.py` imports models directly at top-level

This forms a loop: `app.py` -> `models.py` -> `app.py`.

We avoid this by:
1. Creating the `db` object at the top of `app.py` but not binding it to the app at import time:
   ```python
   # app.py
   db = SQLAlchemy()
   ```
2. Using the application factory `create_app()` and calling `db.init_app(app)` inside it. This defers the binding until runtime:
   ```python
   # app.py
   def create_app():
       app = Flask(__name__, template_folder='templates')
       app.config.from_object(Config)
       db.init_app(app)
       ...
       return app
   ```
3. Importing routes after the app and db are initialized inside `create_app()`:
   ```python
   from routes import register_routes
   register_routes(app, db)
   ```
   This local import helps prevent import-time cycles.
4. In `models.py`, we import `db` from `app`:
   ```python
   # models.py
   from app import db
   class Person(db.Model):
       ...
   ```
   Because `db` is defined at module scope in `app.py` and only bound to the app later, this works without causing a cycle, provided we avoid importing `models` at the top-level of `app.py`. The factory pattern plus on-demand imports resolve the circular dependency.

### Networking concepts in this app

- HTTP server: When `run.py` runs, the Werkzeug development server listens on `127.0.0.1:5000` (TCP). Clients (your browser, curl, etc.) send HTTP requests over TCP; the server returns responses over the same connection.
- Database connection: SQLAlchemy opens a TCP connection to the database host/port described in `SQLALCHEMY_DATABASE_URI`. If configured, connections can be TLS-encrypted. Connection pooling is handled internally by SQLAlchemy.
- URI format: `postgresql://user:password@host:port/database`

### Migrations: changing the schema safely

When you edit models (which define the table schema), create and apply migrations:
1. Autogenerate a migration that captures model-to-schema differences:
   ```bash
   flask db migrate -m "describe schema change"
   ```
2. Apply the new migration to the database:
   ```bash
   flask db upgrade
   ```

Behind the scenes, Alembic compares the current model metadata to the last applied revision and creates a migration script in `migrations/versions/`. Upgrading applies that script to the database schema.

### Core concepts explained (for beginners)

This section introduces key terms in simple language and shows where they appear in your code.

- Factory function (application factory):
  - A “factory” is just a function that builds and returns something new each time you call it.
  - In Flask, the factory pattern is used to build the app only when you need it, instead of at import time. This keeps startup predictable and avoids import loops.
  - Where in code: `create_app()` in `app.py`:
    ```python
    def create_app():
        app = Flask(__name__, template_folder='templates')
        app.config.from_object(Config)
        db.init_app(app)
        from routes import register_routes
        register_routes(app, db)
        Migrate(app, db)
        return app
    ```
  - Why it matters: You can create multiple app instances (e.g., for tests), delay heavy setup until needed, and avoid circular imports by importing modules inside the factory.

- Extension:
  - An extension adds features to Flask without you coding everything from scratch.
  - Examples: SQLAlchemy (database/ORM), Migrate (migrations), LoginManager (auth), etc.
  - You typically create an extension object once (unbound), then attach it to your app inside the factory.
  - Where in code:
    - Create: `db = SQLAlchemy()` (top of `app.py`)
    - Bind: `db.init_app(app)` (inside `create_app()`)
    - Migrations: `Migrate(app, db)`
  - Mental model: Think of an extension like a plugin. You prepare it (create the object) and then plug it into your app when the app exists.

- TCP (Transmission Control Protocol):
  - TCP is the basic “reliable delivery” system most internet traffic uses. It makes sure data arrives in order and without loss.
  - Your Flask server listens for HTTP requests over TCP (e.g., `127.0.0.1:5000`). Your browser opens a TCP connection to send the request and receive the response.
  - SQLAlchemy also uses TCP to connect to your database server (`host:port` in the URI). The database server listens on a port (e.g., PostgreSQL commonly on 5432).
  - Where in code:
    - Server: `flask_app.run(debug=True)` in `run.py` (Werkzeug dev server listens on TCP).
    - Database URI in `config.py` defines the TCP host/port for the DB.
  - Analogy: Mailing a packet with tracking. TCP guarantees it gets there, in order, or it retries.

- Migration:
  - A migration is a small, versioned script that changes the database structure (schema).
  - Why: When your models change (e.g., add a column), your database tables must also change. Migrations safely apply those changes.
  - Common commands:
    ```bash
    flask db migrate -m "describe schema change"  # detect model changes and create a script
    flask db upgrade                              # run the script against the database
    ```
  - Where in code: the migration environment is set up via `Migrate(app, db)` in `app.py`. Scripts live under `migrations/versions/`.
  - Analogy: Instructions to remodel your room. Each migration is a step; applying them in order updates the room to match your new plan.

- Object (and ORM model):
  - An “object” is an instance of a class in Python. Classes define properties (attributes) and behaviors (methods). Objects are concrete examples created from those definitions.
  - ORM model classes (like `Person`) represent rows in a table. Columns are defined as attributes. The ORM turns database rows into Python objects and back.
  - Where in code: `models.py`
    ```python
    class Person(db.Model):
        __tablename__ = 'people'
        pid = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.Text, nullable=False)
        ...
    ```
    - Querying returns objects:
      ```python
      people = Person.query.all()  # list[Person]
      ```
  - Analogy: A class is the blueprint of a car model; an object is a specific car made from that blueprint.

### What happens when you run `run.py` (step-by-step)

1. `run.py` imports the factory:
   ```python
   from app import create_app
   ```
   - This loads `app.py`, which defines `db = SQLAlchemy()` and `create_app()`. Note: the database is not connected yet—`db` is just an unbound extension at this point.

2. `flask_app = create_app()`:
   - Inside `create_app()` (in `app.py`):
     - A Flask instance is created:
       ```python
       app = Flask(__name__, template_folder='templates')
       ```
     - Config is loaded:
       ```python
       app.config.from_object(Config)  # from config.py
       ```
       - This includes `SQLALCHEMY_DATABASE_URI`, which contains networking details for the DB TCP connection.
     - The SQLAlchemy extension is initialized and bound to the app:
       ```python
       db.init_app(app)
       ```
       - Now `db` knows how to connect to the database using the configured URI (when a request or context needs it).
     - Routes are registered:
       ```python
       from routes import register_routes
       register_routes(app, db)
       ```
       - The `register_routes` function attaches URL rules (HTTP endpoints) to `app`. Import happens here to avoid circular imports.
     - Migration support is set up:
       ```python
       migrate = Migrate(app, db)
       ```
       - This wires Alembic to your app and SQLAlchemy metadata so `flask db ...` commands work.
     - The fully configured `app` is returned to `run.py`.

3. `if __name__ == '__main__': flask_app.run(debug=True)`:
   - The Werkzeug development server starts, binding to `127.0.0.1:5000` by default (networking: TCP listener).
   - When a client hits `GET /`, Flask routes the request to `index()` in `routes.py`.

4. Request handling (`routes.py`):
   - `index()` executes:
     ```python
     people = Person.query.all()
     ```
     - The ORM opens/uses a DB connection over TCP to run a SELECT on the `people` table.
   - The view renders `templates/index.html`:
     ```python
     return render_template('index.html', person=people)
     ```
   - Flask returns the rendered HTML to the client over the same TCP connection.

### Tips for students

- The application factory pattern is essential for clean initialization, testing, and avoiding circular imports. Keep imports that depend on the app (like `routes`) inside the factory.
- Models describe table schemas; changes to models are schema changes. Always migrate and upgrade your DB when models change.
- Treat the DB URI as a secret. Use environment variables for production.
- Understand the networking path:
  - Browser -> HTTP -> Flask server (127.0.0.1:5000 by default)
  - Flask -> SQLAlchemy -> TCP connection -> Database server

### Common commands

```bash
# Generate a new migration after changing models (schemas)
flask db migrate -m "describe schema change"

# Apply the migration to the database
flask db upgrade

# Run the development server
python run.py
```


