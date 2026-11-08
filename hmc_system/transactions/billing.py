"""Generate monthly bills and record component-based payments."""
from ..utilities.database import get_db
from ..utilities.audit import audit
from ..utilities.validation import month_value, now
from .bill import Bill

class BillingService:
    @staticmethod
    def generate(student_id, month, user_id):
        month = month_value(month)
        db = get_db()
        row = db.execute('SELECT r.rent,h.amenity,h.id hall_id FROM allocations a JOIN rooms r ON r.id=a.room_id JOIN halls h ON h.id=r.hall_id WHERE a.student_id=?', (student_id,)).fetchone()
        charge = db.execute('SELECT amount FROM mess_charges WHERE student_id=? AND month=?', (student_id,month)).fetchone()
        if not row:
            raise ValueError('Allocate a room before generating a bill.')
        if not charge:
            raise ValueError('The mess manager must enter charges for this month first (zero is allowed).')
        with db:
            db.execute('INSERT INTO bills(student_id,hall_id,month,rent,mess,amenity,created) VALUES(?,?,?,?,?,?,?)', (student_id,row['hall_id'],month,row['rent'],charge['amount'],row['amenity'],now()))
            audit(user_id,'BILL_GENERATED',f'student={student_id}; month={month}')

    @staticmethod
    def pay(bill_id, amount, user_id):
        if amount <= 0:
            raise ValueError('Payment must be greater than zero.')
        db = get_db()
        with db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM bills WHERE id=?',(bill_id,)).fetchone()
            if not row:
                raise ValueError('Bill not found.')
            paid = db.execute('SELECT coalesce(sum(rent),0) rent,coalesce(sum(mess),0) mess,coalesce(sum(amenity),0) amenity FROM payments WHERE bill_id=?',(bill_id,)).fetchone()
            bill = Bill(row['id'],row['rent'],row['mess'],row['amenity'],sum(paid))
            if amount > bill.balance:
                raise ValueError('Payment exceeds the outstanding balance.')
            # Consistent allocation rule: mess first, then rent, then amenities.
            parts = {}
            remaining = amount
            for component in ('mess','rent','amenity'):
                parts[component] = min(remaining,row[component]-paid[component])
                remaining -= parts[component]
            if parts['mess'] and db.execute('SELECT 1 FROM settlements WHERE hall_id=? AND month=?',(row['hall_id'],now()[:7])).fetchone():
                raise ValueError('Mess collections for this hall and month are closed by a settlement. Record payments before closing the collection month.')
            cur = db.execute('INSERT INTO payments(bill_id,rent,mess,amenity,created,user_id) VALUES(?,?,?,?,?,?)', (bill_id,parts['rent'],parts['mess'],parts['amenity'],now(),user_id))
            audit(user_id,'PAYMENT_RECORDED',f'bill={bill_id}; paise={amount}')
            return cur.lastrowid
