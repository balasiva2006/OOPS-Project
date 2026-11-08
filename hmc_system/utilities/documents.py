"""Store small private documents in PostgreSQL, with no local file writes."""
from .database import get_db


def store_document(name, content_type, data):
    """Call inside transaction() so files and student records commit together."""
    if len(data) > 4 * 1024 * 1024:
        raise ValueError('Each document must be smaller than 4 MB.')
    get_db().execute(
        'INSERT INTO documents(name,content_type,data) VALUES(%s,%s,%s) '
        'ON CONFLICT(name) DO NOTHING',
        (name, content_type, data),
    )
