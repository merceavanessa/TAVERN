import os
from authlib.integrations.flask_client import OAuth
from flask_login import UserMixin


# ── User model ─────────────────────────────────────────────
class User(UserMixin):
    def __init__(self, id, email, name):
        self.id    = str(id)
        self.email = email
        self.name  = name


# ── Email whitelist ─────────────────────────────────────────
def is_email_allowed(email: str) -> bool:
    allowed = set(
        e.strip()
        for e in os.environ.get("ALLOWED_EMAILS", "").split(",")
        if e.strip()
    )
    return email in allowed


# ── OAuth setup ────────────────────────────────────────────
oauth = OAuth()

def register_oauth(app):
    oauth.init_app(app)
    oauth.register(
        name="google",
        client_id=app.config["GOOGLE_CLIENT_ID"],
        client_secret=app.config["GOOGLE_CLIENT_SECRET"],
        server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid email profile",
        },
    )
    return oauth