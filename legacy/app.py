import os
import json
import uuid
import re
from datetime import datetime, date
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify
)
from werkzeug.utils import secure_filename

from models import db, User, Chapter, TeamMember, Event, GalleryImage, Announcement, Application

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'btg-secret-key-change-in-production')

# Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(
    os.path.dirname(__file__), 'data', 'btg.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

# File uploads
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Legacy JSON paths
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
POSTS_FILE = os.path.join(DATA_DIR, 'posts.json')
EVENTS_FILE = os.path.join(DATA_DIR, 'events.json')
os.makedirs(DATA_DIR, exist_ok=True)

# Ensure upload subfolders
for sub in ['logos', 'covers', 'team', 'events', 'gallery']:
    os.makedirs(os.path.join(UPLOAD_FOLDER, sub), exist_ok=True)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(filepath, default=None):
    if default is None:
        default = []
    if not os.path.exists(filepath):
        save_json(filepath, default)
    with open(filepath, 'r') as f:
        return json.load(f)


def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_upload(file, subfolder=''):
    if file and allowed_file(file.filename):
        ext = file.filename.rsplit('.', 1)[1].lower()
        name = f"{uuid.uuid4().hex}.{ext}"
        path = os.path.join(UPLOAD_FOLDER, subfolder, name)
        file.save(path)
        return f"uploads/{subfolder}/{name}"
    return ''


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9-]', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


def get_upload_url(path):
    if not path:
        return ''
    return url_for('static', filename=path)


def ensure_admin_user():
    admin = User.query.filter_by(role='super_admin').first()
    if not admin:
        admin = User(name='Admin', email='admin@bridgethegaprobotics.org', role='super_admin')
        admin.set_password('btg-admin-2026')
        db.session.add(admin)
        db.session.commit()


# ---------------------------------------------------------------------------
# Auth decorators
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


def super_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        user = db.session.get(User, session['user_id'])
        if not user or user.role != 'super_admin':
            flash('Access denied. Super admin privileges required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


def chapter_president_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in first.', 'warning')
            return redirect(url_for('login'))
        user = db.session.get(User, session['user_id'])
        if not user or user.role not in ('chapter_president', 'super_admin'):
            flash('Access denied.', 'error')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route('/')
def home():
    events = load_json(EVENTS_FILE)
    past_events = [e for e in events if e.get('status') == 'past']
    past_events.sort(key=lambda x: x.get('date', ''), reverse=True)
    chapters = Chapter.query.filter_by(published=True).order_by(Chapter.name).all()
    return render_template('home.html', highlights=past_events, chapters=chapters)


@app.route('/kits')
def kits():
    return render_template('kits.html')


@app.route('/partners')
def partners():
    return render_template('partners.html')


@app.route('/events')
def events():
    events_list = load_json(EVENTS_FILE)
    chapter_events = Event.query.order_by(Event.date.desc()).all()
    return render_template('events.html', events=events_list, chapter_events=chapter_events)


@app.route('/blog')
def blog():
    posts = load_json(POSTS_FILE)
    posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return render_template('blog.html', posts=posts)


@app.route('/blog/<post_id>')
def blog_post(post_id):
    posts = load_json(POSTS_FILE)
    post = next((p for p in posts if p['id'] == post_id), None)
    if not post:
        flash('Post not found.', 'error')
        return redirect(url_for('blog'))
    return render_template('blog_post.html', post=post)


# ---------------------------------------------------------------------------
# Public Chapters
# ---------------------------------------------------------------------------

@app.route('/chapters')
def chapters_list():
    all_chapters = Chapter.query.filter_by(published=True).order_by(Chapter.name).all()
    return render_template('chapters/list.html', chapters=all_chapters)


@app.route('/chapters/<slug>')
def chapter_detail(slug):
    chapter = Chapter.query.filter_by(slug=slug, published=True).first_or_404()
    team = TeamMember.query.filter_by(chapter_id=chapter.id).order_by(TeamMember.display_order).all()
    now = date.today()
    upcoming = Event.query.filter(
        Event.chapter_id == chapter.id,
        Event.date >= now,
        Event.status != 'completed'
    ).order_by(Event.date).all()
    past = Event.query.filter(
        Event.chapter_id == chapter.id,
        Event.date < now
    ).order_by(Event.date.desc()).all()
    gallery = GalleryImage.query.filter_by(chapter_id=chapter.id).order_by(GalleryImage.display_order).all()
    announcements = Announcement.query.filter_by(chapter_id=chapter.id).order_by(
        Announcement.pinned.desc(), Announcement.created_at.desc()
    ).all()
    return render_template(
        'chapters/detail.html',
        chapter=chapter, team=team,
        upcoming_events=upcoming, past_events=past,
        gallery=gallery, announcements=announcements
    )


@app.route('/chapters/<slug>/join', methods=['POST'])
def chapter_apply(slug):
    chapter = Chapter.query.filter_by(slug=slug).first_or_404()
    app_record = Application(
        chapter_id=chapter.id,
        applicant_name=request.form.get('name', ''),
        email=request.form.get('email', ''),
        school=request.form.get('school', ''),
        city=request.form.get('city', ''),
        interests=request.form.get('interests', ''),
        motivation=request.form.get('motivation', ''),
    )
    db.session.add(app_record)
    db.session.commit()
    flash('Application submitted! We will reach out soon.', 'success')
    return redirect(url_for('chapter_detail', slug=slug))


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['role'] = user.role
            session['chapter_id'] = user.chapter_id
            flash('Welcome back!', 'success')
            if user.role == 'super_admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


# ---------------------------------------------------------------------------
# Super Admin Dashboard
# ---------------------------------------------------------------------------

@app.route('/admin')
@login_required
def admin_dashboard():
    user = db.session.get(User, session['user_id'])
    if user.role == 'chapter_president':
        return redirect(url_for('dashboard'))
    chapters = Chapter.query.order_by(Chapter.name).all()
    users = User.query.order_by(User.name).all()
    total_chapters = Chapter.query.count()
    total_members = TeamMember.query.count()
    total_events = Event.query.count()
    total_apps = Application.query.count()
    return render_template(
        'admin/dashboard.html',
        chapters=chapters, users=users,
        total_chapters=total_chapters, total_members=total_members,
        total_events=total_events, total_apps=total_apps
    )


# --- Chapter CRUD (Admin) ---

@app.route('/admin/chapters')
@super_admin_required
def admin_chapters():
    chapters = Chapter.query.order_by(Chapter.name).all()
    return render_template('admin/chapters.html', chapters=chapters)


@app.route('/admin/chapters/create', methods=['GET', 'POST'])
@super_admin_required
def admin_chapter_create():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        city = request.form.get('city', '').strip()
        if not name or not city:
            flash('Name and city are required.', 'error')
            return render_template('admin/chapter_form.html', chapter=None)

        slug_base = slugify(name)
        slug = slug_base
        counter = 1
        while Chapter.query.filter_by(slug=slug).first():
            slug = f"{slug_base}-{counter}"
            counter += 1

        chapter = Chapter(
            slug=slug,
            name=name,
            city=city,
            description=request.form.get('description', ''),
            about=request.form.get('about', ''),
            mission=request.form.get('mission', ''),
            vision=request.form.get('vision', ''),
            status=request.form.get('status', 'active'),
            published='published' in request.form,
            contact_email=request.form.get('contact_email', ''),
            contact_phone=request.form.get('contact_phone', ''),
            address=request.form.get('address', ''),
            instagram=request.form.get('instagram', ''),
            linkedin=request.form.get('linkedin', ''),
            website=request.form.get('website', ''),
        )

        if 'logo' in request.files and request.files['logo'].filename:
            chapter.logo = save_upload(request.files['logo'], 'logos')
        if 'cover_image' in request.files and request.files['cover_image'].filename:
            chapter.cover_image = save_upload(request.files['cover_image'], 'covers')

        db.session.add(chapter)
        db.session.commit()
        flash(f'Chapter "{chapter.name}" created!', 'success')
        return redirect(url_for('admin_chapters'))

    return render_template('admin/chapter_form.html', chapter=None)


@app.route('/admin/chapters/<int:chapter_id>/edit', methods=['GET', 'POST'])
@super_admin_required
def admin_chapter_edit(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        flash('Chapter not found.', 'error')
        return redirect(url_for('admin_chapters'))

    if request.method == 'POST':
        chapter.name = request.form.get('name', chapter.name)
        chapter.city = request.form.get('city', chapter.city)
        chapter.description = request.form.get('description', '')
        chapter.about = request.form.get('about', '')
        chapter.mission = request.form.get('mission', '')
        chapter.vision = request.form.get('vision', '')
        chapter.objectives = request.form.get('objectives', '')
        chapter.status = request.form.get('status', 'active')
        chapter.published = 'published' in request.form
        chapter.contact_email = request.form.get('contact_email', '')
        chapter.contact_phone = request.form.get('contact_phone', '')
        chapter.address = request.form.get('address', '')
        chapter.google_maps = request.form.get('google_maps', '')
        chapter.instagram = request.form.get('instagram', '')
        chapter.linkedin = request.form.get('linkedin', '')
        chapter.discord = request.form.get('discord', '')
        chapter.website = request.form.get('website', '')

        if 'logo' in request.files and request.files['logo'].filename:
            chapter.logo = save_upload(request.files['logo'], 'logos')
        if 'cover_image' in request.files and request.files['cover_image'].filename:
            chapter.cover_image = save_upload(request.files['cover_image'], 'covers')

        db.session.commit()
        flash('Chapter updated!', 'success')
        return redirect(url_for('admin_chapters'))

    return render_template('admin/chapter_form.html', chapter=chapter)


@app.route('/admin/chapters/<int:chapter_id>/delete', methods=['POST'])
@super_admin_required
def admin_chapter_delete(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        flash('Chapter not found.', 'error')
    else:
        db.session.delete(chapter)
        db.session.commit()
        flash(f'Chapter "{chapter.name}" deleted.', 'info')
    return redirect(url_for('admin_chapters'))


@app.route('/admin/chapters/<int:chapter_id>/toggle', methods=['POST'])
@super_admin_required
def admin_chapter_toggle(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if chapter:
        chapter.published = not chapter.published
        db.session.commit()
        flash(f'Chapter "{chapter.name}" {"published" if chapter.published else "unpublished"}.', 'success')
    return redirect(url_for('admin_chapters'))


# --- User Management (Admin) ---

@app.route('/admin/users')
@super_admin_required
def admin_users():
    users = User.query.order_by(User.name).all()
    chapters = Chapter.query.order_by(Chapter.name).all()
    return render_template('admin/users.html', users=users, chapters=chapters)


@app.route('/admin/users/create', methods=['POST'])
@super_admin_required
def admin_user_create():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    role = request.form.get('role', 'chapter_president')
    chapter_id = request.form.get('chapter_id', type=int)

    if not name or not email or not password:
        flash('Name, email, and password are required.', 'error')
        return redirect(url_for('admin_users'))

    if User.query.filter_by(email=email).first():
        flash('Email already in use.', 'error')
        return redirect(url_for('admin_users'))

    user = User(name=name, email=email, role=role, chapter_id=chapter_id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'User "{user.name}" created!', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@super_admin_required
def admin_user_edit(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin_users'))

    user.name = request.form.get('name', user.name)
    user.email = request.form.get('email', user.email).strip().lower()
    user.role = request.form.get('role', user.role)
    user.chapter_id = request.form.get('chapter_id', type=int)

    password = request.form.get('password', '')
    if password:
        user.set_password(password)

    db.session.commit()
    flash('User updated!', 'success')
    return redirect(url_for('admin_users'))


@app.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@super_admin_required
def admin_user_delete(user_id):
    user = db.session.get(User, user_id)
    if user and user.role != 'super_admin':
        db.session.delete(user)
        db.session.commit()
        flash('User deleted.', 'info')
    else:
        flash('Cannot delete super admin.', 'error')
    return redirect(url_for('admin_users'))


# ---------------------------------------------------------------------------
# Secret Admin Panel (gokul007)
# ---------------------------------------------------------------------------

@app.route('/gokul007')
def secret_admin():
    if not session.get('user_id'):
        user = User.query.filter_by(role='super_admin').first()
        if user:
            session['user_id'] = user.id
            session['role'] = user.role
            session['chapter_id'] = user.chapter_id
            flash('Welcome to the secret admin panel.', 'success')
        else:
            flash('Access denied.', 'error')
            return redirect(url_for('home'))
    return redirect(url_for('secret_dashboard'))


@app.route('/gokul007/dashboard')
@super_admin_required
def secret_dashboard():
    chapters = Chapter.query.order_by(Chapter.name).all()
    users = User.query.order_by(User.name).all()
    chapters_list = Chapter.query.order_by(Chapter.name).all()
    all_members = TeamMember.query.count()
    all_events = Event.query.count()
    all_apps = Application.query.count()
    all_gallery = GalleryImage.query.count()
    return render_template(
        'admin/secret.html',
        chapters=chapters, users=users,
        chapters_list=chapters_list,
        all_members=all_members, all_events=all_events,
        all_apps=all_apps, all_gallery=all_gallery
    )


@app.route('/gokul007/users')
@super_admin_required
def secret_users():
    users = User.query.order_by(User.name).all()
    chapters = Chapter.query.order_by(Chapter.name).all()
    return render_template('admin/secret_users.html', users=users, chapters=chapters)


@app.route('/gokul007/users/create', methods=['POST'])
@super_admin_required
def secret_user_create():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    password = request.form.get('password', '')
    role = request.form.get('role', 'chapter_president')
    chapter_id = request.form.get('chapter_id', type=int)

    if not name or not email or not password:
        flash('Name, email, and password are required.', 'error')
        return redirect(url_for('secret_users'))

    if User.query.filter_by(email=email).first():
        flash('Email already in use.', 'error')
        return redirect(url_for('secret_users'))

    user = User(name=name, email=email, role=role, chapter_id=chapter_id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    flash(f'User "{user.name}" ({role.replace("_", " ")}) created!', 'success')
    return redirect(url_for('secret_users'))


@app.route('/gokul007/users/<int:user_id>/edit', methods=['POST'])
@super_admin_required
def secret_user_edit(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('secret_users'))
    user.name = request.form.get('name', user.name)
    user.email = request.form.get('email', user.email).strip().lower()
    user.role = request.form.get('role', user.role)
    user.chapter_id = request.form.get('chapter_id', type=int)
    password = request.form.get('password', '')
    if password:
        user.set_password(password)
    db.session.commit()
    flash('User updated!', 'success')
    return redirect(url_for('secret_users'))


@app.route('/gokul007/users/<int:user_id>/delete', methods=['POST'])
@super_admin_required
def secret_user_delete(user_id):
    user = db.session.get(User, user_id)
    if user and user.role != 'super_admin':
        db.session.delete(user)
        db.session.commit()
        flash('User deleted.', 'info')
    else:
        flash('Cannot delete super admin.', 'error')
    return redirect(url_for('secret_users'))


@app.route('/gokul007/chapters')
@super_admin_required
def secret_chapters():
    chapters = Chapter.query.order_by(Chapter.name).all()
    users = User.query.order_by(User.name).all()
    return render_template('admin/secret_chapters.html', chapters=chapters, users=users)


@app.route('/gokul007/chapters/create', methods=['POST'])
@super_admin_required
def secret_chapter_create():
    name = request.form.get('name', '').strip()
    city = request.form.get('city', '').strip()
    if not name or not city:
        flash('Name and city are required.', 'error')
        return redirect(url_for('secret_chapters'))

    slug_base = slugify(name)
    slug = slug_base
    counter = 1
    while Chapter.query.filter_by(slug=slug).first():
        slug = f"{slug_base}-{counter}"
        counter += 1

    chapter = Chapter(
        slug=slug, name=name, city=city,
        description=request.form.get('description', ''),
        status=request.form.get('status', 'active'),
        published='published' in request.form,
    )
    if 'logo' in request.files and request.files['logo'].filename:
        chapter.logo = save_upload(request.files['logo'], 'logos')
    if 'cover_image' in request.files and request.files['cover_image'].filename:
        chapter.cover_image = save_upload(request.files['cover_image'], 'covers')

    db.session.add(chapter)
    db.session.commit()
    flash(f'Chapter "{chapter.name}" created!', 'success')
    return redirect(url_for('secret_chapters'))


@app.route('/gokul007/chapters/<int:chapter_id>/delete', methods=['POST'])
@super_admin_required
def secret_chapter_delete(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        flash('Chapter not found.', 'error')
    else:
        db.session.delete(chapter)
        db.session.commit()
        flash(f'Chapter "{chapter.name}" deleted.', 'info')
    return redirect(url_for('secret_chapters'))


@app.route('/gokul007/chapters/<int:chapter_id>/toggle', methods=['POST'])
@super_admin_required
def secret_chapter_toggle(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if chapter:
        chapter.published = not chapter.published
        db.session.commit()
        flash(f'Chapter "{chapter.name}" {"published" if chapter.published else "unpublished"}.', 'success')
    return redirect(url_for('secret_chapters'))


@app.route('/gokul007/chapters/<int:chapter_id>/reset-president', methods=['POST'])
@super_admin_required
def secret_chapter_reset_president(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        flash('Chapter not found.', 'error')
        return redirect(url_for('secret_chapters'))
    president = User.query.filter_by(chapter_id=chapter_id, role='chapter_president').first()
    if president:
        new_password = request.form.get('new_password', 'reset123')
        president.set_password(new_password)
        db.session.commit()
        flash(f'Password reset for {president.name}. New password: {new_password}', 'success')
    else:
        flash('No chapter president assigned to this chapter.', 'warning')
    return redirect(url_for('secret_chapters'))


@app.route('/gokul007/analytics')
@super_admin_required
def secret_analytics():
    total_chapters = Chapter.query.count()
    published = Chapter.query.filter_by(published=True).count()
    total_users = User.query.count()
    presidents = User.query.filter_by(role='chapter_president').count()
    total_members = TeamMember.query.count()
    total_events = Event.query.count()
    total_gallery = GalleryImage.query.count()
    total_apps = Application.query.count()
    total_announcements = Announcement.query.count()
    chapters = Chapter.query.order_by(Chapter.name).all()

    chapter_data = []
    for c in chapters:
        chapter_data.append({
            'name': c.name,
            'members': TeamMember.query.filter_by(chapter_id=c.id).count(),
            'events': Event.query.filter_by(chapter_id=c.id).count(),
            'gallery': GalleryImage.query.filter_by(chapter_id=c.id).count(),
            'apps': Application.query.filter_by(chapter_id=c.id).count(),
        })

    return render_template(
        'admin/secret_analytics.html',
        total_chapters=total_chapters, published=published,
        total_users=total_users, presidents=presidents,
        total_members=total_members, total_events=total_events,
        total_gallery=total_gallery, total_apps=total_apps,
        total_announcements=total_announcements,
        chapter_data=chapter_data
    )


# ---------------------------------------------------------------------------
# Chapter President Dashboard
# ---------------------------------------------------------------------------

def get_president_chapter():
    user = db.session.get(User, session['user_id'])
    if user.role == 'super_admin':
        return None
    return db.session.get(Chapter, user.chapter_id)


def get_chapter_or_deny(chapter_id):
    user = db.session.get(User, session['user_id'])
    if user.role == 'super_admin':
        return db.session.get(Chapter, chapter_id)
    if user.chapter_id == chapter_id:
        return db.session.get(Chapter, chapter_id)
    return None


@app.route('/dashboard')
@chapter_president_required
def dashboard():
    user = db.session.get(User, session['user_id'])
    if user.role == 'super_admin':
        return redirect(url_for('admin_dashboard'))
    chapter = get_president_chapter()
    if not chapter:
        flash('No chapter assigned.', 'warning')
        return redirect(url_for('home'))

    team_count = TeamMember.query.filter_by(chapter_id=chapter.id).count()
    events_count = Event.query.filter_by(chapter_id=chapter.id).count()
    gallery_count = GalleryImage.query.filter_by(chapter_id=chapter.id).count()
    apps_count = Application.query.filter_by(chapter_id=chapter.id).count()
    upcoming = Event.query.filter(
        Event.chapter_id == chapter.id,
        Event.date >= date.today()
    ).order_by(Event.date).limit(5).all()
    announcements = Announcement.query.filter_by(chapter_id=chapter.id).order_by(
        Announcement.pinned.desc(), Announcement.created_at.desc()
    ).limit(3).all()

    return render_template(
        'dashboard/overview.html',
        chapter=chapter, team_count=team_count,
        events_count=events_count, gallery_count=gallery_count,
        apps_count=apps_count, upcoming_events=upcoming,
        announcements=announcements
    )


# --- About Editor ---

@app.route('/dashboard/about', methods=['GET', 'POST'])
@chapter_president_required
def dashboard_about():
    user = db.session.get(User, session['user_id'])
    chapter = user.role == 'super_admin' and request.args.get('chapter_id')
    if chapter:
        chapter = db.session.get(Chapter, int(chapter))
    else:
        chapter = get_president_chapter() if user.role != 'super_admin' else Chapter.query.first()
    if not chapter:
        flash('No chapter found.', 'error')
        return redirect(url_for('dashboard'))

    if user.role != 'super_admin' and user.chapter_id != chapter.id:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        chapter.name = request.form.get('name', chapter.name)
        chapter.city = request.form.get('city', chapter.city)
        chapter.description = request.form.get('description', '')
        chapter.about = request.form.get('about', '')
        chapter.mission = request.form.get('mission', '')
        chapter.vision = request.form.get('vision', '')
        chapter.objectives = request.form.get('objectives', '')
        if 'logo' in request.files and request.files['logo'].filename:
            chapter.logo = save_upload(request.files['logo'], 'logos')
        if 'cover_image' in request.files and request.files['cover_image'].filename:
            chapter.cover_image = save_upload(request.files['cover_image'], 'covers')
        db.session.commit()
        flash('Chapter info updated!', 'success')
        return redirect(url_for('dashboard_about'))

    return render_template('dashboard/about.html', chapter=chapter)


# --- Team Management ---

@app.route('/dashboard/team')
@chapter_president_required
def dashboard_team():
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard'))
    members = TeamMember.query.filter_by(chapter_id=c.id).order_by(TeamMember.display_order).all()
    return render_template('dashboard/team.html', chapter=c, members=members)


@app.route('/dashboard/team/add', methods=['POST'])
@chapter_president_required
def dashboard_team_add():
    chapter_id = request.form.get('chapter_id', type=int)
    c = get_chapter_or_deny(chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))

    member = TeamMember(
        chapter_id=c.id,
        name=request.form.get('name', ''),
        position=request.form.get('position', ''),
        bio=request.form.get('bio', ''),
        linkedin=request.form.get('linkedin', ''),
        email=request.form.get('email', ''),
        display_order=request.form.get('display_order', 0, type=int),
    )
    if 'photo' in request.files and request.files['photo'].filename:
        member.photo = save_upload(request.files['photo'], 'team')
    db.session.add(member)
    db.session.commit()
    flash('Team member added!', 'success')
    return redirect(url_for('dashboard_team', chapter_id=c.id))


@app.route('/dashboard/team/<int:member_id>/edit', methods=['POST'])
@chapter_president_required
def dashboard_team_edit(member_id):
    member = db.session.get(TeamMember, member_id)
    if not member:
        flash('Member not found.', 'error')
        return redirect(url_for('dashboard'))
    c = get_chapter_or_deny(member.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))

    member.name = request.form.get('name', member.name)
    member.position = request.form.get('position', member.position)
    member.bio = request.form.get('bio', '')
    member.linkedin = request.form.get('linkedin', '')
    member.email = request.form.get('email', '')
    member.display_order = request.form.get('display_order', 0, type=int)
    if 'photo' in request.files and request.files['photo'].filename:
        member.photo = save_upload(request.files['photo'], 'team')
    db.session.commit()
    flash('Team member updated!', 'success')
    return redirect(url_for('dashboard_team', chapter_id=member.chapter_id))


@app.route('/dashboard/team/<int:member_id>/delete', methods=['POST'])
@chapter_president_required
def dashboard_team_delete(member_id):
    member = db.session.get(TeamMember, member_id)
    if not member:
        flash('Member not found.', 'error')
        return redirect(url_for('dashboard'))
    c = get_chapter_or_deny(member.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    db.session.delete(member)
    db.session.commit()
    flash('Team member removed.', 'info')
    return redirect(url_for('dashboard_team', chapter_id=member.chapter_id))


@app.route('/dashboard/team/reorder', methods=['POST'])
@chapter_president_required
def dashboard_team_reorder():
    data = request.get_json()
    for item in data:
        member = db.session.get(TeamMember, item.get('id'))
        if member:
            member.display_order = item.get('order', 0)
    db.session.commit()
    return jsonify({'ok': True})


# --- Events Management ---

@app.route('/dashboard/events')
@chapter_president_required
def dashboard_events():
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard'))
    events = Event.query.filter_by(chapter_id=c.id).order_by(Event.date.desc()).all()
    return render_template('dashboard/events.html', chapter=c, events=events)


@app.route('/dashboard/events/create', methods=['POST'])
@chapter_president_required
def dashboard_event_create():
    chapter_id = request.form.get('chapter_id', type=int)
    c = get_chapter_or_deny(chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))

    try:
        event_date = datetime.strptime(request.form.get('date', ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        flash('Invalid date.', 'error')
        return redirect(url_for('dashboard_events', chapter_id=c.id))

    event = Event(
        chapter_id=c.id,
        title=request.form.get('title', ''),
        description=request.form.get('description', ''),
        venue=request.form.get('venue', ''),
        date=event_date,
        time=request.form.get('time', ''),
        status=request.form.get('status', 'upcoming'),
        registration_link=request.form.get('registration_link', ''),
    )
    if 'banner' in request.files and request.files['banner'].filename:
        event.banner = save_upload(request.files['banner'], 'events')
    db.session.add(event)
    db.session.commit()
    flash('Event created!', 'success')
    return redirect(url_for('dashboard_events', chapter_id=c.id))


@app.route('/dashboard/events/<int:event_id>/edit', methods=['POST'])
@chapter_president_required
def dashboard_event_edit(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('dashboard'))
    c = get_chapter_or_deny(event.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))

    try:
        event.date = datetime.strptime(request.form.get('date', ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        pass
    event.title = request.form.get('title', event.title)
    event.description = request.form.get('description', '')
    event.venue = request.form.get('venue', '')
    event.time = request.form.get('time', '')
    event.status = request.form.get('status', 'upcoming')
    event.registration_link = request.form.get('registration_link', '')
    if 'banner' in request.files and request.files['banner'].filename:
        event.banner = save_upload(request.files['banner'], 'events')
    db.session.commit()
    flash('Event updated!', 'success')
    return redirect(url_for('dashboard_events', chapter_id=event.chapter_id))


@app.route('/dashboard/events/<int:event_id>/delete', methods=['POST'])
@chapter_president_required
def dashboard_event_delete(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('dashboard'))
    c = get_chapter_or_deny(event.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted.', 'info')
    return redirect(url_for('dashboard_events', chapter_id=event.chapter_id))


# --- Gallery Management ---

@app.route('/dashboard/gallery')
@chapter_president_required
def dashboard_gallery():
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard'))
    images = GalleryImage.query.filter_by(chapter_id=c.id).order_by(GalleryImage.display_order).all()
    return render_template('dashboard/gallery.html', chapter=c, images=images)


@app.route('/dashboard/gallery/upload', methods=['POST'])
@chapter_president_required
def dashboard_gallery_upload():
    chapter_id = request.form.get('chapter_id', type=int)
    c = get_chapter_or_deny(chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))

    files = request.files.getlist('images')
    caption = request.form.get('caption', '')
    for file in files:
        if file and allowed_file(file.filename):
            path = save_upload(file, 'gallery')
            if path:
                img = GalleryImage(
                    chapter_id=c.id,
                    image=path,
                    caption=caption,
                    display_order=GalleryImage.query.filter_by(chapter_id=c.id).count()
                )
                db.session.add(img)
    db.session.commit()
    flash('Images uploaded!', 'success')
    return redirect(url_for('dashboard_gallery', chapter_id=c.id))


@app.route('/dashboard/gallery/<int:image_id>/delete', methods=['POST'])
@chapter_president_required
def dashboard_gallery_delete(image_id):
    img = db.session.get(GalleryImage, image_id)
    if not img:
        flash('Image not found.', 'error')
        return redirect(url_for('dashboard'))
    c = get_chapter_or_deny(img.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    db.session.delete(img)
    db.session.commit()
    flash('Image removed.', 'info')
    return redirect(url_for('dashboard_gallery', chapter_id=img.chapter_id))


@app.route('/dashboard/gallery/reorder', methods=['POST'])
@chapter_president_required
def dashboard_gallery_reorder():
    data = request.get_json()
    for item in data:
        img = db.session.get(GalleryImage, item.get('id'))
        if img:
            img.display_order = item.get('order', 0)
    db.session.commit()
    return jsonify({'ok': True})


# --- Announcements ---

@app.route('/dashboard/announcements')
@chapter_president_required
def dashboard_announcements():
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard'))
    announcements = Announcement.query.filter_by(chapter_id=c.id).order_by(
        Announcement.pinned.desc(), Announcement.created_at.desc()
    ).all()
    return render_template('dashboard/announcements.html', chapter=c, announcements=announcements)


@app.route('/dashboard/announcements/create', methods=['POST'])
@chapter_president_required
def dashboard_announcement_create():
    chapter_id = request.form.get('chapter_id', type=int)
    c = get_chapter_or_deny(chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    announcement = Announcement(
        chapter_id=c.id,
        title=request.form.get('title', ''),
        content=request.form.get('content', ''),
        pinned='pinned' in request.form,
    )
    db.session.add(announcement)
    db.session.commit()
    flash('Announcement created!', 'success')
    return redirect(url_for('dashboard_announcements', chapter_id=c.id))


@app.route('/dashboard/announcements/<int:ann_id>/edit', methods=['POST'])
@chapter_president_required
def dashboard_announcement_edit(ann_id):
    ann = db.session.get(Announcement, ann_id)
    if not ann:
        flash('Announcement not found.', 'error')
        return redirect(url_for('dashboard'))
    c = get_chapter_or_deny(ann.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    ann.title = request.form.get('title', ann.title)
    ann.content = request.form.get('content', '')
    ann.pinned = 'pinned' in request.form
    db.session.commit()
    flash('Announcement updated!', 'success')
    return redirect(url_for('dashboard_announcements', chapter_id=c.id))


@app.route('/dashboard/announcements/<int:ann_id>/delete', methods=['POST'])
@chapter_president_required
def dashboard_announcement_delete(ann_id):
    ann = db.session.get(Announcement, ann_id)
    if not ann:
        flash('Announcement not found.', 'error')
        return redirect(url_for('dashboard'))
    c = get_chapter_or_deny(ann.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    db.session.delete(ann)
    db.session.commit()
    flash('Announcement deleted.', 'info')
    return redirect(url_for('dashboard_announcements', chapter_id=c.id))


# --- Settings ---

@app.route('/dashboard/settings', methods=['GET', 'POST'])
@chapter_president_required
def dashboard_settings():
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        c.contact_email = request.form.get('contact_email', '')
        c.contact_phone = request.form.get('contact_phone', '')
        c.address = request.form.get('address', '')
        c.google_maps = request.form.get('google_maps', '')
        c.instagram = request.form.get('instagram', '')
        c.linkedin = request.form.get('linkedin', '')
        c.discord = request.form.get('discord', '')
        c.website = request.form.get('website', '')
        db.session.commit()
        flash('Settings updated!', 'success')
        return redirect(url_for('dashboard_settings'))

    return render_template('dashboard/settings.html', chapter=c)


# --- Applications ---

@app.route('/dashboard/applications')
@chapter_president_required
def dashboard_applications():
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard'))
    apps = Application.query.filter_by(chapter_id=c.id).order_by(Application.created_at.desc()).all()
    return render_template('dashboard/applications.html', chapter=c, applications=apps)


@app.route('/dashboard/applications/<int:app_id>/status', methods=['POST'])
@chapter_president_required
def dashboard_application_status(app_id):
    app_record = db.session.get(Application, app_id)
    if not app_record:
        flash('Application not found.', 'error')
        return redirect(url_for('dashboard'))
    c = get_chapter_or_deny(app_record.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard'))
    app_record.status = request.form.get('status', 'pending')
    db.session.commit()
    flash('Application status updated.', 'success')
    return redirect(url_for('dashboard_applications', chapter_id=c.id))


# ---------------------------------------------------------------------------
# Legacy admin routes (preserve existing blog/event management)
# ---------------------------------------------------------------------------

@app.route('/admin/legacy')
@login_required
def admin_legacy():
    posts = load_json(POSTS_FILE)
    evts = load_json(EVENTS_FILE)
    posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    evts.sort(key=lambda x: x.get('date', ''), reverse=True)
    return render_template('admin.html', posts=posts, events=evts)


@app.route('/admin/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        posts = load_json(POSTS_FILE)
        post = {
            'id': str(uuid.uuid4()),
            'title': request.form['title'],
            'content': request.form['content'],
            'author': request.form.get('author', 'Admin'),
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        posts.append(post)
        save_json(POSTS_FILE, posts)
        flash('Post created successfully!', 'success')
        return redirect(url_for('blog'))
    return render_template('new_post.html')


@app.route('/admin/post/<post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    posts = load_json(POSTS_FILE)
    post = next((p for p in posts if p['id'] == post_id), None)
    if not post:
        flash('Post not found.', 'error')
        return redirect(url_for('admin_legacy'))
    if request.method == 'POST':
        post['title'] = request.form['title']
        post['content'] = request.form['content']
        post['author'] = request.form.get('author', post.get('author', 'Admin'))
        post['updated_at'] = datetime.now().isoformat()
        save_json(POSTS_FILE, posts)
        flash('Post updated successfully!', 'success')
        return redirect(url_for('blog'))
    return render_template('edit_post.html', post=post)


@app.route('/admin/post/<post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    posts = load_json(POSTS_FILE)
    posts = [p for p in posts if p['id'] != post_id]
    save_json(POSTS_FILE, posts)
    flash('Post deleted successfully!', 'success')
    return redirect(url_for('admin_legacy'))


@app.route('/admin/event/new', methods=['GET', 'POST'])
@login_required
def new_event():
    if request.method == 'POST':
        evts = load_json(EVENTS_FILE)
        event = {
            'id': str(uuid.uuid4()),
            'title': request.form['title'],
            'description': request.form['description'],
            'date': request.form['date'],
            'location': request.form.get('location', ''),
            'status': request.form.get('status', 'upcoming'),
            'created_at': datetime.now().isoformat()
        }
        evts.append(event)
        save_json(EVENTS_FILE, evts)
        flash('Event created successfully!', 'success')
        return redirect(url_for('events'))
    return render_template('new_event.html')


@app.route('/admin/event/<event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    evts = load_json(EVENTS_FILE)
    event = next((e for e in evts if e['id'] == event_id), None)
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('admin_legacy'))
    if request.method == 'POST':
        event['title'] = request.form['title']
        event['description'] = request.form['description']
        event['date'] = request.form['date']
        event['location'] = request.form.get('location', '')
        event['status'] = request.form.get('status', 'upcoming')
        save_json(EVENTS_FILE, evts)
        flash('Event updated successfully!', 'success')
        return redirect(url_for('events'))
    return render_template('edit_event.html', event=event)


@app.route('/admin/event/<event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    evts = load_json(EVENTS_FILE)
    evts = [e for e in evts if e['id'] != event_id]
    save_json(EVENTS_FILE, evts)
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('admin_legacy'))


# ---------------------------------------------------------------------------
# Context processors
# ---------------------------------------------------------------------------

@app.context_processor
def inject_user():
    user = None
    if session.get('user_id'):
        user = db.session.get(User, session['user_id'])
    return {'current_user': user}


@app.context_processor
def inject_now():
    return {'now': datetime.now()}


# ---------------------------------------------------------------------------
# Init & Run
# ---------------------------------------------------------------------------

def init_db():
    with app.app_context():
        db.create_all()
        ensure_admin_user()
        # Seed sample chapters if empty
        if Chapter.query.count() == 0:
            samples = [
                {
                    'slug': 'chennai', 'name': 'Chennai Chapter',
                    'city': 'Chennai', 'description': 'Bringing robotics to students in Chennai.',
                    'about': 'Our Chennai chapter runs weekly robotics workshops.',
                    'mission': 'Make STEM accessible to every child in Chennai.',
                    'status': 'active',
                },
                {
                    'slug': 'bangalore', 'name': 'Bangalore Chapter',
                    'city': 'Bangalore', 'description': 'Inspiring young innovators in Bangalore.',
                    'about': 'Bangalore chapter focuses on kit distribution.',
                    'mission': 'Build the next generation of innovators.',
                    'status': 'active',
                },
            ]
            for s in samples:
                c = Chapter(**s)
                db.session.add(c)
            db.session.commit()

            # Assign chapters to existing users
            users = User.query.filter_by(role='chapter_president').all()
            chapters = Chapter.query.all()
            for i, u in enumerate(users):
                if i < len(chapters):
                    u.chapter_id = chapters[i].id
            db.session.commit()


if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5020)
