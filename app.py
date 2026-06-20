import os
import json
import uuid
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'btg-secret-key-change-in-production')

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
POSTS_FILE = os.path.join(DATA_DIR, 'posts.json')
EVENTS_FILE = os.path.join(DATA_DIR, 'events.json')

os.makedirs(DATA_DIR, exist_ok=True)


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


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            flash('Please log in to access the admin panel.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def home():
    events = load_json(EVENTS_FILE)
    past_events = [e for e in events if e.get('status') == 'past']
    past_events.sort(key=lambda x: x.get('date', ''), reverse=True)
    return render_template('home.html', highlights=past_events)


@app.route('/kits')
def kits():
    return render_template('kits.html')


@app.route('/partners')
def partners():
    return render_template('partners.html')


@app.route('/events')
def events():
    events_list = load_json(EVENTS_FILE)
    return render_template('events.html', events=events_list)


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


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'btgadmin':
            session['logged_in'] = True
            flash('Welcome to the admin panel!', 'success')
            return redirect(url_for('admin'))
        flash('Invalid credentials.', 'error')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('home'))


@app.route('/admin')
@login_required
def admin():
    posts = load_json(POSTS_FILE)
    events = load_json(EVENTS_FILE)
    posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    events.sort(key=lambda x: x.get('date', ''), reverse=True)
    return render_template('admin.html', posts=posts, events=events)


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
        return redirect(url_for('admin'))
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
    return redirect(url_for('admin'))


@app.route('/admin/event/new', methods=['GET', 'POST'])
@login_required
def new_event():
    if request.method == 'POST':
        events = load_json(EVENTS_FILE)
        event = {
            'id': str(uuid.uuid4()),
            'title': request.form['title'],
            'description': request.form['description'],
            'date': request.form['date'],
            'location': request.form.get('location', ''),
            'status': request.form.get('status', 'upcoming'),
            'created_at': datetime.now().isoformat()
        }
        events.append(event)
        save_json(EVENTS_FILE, events)
        flash('Event created successfully!', 'success')
        return redirect(url_for('events'))
    return render_template('new_event.html')


@app.route('/admin/event/<event_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_event(event_id):
    events = load_json(EVENTS_FILE)
    event = next((e for e in events if e['id'] == event_id), None)
    if not event:
        flash('Event not found.', 'error')
        return redirect(url_for('admin'))
    if request.method == 'POST':
        event['title'] = request.form['title']
        event['description'] = request.form['description']
        event['date'] = request.form['date']
        event['location'] = request.form.get('location', '')
        event['status'] = request.form.get('status', 'upcoming')
        save_json(EVENTS_FILE, events)
        flash('Event updated successfully!', 'success')
        return redirect(url_for('events'))
    return render_template('edit_event.html', event=event)


@app.route('/admin/event/<event_id>/delete', methods=['POST'])
@login_required
def delete_event(event_id):
    events = load_json(EVENTS_FILE)
    events = [e for e in events if e['id'] != event_id]
    save_json(EVENTS_FILE, events)
    flash('Event deleted successfully!', 'success')
    return redirect(url_for('admin'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
