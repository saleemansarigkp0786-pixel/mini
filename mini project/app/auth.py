import re

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy import func

from .extensions import db
from .models import User

bp = Blueprint("auth", __name__, url_prefix="/auth")


def password_is_acceptable(password):
    return len(password) >= 10 and bool(re.search(r"[A-Za-z]", password)) and bool(re.search(r"\d", password))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or len(name) > 100 or "@" not in email:
            flash("Enter a name and a valid email address.", "error")
        elif not password_is_acceptable(password):
            flash("Choose a password with at least 10 characters, including a letter and a number.", "error")
        elif db.session.scalar(db.select(User).where(func.lower(User.email) == email)):
            flash("That email is already registered.", "error")
        else:
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash("Your account is ready. Add your degree details next.", "success")
            return redirect(url_for("student.onboarding"))
    return render_template("auth/register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("student.dashboard"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = db.session.scalar(db.select(User).where(func.lower(User.email) == email))
        if user and user.check_password(request.form.get("password", "")):
            login_user(user, remember=request.form.get("remember") == "on")
            return redirect(url_for("student.dashboard"))
        flash("Email or password was not recognized.", "error")
    return render_template("auth/login.html")


@bp.post("/logout")
def logout():
    logout_user()
    flash("You have been signed out.", "success")
    return redirect(url_for("landing"))