# PR Response Doc — CineLog Watchlist Feature

## AI Usage

I used Claude Code (an AI coding assistant) throughout this project:

- **Codebase orientation:** Before touching any review comment, I had it read and summarize `models.py`, `services/collection_service.py`, and `tests/test_collection.py` so I understood the `verb_to_noun` naming convention, the query-then-raise deduplication pattern in `add_to_collection()`, and the fixture structure the tests share.
- **Finding call sites:** I used a project-wide search (`grep` for `save_to_watchlist`) to confirm the rename in Comment 1 caught every reference.
- **Commit hygiene:** I checked my commit messages against conventional commit format and used a scripted interactive rebase to reword the original "added watchlist model and endpoint / fixed a bug / more changes" commit.
- **Stress-testing Comments 4 and 5:** I drafted positions and asked the AI what counterarguments a reviewer would raise. For Comment 4, it pushed on the privacy-expectation angle, which is why the final response explicitly names the mitigation (the new explicit `public` parameter) instead of just defending the default. The reasoning below is grounded in CineLog's actual code (the `get_collection()` sort convention, the existing `public` column default) rather than generic arguments.

## Comment 1 — Rename
**What I did:** Renamed `save_to_watchlist()` to `add_to_watchlist()` in `services/watchlist_service.py` and updated the one call site in `routes/watchlist/watchlist.py` (both the import and the call in `add_film()`). This matches the project's `verb_to_noun` convention documented at the top of `collection_service.py` (`add_to_collection`, `remove_from_collection`, `get_collection`).

**How I verified:** Ran a project-wide search for `save_to_watchlist` after the change — zero matches remained. Full test suite passes.

## Comment 2 — Deduplication
**What I did:** Added a duplicate check to `add_to_watchlist()` that mirrors `add_to_collection()` exactly: query `WatchlistEntry` by `(user_id, film_id)` before inserting, and raise a new `AlreadyOnWatchlistError` (analogous to `AlreadyInCollectionError`) if an entry already exists. The exception is defined in `watchlist_service.py` alongside the function, matching where the collection service defines its own errors.

**How I verified:** Wrote `test_add_to_watchlist_duplicate_raises`, which adds the same film twice, asserts the second call raises `AlreadyOnWatchlistError`, and asserts exactly one row exists afterward. It's modeled on `test_add_to_collection_duplicate_raises`.

## Comment 3 — Missing test
**What I did:** Created `tests/test_watchlist.py` with `test_add_to_watchlist_nonexistent_film_raises`. I copied the fixture structure from `test_collection.py` (an isolated in-memory SQLite app fixture, plus `sample_user`/`sample_film` fixtures) and modeled the test on `test_add_to_collection_nonexistent_film_raises`: pass a UUID that isn't in the database and assert `FilmNotFoundError` is raised rather than a database integrity error.

**How I verified:** `pytest tests/test_watchlist.py -v` passes, and the full suite (`pytest tests/ -v`) passes — 8 tests total.

## Comment 4 — Default visibility
**My position:** Keep `public=True` as the default — but make it an intentional, documented decision rather than an inherited one, and give callers an explicit escape hatch.

**Reasoning:** CineLog is a *community* film tracking app — the value of a watchlist here is social discovery: seeing what friends want to watch, comparing lists, finding films through other people. A watchlist is a list of intentions ("films I want to see"), not a record of behavior. It carries much less sensitive signal than, say, viewing history or ratings. Defaulting to public optimizes for the behavior we want on the platform: most users never touch settings, so whichever default we pick is the state ~90% of lists will live in. A private-by-default watchlist would make the social layer of the app effectively empty for most users, killing discovery for everyone. Public-by-default with an easy opt-out serves the common case while still protecting users who care.

**Tradeoff acknowledged:** The cost is that some users will unknowingly expose their watchlist when they'd have preferred privacy — a "surprise disclosure" risk. Two things mitigate it: (1) a watchlist is low-sensitivity content compared to actual watch data, and (2) as part of this PR I added an explicit `public` parameter to the `POST /watchlist/<user_id>/add` endpoint, so clients can surface the choice at add-time instead of silently relying on the default. If CineLog later adds more sensitive list types (e.g., "guilty pleasures" or watch history exports), those should be private by default — this decision is specific to watchlists.

## Comment 5 — Sort order
**My position:** Agreed — I implemented date-added (newest first) as the default sort in `get_watchlist()`.

**Reasoning:** Beyond the maintainer's point that users want to see what they added recently, there's a stronger consistency argument from CineLog's own code: `get_collection()` already returns entries ordered by `date_added.desc()`, and there's an existing test (`test_get_collection_returns_newest_first`) locking that behavior in. Two list features on the same platform sorting differently by default would be surprising to both users and API consumers. A watchlist is also append-heavy: recently added films are the ones you're most likely to act on (watch next), while alphabetical order buries new additions in the middle of the list and only really helps when you're searching for a specific title — a job better served by a search or client-side sort.

**Engagement with reviewer's point:** I initially chose alphabetical because it makes a specific film easy to find in a long list. That's a real use case, but it's the minority one, and it degrades gracefully (you can scan or ctrl-F), whereas "what did I just add?" is the majority case and degrades badly under alphabetical order. If we later get feedback that users want to find titles in long watchlists, the right fix is a `sort` query parameter on `GET /watchlist/<user_id>`, not changing the default. Changing the query also let me drop the `join(Film)` that was only there for the title sort — one less join per request.

## Comment 6 — Rebase
**What conflicted:** Rebasing `feature/watchlist` onto the updated `main` produced no *textual* conflict, but a real *semantic* one: the UUID refactor on `main` rewrote `models.py`, which (a) changed `Film.id` from an autoincrementing integer to a `String(36)` UUID and (b) no longer contained the `WatchlistEntry` model at all. After the rebase, the watchlist service and its tests failed at import time (`ImportError: cannot import name 'WatchlistEntry'`), and the watchlist code still documented integer film IDs.

**How I resolved it:** In a dedicated commit (`fix: update WatchlistEntry film_id to UUID after main branch refactor`), I restored the `WatchlistEntry` model to `models.py` with `film_id` as `db.Column(db.String(36), db.ForeignKey("film.id"))` to match the refactored `Film.id` and `CollectionEntry.film_id`, and updated the integer-era docstrings in `watchlist_service.py` and the route (`film_id` is now documented as a UUID string).

**How I verified no conflict remains:** The rebase completed cleanly (`git rebase origin/main` → "Successfully rebased"); `git log` shows a linear history with no merge commits (`git log --merges origin/main..HEAD` is empty); and the full test suite passes on the rebased branch, including the nonexistent-film test which exercises a UUID-shaped `film_id`.

## Stretch Features

- **`remove_from_watchlist(user_id, film_id)`:** Implemented following `remove_from_collection()`'s exact pattern — query by `(user_id, film_id)`, raise a new `NotOnWatchlistError` if absent, otherwise delete and return `True`. Covered by `test_remove_from_watchlist_deletes_entry`, which asserts both the happy path (entry deleted) and the error path.
- **Second test (my choice of edge case):** `test_add_to_watchlist_duplicate_raises`. I chose the duplicate case because it exercises the exact code added for Comment 2 — without it, the deduplication fix had no regression protection, and a future refactor could silently reintroduce duplicates. It also asserts the row count is still 1, not just that the exception fires.
- **Bug found via end-to-end smoke test:** While manually exercising the endpoints, I found that `GET /watchlist/<user_id>` crashed with `AttributeError: 'WatchlistEntry' object has no attribute 'film'` — the model never had a relationship to `Film`, and no test covered `get_watchlist()`, so the unit suite stayed green. Fixed by adding `film = db.relationship("Film", backref="watchlist_entries")` to `WatchlistEntry` and adding `test_get_watchlist_returns_newest_first` (modeled on `test_get_collection_returns_newest_first`), which both catches this regression and locks in the Comment 5 sort order.
- **Visibility toggle:** `add_to_watchlist()` now accepts `public=True` as a keyword argument, and `POST /watchlist/<user_id>/add` passes through an optional `"public"` field from the JSON body (`data.get("public", True)`). Covered by `test_add_to_watchlist_respects_public_flag`. This also directly supports the Comment 4 decision: the default stays public, but callers can now be explicit.

## PR Description

**What the watchlist feature does:** Adds a per-user watchlist ("films I want to watch") to CineLog. It introduces the `WatchlistEntry` model (UUID primary key, `user_id`/`film_id` foreign keys, `date_added`, `public` flag) and a `watchlist` blueprint with two endpoints:

- `GET /watchlist/<user_id>` — returns the user's watchlist as a list of film dicts (with `date_added` and `public` attached), sorted by date added, newest first.
- `POST /watchlist/<user_id>/add` — body `{"film_id": "<uuid>", "public": <optional bool, default true>}`; adds a film to the watchlist. Returns 201 with the created entry, raises `FilmNotFoundError` for unknown films and `AlreadyOnWatchlistError` for duplicates.

The service layer (`services/watchlist_service.py`) provides `add_to_watchlist()`, `remove_from_watchlist()`, and `get_watchlist()`, mirroring the collection service's naming and error-handling patterns.

**Design decisions:**
1. **Default visibility — public:** Watchlists default to `public=True` because CineLog is a community app and watchlists are low-sensitivity, discovery-friendly content; the endpoint now accepts an explicit `public` flag so clients can offer the choice at add-time. (Full reasoning under Comment 4.)
2. **Sort order — date added, newest first:** Matches `get_collection()`'s existing convention and the append-heavy way watchlists are used; alphabetical lookup is better served by a future `sort` query parameter than by the default. (Full reasoning under Comment 5.)

**How to test manually:**
1. `python -m venv .venv` and activate it, then `pip install -r requirements.txt`.
2. Run `pytest tests/ -v` — all 9 tests should pass.
3. Start the app: `python app.py` (serves at `http://127.0.0.1:5000`; there is no frontend, so use curl).
4. Create a film so you have a UUID to work with, e.g. from a Python shell:
   ```
   from app import create_app, db
   from models import User, Film
   app = create_app()
   with app.app_context():
       u = User(username="demo", email="demo@example.com"); f = Film(title="Paddington 2", year=2017)
       db.session.add_all([u, f]); db.session.commit(); print(u.id, f.id)
   ```
5. Add to the watchlist: `curl -X POST http://127.0.0.1:5000/watchlist/<user_id>/add -H "Content-Type: application/json" -d '{"film_id": "<film_id>"}'` → 201 with the entry (`"public": true`).
6. Repeat the same request → the duplicate is rejected (`AlreadyOnWatchlistError`).
7. Add with `-d '{"film_id": "<other_film_id>", "public": false}'` → entry created with `"public": false`.
8. View it: `curl http://127.0.0.1:5000/watchlist/<user_id>` → films sorted newest-added first.

## Commit History

`git log --oneline` on `feature/watchlist` (newest first) — 14 linear commits, all
conventional format, **no merge commits**:

```
518670a chore: add Vercel serverless config and writable DB path
989095b fix: expose module-level app instance for WSGI entrypoint
1620188 fix: add film relationship to WatchlistEntry so get_watchlist can serialize films
f55dd21 docs: add pr-response.md with visibility and sort order decisions
d7efce2 test: add duplicate-entry test for add_to_watchlist
9400b57 feat: add public visibility parameter to add_to_watchlist endpoint
56c0849 feat: add remove_from_watchlist following collection service pattern
4fd42a9 fix: update WatchlistEntry film_id to UUID after main branch refactor
ac2f8fa fix: sort watchlist by date added to match collection convention
3b56eb6 test: add test for nonexistent film_id in add_to_watchlist
b3e0251 fix: add deduplication check to prevent duplicate watchlist entries
649be82 fix: rename save_to_watchlist to add_to_watchlist per naming convention
b470780 fix: update film retrieval method to use db.session.get in collection and watchlist services
e685d34 feat: add watchlist model and endpoints
```

> **Screenshot:** Run `git log --oneline` on your `feature/watchlist` branch and
> paste the screenshot image directly below this line before submitting. The text
> block above mirrors that output exactly.
