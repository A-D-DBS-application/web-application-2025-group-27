"""Database models (ORM) declared with SQLAlchemy.

Each ORM model class defines the table schema in the database:
- Class name represents an entity; `__tablename__` sets the table name.
- Columns declared with `db.Column` map to table columns and constraints.

Networking and DB connectivity:
- The ORM opens a TCP connection to the DB server using the configured URI.
- Queries are executed over this connection; connection pooling may be used under the hood.

Schema changes and migrations:
- When you edit a model (schema), generate and apply a migration: (just like commiting and pushing)
    flask db migrate -m "describe schema change"
    flask db upgrade
"""

from app import db


class Person(db.Model): # Person inherits form db.Model -> so know we made a database model
    """Person model mapped to the `people` table (table schema).

    Columns:
        pid (int): Primary key.
        name (str): Person's name (required).
        age (int | None): Person's age.
        job (str | None): Person's job title/role.

    Notes:
    - Query via `Person.query` (e.g., `.all()`, `.filter_by(...)`, `.get(pk)`).
    - Create and persist via `db.session.add(instance)` and `db.session.commit()`.
    """
    __tablename__ = 'people'
    pid = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.Text, nullable = False)
    age = db.Column(db.Integer)
    job = db.Column(db.Text)


    def __repr__(self):
        """Return a concise, readable representation for debugging."""
        return f'Person with name {self.name} is {self.age} years old and works as a {self.job}'