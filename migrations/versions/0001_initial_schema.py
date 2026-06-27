"""Initial schema with EventImage table

Revision ID: 0001
Revises: 
Create Date: 2026-06-27
"""
from alembic import op
import sqlalchemy as sa

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=True),
        sa.Column('must_change_password', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
    op.create_table('chapters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('slug', sa.String(length=120), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('city', sa.String(length=100), default=''),
        sa.Column('description', sa.Text(), default=''),
        sa.Column('about', sa.Text(), default=''),
        sa.Column('mission', sa.Text(), default=''),
        sa.Column('cover_image', sa.String(length=500), default=''),
        sa.Column('logo', sa.String(length=500), default=''),
        sa.Column('status', sa.String(length=20), default='active'),
        sa.Column('president_name', sa.String(length=120), default=''),
        sa.Column('contact_email', sa.String(length=120), default=''),
        sa.Column('contact_phone', sa.String(length=30), default=''),
        sa.Column('address', sa.String(length=500), default=''),
        sa.Column('google_maps', sa.Text(), default=''),
        sa.Column('instagram', sa.String(length=500), default=''),
        sa.Column('linkedin', sa.String(length=500), default=''),
        sa.Column('discord', sa.String(length=500), default=''),
        sa.Column('website', sa.String(length=500), default=''),
        sa.Column('published', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )
    op.create_table('team_members',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('position', sa.String(length=120), nullable=False),
        sa.Column('bio', sa.Text(), default=''),
        sa.Column('photo', sa.String(length=500), default=''),
        sa.Column('linkedin', sa.String(length=500), default=''),
        sa.Column('email', sa.String(length=120), default=''),
        sa.Column('display_order', sa.Integer(), default=0),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), default=''),
        sa.Column('venue', sa.String(length=300), default=''),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('time', sa.String(length=20), default=''),
        sa.Column('status', sa.String(length=20), default='upcoming'),
        sa.Column('registration_link', sa.String(length=500), default=''),
        sa.Column('banner', sa.String(length=500), default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('event_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('event_id', sa.Integer(), nullable=False),
        sa.Column('image', sa.String(length=500), nullable=False),
        sa.Column('caption', sa.String(length=300), default=''),
        sa.Column('display_order', sa.Integer(), default=0),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('gallery_images',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=False),
        sa.Column('image', sa.String(length=500), nullable=False),
        sa.Column('caption', sa.String(length=300), default=''),
        sa.Column('display_order', sa.Integer(), default=0),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('announcements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('content', sa.Text(), default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table('applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chapter_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('phone', sa.String(length=30), default=''),
        sa.Column('message', sa.Text(), default=''),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['chapter_id'], ['chapters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('applications')
    op.drop_table('announcements')
    op.drop_table('gallery_images')
    op.drop_table('event_images')
    op.drop_table('events')
    op.drop_table('team_members')
    op.drop_table('chapters')
    op.drop_table('users')
