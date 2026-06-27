import json
import math
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort

from btg.extensions import db
from btg.models import User, Chapter, TeamMember, Event, EventImage, GalleryImage, Announcement, Application

public = Blueprint('public', __name__)

# Cached world atlas data for homepage map
_world_atlas_cache = None


def _get_world_atlas():
    global _world_atlas_cache
    if _world_atlas_cache is None:
        try:
            import urllib.request
            url = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json"
            with urllib.request.urlopen(url, timeout=10) as r:
                _world_atlas_cache = json.loads(r.read())
        except Exception:
            _world_atlas_cache = {}
    return _world_atlas_cache


def _decode_arcs(topology):
    """Decode TopoJSON arcs to lists of [lng, lat] coordinates."""
    if not topology or 'arcs' not in topology:
        return []
    transform = topology.get('transform', {})
    scale_x, scale_y = transform.get('scale', [1, 1])
    trans_x, trans_y = transform.get('translate', [0, 0])
    decoded = []
    for arc in topology['arcs']:
        points = []
        x, y = 0, 0
        for dx, dy in arc:
            x += dx
            y += dy
            lng = x * scale_x + trans_x
            lat = y * scale_y + trans_y
            points.append([lng, lat])
        decoded.append(points)
    return decoded


def _flatten_arcs(arc_indices):
    """Recursively flatten TopoJSON arc indices to a list of integers."""
    result = []
    for item in arc_indices:
        if isinstance(item, list):
            result.extend(_flatten_arcs(item))
        else:
            result.append(item)
    return result


def _arc_to_svg_path(arc_indices, decoded_arcs):
    """Convert TopoJSON arc references to an SVG path d string (equirectangular)."""
    W, H = 960, 480
    parts = []
    for idx in _flatten_arcs(arc_indices):
        if idx < 0:
            idx = ~idx
            arc = list(reversed(decoded_arcs[idx]))
        else:
            arc = decoded_arcs[idx]
        for i, (lng, lat) in enumerate(arc):
            x = (lng + 180) / 360 * W
            y = (90 - lat) / 180 * H
            if i == 0:
                parts.append(f"M{x:.1f},{y:.1f}")
            else:
                parts.append(f"L{x:.1f},{y:.1f}")
        parts.append("Z")
    return " ".join(parts)


def _point_in_polygon(lng, lat, polygon):
    """Ray-casting point-in-polygon test."""
    x, y = lng, lat
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside
    return inside


def _get_arc_points(arc_idx, decoded_arcs):
    """Get decoded coordinate list for an arc (handles negative indices for reverse)."""
    if arc_idx < 0:
        idx = ~arc_idx
        return list(reversed(decoded_arcs[idx]))
    return decoded_arcs[arc_idx]


def _country_contains_point(geom, decoded_arcs, pt_lng, pt_lat):
    """Check if a TopoJSON geometry contains a point."""
    def _first_arc_idx(arcs_struct):
        """Get the first arc index from a nested arcs structure."""
        for item in _flatten_arcs(arcs_struct):
            return item
        return None

    first_idx = _first_arc_idx(geom.get('arcs', []))
    if first_idx is not None:
        outer_list = _get_arc_points(first_idx, decoded_arcs)
        return _point_in_polygon(pt_lng, pt_lat, outer_list)
    return False


def _render_world_map_svg(topology, chapter_points, hue=262, W=960, H=480):
    """Return an SVG string of the world map with highlighted chapter countries."""
    decoded = _decode_arcs(topology)
    if not decoded:
        return ""

    objects = topology.get('objects', {})
    countries_data = None
    for key in objects:
        obj = objects[key]
        if obj.get('type') == 'GeometryCollection':
            countries_data = obj.get('geometries', [])
            break
    if not countries_data:
        return ""

    # Determine which country indices contain chapter points
    highlighted = set()
    for i, geom in enumerate(countries_data):
        for pt_lng, pt_lat in chapter_points:
            if _country_contains_point(geom, decoded, pt_lng, pt_lat):
                highlighted.add(i)
                break

    parts = []
    for i, geom in enumerate(countries_data):
        d = _arc_to_svg_path(geom.get('arcs', []), decoded)
        if not d:
            continue
        is_hl = i in highlighted
        fill = f"hsla({hue}, 55%, 55%, 0.2)" if is_hl else f"hsla({hue}, 20%, 85%, 0.2)"
        parts.append(f'<path d="{d}" fill="{fill}" stroke="none"/>')
    return "".join(parts)


# -- Homepage --


@public.route('/')
def home():
    chapters = Chapter.query.filter_by(published=True).order_by(Chapter.name).all()
    chapter_points = [(ch.longitude or 0, ch.latitude or 0) for ch in chapters]
    world_atlas = _get_world_atlas()
    map_svg = _render_world_map_svg(world_atlas, chapter_points)
    highlights = Event.query.order_by(Event.created_at.desc()).limit(3).all()
    return render_template('home.html', chapters=chapters,
                           world_map_svg=map_svg, highlights=highlights)


# -- Static informational pages --


@public.route('/kits')
def kits():
    return render_template('kits.html')


@public.route('/partners')
def partners():
    return render_template('partners.html')


@public.route('/contact')
def contact():
    return render_template('contact.html')



# -- Public events (all chapters) --


@public.route('/events')
def events():
    all_events = Event.query.order_by(Event.created_at.desc()).all()
    return render_template('events.html', events=all_events)


@public.route('/events/<int:event_id>')
def event_detail(event_id):
    event = db.session.get(Event, event_id)
    if not event:
        abort(404)
    images = event.images.order_by(EventImage.display_order).all()
    return render_template('event_detail.html', event=event, images=images)


# -- Public chapters --


@public.route('/chapters')
def chapters_list():
    all_chapters = Chapter.query.filter_by(published=True).order_by(Chapter.name).all()
    chapters_data = []
    for ch in all_chapters:
        pres = User.query.filter_by(chapter_id=ch.id, role='chapter_president').first()
        chapters_data.append({
            'id': ch.slug,
            'name': ch.name,
            'president': pres.name if pres else 'TBD',
            'url': url_for('public.chapter_detail', slug=ch.slug),
            'lat': ch.latitude or 0,
            'lng': ch.longitude or 0,
        })
    president_map = {}
    for u in User.query.filter_by(role='chapter_president').all():
        president_map[u.chapter_id] = u.name
    return render_template('chapters/map.html', chapters=all_chapters, president_map=president_map, chapters_json=json.dumps(chapters_data))


@public.route('/chapters/<slug>')
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


@public.route('/chapters/<slug>/apply')
def chapter_apply_page(slug):
    chapter = Chapter.query.filter_by(slug=slug, published=True).first_or_404()
    return render_template('chapters/apply.html', chapter=chapter)


@public.route('/chapters/<slug>/join', methods=['POST'])
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
    return redirect(url_for('public.chapter_detail', slug=slug))
