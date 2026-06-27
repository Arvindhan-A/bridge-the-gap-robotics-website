import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from btg.extensions import db
from btg.models import User, Chapter, TeamMember, Event, GalleryImage, Announcement, Application, Role, PERMISSIONS
from btg.auth import super_admin_required
from btg.services.upload import save_upload, delete_upload
from btg.config import Config

secret = Blueprint('secret', __name__)

import re


def slugify(text):
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9-]', '-', text)
    text = re.sub(r'-+', '-', text)
    return text.strip('-')


# Gate: redirect to login if not authenticated, no auto-login


@secret.route('/gokul007')
def panel():
    if not session.get('user_id'):
        flash('Please log in first.', 'warning')
        return redirect(url_for('auth.login'))
    user = db.session.get(User, session['user_id'])
    if not user or user.role != 'super_admin':
        flash('Access denied.', 'error')
        return redirect(url_for('public.home'))
    return redirect(url_for('secret.dashboard'))


@secret.route('/gokul007/dashboard')
@super_admin_required
def dashboard():
    chapters = Chapter.query.order_by(Chapter.name).all()
    users = User.query.order_by(User.name).all()
    all_members = TeamMember.query.count()
    all_events = Event.query.count()
    all_apps = Application.query.count()
    all_gallery = GalleryImage.query.count()
    return render_template(
        'admin/secret.html',
        chapters=chapters, users=users,
        all_members=all_members, all_events=all_events,
        all_apps=all_apps, all_gallery=all_gallery
    )


@secret.route('/gokul007/users')
@super_admin_required
def users():
    users = User.query.order_by(User.name).all()
    chapters = Chapter.query.order_by(Chapter.name).all()
    roles = Role.query.order_by(Role.name).all()
    return render_template('admin/secret_users.html', users=users, chapters=chapters, roles=roles)


@secret.route('/gokul007/users/create', methods=['POST'])
@super_admin_required
def user_create():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    username = request.form.get('username', '').strip().lower()
    password = request.form.get('password', '')
    role = request.form.get('role', 'chapter_president')
    chapter_id = request.form.get('chapter_id', type=int)
    role_id = request.form.get('role_id', type=int)

    if not name or not email or not password or not username:
        flash('Name, email, username, and password are required.', 'error')
        return redirect(url_for('secret.users'))

    if User.query.filter_by(email=email).first():
        flash('Email already in use.', 'error')
        return redirect(url_for('secret.users'))

    if User.query.filter_by(username=username).first():
        flash('Username already taken.', 'error')
        return redirect(url_for('secret.users'))

    user = User(name=name, email=email, username=username, role=role, chapter_id=chapter_id, role_id=role_id)
    user.set_password(password)
    user.must_change_password = True
    db.session.add(user)
    db.session.commit()
    flash(f'User "{user.name}" ({role.replace("_", " ")}) created!', 'success')
    return redirect(url_for('secret.users'))


@secret.route('/gokul007/users/<int:user_id>/edit', methods=['POST'])
@super_admin_required
def user_edit(user_id):
    user = db.session.get(User, user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('secret.users'))
    user.name = request.form.get('name', user.name)
    user.email = request.form.get('email', user.email).strip().lower()
    username = request.form.get('username', '').strip().lower()
    if username and username != user.username:
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return redirect(url_for('secret.users'))
        user.username = username
    user.role = request.form.get('role', user.role)
    user.chapter_id = request.form.get('chapter_id', type=int)
    user.role_id = request.form.get('role_id', type=int) or None
    password = request.form.get('password', '')
    if password:
        user.set_password(password)
        user.must_change_password = True
    db.session.commit()
    flash('User updated!', 'success')
    return redirect(url_for('secret.users'))


@secret.route('/gokul007/users/<int:user_id>/delete', methods=['POST'])
@super_admin_required
def user_delete(user_id):
    user = db.session.get(User, user_id)
    if user and user.role != 'super_admin':
        db.session.delete(user)
        db.session.commit()
        flash('User deleted.', 'info')
    else:
        flash('Cannot delete super admin.', 'error')
    return redirect(url_for('secret.users'))


@secret.route('/gokul007/chapters')
@super_admin_required
def chapters():
    chapters = Chapter.query.order_by(Chapter.name).all()
    users = User.query.order_by(User.name).all()
    return render_template('admin/secret_chapters.html', chapters=chapters, users=users)


@secret.route('/gokul007/chapters/create', methods=['POST'])
@super_admin_required
def chapter_create():
    name = request.form.get('name', '').strip()
    city = request.form.get('city', '').strip()
    if not name or not city:
        flash('Name and city are required.', 'error')
        return redirect(url_for('secret.chapters'))

    slug_base = slugify(name)
    slug = slug_base
    counter = 1
    while Chapter.query.filter_by(slug=slug).first():
        slug = f'{slug_base}-{counter}'
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
    return redirect(url_for('secret.chapters'))


@secret.route('/gokul007/chapters/<int:chapter_id>/delete', methods=['POST'])
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
    return redirect(url_for('secret.chapters'))


@secret.route('/gokul007/chapters/<int:chapter_id>/toggle', methods=['POST'])
@super_admin_required
def chapter_toggle(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if chapter:
        chapter.published = not chapter.published
        db.session.commit()
        flash(f'Chapter "{chapter.name}" {"published" if chapter.published else "unpublished"}.', 'success')
    return redirect(url_for('secret.chapters'))


@secret.route('/gokul007/chapters/<int:chapter_id>/reset-president', methods=['POST'])
@super_admin_required
def chapter_reset_president(chapter_id):
    chapter = db.session.get(Chapter, chapter_id)
    if not chapter:
        flash('Chapter not found.', 'error')
        return redirect(url_for('secret.chapters'))
    president = User.query.filter_by(chapter_id=chapter_id, role='chapter_president').first()
    if president:
        new_password = request.form.get('new_password', 'reset123')
        president.set_password(new_password)
        president.must_change_password = True
        db.session.commit()
        flash(f'Password reset for {president.name}.', 'success')
    else:
        flash('No chapter president assigned to this chapter.', 'warning')
    return redirect(url_for('secret.chapters'))


@secret.route('/gokul007/analytics')
@super_admin_required
def analytics():
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


# -- Role Management --


@secret.route('/gokul007/roles')
@super_admin_required
def roles():
    all_roles = Role.query.order_by(Role.name).all()
    return render_template('admin/secret_roles.html', roles=all_roles, permissions=PERMISSIONS)


@secret.route('/gokul007/roles/create', methods=['POST'])
@super_admin_required
def role_create():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    if not name:
        flash('Role name is required.', 'error')
        return redirect(url_for('secret.roles'))
    if Role.query.filter_by(name=name).first():
        flash('Role already exists.', 'error')
        return redirect(url_for('secret.roles'))

    selected = request.form.getlist('permissions')
    role = Role(name=name, description=description)
    role.set_permissions(selected)
    db.session.add(role)
    db.session.commit()
    flash(f'Role "{name}" created!', 'success')
    return redirect(url_for('secret.roles'))


@secret.route('/gokul007/roles/<int:role_id>/edit', methods=['POST'])
@super_admin_required
def role_edit(role_id):
    role = db.session.get(Role, role_id)
    if not role:
        flash('Role not found.', 'error')
        return redirect(url_for('secret.roles'))
    role.name = request.form.get('name', role.name)
    role.description = request.form.get('description', '').strip()
    selected = request.form.getlist('permissions')
    role.set_permissions(selected)
    db.session.commit()
    flash(f'Role "{role.name}" updated!', 'success')
    return redirect(url_for('secret.roles'))


@secret.route('/gokul007/roles/<int:role_id>/delete', methods=['POST'])
@super_admin_required
def role_delete(role_id):
    role = db.session.get(Role, role_id)
    if not role:
        flash('Role not found.', 'error')
        return redirect(url_for('secret.roles'))
    if role.is_system:
        flash('System roles cannot be deleted.', 'error')
        return redirect(url_for('secret.roles'))
    # Reassign users with this role to None
    User.query.filter_by(role_id=role.id).update({User.role_id: None})
    db.session.delete(role)
    db.session.commit()
    flash(f'Role "{role.name}" deleted.', 'info')
    return redirect(url_for('secret.roles'))
