from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from scene.data.base import Base

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "scene.db"


def default_database_url() -> str:
    DEFAULT_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_DATABASE_PATH}"


def get_engine(database_url: str | None = None) -> Engine:
    return create_engine(database_url or default_database_url())


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or get_engine())


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


@contextmanager
def session_scope(database_url: str | None = None) -> Iterator[Session]:
    engine = get_engine(database_url)
    init_db(engine)
    session = get_session_factory(engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
