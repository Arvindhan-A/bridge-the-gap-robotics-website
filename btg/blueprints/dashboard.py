from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify

from btg.extensions import db
from btg.models import User, Chapter, TeamMember, Event, EventImage, GalleryImage, Announcement, Application
from btg.auth import chapter_president_required
from btg.services.upload import save_upload

dashboard = Blueprint('dashboard', __name__)


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


# -- Overview --


@dashboard.route('/dashboard')
@chapter_president_required
def overview():
    user = db.session.get(User, session['user_id'])
    if user.role == 'super_admin':
        return redirect(url_for('admin.dashboard'))
    chapter = get_president_chapter()
    if not chapter:
        flash('No chapter assigned.', 'warning')
        return redirect(url_for('public.home'))

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


# -- About --


@dashboard.route('/dashboard/about', methods=['GET', 'POST'])
@chapter_president_required
def about():
    user = db.session.get(User, session['user_id'])
    chapter = user.role == 'super_admin' and request.args.get('chapter_id')
    if chapter:
        chapter = db.session.get(Chapter, int(chapter))
    else:
        chapter = get_president_chapter() if user.role != 'super_admin' else Chapter.query.first()
    if not chapter:
        flash('No chapter found.', 'error')
        return redirect(url_for('dashboard.overview'))

    if user.role != 'super_admin' and user.chapter_id != chapter.id:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))

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
        return redirect(url_for('dashboard.about'))

    return render_template('dashboard/about.html', chapter=chapter)


# -- Team --


@dashboard.route('/dashboard/team')
@chapter_president_required
def team():
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    members = TeamMember.query.filter_by(chapter_id=c.id).order_by(TeamMember.display_order).all()
    return render_template('dashboard/team.html', chapter=c, members=members)


@dashboard.route('/dashboard/team/add', methods=['POST'])
@chapter_president_required
def team_add():
    chapter_id = request.form.get('chapter_id', type=int)
    c = get_chapter_or_deny(chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))

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
    return redirect(url_for('dashboard.team', chapter_id=c.id))


@dashboard.route('/dashboard/team/<int:member_id>/edit', methods=['POST'])
@chapter_president_required
def team_edit(member_id):
    member = db.session.get(TeamMember, member_id)
    if not member:
        flash('Member not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    c = get_chapter_or_deny(member.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))

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
    return redirect(url_for('dashboard.team', chapter_id=member.chapter_id))


@dashboard.route('/dashboard/team/<int:member_id>/delete', methods=['POST'])
@chapter_president_required
def team_delete(member_id):
    member = db.session.get(TeamMember, member_id)
    if not member:
        flash('Member not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    c = get_chapter_or_deny(member.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))
    member.delete_files()
    db.session.delete(member)
    db.session.commit()
    flash('Team member removed.', 'info')
    return redirect(url_for('dashboard.team', chapter_id=member.chapter_id))


@dashboard.route('/dashboard/team/reorder', methods=['POST'])
@chapter_president_required
def team_reorder():
    data = request.get_json()
    for item in data:
        member = db.session.get(TeamMember, item.get('id'))
        if member:
            member.display_order = item.get('order', 0)
    db.session.commit()
    return jsonify({'ok': True})


# -- Events --


@dashboard.route('/dashboard/events')
@chapter_president_required
def events():
    import os
    events_folder = os.path.join('static', 'images', 'events')
    existing_images = []
    if os.path.exists(events_folder):
        existing_images = [f for f in os.listdir(events_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))]
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard.overview'))

    edit_event = None
    edit_id = request.args.get('edit', type=int)
    if edit_id:
        edit_event = db.session.get(Event, edit_id)
        if not edit_event or edit_event.chapter_id != c.id:
            edit_event = None

    evts = Event.query.filter_by(chapter_id=c.id).order_by(Event.date.desc()).all()
    return render_template('dashboard/events.html', chapter=c, events=evts, edit_event=edit_event, existing_images=existing_images)


@dashboard.route('/dashboard/events/create', methods=['POST'])
@chapter_president_required
def event_create():
    chapter_id = request.form.get('chapter_id', type=int)
    c = get_chapter_or_deny(chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))

    try:
        event_date = datetime.strptime(request.form.get('date', ''), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        flash('Invalid date.', 'error')
        return redirect(url_for('dashboard.events', chapter_id=c.id))

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

    # Save gallery images
    save_event_gallery(event)

    flash('Event created!', 'success')
    return redirect(url_for('dashboard.events', chapter_id=c.id))


@dashboard.route('/dashboard/events/update', methods=['POST'])
@chapter_president_required
def event_update():
    event_id = request.form.get('event_id', type=int)
    event = db.session.get(Event, event_id) if event_id else None
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    c = get_chapter_or_deny(event.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))

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

    # Save gallery images
    save_event_gallery(event)

    db.session.commit()
    flash('Event updated!', 'success')
    return redirect(url_for('dashboard.events', chapter_id=event.chapter_id))


def save_event_gallery(event):
    import os
    existing = request.form.getlist('existing_gallery')
    for img_name in existing:
        path = os.path.join('images', 'events', img_name)
        if os.path.exists(os.path.join('static', path)):
            img = EventImage(event_id=event.id, image=path, display_order=event.images.count())
            db.session.add(img)
    files = request.files.getlist('gallery_images')
    for file in files:
        if file and file.filename:
            path = save_upload(file, 'events/gallery')
            if path:
                img = EventImage(event_id=event.id, image=path, display_order=event.images.count())
                db.session.add(img)


@dashboard.route('/dashboard/events/<int:event_id>/delete', methods=['POST'])
@chapter_president_required
def event_delete(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    c = get_chapter_or_deny(event.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))
    event.delete_files()
    db.session.delete(event)
    db.session.commit()
    flash('Event deleted.', 'info')
    return redirect(url_for('dashboard.events', chapter_id=event.chapter_id))


# -- Gallery --


@dashboard.route('/dashboard/gallery')
@chapter_president_required
def gallery():
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    images = GalleryImage.query.filter_by(chapter_id=c.id).order_by(GalleryImage.display_order).all()
    return render_template('dashboard/gallery.html', chapter=c, images=images)


@dashboard.route('/dashboard/gallery/upload', methods=['POST'])
@chapter_president_required
def gallery_upload():
    chapter_id = request.form.get('chapter_id', type=int)
    c = get_chapter_or_deny(chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))

    files = request.files.getlist('images')
    caption = request.form.get('caption', '')
    count = 0
    for file in files:
        if file and file.filename:
            path = save_upload(file, 'gallery')
            if path:
                img = GalleryImage(
                    chapter_id=c.id,
                    image=path,
                    caption=caption,
                    display_order=GalleryImage.query.filter_by(chapter_id=c.id).count()
                )
                db.session.add(img)
                count += 1
    db.session.commit()
    flash(f'{count} images uploaded!', 'success')
    return redirect(url_for('dashboard.gallery', chapter_id=c.id))


@dashboard.route('/dashboard/gallery/<int:image_id>/delete', methods=['POST'])
@chapter_president_required
def gallery_delete(image_id):
    img = db.session.get(GalleryImage, image_id)
    if not img:
        flash('Image not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    c = get_chapter_or_deny(img.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))
    img.delete_files()
    db.session.delete(img)
    db.session.commit()
    flash('Image removed.', 'info')
    return redirect(url_for('dashboard.gallery', chapter_id=c.id))


@dashboard.route('/dashboard/gallery/reorder', methods=['POST'])
@chapter_president_required
def gallery_reorder():
    data = request.get_json()
    for item in data:
        img = db.session.get(GalleryImage, item.get('id'))
        if img:
            img.display_order = item.get('order', 0)
    db.session.commit()
    return jsonify({'ok': True})


# -- Announcements --


@dashboard.route('/dashboard/announcements')
@chapter_president_required
def announcements():
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    anns = Announcement.query.filter_by(chapter_id=c.id).order_by(
        Announcement.pinned.desc(), Announcement.created_at.desc()
    ).all()
    return render_template('dashboard/announcements.html', chapter=c, announcements=anns)


@dashboard.route('/dashboard/announcements/create', methods=['POST'])
@chapter_president_required
def announcement_create():
    chapter_id = request.form.get('chapter_id', type=int)
    c = get_chapter_or_deny(chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))
    announcement = Announcement(
        chapter_id=c.id,
        title=request.form.get('title', ''),
        content=request.form.get('content', ''),
        pinned='pinned' in request.form,
    )
    db.session.add(announcement)
    db.session.commit()
    flash('Announcement created!', 'success')
    return redirect(url_for('dashboard.announcements', chapter_id=c.id))


@dashboard.route('/dashboard/announcements/<int:ann_id>/edit', methods=['POST'])
@chapter_president_required
def announcement_edit(ann_id):
    ann = db.session.get(Announcement, ann_id)
    if not ann:
        flash('Announcement not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    c = get_chapter_or_deny(ann.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))
    ann.title = request.form.get('title', ann.title)
    ann.content = request.form.get('content', '')
    ann.pinned = 'pinned' in request.form
    db.session.commit()
    flash('Announcement updated!', 'success')
    return redirect(url_for('dashboard.announcements', chapter_id=c.id))


@dashboard.route('/dashboard/announcements/<int:ann_id>/delete', methods=['POST'])
@chapter_president_required
def announcement_delete(ann_id):
    ann = db.session.get(Announcement, ann_id)
    if not ann:
        flash('Announcement not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    c = get_chapter_or_deny(ann.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))
    db.session.delete(ann)
    db.session.commit()
    flash('Announcement deleted.', 'info')
    return redirect(url_for('dashboard.announcements', chapter_id=c.id))


# -- Profile --


@dashboard.route('/dashboard/profile', methods=['GET', 'POST'])
@chapter_president_required
def profile():
    user = db.session.get(User, session['user_id'])
    if request.method == 'POST':
        user.name = request.form.get('name', user.name)
        email = request.form.get('email', '').strip().lower()
        if email and email != user.email:
            if User.query.filter_by(email=email).first():
                flash('Email already in use.', 'error')
                return redirect(url_for('dashboard.profile'))
            user.email = email
        username = request.form.get('username', '').strip().lower()
        if username and username != user.username:
            if User.query.filter_by(username=username).first():
                flash('Username already taken.', 'error')
                return redirect(url_for('dashboard.profile'))
            user.username = username
        password = request.form.get('password', '')
        if password:
            user.set_password(password)
        db.session.commit()
        flash('Profile updated!', 'success')
        return redirect(url_for('dashboard.profile'))
    return render_template('dashboard/profile.html', user=user)


# -- Settings --


@dashboard.route('/dashboard/settings', methods=['GET', 'POST'])
@chapter_president_required
def settings():
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard.overview'))

    if request.method == 'POST':
        c.contact_email = request.form.get('contact_email', '')
        c.contact_phone = request.form.get('contact_phone', '')
        c.address = request.form.get('address', '')
        c.google_maps = request.form.get('google_maps', '')
        c.instagram = request.form.get('instagram', '')
        c.linkedin = request.form.get('linkedin', '')
        c.discord = request.form.get('discord', '')
        c.website = request.form.get('website', '')
        try:
            c.latitude = float(request.form.get('latitude')) if request.form.get('latitude') else None
        except (ValueError, TypeError):
            c.latitude = None
        try:
            c.longitude = float(request.form.get('longitude')) if request.form.get('longitude') else None
        except (ValueError, TypeError):
            c.longitude = None
        db.session.commit()
        flash('Settings updated!', 'success')
        return redirect(url_for('dashboard.settings'))

    return render_template('dashboard/settings.html', chapter=c)


# -- Applications --


@dashboard.route('/dashboard/applications')
@chapter_president_required
def applications():
    user = db.session.get(User, session['user_id'])
    chapter = get_president_chapter() if user.role != 'super_admin' else None
    chapter_id = chapter.id if chapter else request.args.get('chapter_id', type=int)
    c = db.session.get(Chapter, chapter_id) if chapter_id else None
    if not c:
        flash('Chapter not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    apps = Application.query.filter_by(chapter_id=c.id).order_by(Application.created_at.desc()).all()
    return render_template('dashboard/applications.html', chapter=c, applications=apps)


@dashboard.route('/dashboard/applications/<int:app_id>/status', methods=['POST'])
@chapter_president_required
def application_status(app_id):
    app_record = db.session.get(Application, app_id)
    if not app_record:
        flash('Application not found.', 'error')
        return redirect(url_for('dashboard.overview'))
    c = get_chapter_or_deny(app_record.chapter_id)
    if not c:
        flash('Access denied.', 'error')
        return redirect(url_for('dashboard.overview'))
    app_record.status = request.form.get('status', 'pending')
    db.session.commit()
    flash('Application status updated.', 'success')
    return redirect(url_for('dashboard.applications', chapter_id=c.id))
