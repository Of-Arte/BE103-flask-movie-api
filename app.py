from flask import Flask, g, send_file, jsonify, send_from_directory, request
import sqlite3
from flasgger import Swagger
import os

DATABASE = 'movies.db'

app = Flask(__name__)
swagger = Swagger(app)

# in-memory data store
movies = [
    {
        "id": 1,
        "title": "Inception",
        "director": "Christopher Nolan",
        "year": 2010,
        "watched": True
    },
    {
        "id": 2,
        "title": "The Matrix",
        "director": "Lana Wachowski, Lilly Wachowski",
        "year": 1999,
        "watched": True
    },
    {
        "id": 3,
        "title": "Spider-Man: Into the Spider-Verse",
        "director": "Peter Ramsey, Bob Persichetti, Rodney Rothman",
        "year": 2018,
        "watched": False
    },
]

@app.route('/')
def home():
    return send_from_directory(
        os.path.dirname(__file__),
        'index.html'
    )

@app.route('/api')
def api_hello():
    """
    API welcome message
    ---
    responses:
      200:
        description: Welcome message
        schema:
          type: object
          properties:
            message:
              type: string
    """
    return jsonify({'message': 'Welcome to the movie API!'})

def get_db():
    if "db" not in g: # check if db is not already in the local request object
        g.db = sqlite3.connect(DATABASE) # create and store db connection
        g.db.row_factory = sqlite3.Row # allows us to access columns by name instead of index
    return g.db

@app.teardown_appcontext
def close_db(exception): # teardown is a flask decorator that runs when the request context is torn down
    db = g.pop('db', None) # pop is used to remove the db from the request global object

    if db is not None: # if db is not None, it means there is a database connection
        db.close() # close the database connection

@app.get("/db-ping")
def db_ping():
    """
    Check the SQLite database connection
    ---
    responses:
      200:
        description: Database is reachable
        schema:
          type: object
          properties:
            ok:
              type: boolean
            value:
              type: integer
    """
    db = get_db()         # open (or reuse) the connection for this request
    cursor = db.cursor()   # just to prove we can talk to SQLite
    cursor.execute("SELECT 1")  # simple throwaway query
    row = cursor.fetchone()
    return jsonify({"ok": True, "value": row[0]})

@app.route("/movies", methods=["GET"])
def get_all_movies():
    """
    Get all movies
    ---
    responses:
      200:
        description: A list of movies
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              title:
                type: string
              year:
                type: integer
              director_id:
                type: integer
    """
    db = get_db() # get the database connection
    cursor = db.execute("SELECT id, title, year, director_id FROM movies")
    rows = cursor.fetchall()

    movies_db = [dict(row) for row in rows]  # sqlite3.Row -> dict

    return jsonify(movies_db), 200


@app.route("/movies/<int:id>", methods=["GET"])
def get_movie(id):
    """
    Get a movie by ID
    ---
    parameters:
      - name: id
        in: path
        type: integer
        required: true
        description: ID of the movie to retrieve
    responses:
      200:
        description: A movie object
        schema:
          type: object
          properties:
            id:
              type: integer
            title:
              type: string
            year:
              type: integer
            director_id:
              type: integer
      404:
        description: Movie not found
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
    """
    db = get_db() # get the database connection
    query = "SELECT id, title, year, director_id FROM movies WHERE id = ?" # use ? for id parameter as a placeholder to prevent sql injection
    cursor = db.execute(query, (id,))
    row = cursor.fetchone()
    if row:
        movie = dict(row)
    else:
        movie = None

    if movie is None:
        return jsonify({
            "error": "Not Found",
            "message": f"Movie with id {id} was not found."
        }), 404
    
    return jsonify(movie), 200

@app.route("/movies/<int:id>", methods=["PUT"])
def update_movie(id):
    """
    Update a movie by ID
    ---
    parameters:
      - name: id
        in: path
        type: integer
        required: true
        description: ID of the movie to update
      - in: body
        name: movie
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
            year:
              type: integer
            director_id:
              type: integer
          required:
            - title
            - year
            - director_id
    responses:
      200:
        description: Movie updated
        schema:
          type: object
          properties:
            id:
              type: integer
            title:
              type: string
            year:
              type: integer
            director_id:
              type: integer
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
      404:
        description: Movie not found
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
    """

    data = request.get_json(silent=True)

    errors = validate_movie(data)

    if errors:
        return error_response("Bad Request", "; ".join(errors), 400)

    # find the movie index by id
    index = next((i for i, m in enumerate(movies) if m["id"] == id), None)

    if index is None: # check if movie was found, for idempotency, means if the same request is sent multiple times, the response will be the same
        return jsonify({
            "error": "Not Found",
            "message": f"Movie with id {id} not found."
        }), 404

    updated_movie = {
        "id": id,  # keep the same id from the URL
        "title": data["title"],
        "director": data["director"],
        "year": data["year"],
        "watched": data["watched"],
    }

    movies[index] = updated_movie

    return jsonify(updated_movie), 200

def validate_movie(data):
    """Return a list of error messages for a movie request body (empty if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a valid JSON object."]

    errors = []

    if "title" not in data or not isinstance(data["title"], str) or not data["title"].strip(): # check if title is not in body or title is not a string or has an empty value
        errors.append("Title is required and must be a non-empty string.")

    if "director" not in data or not isinstance(data["director"], str) or not data["director"].strip():
        errors.append("Director is required and must be a non-empty string.")

    if "year" not in data or not isinstance(data["year"], int):
        errors.append("Year is required and must be a number.")

    if "watched" not in data or not isinstance(data["watched"], bool):
        errors.append("Watched is required and must be true or false.")

    return errors


def error_response(error, message, status):
    """Build the standard JSON error response."""
    return jsonify({"error": error, "message": message}), status


@app.route("/movies", methods=["POST"])
def create_movie():
    """
    Create a new movie
    ---
    parameters:
      - in: body
        name: movie
        required: true
        schema:
          type: object
          properties:
            title:
              type: string
            year:
              type: integer
            director_id:
              type: integer
          required:
            - title
            - year
            - director_id
    responses:
      201:
        description: Movie created
        schema:
          type: object
          properties:
            id:
              type: integer
            title:
              type: string
            year:
              type: integer
            director_id:
              type: integer
      400:
        description: Bad request
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
    """

    data = request.get_json(silent=True)  # parses the JSON body into a Python dict (None if invalid)

    # 1) Work out the next id on the server
    if movies:
        next_id = max(m["id"] for m in movies) + 1 # finds the largest existing ID and adds 1
    else:
        next_id = 1 # if no movies, starts at 1

    errors = validate_movie(data)

    if errors:
        return error_response("Bad Request", "; ".join(errors), 400)

    # declare new movie definition
    new_movie = {
        "id": next_id,
        "title": data["title"],
        "director": data["director"],
        "year": data["year"],
        "watched": data["watched"],
    }

    movies.append(new_movie) # add to the in memory list

    return jsonify(new_movie), 201 # return created movie and 201 (CREATED)

@app.route("/movies/<int:id>", methods=["DELETE"])
def delete_movie(id):
    """
    Delete a movie by ID
    ---
    parameters:
      - name: id
        in: path
        type: integer
        required: true
        description: ID of the movie to delete
    responses:
      204:
        description: Movie deleted (no content)
      404:
        description: Movie not found
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
    """

    # find movie
    index = next((i for i, m in enumerate(movies) if m["id"] == id), None)

    # check if movie was found
    if index is None:
        return jsonify({
            "error": "Not Found",
            "message": f"Movie with id {id} not found."
        }), 404

    del movies[index]

    # return empty response with 204 status code
    return "", 204


if __name__ == '__main__':
    app.run(port=5001, debug=True)