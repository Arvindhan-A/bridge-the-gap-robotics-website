import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from btg import create_app
from btg.extensions import db as _db
from btg.config import Config
from btg.models import User, Chapter


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = 'test-secret'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = tempfile.mkdtemp()


@pytest.fixture(scope='session')
def app():
    app = create_app(TestConfig)
    return app


@pytest.fixture(scope='function', autouse=True)
def db(app):
    with app.app_context():
        _db.create_all()
        _seed_test_data()
        yield _db
        _db.session.rollback()
        for table in reversed(_db.metadata.sorted_tables):
            _db.session.execute(table.delete())
        _db.session.commit()


def _seed_test_data():
    """Seed minimal test data for each test."""
    if not User.query.first():
        admin = User(
            name='Arvind', email='arvindtrial@gmail.com',
            username='arvind',
            role='super_admin', must_change_password=False,
        )
        admin.set_password('trial@123')
        _db.session.add(admin)
        _db.session.commit()


@pytest.fixture(scope='function')
def client(app, db):
    return app.test_client()
