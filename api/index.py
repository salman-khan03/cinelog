"""
api/index.py — Vercel serverless entrypoint.

Vercel's @vercel/python runtime imports the WSGI callable named `app` from
this module. We re-export the Flask app built by the application factory and
add a small landing route so the deployment root returns a helpful response
instead of a bare 404 (the API itself has no frontend).
"""

from flask import jsonify

from app import app


@app.route("/")
def index():
    """Landing route: confirms the API is up and lists the endpoints."""
    return jsonify({
        "service": "CineLog API",
        "status": "ok",
        "endpoints": {
            "films": "/films",
            "collection": "/collection/<user_id>",
            "watchlist": "/watchlist/<user_id>",
            "add_to_watchlist": "POST /watchlist/<user_id>/add",
        },
    })
