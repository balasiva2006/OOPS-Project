"""Record application actions in the current database transaction."""
from .database import get_db
from .validation import now

def audit(user_id, action, detail):
    get_db().execute('INSERT INTO audit(user_id,action,detail,created) VALUES(%s,%s,%s,%s)',
                     (user_id, action, detail, now()))
