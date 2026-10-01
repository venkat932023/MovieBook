import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "moviebook.db"

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def create_database():
    conn = get_connection()
    cur = conn.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        mobile TEXT NOT NULL,
        password TEXT NOT NULL,
        city TEXT DEFAULT 'Not set',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS theatres (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        city TEXT NOT NULL,
        address TEXT DEFAULT '',
        latitude REAL NOT NULL,
        longitude REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS movies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        language TEXT DEFAULT 'English',
        rating REAL DEFAULT 0,
        poster TEXT DEFAULT '',
        genre TEXT DEFAULT 'Drama',
        description TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS shows (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        theatre_id INTEGER NOT NULL,
        movie_id INTEGER NOT NULL,
        show_time TEXT NOT NULL,
        price INTEGER NOT NULL,
        available_seats INTEGER NOT NULL DEFAULT 100,
        FOREIGN KEY(theatre_id) REFERENCES theatres(id) ON DELETE CASCADE,
        FOREIGN KEY(movie_id) REFERENCES movies(id) ON DELETE CASCADE,
        UNIQUE(theatre_id, movie_id, show_time)
    );
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        movie TEXT NOT NULL,
        theatre TEXT NOT NULL,
        booking_date TEXT NOT NULL,
        show_time TEXT NOT NULL,
        seats INTEGER NOT NULL,
        total_price INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'Confirmed',
        show_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        movie_id TEXT NOT NULL,
        movie_title TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_email, movie_id)
    );
    CREATE TABLE IF NOT EXISTS contact_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Safe upgrades for databases from older MovieBook versions.
    for table, additions in {
        "users": [("city", "TEXT DEFAULT 'Not set'"), ("created_at", "TEXT")],
        "theatres": [("address", "TEXT DEFAULT ''")],
        "movies": [("genre", "TEXT DEFAULT 'Drama'"), ("description", "TEXT DEFAULT ''")],
        "bookings": [("show_id", "INTEGER"), ("created_at", "TEXT")]
    }.items():
        cols = {r["name"] for r in cur.execute(f"PRAGMA table_info({table})").fetchall()}
        for name, definition in additions:
            if name not in cols:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

    theatres = [
        ("PVR Cinemas", "Hyderabad", "Banjara Hills, Hyderabad", 17.3850, 78.4867),
        ("AMB Cinemas", "Hyderabad", "Gachibowli, Hyderabad", 17.4401, 78.3489),
        ("INOX Megaplex", "Hyderabad", "GVK One, Banjara Hills", 17.4156, 78.4347),
        ("Asian Cinemas", "Hyderabad", "RTC X Roads, Hyderabad", 17.3616, 78.4747),
        ("PVR Cinemas", "Vijayawada", "Trendset Mall, Vijayawada", 16.5062, 80.6480),
        ("INOX Cinemas", "Vijayawada", "LEPL Capital Mall, Vijayawada", 16.5074, 80.6466),
        ("PVR Cinemas", "Guntur", "Lakshmipuram, Guntur", 16.3067, 80.4365),
        ("Asian Cinemas", "Guntur", "Brodipet, Guntur", 16.3067, 80.4365),
        ("PVR Cinemas", "Bapatla", "Bapatla, Andhra Pradesh", 15.9040, 80.4670),
        ("INOX Cinemas", "Visakhapatnam", "Visakhapatnam, Andhra Pradesh", 17.6868, 83.2185)
    ]
    if cur.execute("SELECT COUNT(*) AS c FROM theatres").fetchone()["c"] == 0:
        cur.executemany("INSERT INTO theatres(name,city,address,latitude,longitude) VALUES (?,?,?,?,?)", theatres)

    movies = [
        ("Action Hero", "Telugu", 8.5, "", "Action", "An action-packed entertainer with a strong hero journey."),
        ("Love Story", "Telugu", 8.2, "", "Romance", "A romantic drama about love, family and life choices."),
        ("Comedy Night", "Hindi", 7.9, "", "Comedy", "A light-hearted comedy for a fun movie evening."),
        ("Mystery House", "English", 8.7, "", "Thriller", "A mystery thriller filled with suspense and unexpected twists."),
        ("Dream Journey", "English", 8.1, "", "Adventure", "An adventurous journey across beautiful destinations."),
        ("Paradise", "Malayalam", 7.5, "", "Drama", "Paradise is available as a MovieBook fallback title.")
    ]
    for m in movies:
        cur.execute("INSERT OR IGNORE INTO movies(name,language,rating,poster,genre,description) VALUES (?,?,?,?,?,?)", m)

    theatre_ids = [r["id"] for r in cur.execute("SELECT id FROM theatres").fetchall()]
    movie_ids = [r["id"] for r in cur.execute("SELECT id FROM movies").fetchall()]
    show_times = [("10:00 AM", 200), ("01:30 PM", 200), ("04:30 PM", 220), ("07:30 PM", 250), ("10:30 PM", 220)]
    for theatre_id in theatre_ids:
        for movie_id in movie_ids:
            for show_time, price in show_times:
                cur.execute("""INSERT OR IGNORE INTO shows(theatre_id,movie_id,show_time,price,available_seats)
                               VALUES (?,?,?,?,100)""", (theatre_id, movie_id, show_time, price))
    conn.commit()
    conn.close()
    print(f"MovieBook database is ready: {DB_PATH}")

if __name__ == "__main__":
    create_database()
