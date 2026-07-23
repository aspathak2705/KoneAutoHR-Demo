class UnitOfWork:
    """
    Module 0.4 — Unit of Work
    Lightweight context manager to coordinate service transaction commits and rollbacks.
    """
    def __init__(self, db):
        self.db = db

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            try:
                self.db.rollback()
            except Exception:
                pass
        else:
            try:
                self.db.commit()
            except Exception:
                pass
