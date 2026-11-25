"""Flask-style routes; Flask is not required for static analysis."""

from flask import Flask

app = Flask(__name__)


def load_user(user_id):
    return {"id": user_id, "name": "Ada"}


@app.route("/users/<int:user_id>")
def user_detail(user_id):
    return load_user(user_id)


def obsolete_admin_panel():
    return "retired"
