"""Run once before starting: python seed.py. Safe to rerun; existing data is kept."""
from pathlib import Path
from werkzeug.security import generate_password_hash
from . import create_app
from .utilities.database import get_db
from .accommodation import AllocationService

def main():
    """Add demo records without replacing existing records or passwords."""
    app = create_app()

    with app.app_context():
        db=get_db()
        with db:
            db.execute('INSERT OR IGNORE INTO halls(id,name,amenity,amenities) VALUES(1,?,?,?)',('Old Hall',30000,'Reading room, TV room'))
            db.execute('INSERT OR IGNORE INTO halls(id,name,amenity,amenities) VALUES(2,?,?,?)',('New Hall',50000,'Reading room, TV room, play room'))
            for hall,number,capacity,rent in [(1,'101',1,150000),(1,'102',2,100000),(2,'201',1,220000),(2,'202',2,160000)]:
                db.execute('INSERT OR IGNORE INTO rooms(hall_id,number,capacity,rent) VALUES(?,?,?,?)',(hall,number,capacity,rent))
            accounts=[('admin','Admin@123','admin',None),('warden1','Warden@123','warden',1),('warden2','Warden@123','warden',2),('mess1','Mess@123','mess_manager',1),('mess2','Mess@123','mess_manager',2),('chief','Chief@123','controlling_warden',None)]
            for username,password,role,hall in accounts:
                db.execute('INSERT OR IGNORE INTO users(username,password_hash,role,hall_id) VALUES(?,?,?,?)',(username,generate_password_hash(password),role,hall))
            upload=Path(app.config['UPLOAD_FOLDER'])
            # Small valid PNG sample image, purely a placeholder.
            import base64
            (upload/'demo.png').write_bytes(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a7xkAAAAASUVORK5CYII='))
            (upload/'demo_note.txt').write_text('DEMONSTRATION admission note only. Replace with a real uploaded document for an actual student.')
            db.execute('INSERT OR IGNORE INTO students(roll,name,address,mobile,parent_phone,photo,admission_note) VALUES(?,?,?,?,?,?,?)',('DEMO001','Demo Student','Sample address','9000000000','9000000001','demo.png','demo_note.txt'))
            sid=db.execute('SELECT id FROM students WHERE roll=?',('DEMO001',)).fetchone()[0]
            db.execute('INSERT OR IGNORE INTO users(username,password_hash,role,student_id) VALUES(?,?,?,?)',('student1',generate_password_hash('Student@123'),'student',sid))
        if not db.execute('SELECT 1 FROM allocations WHERE student_id=?',(sid,)).fetchone():
            room=db.execute('SELECT id FROM rooms WHERE hall_id=1 AND number=?',('101',)).fetchone()[0]
            admin=db.execute('SELECT id FROM users WHERE username=?',('admin',)).fetchone()[0]
            AllocationService.allocate(sid,room,admin)
    print('Sample data is ready. Run: python app.py')
    print('Admin: admin / Admin@123 | Student: student1 / Student@123')
    print('See README.md for all role accounts. Change demo passwords before using real data.')


if __name__ == '__main__':
    main()
