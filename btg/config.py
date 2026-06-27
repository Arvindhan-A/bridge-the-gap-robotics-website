import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'change-this-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        'sqlite:///' + os.path.join(BASE_DIR, 'data', 'btg.db')
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Seed credentials (used if DB is empty)
    SEED_ADMIN_EMAIL = os.environ.get('BTG_ADMIN_EMAIL', 'admin@bridgethegaprobotics.org')
    SEED_ADMIN_PASSWORD = os.environ.get('BTG_ADMIN_PASSWORD', '')
    SEED_PRESIDENT_PASSWORD = os.environ.get('BTG_PRESIDENT_PASSWORD', '')

    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Rate limiting
    LOGIN_RATE_LIMIT = 5
    LOGIN_RATE_WINDOW = 60
