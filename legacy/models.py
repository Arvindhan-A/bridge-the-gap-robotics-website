import os
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'btg.db')


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='chapter_president')
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Chapter(db.Model):
    __tablename__ = 'chapters'
    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, default='')
    about = db.Column(db.Text, default='')
    mission = db.Column(db.Text, default='')
    vision = db.Column(db.Text, default='')
    objectives = db.Column(db.Text, default='')
    cover_image = db.Column(db.String(500), default='')
    logo = db.Column(db.String(500), default='')
    status = db.Column(db.String(20), default='active')
    published = db.Column(db.Boolean, default=True)
    contact_email = db.Column(db.String(120), default='')
    contact_phone = db.Column(db.String(50), default='')
    address = db.Column(db.String(500), default='')
    google_maps = db.Column(db.String(500), default='')
    instagram = db.Column(db.String(500), default='')
    linkedin = db.Column(db.String(500), default='')
    discord = db.Column(db.String(500), default='')
    website = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    members = db.relationship('TeamMember', backref='chapter', lazy='dynamic', cascade='all, delete-orphan')
    events = db.relationship('Event', backref='chapter', lazy='dynamic', cascade='all, delete-orphan')
    gallery = db.relationship('GalleryImage', backref='chapter', lazy='dynamic', cascade='all, delete-orphan')
    announcements = db.relationship('Announcement', backref='chapter', lazy='dynamic', cascade='all, delete-orphan')
    applications = db.relationship('Application', backref='chapter', lazy='dynamic', cascade='all, delete-orphan')


class TeamMember(db.Model):
    __tablename__ = 'team_members'
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)
    position = db.Column(db.String(120), nullable=False)
    bio = db.Column(db.Text, default='')
    photo = db.Column(db.String(500), default='')
    linkedin = db.Column(db.String(500), default='')
    email = db.Column(db.String(120), default='')
    display_order = db.Column(db.Integer, default=0)


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    venue = db.Column(db.String(300), default='')
    date = db.Column(db.Date, nullable=False)
    time = db.Column(db.String(20), default='')
    status = db.Column(db.String(20), default='upcoming')
    registration_link = db.Column(db.String(500), default='')
    banner = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GalleryImage(db.Model):
    __tablename__ = 'gallery_images'
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    image = db.Column(db.String(500), nullable=False)
    caption = db.Column(db.String(300), default='')
    display_order = db.Column(db.Integer, default=0)


class Announcement(db.Model):
    __tablename__ = 'announcements'
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, default='')
    pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Application(db.Model):
    __tablename__ = 'applications'
    id = db.Column(db.Integer, primary_key=True)
    chapter_id = db.Column(db.Integer, db.ForeignKey('chapters.id'), nullable=False)
    applicant_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    school = db.Column(db.String(200), default='')
    city = db.Column(db.String(120), default='')
    interests = db.Column(db.Text, default='')
    motivation = db.Column(db.Text, default='')
    status = db.Column(db.String(20), default='pending')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
