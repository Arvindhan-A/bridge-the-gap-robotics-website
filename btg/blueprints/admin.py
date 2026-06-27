import json
import os
import uuid
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from btg.extensions import db
from btg.models import User, Chapter, TeamMember, Event, GalleryImage, Announcement, Application
from btg.auth import login_required, super_admin_required
from btg.services.upload import save_upload

admin = Blueprint('admin', __name__)


def try_float(val):
    try:
        return float(val) if val else None
    except (ValueError, TypeError):
        return None


BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
POSTS_FILE = os.path.join(DATA_DIR, 'posts.json')
EVENTS_FILE = os.path.join(DATA_DIR, 'events.json')


def load_json(filepath, default=None):
    if default is None:
        default = []
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            json.dump(default, f)
    with open(filepath) as f:
        return json.load(f)


def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2, default=str)


# Utility copied from old app (for slug generation)
import re


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9-]', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


# -- Dashboard --


@admin.route('/admin')
@login_required
def dashboard():
    user = db.session.get(User, session['user_id'])
    if user.role == 'chapter_president':
        return redirect(url_for('dashboard.overview'))
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


# -- Chapter CRUD --


@admin.route('/admin/chapters')
@super_admin_required
def chapters():
    chapters = Chapter.query.order_by(Chapter.name).all()
    return render_template('admin/chapters.html', chapters=chapters)


@admin.route('/admin/chapters/create', methods=['GET', 'POST'])
@super_admin_required
def chapter_create():
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
            slug = f'{slug_base}-{counter}'
            counter += 1

        chapter = Chapter(
            slug=slug, name=name, city=city,
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
            latitude=try_float(request.form.get('latitude')),
            longitude=try_float(request.form.get('longitude')),
        )
        if 'logo' in request.files and request.files['logo'].filename:
            chapter.logo = save_upload(request.files['logo'], 'logos')
        if 'cover_image' in request.files and request.files['cover_image'].filename:
            chapter.cover_image = save_upload(request.files['cover_image'], 'covers')

        db.session.add(chapter)
        db.session.commit()
        flash(f'Chapter "{chapter.name}" created!', 'success')
        return redirect(url_for('admin.chapters'))

    return render_template('admin/chapter_form.html', chapter=None)


@admin.route('/admin/chapters/<int:chapter_id>/edit', methods=['GET', 'POST'])
@super_admin_required
def chapter_edit(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        flash('Chapter not found.', 'error')
        return redirect(url_for('admin.chapters'))

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
        try:
            chapter.latitude = float(request.form.get('latitude')) if request.form.get('latitude') else None
        except (ValueError, TypeError):
            chapter.latitude = None
        try:
            chapter.longitude = float(request.form.get('longitude')) if request.form.get('longitude') else None
        except (ValueError, TypeError):
            chapter.longitude = None

        if 'logo' in request.files and request.files['logo'].filename:
            chapter.logo = save_upload(request.files['logo'], 'logos')
        if 'cover_image' in request.files and request.files['cover_image'].filename:
            chapter.cover_image = save_upload(request.files['cover_image'], 'covers')

        db.session.commit()
        flash('Chapter updated!', 'success')
        return redirect(url_for('admin.chapters'))

    return render_template('admin/chapter_form.html', chapter=chapter)


@admin.route('/admin/chapters/<int:chapter_id>/delete', methods=['POST'])
@super_admin_required
def chapter_delete(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        flash('Chapter not found.', 'error')
    else:
        chapter.delete_files()
        db.session.delete(chapter)
        db.session.commit()
        flash(f'Chapter "{chapter.name}" deleted.', 'info')
    return redirect(url_for('admin.chapters'))


@admin.route('/admin/chapters/<int:chapter_id>/toggle', methods=['POST'])
@super_admin_required
def chapter_toggle(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if chapter:
        chapter.published = not chapter.published
        db.session.commit()
        flash(f'Chapter "{chapter.name}" {"published" if chapter.published else "unpublished"}.', 'success')
    return redirect(url_for('admin.chapters'))


# -- User management --


@admin.route('/admin/users')
@super_admin_required
def users():
    users = User.query.order_by(User.name).all()
    chapters = Chapter.query.order_by(Chapter.name).all()
    chapter_map = {c.id: c.name for c in chapters}
    return render_template('admin/users.html', users=users, chapters=chapters, chapter_map=chapter_map)


@admin.route('/admin/users/create', methods=['POST'])
@super_admin_required
def user_create():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '')
    role = request.form.get('role', 'chapter_president')
    chapter_id = request.form.get('chapter_id', type=int)

    if not name or not email or not password or not username:
        flash('Name, email, username, and password are required.', 'error')
        return redirect(url_for('admin.users'))

    if User.query.filter_by(email=email).first():
        flash('Email already in use.', 'error')
        return redirect(url_for('admin.users'))

    if User.query.filter_by(username=username).first():
        flash('Username already taken.', 'error')
        return redirect(url_for('admin.users'))

    user = User(name=name, email=email, username=username, role=role, chapter_id=chapter_id)
    user.set_password(password)
    user.must_change_password = True
    db.session.add(user)
    db.session.commit()
    flash(f'User "{user.name}" created!', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/admin/users/<int:user_id>/edit', methods=['GET'])
@super_admin_required
def user_edit_page(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin.users'))
    chapters = Chapter.query.order_by(Chapter.name).all()
    return render_template('admin/user_edit.html', user=user, chapters=chapters)


@admin.route('/admin/users/<int:user_id>/edit', methods=['POST'])
@super_admin_required
def user_edit(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('admin.users'))
    user.name = request.form.get('name', user.name)
    user.email = request.form.get('email', user.email).strip().lower()
    username = request.form.get('username', '').strip().lower()
    if username and username != user.username:
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return redirect(url_for('admin.user_edit_page', user_id=user_id))
        user.username = username
    user.role = request.form.get('role', user.role)
    user.chapter_id = request.form.get('chapter_id', type=int)
    password = request.form.get('password', '')
    if password:
        user.set_password(password)
        user.must_change_password = True
    db.session.commit()
    flash('User updated!', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/admin/users/<int:user_id>/delete', methods=['POST'])
@super_admin_required
def user_delete(user_id):
    user = db.session.get(User, user_id)
    if user and user.role != 'super_admin':
        db.session.delete(user)
        db.session.commit()
        flash('User deleted.', 'info')
    else:
        flash('Cannot delete super admin.', 'error')
    return redirect(url_for('admin.users'))


# -- Legacy admin routes --


@admin.route('/admin/legacy')
@login_required
def legacy():
    events = Event.query.order_by(Event.created_at.desc()).all()
    return render_template('admin.html', events=events)


@admin.route('/admin/post/new', methods=['GET', 'POST'])
@login_required
def new_post():
    if request.method == 'POST':
        event = Event(
            chapter_id=None,
            title=request.form['title'],
            content=request.form['content'],
            author=request.form.get('author', 'Admin'),
            description=request.form.get('content', '')[:300],
            date=datetime.utcnow().date(),
            status='published',
        )
        db.session.add(event)
        db.session.commit()
        flash('Event created successfully!', 'success')
        return redirect(url_for('admin.legacy'))
    return render_template('new_event.html')


@admin.route('/admin/post/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('admin.legacy'))
    if request.method == 'POST':
        event.title = request.form['title']
        event.content = request.form.get('content', '')
        event.author = request.form.get('author', 'Admin')
        event.description = request.form.get('description', request.form.get('content', '')[:300])
        event.venue = request.form.get('venue', '')
        try:
            event.date = datetime.strptime(request.form.get('date', ''), '%Y-%m-%d').date()
        except (ValueError, KeyError):
            pass
        event.time = request.form.get('time', '')
        event.status = request.form.get('status', event.status)
        event.registration_link = request.form.get('registration_link', '')
        if 'banner' in request.files and request.files['banner'].filename:
            event.banner = save_upload(request.files['banner'], 'events')
        db.session.commit()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('admin.legacy'))
    return render_template('edit_event.html', event=event)


@admin.route('/admin/post/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_post(event_id):
    event = db.session.get(Event, event_id)
    if event:
        db.session.delete(event)
        db.session.commit()
        flash('Event deleted successfully!', 'success')
    return redirect(url_for('admin.legacy'))


@admin.route('/admin/event/new', methods=['GET', 'POST'])
@login_required
def new_event():
    if request.method == 'POST':
        try:
            event_date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        except (ValueError, KeyError):
            event_date = datetime.utcnow().date()
        event = Event(
            chapter_id=None,
            title=request.form['title'],
            content=request.form.get('content', ''),
            author=request.form.get('author', 'Admin'),
            description=request.form.get('description', request.form.get('content', '')[:300]),
            date=event_date,
            status=request.form.get('status', 'published'),
        )
        db.session.add(event)
        db.session.commit()
        flash('Event created successfully!', 'success')
        return redirect(url_for('admin.legacy'))
    return render_template('new_event.html', event=None)


@admin.route('/admin/event/<int:event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('admin.legacy'))
    if request.method == 'POST':
        event.title = request.form['title']
        event.content = request.form.get('content', '')
        event.author = request.form.get('author', 'Admin')
        event.description = request.form.get('description', request.form.get('content', '')[:300])
        try:
            event.date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
        except (ValueError, KeyError):
            pass
        event.status = request.form.get('status', event.status)
        db.session.commit()
        flash('Event updated successfully!', 'success')
        return redirect(url_for('admin.legacy'))
    return render_template('edit_event.html', event=event)


@admin.route('/admin/event/<int:event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    event = db.session.get(Event, event_id)
    if event:
        db.session.delete(event)
        db.session.commit()
        flash('Event deleted successfully!', 'success')
    return redirect(url_for('admin.legacy'))


# -- Super admin application views --


@admin.route('/admin/applications')
@super_admin_required
def applications():
    apps = Application.query.order_by(Application.created_at.desc()).all()
    chapters = {c.id: c.name for c in Chapter.query.all()}
    # Group by chapter
    from collections import defaultdict
    grouped = defaultdict(list)
    for a in apps:
        grouped[a.chapter_id].append(a)
    return render_template('admin/applications.html', grouped=dict(grouped), chapters=chapters)


@admin.route('/admin/applications/<int:app_id>/status', methods=['POST'])
@super_admin_required
def application_status(app_id):
    app_record = db.session.get(Application, app_id)
    if not app_record:
        flash('Application not found.', 'error')
        return redirect(url_for('admin.applications'))
    app_record.status = request.form.get('status', 'pending')
    db.session.commit()
    flash('Application status updated.', 'success')
    return redirect(url_for('admin.applications'))
