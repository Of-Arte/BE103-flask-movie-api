from flask import Flask, g, send_file, jsonify, send_from_directory, request
import sqlite3
from flasgger import Swagger
import os

DATABASE = 'movies.db'

app = Flask(__name__)
swagger = Swagger(app)

# in-memory data store
# movies = [
#     {
#         "id": 1,
#         "title": "Inception",
#         "director": "Christopher Nolan",
#         "year": 2010,
#         "watched": True
#     },
#     {
#         "id": 2,
#         "title": "The Matrix",
#         "director": "Lana Wachowski, Lilly Wachowski",
#         "year": 1999,
#         "watched": True
#     },
#     {
#         "id": 3,
#         "title": "Spider-Man: Into the Spider-Verse",
#         "director": "Peter Ramsey, Bob Persichetti, Rodney Rothman",
#         "year": 2018,
#         "watched": False
#     },
# ]

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

@app.route("/directors", methods=["GET"])
def get_all_directors():
    """
    Get all directors
    ---
    responses:
      200:
        description: A list of directors
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              name:
                type: string
    """
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, name FROM directors") # get all directors
    except sqlite3.OperationalError:
        return error_response("Internal Server Error", "The database could not retrieve this operation.", 500)

    rows = cursor.fetchall()
    directors = [dict(row) for row in rows]
    response = jsonify(directors)
    response.status_code = 200
    return response

@app.route("/directors/<int:id>/movies", methods=["GET"])
def get_movies_by_director(id):
    """
    Get all movies by director
    ---
    parameters:
      - name: id
        in: path
        type: integer
        required: true
        description: ID of the director
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
              rating:
                type: number
              director_id:
                type: integer
      404:
        description: Director not found
        schema:
          type: object
          properties:
            error:
              type: string
            message:
              type: string
    """
    db = get_db()
    cursor = db.cursor()
    try:
        cursor.execute("SELECT id, name FROM directors WHERE id = ?", (id,)) # check if director exists
        row = cursor.fetchone()
        if not row:
            return error_response("Not Found", f"Director with the given ID '{id}' not found.", 404)
        cursor.execute("SELECT id, title, year, rating, director_id FROM movies WHERE director_id = ?", (id,)) # get movies by director id
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        return error_response("Internal Server Error", "The database could not retrieve this operation.", 500)
    
    movies = [dict(row) for row in rows]
    response = jsonify(movies)
    response.status_code = 200
    return response
    
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
              rating:
                type: number
              director_id:
                type: integer
    """
    db = get_db() # get the database connection
    cursor = db.cursor()
    try:
      cursor.execute("SELECT id, title, year, rating, director_id FROM movies")
    except sqlite3.OperationalError:
      return error_response("Internal Server Error", "The database could not retrieve this operation.", 500)

    rows = cursor.fetchall()
    movies = [dict(row) for row in rows] if rows else []
    response = jsonify(movies)
    response.status_code = 200
    return response

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
            rating:
              type: number
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
    cursor = db.cursor()
    query = "SELECT id, title, year, rating, director_id FROM movies WHERE id = ?" # use ? for id parameter as a placeholder to prevent sql injection
    try:
        cursor.execute(query, (id,))
    except sqlite3.OperationalError:
        return error_response("Internal Server Error", "The database could not retrieve this operation.", 500)

    row = cursor.fetchone()
    if not row:
        return error_response("Not Found", f"Movie with id {id} was not found.", 404)

    movie = dict(row)
    response = jsonify(movie)
    response.status_code = 200
    return response

@app.route("/movies/<int:id>/full", methods=["GET"])
def get_movie_full(id):
    """
    Get a movie by ID with director name
    ---
    parameters:
      - name: id
        in: path
        type: integer
        required: true
        description: ID of the movie to retrieve
    responses:
      200:
        description: A movie object with director name
        schema:
          type: object
          properties:
            id:
              type: integer
            title:
              type: string
            year:
              type: integer
            rating:
              type: number
            director_id:
              type: integer
            director_name:
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
    db = get_db()
    cursor = db.cursor()
    query = """
        SELECT m.id, m.title, m.year, d.name AS director_name 
        FROM movies m 
        JOIN directors d ON m.director_id = d.id 
        WHERE m.id = ?
    """
    try: 
        cursor.execute(query, (id,))
    except sqlite3.OperationalError:
        return error_response("Internal Server Error", "The database could not retrieve this operation.", 500)
        
    row = cursor.fetchone()
    if not row:
        return error_response("Not Found", f"Movie with id {id} was not found.", 404)

    movie = dict(row)

    response = jsonify(movie)
    response.status_code = 200
    return response

def validate_movie(data):
    """Return a list of error messages for a movie request body (empty if valid)."""
    if not isinstance(data, dict):
        return ["Request body must be a valid JSON object."]

    errors = []

    if "title" not in data or not isinstance(data["title"], str) or not data["title"].strip(): # check if title is not in body or title is not a string or has an empty value
        errors.append("Title is required and must be a non-empty string.")

    if "year" not in data or not isinstance(data["year"], int):
        errors.append("Year is required and must be a number.")
    
    if "rating" in data:
        if not isinstance(data["rating"], (int, float)):
            errors.append("Rating must be a number.")
        elif data["rating"] < 0 or data["rating"] > 10:
            errors.append("Rating must be between 0 and 10.")

    if "director_id" not in data or not isinstance(data["director_id"], int) or not data["director_id"]:
        errors.append("Director is required and must be a valid ID.")

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
            rating:
              type: number
          required:
            - title
            - year
            - director_id
            - rating
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

    errors = validate_movie(data)

    if errors:
        return error_response("Bad Request", "; ".join(errors), 400)

    db = get_db()
    cursor = db.cursor()
    query = """
    INSERT INTO movies (title, year, rating, director_id)
    VALUES(?, ?, ?, ?)
    """

    try: 
        cursor.execute(query, (data["title"], data["year"], data["rating"], data["director_id"]))

        # Get the ID of the newly created movie
        new_id = cursor.lastrowid

        db.commit()
    except sqlite3.IntegrityError:
        return error_response("Conflict", "Movie could not be created because it conflicts with existing data or constraints.", 409)
    except sqlite3.OperationalError:
        return error_response("Internal Server Error", "The database could not retrieve this operation.", 500)
    new_movie = {
        "id": new_id,
        "title": data["title"],
        "year": data["year"],
        "rating": data["rating"],
        "director_id": data["director_id"]
    }

    response = jsonify(new_movie)
    response.status_code = 201 
    response.headers["Location"] = f"/movies/{new_id}" # set location header to the URL of the newly created movie
    return response 

@app.route("/movies/<int:id>", methods=["PATCH"]) # PATCH to replace some fields - PUT would replace the whole resource 
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
            rating:
              type: number
            director_id:
              type: integer
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
            rating:
              type: number
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

    fields = []
    values = []
    allowed_fields = ["title", "year", "rating", "director_id"]

    for field in allowed_fields:
        if field in data:
            fields.append(f"{field} = ?") # if a field exists, add it to the fields list as "field = ?"
            values.append(data[field])
    
    if not fields:
        return error_response("Bad Request", "At least one field must be provided.", 400)

    set_clause = ", ".join(fields) # convert fields list [] into a comma-separated string of "field = ?"

    db = get_db()
    cursor = db.cursor()
    query = f"UPDATE movies SET {set_clause} WHERE id = ?"
    values.append(id)  # add id to the end for the WHERE id = ?
    
    try:
        cursor.execute(query, values)
    except sqlite3.OperationalError:
        return error_response("Internal Server Error", "The database could not retrieve this operation.", 500)
    except sqlite3.IntegrityError:
        return error_response("Conflict", "Movie could not be updated because it conflicts with existing data or constraints.", 409)

    if cursor.rowcount == 0:
        return jsonify({
            "error": "Not Found",
            "message": f"Movie with id {id} not found."
        }), 404

    db.commit()

    cursor.execute("SELECT * FROM movies WHERE id = ?", (id,))
    row = cursor.fetchone()
    updated_movie = dict(row)

    response = jsonify(updated_movie)
    response.status_code = 200
    return response

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

    db = get_db()
    cursor = db.cursor()
    query = """
    DELETE FROM movies
    WHERE id = ?
    """

    try:
        cursor.execute(query, (id,))
    except sqlite3.OperationalError:
        return error_response("Internal Server Error", "The database could not retrieve this operation.", 500)

    if cursor.rowcount == 0: # if no rows were deleted, the movie was not found
        return jsonify({
            "error": "Not Found",
            "message": f"Movie with id {id} not found."
        }), 404

    db.commit()

    return "", 204 # return empty response with 204 status code


if __name__ == '__main__':
    app.run(port=5001, debug=True)