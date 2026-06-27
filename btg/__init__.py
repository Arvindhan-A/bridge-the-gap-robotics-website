import os
import json
import logging
import glob
from flask import Flask, session, render_template
from datetime import datetime

from btg.config import Config, BASE_DIR
from btg.extensions import db, csrf, migrate
from btg.models import User, Chapter, Event, EventImage, TeamMember, GalleryImage, Announcement, Application, Role, PERMISSIONS
from btg.blueprints.public import public
from btg.blueprints.auth_bp import auth
from btg.blueprints.admin import admin
from btg.blueprints.dashboard import dashboard
from btg.blueprints.secret import secret


def create_app(config_class=Config):
    app = Flask(__name__,
                template_folder=os.path.join(BASE_DIR, 'templates'),
                static_folder=os.path.join(BASE_DIR, 'static'))
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    # Ensure upload directories exist
    for sub in ['logos', 'covers', 'team', 'events', 'events/gallery', 'gallery']:
        os.makedirs(os.path.join(Config.UPLOAD_FOLDER, sub), exist_ok=True)

    # Ensure data directory exists
    os.makedirs(os.path.join(BASE_DIR, 'data'), exist_ok=True)

    # Register blueprints
    app.register_blueprint(public)
    app.register_blueprint(auth)
    app.register_blueprint(admin)
    app.register_blueprint(dashboard)
    app.register_blueprint(secret)

    # Context processors
    @app.context_processor
    def inject_user():
        user = None
        if session.get('user_id'):
            user = db.session.get(User, session['user_id'])
        return {'current_user': user}

    @app.context_processor
    def inject_now():
        return {'now': datetime.now()}

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    # Healthcheck
    @app.route('/health')
    def health():
        return {'status': 'ok'}, 200

    # Logging
    if not app.debug:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    # Initialize database
    with app.app_context():
        db.create_all()
        _seed_data()

    return app


def _seed_data():
    """Seed admin user, roles, and sample chapters if DB is empty."""

    # Seed default roles
    if Role.query.count() == 0:
        super_admin_role = Role(
            name='Super Admin',
            description='Full access to all features.',
            permissions=json.dumps([p[0] for p in PERMISSIONS]),
            is_system=True,
        )
        db.session.add(super_admin_role)

        president_role = Role(
            name='Chapter President',
            description='Manage their own chapter events, team, announcements, and applications.',
            permissions=json.dumps(['manage_events', 'manage_announcements', 'manage_applications']),
            is_system=True,
        )
        db.session.add(president_role)

        viewer_role = Role(
            name='Viewer',
            description='Read-only access to analytics and content.',
            permissions=json.dumps(['view_analytics']),
            is_system=True,
        )
        db.session.add(viewer_role)
        db.session.commit()

    # Seed master admin
    admin = User.query.filter_by(role='super_admin').first()
    if not admin:
        admin = User(
            name='Arvind',
            email='arvindtrial@gmail.com',
            username='arvind',
            role='super_admin',
            role_id=Role.query.filter_by(name='Super Admin').first().id,
            must_change_password=False,
        )
        admin.set_password('trial@123')
        db.session.add(admin)

    if Chapter.query.count() == 0:
        samples = [
            {
                'slug': 'chennai', 'name': 'Chennai Chapter',
                'city': 'Chennai',
                'description': 'Bringing robotics to students in Chennai.',
                'about': 'Our Chennai chapter runs weekly robotics workshops.',
                'mission': 'Make STEM accessible to every child in Chennai.',
                'status': 'active',
                'latitude': 13.0827, 'longitude': 80.2707,
            },
            {
                'slug': 'bangalore', 'name': 'Bangalore Chapter',
                'city': 'Bangalore',
                'description': 'Inspiring young innovators in Bangalore.',
                'about': 'Bangalore chapter focuses on kit distribution.',
                'mission': 'Build the next generation of innovators.',
                'status': 'active',
                'latitude': 12.9716, 'longitude': 77.5946,
            },
        ]
        for s in samples:
            c = Chapter(**s)
            db.session.add(c)
        db.session.commit()

        pres_role_id = Role.query.filter_by(name='Chapter President').first().id
        pres_pw = Config.SEED_PRESIDENT_PASSWORD or 'btg-chennai-2026'
        pres = User.query.filter_by(role='chapter_president').first()
        if not pres:
            pres = User(
                name='Chennai President',
                email='president.chennai@bridgethegaprobotics.org',
                username='chennai_president',
                role='chapter_president',
                role_id=pres_role_id,
                chapter_id=Chapter.query.filter_by(slug='chennai').first().id,
                must_change_password=True,
            )
            pres.set_password(pres_pw)
            db.session.add(pres)

        pres_pw2 = Config.SEED_PRESIDENT_PASSWORD or 'btg-bangalore-2026'
        pres2 = User(
            name='Bangalore President',
            email='president.bangalore@bridgethegaprobotics.org',
            username='bangalore_president',
            role='chapter_president',
            role_id=pres_role_id,
            chapter_id=Chapter.query.filter_by(slug='bangalore').first().id,
            must_change_password=True,
        )
        pres2.set_password(pres_pw2)
        db.session.add(pres2)

    # Seed sample event with gallery images
    if Event.query.filter_by(title='Robotics Workshop Series').first() is None:
        chennai = Chapter.query.filter_by(slug='chennai').first()
        if chennai:
            event = Event(
                chapter_id=chennai.id,
                title='Robotics Workshop Series',
                description='Join us for an exciting robotics workshop series covering fundamentals to advanced concepts.',
                content='<p>Learn to build and program robots with our hands-on workshops.</p><ul><li>Week 1: Introduction to Robotics</li><li>Week 2: Programming Basics</li><li>Week 3: Advanced Challenges</li></ul>',
                venue='Chennai Community Center',
                date=datetime(2026, 7, 15),
                time='10:00 AM - 4:00 PM',
                status='upcoming',
                registration_link='https://example.com/register',
            )
            db.session.add(event)
            db.session.commit()

            # Add all images from static/images/events as gallery
            images_dir = os.path.join(BASE_DIR, 'static', 'images', 'events')
            for img_path in sorted(glob.glob(os.path.join(images_dir, '*.jpg')) + glob.glob(os.path.join(images_dir, '*.jpeg')) + glob.glob(os.path.join(images_dir, '*.png'))):
                img_name = os.path.basename(img_path)
                img = EventImage(
                    event_id=event.id,
                    image=f'images/events/{img_name}',
                    display_order=event.images.count(),
                )
                db.session.add(img)
            db.session.commit()

    db.session.commit()