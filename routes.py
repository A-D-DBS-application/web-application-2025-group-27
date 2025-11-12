"""HTTP route registration and view functions.

Defines `register_routes(app, db)` that attaches routes to the provided Flask `app`.
Views use SQLAlchemy ORM models (table schemas) to query the database and render
Jinja2 templates via `render_template`.

Networking terminology:
- A route defines an HTTP endpoint (URL path) that clients call.
- The server listens on a host/IP and port; requests arrive over TCP, responses are sent back over the same connection.

Key concepts:
- `@app.route('/')` registers a URL rule for a view.
- `GET /`: `Person.query.all()` uses the ORM to fetch all rows from the `people` table via the DB network connection.
- `POST /`: reads form fields (`name`, `age`, `job`), creates a `Person`, commits via `db.session`.
- `render_template('index.html', people=people)` passes the list to the template under the `people` key.

Server-side validation vs client-side validation:
- The HTML `required` attribute (client-side) can be bypassed (old browsers, JS disabled, API clients).
- We still validate on the server (e.g., missing/invalid `pid`) to guarantee correctness and return clear errors.

Flash messages and POST/Redirect/GET pattern:
- This app uses Flask's `flash()` system for user feedback (success/error messages).
- Flash messages are stored in the session and survive redirects, making them ideal for the POST/Redirect/GET pattern.
- Why POST/Redirect/GET? After a POST (create/delete), we redirect to GET instead of re-rendering the template directly.
  This prevents duplicate submissions if the user refreshes (they refresh the GET, not the POST) and provides cleaner URLs.
- Why `people=[]` is no longer needed on POST errors:
  - Previously: On POST errors, we re-rendered the template immediately with `render_template('index.html', people=people, error=...)`.
    This required manually querying `people` even on errors, or passing `people=[]` as a fallback.
  - Now: On POST errors, we call `flash('error message')` and `redirect(url_for('index'))`.
    The redirect triggers a fresh GET request, which runs the normal GET handler that queries `people` from the database.
    Flash messages are automatically displayed by the base template, so we don't need to pass an `error` context variable.
  - Result: Cleaner separation of concerns (GET handles display, POST handles mutations), and we avoid duplicating the `people` query logic.

Schema changes:
- If you modify models (table schemas), remember to migrate:
    flask db migrate -m "describe schema change"
    flask db upgrade
"""

from flask import render_template, request, redirect, url_for, flash
from models import Person


def register_routes(app, db):
    """Register all URL routes on the given Flask application.

    Args:
        app (Flask): The Flask application instance to attach routes to.
        db (SQLAlchemy): The SQLAlchemy instance (not directly used here, useful for future use).
    """
    @app.route('/', methods=['GET', 'POST']) 
    def index():
        """Homepage that lists all people and accepts new entries.

        Detailed flow:
        - GET:
            1) Query all people via the ORM: `Person.query.all()`.
            2) If the query fails (e.g., DB down), flash an error message and render the page
               with `people=[]` so the template still works while surfacing the failure.
        - POST:
            1) Read form inputs `name`, `age`, `job` and coerce `age` (empty -> None).
            2) Create a `Person` instance via attribute assignment (works around driver named-parameter quirks).
            3) Validate `name`; if missing, flash and redirect (no manual re-render).
            4) Add+commit inside try/except; on failure, rollback, flash, and redirect.
            5) On success, flash a success message and redirect (POST/Redirect/GET).

        Error handling rationale:
        - Flash messages survive redirects and keep the controller slim; the template
          only needs the `people` list.
        - The only direct render after an error happens during GET when no data is available;
          returning `people=[]` keeps the template stable.

        Returns:
            Response: The rendered HTML page.
        """
        
        if request.method == 'GET':
            try:
                people = Person.query.all()
                return render_template('index.html', people=people)
            except Exception:
                # If the DB is temporarily unavailable or query fails, flash and render an empty list
                flash('Failed to load people from the database', 'error')
                return render_template('index.html', people=[]), 500
        
        elif request.method == 'POST': # dus als je uw form submit gaat uw browser een post request sturen naar de '/' url
            name = request.form.get('name')
            age_str = request.form.get('age')
            age = int(age_str) if age_str else None
            job = request.form.get('job')

            person = Person()
            person.name = name
            person.age = age
            person.job = job

            # same as:
            # person = Person(name=name, age=age, job=job) but the method above avoids the driver's name-paramater isssue

            # Basic server-side validation (defense-in-depth vs client-side 'required')
            if not person.name or person.name.strip() == '':
                flash('Name is required', 'error')
                return redirect(url_for('index')), 400

            try:
                db.session.add(person)
                db.session.commit()
            except Exception:
                db.session.rollback()
                flash('Failed to create person due to a database error', 'error')
                return redirect(url_for('index')), 500

            flash('Person created', 'success')
            return redirect(url_for('index'))

    @app.route('/delete', methods=['POST'])
    def delete():
        """Delete a person by their primary key (pid) provided via form data.

        Detailed flow and validation:
        - The HTML form sends `pid` using method POST (HTML doesn't support DELETE forms).
        - Server-side validation:
            * If `pid` is missing/invalid, flash an error and redirect back to index (client-side `required` is not enough).
            * If no `Person` exists, flash an error and redirect (404).
        - On success:
            * Delete, commit, flash a success message, and redirect to index.
            * If a DB error occurs, rollback, flash an error, and redirect (500).
        """
        pid_str = request.form.get('pid')
        if not pid_str:
            flash('Missing pid', 'error')
            return redirect(url_for('index')), 400
        try:
            pid = int(pid_str)
        except ValueError:
            flash('Invalid pid', 'error')
            return redirect(url_for('index')), 400
        # Look up without auto-404 so we can show a friendly message
        person = Person.query.get(pid)
        if person is None:
            flash(f'Person with pid {pid} not found', 'error')
            return redirect(url_for('index')), 404
        try:
            db.session.delete(person)
            db.session.commit()
        except Exception: # Exception is the base class for all exceptions -> so this will catch all exceptions
            db.session.rollback() # rollback the transaction -> so the database is not modified
            flash('Failed to delete person due to a server error', 'error')
            return redirect(url_for('index')), 500
        flash('Person deleted', 'success') # this flash message gets stored in the session and will be displayed in the base.html template
        return redirect(url_for('index')) # redirect to the home page, this then will show the flash message and the updated list of people

    @app.route('/details/<pid>', methods=['GET'])
    def details(pid): # the pid stored in url as a variable you can access directly
        """Display details of a person by their primary key (pid) provided via query parameter.

        Detailed flow and validation:
        - The HTML form sends `pid` using method GET (HTML doesn't support DELETE forms).
        - Server-side validation:
            * If `pid` is missing/invalid, flash an error and redirect back to index (client-side `required` is not enough).
            * If no `Person` exists, flash an error and redirect (404).

        Route: /details/<pid>
        Method: GET
        Using GET only: data is passed in the URL (via <a href>), not through a form submission, so POST isn't needed.
        Only GET is needed because the page is accessed via a hyperlink (<a href="/details/...">), not a form submit. The PID comes from the URL path itself, so no POST data is sent.
        Explanation:
        Using GET (via URL) is better than POST in this case because:
        - The data (person ID) is not sensitive and safe to appear in the URL.
        - The route only retrieves and displays information — it does not modify server data.
        - GET requests can be bookmarked, shared, and reloaded easily, improving usability.
        - This route is typically accessed through a hyperlink (<a href="...">), not a form submission,
        so no POST request is needed.
        """
        person = Person.query.get(pid)
        return render_template('details.html', person=person)