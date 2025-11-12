## End-to-end flow: What happens when you run `run.py`

This is a precise, step-by-step walkthrough of everything that happens from the moment you execute `python run.py` until a request is handled and a response is returned. It references code in this folder:
- `run.py`
- `app.py`
- `config.py`
- `routes.py`
- `models.py`

The goal is to expose each moving part so a new developer can follow the entire lifecycle clearly.

---

### A. Process start and module import resolution

1) You type:
   ```bash
   python run.py
   ```
2) Python starts a new interpreter process and attempts to import the top-level module specified: `run.py`.
3) Python compiles `run.py` to bytecode (if needed) and begins executing it top-to-bottom.
4) The first line executes:
   ```python
   from app import create_app
   ```
   - Python looks for a module named `app` in the same directory (per `sys.path` resolution).
   - It finds `6_databases_sqlalchemy/app.py` and imports it.
5) While importing `app.py`, Python executes that file top-to-bottom. Inside `app.py`, module-level statements run:
   - Imports:
     ```python
     from flask import Flask
     from flask_sqlalchemy import SQLAlchemy
     from flask_migrate import Migrate
     from config import Config
     ```
   - These trigger Python to import `flask`, `flask_sqlalchemy`, `flask_migrate`, and then `config.py`.
6) Python imports `config.py` and executes it:
   - Defines class `Config` with `SECRET_KEY`, `SQLALCHEMY_DATABASE_URI`, and `SQLALCHEMY_TRACK_MODIFICATIONS`.
   - Returns control to `app.py`.
7) Back in `app.py`, the module-level line executes:
   ```python
   db = SQLAlchemy()
   ```
   - This creates an unbound SQLAlchemy extension object.
   - Important: It is not yet connected to any Flask app or database.
8) Still in `app.py`, Python now “knows” there is a `create_app` function, but it hasn’t been called yet.
9) Python finishes importing `app.py`. The `app` module (i.e., `app.py`) is now cached in `sys.modules`, so future imports reuse it.

---

### B. Creating the Flask app via the factory

10) Control returns to `run.py`. Next line executes:
    ```python
    flask_app = create_app()
    ```
    - This calls the factory function defined in `app.py`.
11) Inside `create_app()` (`app.py`):
    ```python
    app = Flask(__name__, template_folder='templates')
    ```
    - A new Flask application instance is created.
    - `__name__` helps Flask locate resources; `template_folder` points Jinja2 to `templates/`.
12) Still in `create_app()`, we load configuration:
    ```python
    app.config.from_object(Config)
    ```
    - Flask reads attributes from `Config` (from `config.py`) and stores them in `app.config`.
    - Key values include:
      - `SECRET_KEY`: used for session/CSRF signing.
      - `SQLALCHEMY_DATABASE_URI`: database connection string (includes host and port used over TCP).
      - `SQLALCHEMY_TRACK_MODIFICATIONS`: disabled for performance.
13) We bind the SQLAlchemy extension to this app:
    ```python
    db.init_app(app)
    ```
    - What this actually does:
      - Attaches Flask-SQLAlchemy to the Flask app instance so the extension can access `app.config`, logging, and application context.
      - Lazily configures a SQLAlchemy “Engine” factory based on `SQLALCHEMY_DATABASE_URI`. The Engine manages DB connections (TCP sockets) and pooling. The actual Engine is typically created on first use.
      - Prepares a scoped session (thread-/context-local) so each request gets its own session that is cleaned up after the request.
      - Registers teardown handlers to remove/rollback sessions at the end of a request or app context to prevent leaks.
14) We register routes by importing a function locally (to avoid circular imports) and invoking it:
    ```python
    from routes import register_routes
    register_routes(app, db)
    ```
    - This import brings in `routes.py`. Python executes it top-to-bottom, defining `register_routes`.
    - `register_routes` attaches URL rules to `app` (e.g., `@app.route('/')` for the homepage).
15) We set up migrations:
    ```python
    migrate = Migrate(app, db)
    ```
    - What this actually does (concrete details):
      - Integrates Alembic (the migration engine) with Flask and SQLAlchemy.
      - Binds your SQLAlchemy “MetaData” (table and column definitions behind your models) to Alembic’s environment so migrations can inspect schemas.
      - Ensures the `flask` CLI gains migration subcommands (e.g., `flask db migrate`, `flask db upgrade`) via Flask-Migrate’s click commands.
      - Points Alembic to the `migrations/` directory (created by `flask db init` originally), which contains:
        - `env.py`: Orchestrates how Alembic connects to the DB and loads target metadata (your models’ metadata).
        - `script.py.mako`: Template for new migration files.
        - `versions/`: Versioned migration scripts with `upgrade()`/`downgrade()` functions.
      - When you run `flask db migrate`:
        1. Flask CLI creates an application context so extensions (including `db`) can load config.
        2. Alembic loads `env.py` which pulls the SQLAlchemy URL from config and the target metadata from `db`.
        3. Autogenerate compares the current model metadata to the DB schema (or to the last migration) and produces a diff.
        4. A new migration script is created under `migrations/versions/` with Python code describing the DDL to apply (e.g., `op.add_column`, `op.create_table`).
      - When you run `flask db upgrade`:
        1. Alembic connects to the DB, reads the current revision from the `alembic_version` table.
        2. It runs pending `upgrade()` functions in order to bring the schema up to date.
        3. If any step fails, the process stops so you can fix it (atomic-ish behavior per step).
16) `create_app()` returns the fully configured `app` object to `run.py`.

---

### C. Starting the development server (network listener)

17) Back in `run.py`, we hit:
    ```python
    if __name__ == '__main__':
        flask_app.run(debug=True)
    ```
18) Since this is the main module execution, the condition is true. Flask starts the Werkzeug development server.
19) The dev server binds a TCP socket to `127.0.0.1:5000` (by default).
    - “Binds” means it opens a listening socket at that IP/port and waits for incoming connections.
20) The server configures a WSGI app entrypoint internally (your Flask app conforms to WSGI: a callable taking `environ` and `start_response`).
21) The server enters an event loop, accepting incoming HTTP requests over TCP and dispatching them to Flask.
22) With `debug=True`, the reloader may monitor files; if code changes, it restarts the process to pick up changes.

---

### D. Handling the first HTTP request (routing and view execution)

Assume a browser navigates to `http://127.0.0.1:5000/`.

23) The browser creates a TCP connection to `127.0.0.1` on port `5000`.
24) It sends an HTTP GET request for path `/` (includes HTTP headers and possibly cookies).
25) The Werkzeug server accepts the connection and reads the request bytes from the socket.
26) Werkzeug parses the HTTP request, builds a WSGI `environ` dict (method, path, headers, query string, etc.).
27) Werkzeug calls your Flask app WSGI callable with `environ` and `start_response`.
28) Flask creates an application context and request context:
    - Application context exposes `current_app`.
    - Request context exposes `request`, `session`, etc.
29) Flask’s routing system matches the URL path `/` to a view function registered in `routes.py`:
    ```python
    @app.route('/')
    def index():
        ...
    ```
30) Flask calls the view function `index()` in `routes.py`.
31) Inside `index()`, we query the ORM:
    ```python
    people = Person.query.all()
    ```
    - `Person` is an ORM model class from `models.py`.
    - Flask-SQLAlchemy provides `Model.query`, which is a query object bound to the current scoped session.
    - SQLAlchemy compiles a `SELECT * FROM people` statement appropriate for the DB dialect (PostgreSQL here).
32) If the SQLAlchemy Engine (connection pool) is not initialized yet, it is created now using `SQLALCHEMY_DATABASE_URI`.
33) The Engine opens a TCP connection from the pool to the DB server (or borrows one if available):
    - Resolves `host` and `port` from the URI (e.g., `aws-1-eu-north-1.pooler.supabase.com:6543`).
    - Authenticates with `user` and `password`.
    - Optionally negotiates TLS if configured.
34) SQLAlchemy sends the compiled SQL to the database over the TCP connection.
35) The database executes the query, streams rows back over TCP.
36) SQLAlchemy constructs `Person` instances for each row (ORM identity map ensures one Python object per row identity within the session).
37) `index()` then renders the template:
    ```python
    return render_template('index.html', person=people)
    ```
38) Jinja2 locates `templates/index.html` (relative to `template_folder` in `Flask(__name__, template_folder='templates')`).
39) Jinja2 compiles the template to bytecode (cached) and renders it using the provided context: `person=people`.
40) The rendered template (a string of HTML) is returned to Flask.
41) Flask constructs a `Response` object with body, status code (default 200), and headers (e.g., `Content-Type: text/html; charset=utf-8`).
42) Flask returns the `Response` to Werkzeug.
43) Werkzeug serializes the response and writes it to the TCP socket back to the client.
44) The browser receives the bytes, interprets HTTP headers, and renders HTML.

---

### E. Teardown, connection management, and next requests

45) After the response is returned, Flask triggers teardown handlers:
    - The scoped session is removed; pending transactions are committed or rolled back as configured.
    - Request and application contexts are popped, releasing memory and locals.
46) SQLAlchemy keeps the DB connection in the pool (idle) for reuse; pool size and recycle settings are configurable.
47) If another request arrives, steps 23–44 repeat. Reusing pooled connections reduces latency.
48) If you change models and run:
    ```bash
    flask db migrate -m "describe schema change"
    flask db upgrade
    ```
    - Migrate details (deeper):
      - `flask db migrate`: Under an app context, Alembic’s env loads your models’ metadata (from `db`) and compares it to the current DB schema or previous migration state. It generates a Python migration script in `migrations/versions/` with `upgrade()` (DDL to apply) and `downgrade()` (DDL to revert).
      - `flask db upgrade`: Connects to the DB, checks `alembic_version` table for current revision, and sequentially executes `upgrade()` functions of pending scripts. On success, updates `alembic_version`.
49) If you change routes/templates, the dev server’s reloader notices file changes and restarts the process; new requests use updated code.
50) If you use the Flask CLI directly (e.g., `flask run`, `flask db migrate`), Flask locates your app by:
    - Using `FLASK_APP=run.py` (or a module path) so it can import `create_app()` or the `app` object.
    - Creating an app context so extensions (`db`, `Migrate`) can access configuration and metadata.

---

### F. Where each responsibility lives (mental map)

- App creation and wiring: `app.py` (`create_app()`, `db.init_app(app)`, `Migrate(app, db)`, and `register_routes(...)`).
- Configuration: `config.py` (contains DB URI and other settings).
- HTTP endpoints: `routes.py` (uses models, calls templates).
- Data layer (schema and ORM models): `models.py` (classes mapped to tables).
- Entry point and server start: `run.py` (imports factory, starts dev server).

---

### G. Key terms (quick glossary)

- Factory function: A function that builds and returns a fully initialized object (here, the Flask app). See `create_app()` in `app.py`.
- Extension: A plugin that adds functionality to Flask (e.g., SQLAlchemy, Migrate). Created unbound, then initialized with `init_app(app)`.
- TCP: Reliable transport protocol used for HTTP and the DB connection. Server listens on an IP/port; clients connect and exchange data.
- Migration: A versioned script that changes the database schema to match model changes (`flask db migrate`, `flask db upgrade`).
- Object/Model instance: A Python instance representing a database row (e.g., `Person` objects from `Person.query.all()`).

---

### H. Plain-language explanations and analogies (read this if the terms feel abstract)

- Lazy Engine creation:
  - Plain: Don’t build the heavy database machinery until the moment you actually need to talk to the DB.
  - Analogy: Don’t start your car engine until you’re ready to drive.

- Scoped session:
  - Plain: Each web request gets its own “work folder” (a session) for DB operations so they don’t mix with other requests.
  - Analogy: Students in a classroom each have their own notebook; no one writes in someone else’s notebook.

- Teardown behavior:
  - Plain: After a request finishes, Flask-SQLAlchemy cleans up the “work folder” (session) so nothing leaks into the next request.
  - Analogy: At the end of class, students close their notebooks and put them away.

- Alembic env:
  - Plain: The migration “workshop setup” files that tell Alembic how to find your models and connect to your DB.
  - Analogy: The workshop manual that explains where the tools are and how to use them for building.

- CLI commands:
  - Plain: Terminal shortcuts (like `flask db migrate`) that let you ask the app to generate/apply schema changes.
  - Analogy: Buttons on a control panel that perform standard tasks for you.

- Versions folder:
  - Plain: A folder where Alembic stores step-by-step scripts describing how your database structure changed over time.
  - Analogy: A photo album of your room remodel—each photo shows one change (new shelf, new paint, etc.).

- WSGI callable:
  - Plain: A standard “function-like” interface that web servers use to talk to your Flask app.
  - Analogy: A universal plug shape so any charger (server) can connect to your device (app).

- Event loop:
  - Plain: The server’s “listener” that waits for new connections, handles them one by one (or concurrently), and repeats forever.
  - Analogy: A receptionist who continuously picks up the phone each time it rings.

- Reloader:
  - Plain: In debug mode, a helper that restarts your app when files change so you see updates without manual restarts.
  - Analogy: A stage crew that swaps in a new script the moment the playwright edits a line.

- WSGI environ:
  - Plain: A big dictionary with all request details (method, path, headers, query) passed from the server to your app.
  - Analogy: A package of paperwork that comes with every phone call—caller ID, purpose, notes.

- Context creation (application/request context):
  - Plain: Temporary “shortcuts” that let your code access `current_app`, `request`, and DB session without passing them around.
  - Analogy: Putting a folder on your desk for the current task so you can grab documents quickly.

- Query compilation:
  - Plain: SQLAlchemy turns your Python query (e.g., `Person.query.all()`) into real SQL that the database understands.
  - Analogy: Translating your order into the exact words the kitchen needs to cook the dish.

- Engine/pool creation:
  - Plain: The Engine opens and manages database connections; the pool keeps some open for reuse to be faster.
  - Analogy: A taxi stand with cars waiting; you grab one instead of calling a new taxi each time.

- TCP connect/auth:
  - Plain: Open a network connection to the database’s host/port and log in with username/password.
  - Analogy: Dial a phone number and speak a password to get through the gate.

- Result mapping (ORM identity map):
  - Plain: SQLAlchemy turns database rows into `Person` objects and ensures you get the same Python object for the same row during a session.
  - Analogy: If you already met Alex today, you don’t create a “new Alex”—you recognize and refer to the same person.

- Jinja compilation/cache:
  - Plain: The template file is converted to fast code the first time, then reused for speed; variables fill in the blanks.
  - Analogy: Preheating an oven once, then quickly baking multiple trays.

- Response assembly:
  - Plain: Flask wraps your rendered HTML (or JSON) with status code and headers into a Response object.
  - Analogy: Packing a gift (content) into a box (headers + status) before mailing.

- Socket write:
  - Plain: The server sends the response bytes back to the browser over the same network connection.
  - Analogy: Speaking your answer back through the same phone call.


