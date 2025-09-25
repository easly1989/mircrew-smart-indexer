"""
Data models for MIRCrew Smart Indexer.
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, BigInteger, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.sql import sqltypes


class IPAddressType(sqltypes.TypeDecorator):
    """Custom type that uses INET for PostgreSQL and String for SQLite."""
    impl = String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(INET())
        else:
            return dialect.type_descriptor(String(45))  # IPv6 addresses are up to 45 chars


class IDType(sqltypes.TypeDecorator):
    """Custom type that uses BigInteger for PostgreSQL and Integer for SQLite."""
    impl = Integer
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(BigInteger())
        else:
            return dialect.type_descriptor(Integer())
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime
from config.settings import settings

Base = declarative_base()

# Database engine and session
engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class UserThreadLikes(Base):
    """Tracks user likes/unlikes on threads."""
    __tablename__ = 'user_thread_likes'

    id = Column(IDType, primary_key=True, autoincrement=True)
    thread_id = Column(String(32), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    liked_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    unliked_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index('idx_user_thread_likes_active', 'thread_id', 'user_id',
              postgresql_where=(unliked_at.is_(None))),
    )

    def __repr__(self):
        return f"<UserThreadLikes(thread_id={self.thread_id}, user_id={self.user_id})>"


class ThreadMetadataCache(Base):
    """Cached metadata for threads."""
    __tablename__ = 'thread_metadata_cache'

    thread_id = Column(String(32), primary_key=True)
    title = Column(Text, nullable=False)
    author = Column(String(64), nullable=False)
    post_date = Column(DateTime(timezone=True), nullable=False)
    last_update = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    like_count = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<ThreadMetadataCache(thread_id={self.thread_id}, title={self.title})>"


class LikeHistory(Base):
    """Audit log for like/unlike actions."""
    __tablename__ = 'like_history'

    id = Column(IDType, primary_key=True, autoincrement=True)
    thread_id = Column(String(32), nullable=False, index=True)
    user_id = Column(String(64), nullable=False, index=True)
    action = Column(String(16), nullable=False)  # 'like' or 'unlike'
    performed_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    ip_address = Column(IPAddressType, nullable=False)

    def __repr__(self):
        return f"<LikeHistory(thread_id={self.thread_id}, user_id={self.user_id}, action={self.action})>"


def get_db():
    """Get database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)