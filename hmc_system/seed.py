"""Create fictitious demo data. Run: python seed.py."""
import base64
from werkzeug.security import generate_password_hash

from . import create_app
from .accommodation import AllocationService
from .utilities.database import get_db, init_db, transaction
from .utilities.documents import store_document


def seed_demo():
    """Add demo data without replacing existing records or passwords."""
    init_db()
    with transaction() as db:
        halls = {}
        for name, amenity, amenities in [
            ('Old Hall', 30000, 'Reading room, TV room'),
            ('New Hall', 50000, 'Reading room, TV room, play room'),
        ]:
            db.execute(
                'INSERT INTO halls(name,amenity,amenities) VALUES(%s,%s,%s) '
                'ON CONFLICT(name) DO NOTHING', (name, amenity, amenities),
            )
            halls[name] = db.execute(
                'SELECT id FROM halls WHERE name=%s', (name,)
            ).fetchone()['id']

        for hall, number, capacity, rent in [
            ('Old Hall', '101', 1, 150000),
            ('Old Hall', '102', 2, 100000),
            ('New Hall', '201', 1, 220000),
            ('New Hall', '202', 2, 160000),
        ]:
            db.execute(
                'INSERT INTO rooms(hall_id,number,capacity,rent) VALUES(%s,%s,%s,%s) '
                'ON CONFLICT(hall_id,number) DO NOTHING',
                (halls[hall], number, capacity, rent),
            )

        accounts = [
            ('admin', 'Admin@123', 'admin', None),
            ('warden1', 'Warden@123', 'warden', halls['Old Hall']),
            ('warden2', 'Warden@123', 'warden', halls['New Hall']),
            ('mess1', 'Mess@123', 'mess_manager', halls['Old Hall']),
            ('mess2', 'Mess@123', 'mess_manager', halls['New Hall']),
            ('chief', 'Chief@123', 'controlling_warden', None),
        ]
        for username, password, role, hall_id in accounts:
            db.execute(
                'INSERT INTO users(username,password_hash,role,hall_id) VALUES(%s,%s,%s,%s) '
                'ON CONFLICT(username) DO NOTHING',
                (username, generate_password_hash(password), role, hall_id),
            )

        store_document('demo.png', 'image/png', base64.b64decode(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7xkAAAAASUVORK5CYII='
        ))
        store_document('demo_note.txt', 'text/plain', b'DEMONSTRATION admission note only.')
        db.execute(
            'INSERT INTO students(roll,name,address,mobile,parent_phone,photo,admission_note) '
            'VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(roll) DO NOTHING',
            ('DEMO001', 'Demo Student', 'Sample address', '9000000000',
             '9000000001', 'demo.png', 'demo_note.txt'),
        )
        sid = db.execute('SELECT id FROM students WHERE roll=%s', ('DEMO001',)).fetchone()['id']
        db.execute(
            'INSERT INTO users(username,password_hash,role,student_id) VALUES(%s,%s,%s,%s) '
            'ON CONFLICT(username) DO NOTHING',
            ('student1', generate_password_hash('Student@123'), 'student', sid),
        )
        if not db.execute('SELECT 1 FROM allocations WHERE student_id=%s', (sid,)).fetchone():
            room = db.execute(
                'SELECT id FROM rooms WHERE hall_id=%s AND number=%s',
                (halls['Old Hall'], '101'),
            ).fetchone()['id']
            admin = db.execute('SELECT id FROM users WHERE username=%s', ('admin',)).fetchone()['id']
            AllocationService.allocate(sid, room, admin)


def main():
    app = create_app()
    with app.app_context():
        seed_demo()
    print('Sample data is ready. Run: python app.py')
    print('Admin: admin / Admin@123 | Student: student1 / Student@123')
    print('Change demo passwords before making the app public.')


if __name__ == '__main__':
    main()
