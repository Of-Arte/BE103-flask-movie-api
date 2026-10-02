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
        "watched": True,
        "reviews": []
    },
    {
        "id": 2,
        "title": "The Matrix",
        "director": "Lana Wachowski, Lilly Wachowski",
        "year": 1999,
        "watched": True,
        "reviews": []
    },
    {
        "id": 3,
        "title": "Spider-Man: Into the Spider-Verse",
        "director": "Peter Ramsey, Bob Persichetti, Rodney Rothman",
        "year": 2018,
        "watched": False,
        "reviews": []
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
    db = get_db()          # open (or reuse) the connection for this request
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
    """
    
    return jsonify(movies)


@app.route("/movies/<int:id>", methods=["GET"])
def get_movie(id):
    """
    Get a movie by ID
    ---
    responses:
        200:
            description: A movie object
        404:
            description: Movie not found
    """
    movie = next((m for m in movies if m["id"] == id), None)
    
    if movie is None:
        return jsonify({
            "error": "Not Found",
            "message": f"Movie with id {id} was not found."
        }), 404
    
    return jsonify(movie)

@app.route("/movies/<int:id>", methods=["PUT"])
def update_movie(id):
    """
    Update a movie by ID
    ---
    responses:
        200:
            description: A movie object
        400:
            description: Bad request
        404:
            description: Movie not found
    """

    data = request.get_json()

    errors = []

    if "title" not in data or not isinstance(data["title"], str) or not data["title"].strip():
        errors.append("Title is required and must be a non-empty string.")

    if "director" not in data or not isinstance(data["director"], str) or not data["director"].strip():
        errors.append("Director is required and must be a non-empty string.")

    if "year" not in data or not isinstance(data["year"], int):
        errors.append("Year is required and must be a number.")

    if "watched" not in data or not isinstance(data["watched"], bool):
        errors.append("Watched is required and must be true or false.")

    if errors:
        return jsonify({
            "error": "Bad Request",
            "message": "; ".join(errors)
        }), 400

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

@app.route("/movies", methods=["POST"])
def create_movie():
    """
    Create a new movie
    ---
    responses:
        201:
            description: A movie object
        400:
            description: Bad request
    """

    data = request.get_json()  # parses the JSON body into a Python dict
    
    # 1) Work out the next id on the server
    if movies:
        next_id = max(m["id"] for m in movies) + 1 # finds the largest existing ID and adds 1
    else:
        next_id = 1 # if no movies, starts at 1

    errors = []

    if "title" not in data or not isinstance(data["title"], str) or not data["title"].strip(): # check if title is not in body or title is not a string or has an empty value
        errors.append("Title is required and must be a non-empty string.")

    if "director" not in data or not isinstance(data["director"], str) or not data["director"].strip():
        errors.append("Director is required and must be a non-empty string.")

    if "year" not in data or not isinstance(data["year"], int):
        errors.append("Year is required and must be a number.")

    if "watched" not in data or not isinstance(data["watched"], bool):
        errors.append("Watched is required and must be true or false.")

    if errors:
        return jsonify({
            "error": "Bad Request",
            "message": "; ".join(errors)
        }), 400

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
    responses:
        204:
            description: A movie object
        404:
            description: Movie not found
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

def find_movie(movie_id):
    return next((m for m in movies if m["id"] == movie_id), None)


@app.route("/movies/<int:movie_id>/reviews", methods=["POST"])
def add_review(movie_id):
    """
    Add a review to a movie
    ---
    parameters:
      - name: movie_id
        in: path
        type: integer
        required: true
        description: ID of the movie to review
      - in: body
        name: review
        required: true
        schema:
          type: object
          properties:
            author:
              type: string
            rating:
              type: integer
            comment:
              type: string
          required:
            - author
            - rating
            - comment
    responses:
      201:
        description: Review created
        schema:
          type: object
          properties:
            id:
              type: integer
            author:
              type: string
            rating:
              type: integer
            comment:
              type: string
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
    # 1. Find movie or 404
    movie = find_movie(movie_id)
    if movie is None:
        return (
            jsonify({
                "error": "Not Found",
                "message": f"Movie with id {movie_id} not found"
            }),
            404,
        )

    # 2. Parse JSON body safely
    data = request.get_json(silent=True)
    if data is None:
        return (
            jsonify({
                "error": "Bad Request",
                "message": "Request body must be valid JSON"
            }),
            400,
        )

    author = data.get("author")
    rating = data.get("rating")
    comment = data.get("comment")

    # 3. Presence validation
    if author is None:
        return (
            jsonify({
                "error": "Bad Request",
                "message": "author is required"
            }),
            400,
        )
    if rating is None:
        return (
            jsonify({
                "error": "Bad Request",
                "message": "rating is required"
            }),
            400,
        )
    if comment is None:
        return (
            jsonify({
                "error": "Bad Request",
                "message": "comment is required"
            }),
            400,
        )

    # 4. Type validation
    if not isinstance(author, str):
        return (
            jsonify({
                "error": "Bad Request",
                "message": "author must be a string"
            }),
            400,
        )
    if not isinstance(rating, (int, float)):
        return (
            jsonify({
                "error": "Bad Request",
                "message": "rating must be a number"
            }),
            400,
        )
    if not isinstance(comment, str):
        return (
            jsonify({
                "error": "Bad Request",
                "message": "comment must be a string"
            }),
            400,
        )

    # 5. Create new review id
    existing_reviews = movie["reviews"]
    new_id = (max((r["id"] for r in existing_reviews), default=0) + 1)

    new_review = {
        "id": new_id,
        "author": author,
        "rating": rating,
        "comment": comment,
    }

    # 6. Append and return 201 with review
    movie["reviews"].append(new_review)

    return jsonify(new_review), 201


if __name__ == '__main__':
    app.run(port=5001, debug=True)