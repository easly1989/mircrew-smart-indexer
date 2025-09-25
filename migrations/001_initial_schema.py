"""
Initial database schema migration.
"""
from models import create_tables


def upgrade():
    """Create initial tables."""
    create_tables()


def downgrade():
    """Drop all tables."""
    from models import Base, engine
    Base.metadata.drop_all(bind=engine)


if __name__ == '__main__':
    upgrade()