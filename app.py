from flask import Flask, render_template, request, redirect, session, jsonify, flash, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, math, os, requests
from datetime import date
from database import create_database, get_connection

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

# Load .env without requiring python-dotenv.
def load_env_file():
    path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
load_env_file()
app.secret_key = os.environ.get("SECRET_KEY", "moviebook_college_project_2026")
create_database()


def current_user():
    if "user_id" not in session:
        return None
    conn = get_connection()
    user = conn.execute("SELECT * FROM users WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return user

@app.context_processor
def globals_for_templates():
    return {"logged_in": "user_id" in session, "current_user": current_user(),
            "today_iso": date.today().isoformat(), "today": date.today().strftime("%d %b %Y")}

# ---------- HOME ----------
@app.route("/")
def home():
    conn = get_connection()
    movies = conn.execute("SELECT * FROM movies ORDER BY rating DESC LIMIT 6").fetchall()
    theatres = conn.execute("SELECT * FROM theatres ORDER BY city,name LIMIT 6").fetchall()
    conn.close()
    movies = enrich_local_movies(movies)
    return render_template("index.html", movies=movies, theatres=theatres)

# ---------- AUTH ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        mobile = request.form.get("mobile", "").strip()
        password = request.form.get("password", "")
        city = request.form.get("city", "Not set").strip()
        if not all([name, email, mobile, password]):
            flash("Please fill all required fields.", "error")
            return render_template("register.html")
        conn = get_connection()
        try:
            conn.execute("INSERT INTO users(name,email,mobile,password,city) VALUES (?,?,?,?,?)",
                         (name,email,mobile,generate_password_hash(password),city))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            flash("This email is already registered. Please login.", "error")
            return redirect(url_for("login"))
        conn.close()
        flash("Registration successful. Please login.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    next_url = request.args.get("next", "/")
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        conn = get_connection()
        user = conn.execute("SELECT * FROM users WHERE lower(email)=?", (email,)).fetchone()
        conn.close()
        valid = False
        if user:
            stored = user["password"] or ""
            # Supports both new hashed accounts and old plain-text demo accounts.
            try:
                valid = check_password_hash(stored, password)
            except (ValueError, TypeError):
                valid = stored == password
        if valid:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            session["user_email"] = user["email"]
            flash("Login successful. Welcome to MovieBook!", "success")
            return redirect(next_url if next_url.startswith("/") else "/")
        flash("Invalid email or password. Please check your details or register first.", "error")
    return render_template("login.html", next_url=next_url)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("home"))

# ---------- TMDB ----------
def tmdb_get(path, params=None):
    token = os.environ.get("TMDB_TOKEN", "").strip()
    if not token or token.startswith("PASTE_"):
        return None, "TMDB_TOKEN is missing in .env"
    try:
        r = requests.get("https://api.themoviedb.org/3" + path,
                         params=params or {},
                         headers={"Authorization": f"Bearer {token}", "accept": "application/json"},
                         timeout=12)
        if r.status_code == 401:
            return None, "TMDB token is invalid or expired (401)."
        r.raise_for_status()
        return r.json(), None
    except requests.RequestException as exc:
        return None, f"TMDB unavailable: {exc}"

def normalize_tmdb(item, section="now"):
    poster = item.get("poster_path")
    return {
        "id": item.get("id"),
        "name": item.get("title") or item.get("original_title") or "Untitled",
        "language": (item.get("original_language") or "en").upper(),
        "rating": round(float(item.get("vote_average") or 0), 1),
        "poster": f"https://image.tmdb.org/t/p/w500{poster}" if poster else "",
        "genre": "Upcoming" if section == "upcoming" else "Now Showing",
        "description": item.get("overview") or "Movie details are available on MovieBook.",
        "release_date": item.get("release_date") or "TBA"
    }

def local_movie_list():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM movies ORDER BY rating DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def search_tmdb_movie(title):
    """Return a TMDB poster/rating for a local fallback title when a token is configured."""
    data, _ = tmdb_get(
        "/search/movie",
        {
            "query": title,
            "language": "en-IN",
            "region": "IN",
            "page": 1,
            "include_adult": "false"
        }
    )
    if not data or not data.get("results"):
        return None
    title_lower = title.strip().lower()
    exact = next(
        (x for x in data["results"]
         if (x.get("title") or x.get("original_title") or "").strip().lower() == title_lower),
        data["results"][0]
    )
    return normalize_tmdb(exact, "now")

def enrich_local_movies(movies):
    """Add real TMDB posters to local fallback movie records without replacing local booking data."""
    enriched = []
    for movie in movies:
        item = dict(movie)
        if not item.get("poster"):
            remote = search_tmdb_movie(item.get("name", ""))
            if remote:
                item["poster"] = remote.get("poster", "")
                # Keep local genre/description, but use the real TMDB rating when available.
                if remote.get("rating"):
                    item["rating"] = remote["rating"]
                if remote.get("release_date"):
                    item["release_date"] = remote["release_date"]
                item["poster_source"] = "TMDB"
        enriched.append(item)
    return enriched

def get_now_playing():
    data, err = tmdb_get("/movie/now_playing", {"language":"en-IN","region":"IN","page":1})
    if data and data.get("results"):
        movies = [normalize_tmdb(x, "now") for x in data["results"][:20]]
        return movies, True, None
    # Keep the site usable when the API is unavailable, but enrich local records with real posters
    # whenever a working TMDB token is present.
    return enrich_local_movies(local_movie_list()), False, err

def get_upcoming():
    data, err = tmdb_get("/movie/upcoming", {"language":"en-IN","region":"IN","page":1})
    if data and data.get("results"):
        return [normalize_tmdb(x, "upcoming") for x in data["results"][:20]], True, None
    return [], False, err

def get_paradise():
    data, err = tmdb_get("/search/movie", {"query":"Paradise","language":"en-IN","region":"IN","page":1,"include_adult":"false"})
    if data and data.get("results"):
        # Prefer the result whose title contains Paradise.
        results = sorted(data["results"], key=lambda x: ("paradise" not in (x.get("title") or "").lower(), -(x.get("popularity") or 0)))
        return normalize_tmdb(results[0], "now")
    for m in local_movie_list():
        if m["name"].lower() == "paradise":
            return m
    return None

@app.route("/movies")
def movies():
    query = request.args.get("q", "").strip().lower()
    city = request.args.get("city", "Current location")
    now, live, error = get_now_playing()
    upcoming, upcoming_live, upcoming_error = get_upcoming()
    paradise = get_paradise()
    if paradise and not any(str(x.get("id")) == str(paradise.get("id")) for x in now):
        now.insert(0, paradise)
    if query:
        now = [m for m in now if query in str(m.get("name", "")).lower()]
        upcoming = [m for m in upcoming if query in str(m.get("name", "")).lower()]
    return render_template("movies.html", movies=now, upcoming=upcoming, live=live,
                           upcoming_live=upcoming_live, api_error=error or upcoming_error,
                           city=city, query=query)

# ---------- LOCATION ----------
def haversine(lat1, lon1, lat2, lon2):
    r=6371.0; p1=math.radians(lat1); p2=math.radians(lat2); dp=math.radians(lat2-lat1); dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return r*2*math.atan2(math.sqrt(a),math.sqrt(1-a))

@app.route("/location")
def location():
    conn=get_connection(); theatres=conn.execute("SELECT * FROM theatres ORDER BY city,name").fetchall(); conn.close()
    return render_template("location.html", theatres=theatres)

@app.route("/api/nearby-theatres")
def nearby_theatres():
    try: lat=float(request.args["lat"]); lon=float(request.args["lon"])
    except (KeyError,ValueError): return jsonify({"error":"Valid latitude and longitude are required."}),400
    # Live OpenStreetMap cinema lookup; local DB fallback keeps demo usable.
    q=f'''[out:json][timeout:12];nwr["amenity"="cinema"](around:20000,{lat},{lon});out center tags;'''
    try:
        r=requests.post("https://overpass-api.de/api/interpreter",data=q,headers={"User-Agent":"MovieBook College Project/1.0"},timeout=15)
        if r.ok:
            out=[]
            for item in r.json().get("elements",[]):
                tags=item.get("tags",{}); ilat=item.get("lat") or item.get("center",{}).get("lat"); ilon=item.get("lon") or item.get("center",{}).get("lon")
                if ilat is None or ilon is None: continue
                dist=haversine(lat,lon,float(ilat),float(ilon)); name=tags.get("name") or tags.get("official_name") or "Cinema"
                addr=", ".join(x for x in [tags.get("addr:housenumber"),tags.get("addr:street"),tags.get("addr:city")] if x)
                local_id = None
                try:
                    c = get_connection()
                    match = c.execute("SELECT id FROM theatres WHERE lower(name)=lower(?) ORDER BY ABS(latitude-?) + ABS(longitude-?) LIMIT 1", (name, float(ilat), float(ilon))).fetchone()
                    c.close()
                    local_id = match["id"] if match else None
                except sqlite3.Error:
                    local_id = None
                out.append({"id":local_id,"name":name,"address":addr or "Nearby cinema","city":tags.get("addr:city",""),"latitude":float(ilat),"longitude":float(ilon),"distance":round(dist,2),"map_url":f"https://www.google.com/maps/search/?api=1&query={ilat},{ilon}","book_url":url_for("theatre", theatre_id=local_id) if local_id else url_for("location"),"source":"Live OpenStreetMap"})
            out.sort(key=lambda x:x["distance"])
            if out: return jsonify(out[:15])
    except requests.RequestException: pass
    conn=get_connection(); rows=conn.execute("SELECT * FROM theatres").fetchall(); conn.close(); out=[]
    for t in rows:
        dist=haversine(lat,lon,t["latitude"],t["longitude"])
        if dist<=50:
            out.append({"id":t["id"],"name":t["name"],"address":t["address"],"city":t["city"],"latitude":t["latitude"],"longitude":t["longitude"],"distance":round(dist,2),"map_url":f"https://www.google.com/maps/search/?api=1&query={t['latitude']},{t['longitude']}","source":"MovieBook local theatre database"})
    for item in out:
        item["book_url"] = url_for("theatre", theatre_id=item["id"]) if item.get("id") else url_for("location")
    out.sort(key=lambda x:x["distance"]); return jsonify(out[:15])

@app.route("/theatre/<int:theatre_id>")
def theatre(theatre_id):
    conn = get_connection()
    t = conn.execute("SELECT * FROM theatres WHERE id=?", (theatre_id,)).fetchone()
    if not t:
        conn.close()
        flash("Theatre not found.", "error")
        return redirect(url_for("location"))

    rows = conn.execute("""
        SELECT shows.id AS show_id, shows.show_time, shows.price, shows.available_seats,
               movies.id AS movie_id, movies.name AS movie, movies.language,
               movies.rating, movies.poster, movies.genre, movies.description
        FROM shows
        JOIN movies ON shows.movie_id = movies.id
        WHERE shows.theatre_id=? AND shows.available_seats>0
        ORDER BY movies.name, shows.show_time
    """, (theatre_id,)).fetchall()
    conn.close()

    # Enrich local movie records with real TMDB posters when a TMDB token is available.
    # This makes the Theatre & Shows page display the same poster style as the Movies page.
    shows = []
    poster_cache = {}
    for row in rows:
        item = dict(row)
        title = item.get("movie", "Untitled")
        poster = item.get("poster") or ""
        if not poster and title not in poster_cache:
            data, _ = tmdb_get("/search/movie", {
                "query": title,
                "language": "en-IN",
                "region": "IN",
                "page": 1,
                "include_adult": "false"
            })
            poster_path = ""
            if data and data.get("results"):
                exact = next((x for x in data["results"] if (x.get("title") or "").strip().lower() == title.strip().lower()), data["results"][0])
                poster_path = exact.get("poster_path") or ""
            poster_cache[title] = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else ""
        item["poster_url"] = poster or poster_cache.get(title, "")
        shows.append(item)

    return render_template("theatre.html", theatre=t, shows=shows)

# ---------- BOOKING ----------
@app.route("/booking", methods=["GET","POST"])
def booking():
    if "user_id" not in session:
        flash("Please login before booking tickets.","error")
        return redirect(url_for("login", next=request.full_path))
    show_id=request.args.get("show_id",type=int) or request.form.get("show_id",type=int)
    conn=get_connection()
    show=None
    if show_id:
        show=conn.execute("""SELECT shows.id AS show_id,shows.theatre_id,shows.show_time,shows.price,shows.available_seats,
                           movies.name AS movie,theatres.name AS theatre,theatres.city AS city
                           FROM shows JOIN movies ON shows.movie_id=movies.id JOIN theatres ON shows.theatre_id=theatres.id
                           WHERE shows.id=?""",(show_id,)).fetchone()
    if request.method=="POST":
        if not show: conn.close(); flash("Please select a valid show.","error"); return redirect(url_for("movies"))
        try: seats=int(request.form.get("seats","1"))
        except ValueError: seats=0
        booking_date=request.form.get("booking_date",date.today().isoformat())
        if seats<1 or seats>10: conn.close(); flash("You can book between 1 and 10 seats.","error"); return redirect(url_for("booking",show_id=show_id))
        if seats>show["available_seats"]: conn.close(); flash("Not enough seats available.","error"); return redirect(url_for("booking",show_id=show_id))
        total=seats*show["price"]
        cur=conn.execute("""INSERT INTO bookings(user_email,movie,theatre,booking_date,show_time,seats,total_price,status,show_id)
                            VALUES(?,?,?,?,?,?,?,'Confirmed',?)""",(session["user_email"],show["movie"],show["theatre"],booking_date,show["show_time"],seats,total,show_id))
        booking_id=cur.lastrowid
        conn.execute("UPDATE shows SET available_seats=available_seats-? WHERE id=?",(seats,show_id))
        conn.commit(); conn.close(); flash(f"Booking #{booking_id} confirmed successfully!","success"); return redirect(url_for("my_bookings"))
    conn.close()
    if not show: flash("Select a show from a theatre to continue.","error"); return redirect(url_for("movies"))
    return render_template("booking.html",show=show)

@app.route("/my-bookings")
def my_bookings():
    if "user_id" not in session: flash("Please login to view your bookings.","error"); return redirect(url_for("login"))
    conn=get_connection(); bookings=conn.execute("SELECT * FROM bookings WHERE user_email=? ORDER BY id DESC",(session["user_email"],)).fetchall(); conn.close()
    return render_template("my_bookings.html",bookings=bookings)

@app.route("/cancellation/<int:booking_id>",methods=["GET","POST"])
def cancellation(booking_id):
    if "user_id" not in session: flash("Please login to cancel a booking.","error"); return redirect(url_for("login"))
    conn=get_connection(); b=conn.execute("SELECT * FROM bookings WHERE id=? AND user_email=?",(booking_id,session["user_email"])).fetchone()
    if not b: conn.close(); flash("Booking not found.","error"); return redirect(url_for("my_bookings"))
    if request.method=="POST":
        if b["status"]=="Cancelled": conn.close(); flash("This booking is already cancelled.","error"); return redirect(url_for("my_bookings"))
        if b["show_id"]: conn.execute("UPDATE shows SET available_seats=available_seats+? WHERE id=?",(b["seats"],b["show_id"]))
        conn.execute("UPDATE bookings SET status='Cancelled' WHERE id=?",(booking_id,)); conn.commit(); conn.close(); flash(f"Booking #{booking_id} cancelled successfully.","success"); return redirect(url_for("my_bookings"))
    conn.close(); return render_template("cancellation.html",booking=b)

# ---------- NOTIFY ME ----------
@app.route("/notify",methods=["POST"])
def notify():
    if "user_id" not in session:
        flash("Please login to use Notify Me.","error")
        return redirect(url_for("login", next="/movies"))
    movie_id=str(request.form.get("movie_id","")).strip(); title=request.form.get("movie_title","Movie").strip()
    conn=get_connection(); conn.execute("INSERT OR IGNORE INTO notifications(user_email,movie_id,movie_title) VALUES(?,?,?)",(session["user_email"],movie_id,title)); conn.commit(); conn.close()
    flash(f"🔔 Notify Me enabled for {title}.","success"); return redirect(url_for("movies"))

# ---------- PROFILE / ABOUT / CONTACT ----------
@app.route("/profile",methods=["GET","POST"])
def profile():
    if "user_id" not in session: flash("Please login to open your profile.","error"); return redirect(url_for("login"))
    conn=get_connection()
    if request.method=="POST":
        name=request.form.get("name","").strip(); mobile=request.form.get("mobile","").strip(); city=request.form.get("city","").strip()
        conn.execute("UPDATE users SET name=?,mobile=?,city=? WHERE id=?",(name,mobile,city,session["user_id"])); conn.commit(); session["user_name"]=name; flash("Profile updated successfully.","success")
    user=conn.execute("SELECT * FROM users WHERE id=?",(session["user_id"],)).fetchone(); conn.close(); return render_template("profile.html",user=user)

@app.route("/about")
def about(): return render_template("about.html")

@app.route("/contact",methods=["GET","POST"])
def contact():
    if request.method=="POST":
        name=request.form.get("name","").strip(); email=request.form.get("email","").strip(); message=request.form.get("message","").strip()
        if not all([name,email,message]): flash("Please complete all contact fields.","error")
        else:
            conn=get_connection(); conn.execute("INSERT INTO contact_messages(name,email,message) VALUES(?,?,?)",(name,email,message)); conn.commit(); conn.close(); flash("Your message has been sent successfully.","success"); return redirect(url_for("contact"))
    return render_template("contact.html")

@app.errorhandler(404)
def not_found(error): return render_template("error.html",code=404,message="Page not found."),404

if __name__ == "__main__":
    app.run(debug=True,host="127.0.0.1",port=5000)
