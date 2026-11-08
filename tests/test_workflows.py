"""Run: python -m unittest discover -s tests -v"""
import io
import os
import uuid
import psycopg
from psycopg import sql
import unittest
from werkzeug.security import generate_password_hash
from hmc_system import create_app
from hmc_system.utilities.database import get_db, transaction, init_db
from hmc_system.accommodation import AllocationService
from hmc_system.transactions import BillingService, SettlementService
from hmc_system.utilities.validation import money, now

class HMCWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database_url = os.environ.get('TEST_DATABASE_URL')
        if not cls.database_url:
            raise unittest.SkipTest('Set TEST_DATABASE_URL to run PostgreSQL workflow tests.')

    def setUp(self):
        self.schema = 'hmc_test_' + uuid.uuid4().hex
        self.admin_db = psycopg.connect(self.database_url, autocommit=True)
        self.admin_db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.addCleanup(self.cleanup_database)
        self.app = create_app({
            'TESTING': True,
            'SECRET_KEY': 'test-only-session-key',
            'DATABASE_URL': self.database_url,
            'DATABASE_OPTIONS': '-c search_path=' + self.schema,
        })
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)
        init_db()
        db=get_db()
        with transaction():
            for hid in (1,2):
                db.execute('INSERT INTO halls VALUES(%s,%s,%s,%s)',(hid,f'Hall {hid}',30000,'Reading room'))
                db.execute('INSERT INTO rooms VALUES(%s,%s,%s,%s,%s)',(hid,hid,'101',1,100000))
                db.execute('INSERT INTO students VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(hid,f'R{hid}',f'Student {hid}','Address','9000000000','9000000001','photo.png','note.pdf'))
            for uid,name,role,hid,sid in [(1,'admin','admin',None,None),(2,'student1','student',None,1),(3,'student2','student',None,2),(4,'warden1','warden',1,None),(5,'warden2','warden',2,None),(6,'mess1','mess_manager',1,None),(7,'chief','controlling_warden',None,None)]:
                db.execute('INSERT INTO users VALUES(%s,%s,%s,%s,%s,%s)',(uid,name,generate_password_hash('Password123'),role,hid,sid))
        for table in ('halls', 'rooms', 'students', 'users'):
            db.execute("SELECT setval(pg_get_serial_sequence(%s,'id'),100)", (table,))
        self.client=self.app.test_client()

    def cleanup_database(self):
        self.admin_db.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema)))
        self.admin_db.close()

    def login(self,uid):
        with self.client.session_transaction() as s:s.update(user_id=uid,csrf='test-token')

    def post(self,url,data=None,**kwargs):
        return self.client.post(url,data=dict(data or {},csrf='test-token'),**kwargs)

    def bill(self):
        AllocationService.allocate(1,1,1)
        with transaction():get_db().execute('INSERT INTO mess_charges(student_id,month,amount) VALUES(%s,%s,%s)',(1,now()[:7],200000))
        BillingService.generate(1,now()[:7],1)
        return get_db().execute('SELECT id FROM bills').fetchone()['id']

    def test_money_validation(self):
        self.assertEqual(money('123.45'),12345)
        for value in ('-1','NaN','Infinity','1.001','hello'):
            with self.assertRaises(ValueError):money(value)

    def test_full_room_and_duplicate_allocation(self):
        AllocationService.allocate(1,1,1)
        with self.assertRaises(ValueError):AllocationService.allocate(2,1,1)
        with self.assertRaises(ValueError):AllocationService.allocate(1,2,1)
        self.assertEqual(get_db().execute('SELECT count(*) AS total FROM allocations').fetchone()['total'],1)

    def test_duplicate_bill_and_missing_mess_charge(self):
        AllocationService.allocate(1,1,1);self.login(1)
        data={'student_id':'1','month':now()[:7]}
        self.assertEqual(self.post('/bills/generate',data).status_code,400)
        with transaction():get_db().execute('INSERT INTO mess_charges(student_id,month,amount) VALUES(%s,%s,%s)',(1,now()[:7],0))
        self.assertEqual(self.post('/bills/generate',data).status_code,302)
        self.assertEqual(self.post('/bills/generate',data).status_code,409)

    def test_partial_payment_and_overpayment(self):
        bid=self.bill();BillingService.pay(bid,250000,1)
        row=get_db().execute('SELECT * FROM payments').fetchone()
        self.assertEqual((row['mess'],row['rent'],row['amenity']),(200000,50000,0))
        with self.assertRaises(ValueError):BillingService.pay(bid,80001,1)
        BillingService.pay(bid,80000,1)
        self.assertEqual(get_db().execute('SELECT sum(rent+mess+amenity) AS total FROM payments').fetchone()['total'],330000)

    def test_private_records_and_documents(self):
        AllocationService.allocate(1,1,1);AllocationService.allocate(2,2,1)
        self.login(2)
        self.assertEqual(self.client.get('/students/2').status_code,403)
        self.assertEqual(self.client.get('/students/2/document/photo').status_code,403)
        self.assertEqual(self.client.get('/students/1').status_code,200)
        self.login(4)
        self.assertEqual(self.client.get('/students/2').status_code,403)
        self.assertNotIn(b'Student 2',self.client.get('/students').data)

    def test_complaint_and_hall_restrictions(self):
        AllocationService.allocate(1,1,1);self.login(2)
        self.assertEqual(self.post('/complaints/new',{'category':'Electrical','description':'Light is not working'}).status_code,302)
        self.login(5)
        self.assertEqual(self.client.get('/complaints/1').status_code,403)
        self.assertEqual(self.post('/complaints/1',{'status':'Resolved','atr':'Replaced bulb'}).status_code,403)
        self.login(4)
        self.assertEqual(self.post('/complaints/1',{'status':'Resolved','atr':'Replaced bulb'}).status_code,302)
        self.login(2)
        self.assertIn(b'Replaced bulb',self.client.get('/complaints/1').data)
        self.assertEqual(self.post('/complaints/1',{'status':'Open','atr':'attempt'}).status_code,403)

    def test_settlement_only_uses_collected_mess(self):
        bid=self.bill();BillingService.pay(bid,100000,1)
        SettlementService.create(1,now()[:7],'Manager One','CHQ001',1)
        self.assertEqual(get_db().execute('SELECT amount FROM settlements').fetchone()['amount'],100000)
        with self.assertRaises(ValueError):BillingService.pay(bid,10000,1)
        self.login(6)
        self.assertEqual(self.post('/settlements/1/acknowledge').status_code,302)
        self.assertEqual(get_db().execute('SELECT acknowledged FROM settlements').fetchone()['acknowledged'],1)

    def test_csrf_and_login(self):
        self.client.get('/login')
        self.assertEqual(self.client.post('/login',data={'username':'admin','password':'Password123'}).status_code,400)
        with self.client.session_transaction() as s:token=s['csrf']
        self.assertEqual(self.client.post('/login',data={'username':'admin','password':'Password123','csrf':token}).status_code,302)
        self.assertEqual(self.client.get('/dashboard').status_code,200)

    def test_registration_uploads_and_html_escaping(self):
        self.login(1)
        fields={'roll':'NEW1','name':'<script>alert(1)</script>','address':'Address','mobile':'9000000000','parent_phone':'9000000001','username':'newstudent','password':'Password123',
            'photo':(io.BytesIO(b'\x89PNG\r\n\x1a\nplaceholder'),'photo.png'),
            'admission_note':(io.BytesIO(b'%PDF-1.4 sample'),'note.pdf')}
        self.assertEqual(self.post('/students/register',fields,content_type='multipart/form-data').status_code,302)
        response=self.client.get('/students')
        self.assertIn(b'&lt;script&gt;',response.data)
        self.assertNotIn(b'<script>alert',response.data)
        sid=get_db().execute('SELECT id FROM students WHERE roll=%s',('NEW1',)).fetchone()['id']
        # A second application instance must read the committed database document.
        second_app = create_app(dict(self.app.config))
        second_client = second_app.test_client()
        with second_client.session_transaction() as session:
            session.update(user_id=1, csrf='second-instance')
        with second_app.app_context():
            with second_client.get(f'/students/{sid}/document/photo') as response:
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data, b'\x89PNG\r\n\x1a\nplaceholder')
                self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        with second_client.session_transaction() as session:
            session['user_id'] = 3
        with second_app.app_context():
            self.assertEqual(second_client.get(f'/students/{sid}/document/photo').status_code, 403)

    def test_all_pages_and_print_reports(self):
        bid=self.bill();pid=BillingService.pay(bid,330000,1)
        SettlementService.create(1,now()[:7],'Manager One','CHQ001',1)
        with transaction():get_db().execute('INSERT INTO complaints(student_id,hall_id,category,description,created) VALUES(1,1,%s,%s,%s)',('Electrical','Bulb',now()))
        for uid,urls in {
            1:['/','/dashboard','/halls','/rooms','/students','/students/register','/students/1','/allocate','/allotment/1','/mess-charges','/bills/generate','/bills','/bills/1/pay','/receipts',f'/receipt/{pid}','/complaints','/complaints/1','/occupancy','/settlements','/settlements/1/print','/accounts','/audit','/staff','/change-password','/static/css/style.css'],
            2:['/dashboard','/students/1','/allotment/1','/bills','/receipts',f'/receipt/{pid}','/complaints','/complaints/new','/complaints/1'],
            4:['/dashboard','/students','/rooms','/halls','/accounts','/occupancy','/bills','/complaints/1','/settlements'],
            6:['/dashboard','/mess-charges','/settlements','/settlements/1/print'],
            7:['/dashboard','/occupancy','/accounts','/students','/complaints']
        }.items():
            self.login(uid)
            for url in urls:
                with self.subTest(user=uid,url=url):
                    with self.client.get(url) as response:
                        self.assertEqual(response.status_code,200)
        self.assertEqual(get_db().execute('SELECT count(*) AS total FROM audit').fetchone()['total'],4)

    def test_failed_registration_rolls_back_documents(self):
        self.login(1)
        fields = {
            'roll': 'FAILED', 'name': 'Student', 'address': 'Address',
            'mobile': '9000000000', 'parent_phone': '9000000001',
            'username': 'admin', 'password': 'Password123',
            'photo': (io.BytesIO(b'\x89PNG\r\n\x1a\nphoto'), 'photo.png'),
            'admission_note': (io.BytesIO(b'%PDF-1.4 note'), 'note.pdf'),
        }
        response = self.post('/students/register', fields, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 409)
        self.assertIsNone(get_db().execute('SELECT id FROM students WHERE roll=%s', ('FAILED',)).fetchone())
        self.assertEqual(get_db().execute('SELECT count(*) AS total FROM documents').fetchone()['total'], 0)

    def test_large_valid_bill_does_not_overflow_database_arithmetic(self):
        AllocationService.allocate(1, 1, 1)
        amount = money('10000000')
        with transaction() as db:
            db.execute('UPDATE rooms SET rent=%s WHERE id=1', (amount,))
            db.execute('UPDATE halls SET amenity=%s WHERE id=1', (amount,))
            db.execute('INSERT INTO mess_charges(student_id,month,amount) VALUES(%s,%s,%s)', (1, now()[:7], amount))
        BillingService.generate(1, now()[:7], 1)
        self.login(1)
        self.assertEqual(self.client.get('/bills').status_code, 200)
        self.assertEqual(self.client.get('/accounts').status_code, 200)
        BillingService.pay(1, amount, 1)
        self.assertEqual(self.client.get('/receipts').status_code, 200)

    def test_concurrent_allocations_do_not_overbook(self):
        from concurrent.futures import ThreadPoolExecutor

        def allocate(student_id):
            with self.app.app_context():
                try:
                    AllocationService.allocate(student_id, 1, 1)
                    return 'allocated'
                except ValueError:
                    return 'full'

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(allocate, (1, 2)))
        self.assertCountEqual(results, ['allocated', 'full'])

    def test_concurrent_payments_do_not_overpay(self):
        from concurrent.futures import ThreadPoolExecutor
        bill_id = self.bill()

        def pay(_):
            with self.app.app_context():
                try:
                    BillingService.pay(bill_id, 330000, 1)
                    return 'paid'
                except ValueError:
                    return 'rejected'

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(pay, (1, 2)))
        self.assertCountEqual(results, ['paid', 'rejected'])

    def test_seed_can_be_repeated_and_uses_database_documents(self):
        from hmc_system.seed import seed_demo
        seed_demo()
        original = get_db().execute('SELECT password_hash FROM users WHERE username=%s', ('student1',)).fetchone()
        seed_demo()
        repeated = get_db().execute('SELECT password_hash FROM users WHERE username=%s', ('student1',)).fetchone()
        self.assertEqual(original, repeated)
        self.assertEqual(get_db().execute('SELECT count(*) AS total FROM documents').fetchone()['total'], 2)


if __name__=='__main__':unittest.main()
