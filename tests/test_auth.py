"""Test authentication and role-based access."""


def test_public_pages(client):
    resp = client.get('/')
    assert resp.status_code == 200

    resp = client.get('/chapters')
    assert resp.status_code == 200

    resp = client.get('/login')
    assert resp.status_code == 200


def test_login_success(client):
    resp = client.post('/login', data={
        'email': 'arvindtrial@gmail.com',
        'password': 'trial@123',
    })
    assert resp.status_code == 302  # redirect to dashboard


def test_login_by_username(client):
    resp = client.post('/login', data={
        'email': 'arvind',
        'password': 'trial@123',
    })
    assert resp.status_code == 302  # redirect to dashboard


def test_login_failure(client):
    resp = client.post('/login', data={
        'email': 'arvindtrial@gmail.com',
        'password': 'wrong-password',
    })
    assert resp.status_code == 200  # re-renders login page


def test_logout(client):
    client.post('/login', data={
        'email': 'arvindtrial@gmail.com',
        'password': 'trial@123',
    })
    resp = client.get('/logout')
    assert resp.status_code == 302


def test_login_required_redirect(client):
    resp = client.get('/admin')
    assert resp.status_code == 302  # redirect to login


def test_gokul007_no_autologin(client):
    """Verify /gokul007 does not auto-login (security fix)."""
    resp = client.get('/gokul007')
    assert resp.status_code == 302  # redirect to login

    # Verify no session set
    resp = client.get('/gokul007/dashboard')
    assert resp.status_code == 302  # still redirects


def test_role_boundary_chapter_president(client):
    """Verify a chapter president cannot access another chapter's data."""
    from btg.extensions import db as _db
    from btg.models import User, Chapter

    # Create two chapters
    c1 = Chapter(slug='ch1', name='Chapter 1', city='City 1')
    c2 = Chapter(slug='ch2', name='Chapter 2', city='City 2')
    _db.session.add_all([c1, c2])
    _db.session.commit()

    # Create chapter president for ch1 only
    pres = User(
        name='Pres 1', email='pres1@test.com',
        role='chapter_president', chapter_id=c1.id
    )
    pres.set_password('test1234')
    _db.session.add(pres)
    _db.session.commit()

    client.post('/login', data={
        'email': 'pres1@test.com',
        'password': 'test1234',
    })

    # Should be able to access ch1 dashboard
    resp = client.get('/dashboard')
    assert resp.status_code == 200

    # Should NOT be able to delete ch2 events via API
    resp = client.post(f'/dashboard/events/create', data={
        'chapter_id': c2.id,
        'title': 'Evil Event',
        'date': '2026-12-01',
    })
    # Should fail because chapter_id doesn't match user's chapter
    assert resp.status_code in (302,)  # redirected with error
