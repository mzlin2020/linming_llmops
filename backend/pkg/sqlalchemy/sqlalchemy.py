from contextlib import contextmanager

from flask_sqlalchemy import SQLAlchemy as _SQLAlchemy


class SQLAlchemy(_SQLAlchemy):
    """扩展 Flask-SQLAlchemy：提供 auto_commit() 上下文管理器"""

    @contextmanager
    def auto_commit(self):
        try:
            yield
            self.session.commit()
        except Exception as exc:
            self.session.rollback()
            raise exc
