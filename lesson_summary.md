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

