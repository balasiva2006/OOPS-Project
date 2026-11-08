"""Close a hall collection month and record its mess cheque handover."""
from ..utilities.database import get_db
from ..utilities.audit import audit
from ..utilities.validation import month_value, now

class SettlementService:
    @staticmethod
    def create(hall_id, month, manager, cheque, user_id):
        db = get_db()
        month = month_value(month)
        if month > now()[:7]:
            raise ValueError('A future collection month cannot be settled.')
        with db:
            db.execute('BEGIN IMMEDIATE')
            amount = db.execute('SELECT coalesce(sum(p.mess),0) FROM payments p JOIN bills b ON b.id=p.bill_id WHERE b.hall_id=? AND substr(p.created,1,7)=?',(hall_id,month)).fetchone()[0]
            if amount <= 0:
                raise ValueError('There are no mess collections in the selected collection month.')
            db.execute('INSERT INTO settlements(hall_id,month,amount,manager,cheque,created) VALUES(?,?,?,?,?,?)',(hall_id,month,amount,manager,cheque,now()))
            audit(user_id,'SETTLEMENT_RECORDED',f'hall={hall_id}; collection_month={month}; paise={amount}')
