import pytest

from app import create_app
from app.extensions import db


@pytest.fixture
def app():
    application = create_app({
        "TESTING": True,
        "SECRET_KEY": "pytest-only-secret",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "LOGIN_DISABLED": False,
    })
    with application.app_context():
        db.create_all()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def user(app):
    from app.models import User

    with app.app_context():
        account = User(name="Test Student", email="student@example.test")
        account.set_password("test-password-123")
        db.session.add(account)
        db.session.commit()
        return account.id


@pytest.fixture
def admin(app):
    from app.models import User

    with app.app_context():
        account = User(name="Test Admin", email="admin@example.test", role="admin")
        account.set_password("admin-password-123")
        db.session.add(account)
        db.session.commit()
        return account.id


def login(client, email="student@example.test", password="test-password-123"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)


@pytest.fixture
def login_student():
    return login