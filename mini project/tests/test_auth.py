from app.extensions import db
from app.models import User


def test_register_and_password_hash(client, app):
    response = client.post("/auth/register", data={
        "name": "A Student", "email": "new@example.test", "password": "strong-pass-123"
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b"Degree setup" in response.data
    with app.app_context():
        account = db.session.scalar(db.select(User).where(User.email == "new@example.test"))
        assert account.check_password("strong-pass-123")
        assert account.password_hash != "strong-pass-123"
        assert account.role == "student"


def test_registration_rejects_weak_password(client):
    response = client.post("/auth/register", data={
        "name": "A Student", "email": "new@example.test", "password": "short"
    }, follow_redirects=True)
    assert b"at least 10 characters" in response.data


def test_login_and_invalid_password(client, user):
    response = client.post("/auth/login", data={"email": "student@example.test", "password": "wrong"})
    assert b"not recognized" in response.data
    response = client.post("/auth/login", data={"email": "student@example.test", "password": "test-password-123"})
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/student/dashboard")


def test_student_cannot_open_admin(client, user, login_student):
    login_student(client)
    response = client.get("/admin/")
    assert response.status_code == 403


def test_admin_can_open_admin(client, admin):
    client.post("/auth/login", data={"email": "admin@example.test", "password": "admin-password-123"})
    assert client.get("/admin/").status_code == 200


def test_production_requires_configured_secret():
    from app import create_app
    import pytest

    with pytest.raises(RuntimeError, match="SECRET_KEY must be set"):
        create_app({"APP_ENV": "production", "SECRET_KEY": None})


def test_dotenv_runs_before_config_evaluation(monkeypatch):
    import sys
    import app as app_package

    def load_test_environment():
        monkeypatch.setenv("SECRET_KEY", "loaded-before-config")

    monkeypatch.setattr(app_package, "load_dotenv", load_test_environment)
    sys.modules.pop("config", None)
    application = app_package.create_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"})
    assert application.config["SECRET_KEY"] == "loaded-before-config"
    monkeypatch.delenv("SECRET_KEY", raising=False)
    sys.modules.pop("config", None)


def test_student_pages_render(client, user):
    assert client.get("/").status_code == 200
    client.post("/auth/login", data={"email": "student@example.test", "password": "test-password-123"})
    for path in (
        "/student/dashboard", "/student/onboarding", "/student/profile",
        "/academics/roadmap", "/academics/progress", "/planner/tasks",
        "/planner/what-if", "/career/",
    ):
        assert client.get(path).status_code == 200, path


def test_admin_user_and_curriculum_pages_render(client, admin):
    client.post("/auth/login", data={"email": "admin@example.test", "password": "admin-password-123"})
    assert client.get("/admin/users").status_code == 200
    assert client.get("/admin/programs").status_code == 200


def test_student_cannot_change_another_users_role(client, user, admin):
    client.post("/auth/login", data={"email": "student@example.test", "password": "test-password-123"})
    response = client.post(f"/admin/users/{admin}", data={"role": "student", "enabled": "true"})
    assert response.status_code == 403