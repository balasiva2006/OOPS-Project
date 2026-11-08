"""Allocate students while enforcing room capacity and uniqueness."""
from ..utilities.database import get_db
from ..utilities.audit import audit
from ..utilities.validation import now
from .room import Room

class AllocationService:
    @staticmethod
    def allocate(student_id, room_id, user_id):
        db = get_db()
        with db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT 1 FROM allocations WHERE student_id=?', (student_id,)).fetchone():
                raise ValueError('This student already has a room.')
            row = db.execute('SELECT r.id,r.capacity,count(a.id) occupied FROM rooms r LEFT JOIN allocations a ON a.room_id=r.id WHERE r.id=? GROUP BY r.id', (room_id,)).fetchone()
            if not row or not Room(**dict(row)).can_allocate():
                raise ValueError('The selected room is full or does not exist.')
            db.execute('INSERT INTO allocations(student_id,room_id,created) VALUES(?,?,?)', (student_id, room_id, now()))
            audit(user_id, 'ROOM_ALLOCATED', f'student={student_id}; room={room_id}')
