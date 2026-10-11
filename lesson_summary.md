# Connect SQLite inside a Flask app

### 1. Minimal Flask API with JSON hello

I added `/api` that returns:
```json
{"message": "Movies API"}
```
This is my simple "is the backend up?" check.

### 2. Per-request SQLite connection with `get_db()`

I wrote a `get_db()` function that:
- Uses `sqlite3.connect("movies.db")` to create a connection.
- Stores it on Flask’s `g` as `g.db`.
- Only creates it when a request actually needs it (lazy creation).
- `g` is request-local, not a true global: each request gets its own `g`.

So for a request that calls `get_db()`:
- The connection is created during the view function.
- It’s stored on `g.db` for that request.

### 3. Cleanup with `@app.teardown_appcontext`

I added:

```python
@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()
```

After each request’s app context ends, Flask calls `close_db()`.
It removes `db` from `g` and closes the connection if it exists.
Cleanup happens even if the request handler raised an exception.

### 4. Using the connection in a route

I created `/db-ping`:

```python
@app.get("/db-ping")
def db_ping():
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT 1")
    row = cursor.fetchone()
    return jsonify({"ok": True, "value": row[0]})
```

This proves the pattern works end-to-end:
- `get_db()` creates/gets the connection for this request.
- The route runs a simple query.
- `close_db()` cleans up afterward.

I saw:
```json
{"ok": true, "value": 1}
```

### 5. Why global connections are unsafe

A design like:

```python
conn = sqlite3.connect("movies.db")  # global

@app.get("/bad")
def bad():
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    return jsonify({"ok": True})
```

is dangerous because:
- Every request shares the same `conn`.
- In the default threaded Flask dev server, multiple requests can run in different threads.
- SQLite connections are not safely shared across threads:
  - The connection is bound to the thread that created it.
  - Other threads using it can cause errors and weird behavior.

## Serve GETs from SQLite

Here’s the core of what I completed in this lesson 👇

### 1. `GET /movies` now reads from SQLite

I replaced the in-memory list with a query:

```sql
SELECT id, title, year, director_id FROM movies;
```

In the route, I:
- Used `get_db()` to get a per-request connection.
- Ran `db.execute()`.
- Turned each `sqlite3.Row` into a dict (`[dict(row) for row in rows]`).
- Returned a JSON list (possibly empty) with status 200.

### 2. `GET /movies/<id>` uses a parameterized lookup + 404

I queried by ID using a parameterized `SELECT`:

```sql
SELECT id, title, year, director_id FROM movies WHERE id = ?;
```

In the route, I:
- Called `fetchone()`.
- If no row was found: returned a JSON 404 response: `{"error": "Not Found", "message": "Movie with id X was not found."}`.
- If found: converted the row to a dict and returned it as JSON with status 200.

### 3. `GET /movies/<id>/full` joins movies and directors

I created a joined endpoint that returns movie + director together, using:

```sql
SELECT
  movies.id,
  movies.title,
  movies.year,
  directors.id   AS director_id,
  directors.name AS director_name
FROM movies
INNER JOIN directors
  ON movies.director_id = directors.id
WHERE movies.id = ?;
```

Used `fetchone()` + 404 on missing, returning a JSON object on success.

### 4. Proved persistence across restarts

I called an endpoint (e.g., `/movies/2` or `/movies/2/full`) and verified valid data was returned:
- Stopped the Flask server, restarted it, and called the same endpoint.
- Got the same data back, proving that data now lives in `movies.db` on disk.
- The app uses a per-request SQLite connection instead of recreating an in-memory list on each run.
## Create rows with POST

Here is what my `POST /movies` endpoint does now:

### 1. Parse & validate JSON
- Uses `request.get_json(silent=True)`.
- Runs `validate_movie(data)`.
- If missing/invalid fields (like invalid title or year), returns:
  - **Status:** `400 Bad Request`
  - **Body:** JSON with `error` and `message`

### 2. Insert into SQLite with parameters
- Gets a database connection via `get_db()`.
- Runs:
  ```sql
  INSERT INTO movies (title, year, rating, director_id)
  VALUES (?, ?, ?, ?);
  ```
  with a Python tuple of values (avoiding string formatting to prevent SQL injection).

### 3. Commit the transaction
- Calls `db.commit()` so the new movie row is saved to disk and visible in subsequent `GET` requests.

### 4. Return info about the created movie
- Reads `cursor.lastrowid` to get the new ID.
- Builds a `new_movie` dict with `id`, `title`, `year`, `rating`, and `director_id`.
- Returns:
  - **Status:** `201 Created`
  - **Body:** the `new_movie` JSON object
  - **Header:** `Location: /movies/<new_id>`

---

## UPDATE and DELETE rows with PATCH and DELETE

My `PATCH /movies/<id>` endpoint builds a dynamic `UPDATE` query:

- Loops over `["title", "year", "rating", "director_id"]`.
- For any field present in `data`, it adds `field = ?` to the SQL query and appends its value to the parameters list.
- Appends `id` to the parameters list and executes:
  ```sql
  UPDATE movies SET ... WHERE id = ?;
  ```
- `WHERE id = ?` targets the single specified movie, binding the ID from the URL as the last parameter.

After running `UPDATE`, I use:
- `cursor.rowcount` to check how many rows were affected:
  - `0`: No row matched that ID &rarr; returns `404 Not Found`.
  - `> 0`: A row matched and was updated &rarr; success.
  *(Note: `rowcount` only returns the number of affected rows, not the row data itself.)*

To retrieve the updated record, I run a separate `SELECT` query:
```python
cursor.execute("SELECT * FROM movies WHERE id = ?", (id,))
row = cursor.fetchone()
updated_movie = dict(row)
```
and return `updated_movie` with status `200 OK`.

### Key Takeaways
- `UPDATE + WHERE id = ?` mutates exactly the targeted row.
- `rowcount` confirms if a row was affected (used to decide between 404 and 200).
- `SELECT` fetches the freshly updated row to return in the JSON response.