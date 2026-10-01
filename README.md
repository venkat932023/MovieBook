# MovieBook - NEHA Final Version

## Modules
- Home
- Registration
- Login / Logout
- Profile with avatar button
- Current / Now Showing Movies
- Upcoming Movies + Notify Me
- Live Location / Nearby Theatres
- Theatre & Shows
- Movie posters + ratings on Theatre & Shows
- Booking
- My Bookings
- Cancellation
- About
- Contact

## Run
1. Open this `BookMyShow_Project` folder in VS Code.
2. Open Terminal.
3. Run:

```powershell
pip install -r requirements.txt
python database.py
python app.py
```

4. Open http://127.0.0.1:5000

## Deploy to Render
1. Push this project to a GitHub repository.
2. In Render, choose **New** -> **Blueprint**, connect the repository, and deploy the `render.yaml` configuration.
3. Optionally set `TMDB_TOKEN` in the Render service environment variables to enable TMDB posters and ratings.

The free Render service uses ephemeral storage. The SQLite database is recreated when the service restarts or redeploys, so registered users and bookings are not permanent. Use persistent storage or a hosted database before relying on this for real bookings.

## TMDB
Copy `.env.example` to `.env` and add your working TMDB Bearer token:

```env
TMDB_TOKEN=YOUR_TOKEN_HERE
SECRET_KEY=moviebook_neha_2026
```

TMDB is used for current/upcoming movie posters and ratings. If TMDB is unavailable, MovieBook keeps the local demo data working.

## Login test
Register a new account first. Then use the same email and password on Login. After successful login, the top navigation shows a circular profile avatar and a Profile button. The profile page allows name, mobile and city updates.

## Booking test
Login -> Nearby Theatres -> select a theatre -> Theatre & Shows -> choose a show -> Book Now -> select date/seats -> Confirm Booking -> My Bookings.
