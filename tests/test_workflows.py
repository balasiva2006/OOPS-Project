"""Run: python -m unittest discover -s tests -v"""
import io
import tempfile
import unittest
from pathlib import Path
from werkzeug.security import generate_password_hash
from hmc_system import create_app
from hmc_system.utilities.database import get_db
from hmc_system.accommodation import AllocationService
from hmc_system.transactions import BillingService, SettlementService
from hmc_system.utilities.validation import money, now

class HMCWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.app=create_app({'TESTING':True,'DATABASE':str(Path(self.temp.name)/'test.db'),'UPLOAD_FOLDER':str(Path(self.temp.name)/'uploads')})
        self.ctx=self.app.app_context();self.ctx.push()
        db=get_db()
        with db:
            for hid in (1,2):
                db.execute('INSERT INTO halls VALUES(?,?,?,?)',(hid,f'Hall {hid}',30000,'Reading room'))
                db.execute('INSERT INTO rooms VALUES(?,?,?,?,?)',(hid,hid,'101',1,100000))
                db.execute('INSERT INTO students VALUES(?,?,?,?,?,?,?,?)',(hid,f'R{hid}',f'Student {hid}','Address','9000000000','9000000001','photo.png','note.pdf'))
            for uid,name,role,hid,sid in [(1,'admin','admin',None,None),(2,'student1','student',None,1),(3,'student2','student',None,2),(4,'warden1','warden',1,None),(5,'warden2','warden',2,None),(6,'mess1','mess_manager',1,None),(7,'chief','controlling_warden',None,None)]:
                db.execute('INSERT INTO users VALUES(?,?,?,?,?,?)',(uid,name,generate_password_hash('Password123'),role,hid,sid))
        self.client=self.app.test_client()

    def tearDown(self):
        self.ctx.pop();self.temp.cleanup()

    def login(self,uid):
        with self.client.session_transaction() as s:s.update(user_id=uid,csrf='test-token')

    def post(self,url,data=None,**kwargs):
        return self.client.post(url,data=dict(data or {},csrf='test-token'),**kwargs)

    def bill(self):
        AllocationService.allocate(1,1,1)
        with get_db():get_db().execute('INSERT INTO mess_charges(student_id,month,amount) VALUES(?,?,?)',(1,now()[:7],200000))
        BillingService.generate(1,now()[:7],1)
        return get_db().execute('SELECT id FROM bills').fetchone()[0]

    def test_money_validation(self):
        self.assertEqual(money('123.45'),12345)
        for value in ('-1','NaN','Infinity','1.001','hello'):
            with self.assertRaises(ValueError):money(value)

    def test_full_room_and_duplicate_allocation(self):
        AllocationService.allocate(1,1,1)
        with self.assertRaises(ValueError):AllocationService.allocate(2,1,1)
        with self.assertRaises(ValueError):AllocationService.allocate(1,2,1)
        self.assertEqual(get_db().execute('SELECT count(*) FROM allocations').fetchone()[0],1)

    def test_duplicate_bill_and_missing_mess_charge(self):
        AllocationService.allocate(1,1,1);self.login(1)
        data={'student_id':'1','month':now()[:7]}
        self.assertEqual(self.post('/bills/generate',data).status_code,400)
        with get_db():get_db().execute('INSERT INTO mess_charges(student_id,month,amount) VALUES(?,?,?)',(1,now()[:7],0))
        self.assertEqual(self.post('/bills/generate',data).status_code,302)
        self.assertEqual(self.post('/bills/generate',data).status_code,409)

    def test_partial_payment_and_overpayment(self):
        bid=self.bill();BillingService.pay(bid,250000,1)
        row=get_db().execute('SELECT * FROM payments').fetchone()
        self.assertEqual((row['mess'],row['rent'],row['amenity']),(200000,50000,0))
        with self.assertRaises(ValueError):BillingService.pay(bid,80001,1)
        BillingService.pay(bid,80000,1)
        self.assertEqual(get_db().execute('SELECT sum(rent+mess+amenity) FROM payments').fetchone()[0],330000)

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
        self.assertEqual(get_db().execute('SELECT amount FROM settlements').fetchone()[0],100000)
        with self.assertRaises(ValueError):BillingService.pay(bid,10000,1)
        self.login(6)
        self.assertEqual(self.post('/settlements/1/acknowledge').status_code,302)
        self.assertEqual(get_db().execute('SELECT acknowledged FROM settlements').fetchone()[0],1)

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
        sid=get_db().execute('SELECT id FROM students WHERE roll=?',('NEW1',)).fetchone()[0]
        with self.client.get(f'/students/{sid}/document/photo') as response:
            self.assertEqual(response.status_code,200)

    def test_all_pages_and_print_reports(self):
        bid=self.bill();pid=BillingService.pay(bid,330000,1)
        SettlementService.create(1,now()[:7],'Manager One','CHQ001',1)
        with get_db():get_db().execute('INSERT INTO complaints(student_id,hall_id,category,description,created) VALUES(1,1,?,?,?)',('Electrical','Bulb',now()))
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
        self.assertEqual(get_db().execute('SELECT count(*) FROM audit').fetchone()[0],4)

if __name__=='__main__':unittest.main()
