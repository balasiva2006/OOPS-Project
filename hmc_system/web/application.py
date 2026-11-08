"""HMC educational mini project. Run: python app.py"""
from pathlib import Path
from functools import wraps
import os
import secrets
import psycopg
from dotenv import load_dotenv
from io import BytesIO
import uuid
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort, send_file
from werkzeug.security import generate_password_hash
from ..utilities.database import transaction, get_db, close_db, register_commands
from ..accounts import User
from ..accommodation import AllocationService
from ..transactions import BillingService, SettlementService
from ..utilities.audit import audit
from ..utilities.validation import money, month_value, now
from ..utilities.documents import store_document

ROLES = ('admin','student','mess_manager','warden','controlling_warden')

def create_app(test_config=None):
    # Resolve from the project directory so the existing assets and data stay usable.
    project_root = Path(__file__).resolve().parents[2]
    app = Flask(__name__,
        template_folder=str(project_root / 'templates'),
        static_folder=str(project_root / 'public' / 'static'),
        static_url_path='/static',
        instance_path=str(project_root / 'instance'),
        instance_relative_config=True)
    load_dotenv(project_root / '.env')
    app.config.update(
        SECRET_KEY=os.environ.get('HMC_SECRET_KEY'),
        DATABASE_URL=os.environ.get('DATABASE_URL'),
        MAX_CONTENT_LENGTH=4 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Lax',
        SESSION_COOKIE_SECURE=bool(os.environ.get('VERCEL')),
    )
    if test_config:
        app.config.update(test_config)
    if not app.config['DATABASE_URL']:
        raise RuntimeError('Set DATABASE_URL in .env or your hosting environment.')
    if not app.config['SECRET_KEY']:
        raise RuntimeError('Set HMC_SECRET_KEY to a private random value.')
    app.teardown_appcontext(close_db)
    register_commands(app)

    @app.template_filter('rupees')
    def rupees(value):
        return f'Rs. {int(value or 0)/100:,.2f}'

    @app.before_request
    def load_user():
        g.user = None
        if session.get('user_id'):
            row=get_db().execute('SELECT * FROM users WHERE id=%s',(session['user_id'],)).fetchone()
            if row:
                g.user=User(**dict(row))
        session.setdefault('csrf',secrets.token_hex(24))
        if request.method == 'POST' and not secrets.compare_digest(session['csrf'],request.form.get('csrf','')):
            abort(400,description='Invalid form token. Refresh the page and try again.')

    @app.context_processor
    def context():
        return dict(user=g.user,csrf=session.get('csrf',''),current_month=now()[:7])

    def roles(*allowed):
        def decorator(fn):
            @wraps(fn)
            def wrapped(*args,**kwargs):
                if not g.user:
                    return redirect(url_for('login'))
                if allowed and g.user.role not in allowed:
                    abort(403)
                return fn(*args,**kwargs)
            return wrapped
        return decorator

    def hall_access(hall_id):
        if g.user.role in ('warden','mess_manager') and g.user.hall_id != hall_id:
            abort(403)

    def student_access(student_id):
        if g.user.role=='student':
            if g.user.student_id != student_id:
                abort(403)
        elif g.user.role in ('warden','mess_manager'):
            row=get_db().execute('SELECT r.hall_id FROM allocations a JOIN rooms r ON r.id=a.room_id WHERE a.student_id=%s',(student_id,)).fetchone()
            if not row or row['hall_id'] != g.user.hall_id:
                abort(403)

    def required(name):
        value=request.form.get(name,'').strip()
        if not value or len(value)>3000:
            raise ValueError(f'Provide a valid {name.replace("_"," ")}.')
        return value

    def positive_id(name):
        try:
            value=int(required(name))
            if value<=0: raise ValueError
            return value
        except ValueError:
            raise ValueError(f'Select a valid {name.replace("_"," ")}.')

    def form(title,fields,back='dashboard',note=''):
        return render_template('form.html',title=title,fields=fields,back=back,note=note)

    def options(sql,args=()):
        return [tuple(row.values()) for row in get_db().execute(sql,args).fetchall()]

    def save_upload(field,photo=False):
        upload=request.files.get(field)
        if not upload or not upload.filename:
            raise ValueError(f'Please upload {field.replace("_"," ")}.')
        header=upload.stream.read(12)
        upload.stream.seek(0)
        ext='.png' if header.startswith(b'\x89PNG\r\n\x1a\n') else '.jpg' if header.startswith(b'\xff\xd8\xff') else '.pdf' if header.startswith(b'%PDF-') and not photo else None
        if not ext:
            raise ValueError('Photographs must be PNG/JPEG. Admission notes may also be PDF.')
        name=uuid.uuid4().hex+ext
        content_type = {'.png': 'image/png', '.jpg': 'image/jpeg', '.pdf': 'application/pdf'}[ext]
        store_document(name, content_type, upload.read())
        return name

    @app.route('/')
    def home():
        return render_template('home.html')

    @app.route('/login',methods=['GET','POST'])
    def login():
        if request.method=='POST':
            row=get_db().execute('SELECT * FROM users WHERE username=%s',(request.form.get('username','').strip(),)).fetchone()
            user=User(**dict(row)) if row else None
            if user and user.verify_password(request.form.get('password','')):
                session.clear()
                session['user_id']=user.id
                session['csrf']=secrets.token_hex(24)
                return redirect(url_for('dashboard'))
            flash('Incorrect username or password.','error')
        return render_template('login.html')

    @app.post('/logout')
    def logout():
        session.clear()
        return redirect(url_for('home'))

    @app.get('/dashboard')
    @roles(*ROLES)
    def dashboard():
        return render_template('dashboard.html')

    @app.route('/halls',methods=['GET','POST'])
    @roles('admin','warden','controlling_warden')
    def halls():
        if request.method=='POST':
            if g.user.role!='admin': abort(403)
            with transaction():
                name=required('name')
                get_db().execute('INSERT INTO halls(name,amenity,amenities) VALUES(%s,%s,%s)',(name,money(required('amenity')),required('amenities')))
                audit(g.user.id,'HALL_ADDED',name)
            flash('Hall added.','success')
            return redirect(url_for('halls'))
        rows=get_db().execute('SELECT * FROM halls WHERE (CAST(%s AS INTEGER) IS NULL OR id=%s)',(g.user.hall_id if g.user.role=='warden' else None,g.user.hall_id)).fetchall()
        return render_template('halls.html',rows=rows)

    @app.route('/rooms',methods=['GET','POST'])
    @roles('admin','warden','controlling_warden')
    def rooms():
        if request.method=='POST':
            if g.user.role!='admin': abort(403)
            capacity=positive_id('capacity')
            if capacity>4: raise ValueError('Capacity must be between 1 and 4.')
            with transaction():
                get_db().execute('INSERT INTO rooms(hall_id,number,capacity,rent) VALUES(%s,%s,%s,%s)',(positive_id('hall_id'),required('number'),capacity,money(required('rent'))))
                audit(g.user.id,'ROOM_ADDED',required('number'))
            flash('Room added.','success')
            return redirect(url_for('rooms'))
        rows=get_db().execute('SELECT r.*,h.name hall,count(a.id) occupied FROM rooms r JOIN halls h ON h.id=r.hall_id LEFT JOIN allocations a ON a.room_id=r.id WHERE (CAST(%s AS INTEGER) IS NULL OR h.id=%s) GROUP BY r.id,h.name ORDER BY h.name,r.number',(g.user.hall_id if g.user.role=='warden' else None,g.user.hall_id)).fetchall()
        return render_template('rooms.html',rows=rows,halls=options('SELECT id,name FROM halls'))

    @app.get('/students')
    @roles('admin','warden','controlling_warden')
    def students():
        rows=get_db().execute('SELECT s.*,h.name hall,r.number room FROM students s LEFT JOIN allocations a ON a.student_id=s.id LEFT JOIN rooms r ON r.id=a.room_id LEFT JOIN halls h ON h.id=r.hall_id WHERE (CAST(%s AS INTEGER) IS NULL OR h.id=%s) ORDER BY s.id DESC',(g.user.hall_id if g.user.role=='warden' else None,g.user.hall_id)).fetchall()
        return render_template('students.html',rows=rows)

    @app.route('/students/register',methods=['GET','POST'])
    @roles('admin')
    def register_student():
        if request.method=='POST':
            data={key:required(key) for key in ('roll','name','address','mobile','parent_phone','username','password')}
            if len(data['password'])<8: raise ValueError('Use a password with at least 8 characters.')
            for key in ('mobile','parent_phone'):
                if not data[key].replace('+','').replace(' ','').replace('-','').isdigit() or len(data[key])<8:
                    raise ValueError('Enter valid phone numbers.')
            with transaction():
                photo = save_upload('photo', True)
                note = save_upload('admission_note')
                sid=get_db().execute('INSERT INTO students(roll,name,address,mobile,parent_phone,photo,admission_note) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id',tuple(data[k] for k in ('roll','name','address','mobile','parent_phone'))+(photo,note)).fetchone()['id']
                get_db().execute('INSERT INTO users(username,password_hash,role,student_id) VALUES(%s,%s,%s,%s)',(data['username'],generate_password_hash(data['password']),'student',sid))
                audit(g.user.id,'STUDENT_REGISTERED',f'student={sid}')
            flash('Student and login account created.','success')
            return redirect(url_for('students'))
        return form('Register student',[
            ('roll','Roll number','text',None),('name','Full name','text',None),('address','Permanent address','textarea',None),
            ('mobile','Mobile number','tel',None),('parent_phone',"Parent’s phone",'tel',None),('photo','Photograph (PNG/JPEG)','file',None),
            ('admission_note','Admission note (PDF/PNG/JPEG)','file',None),('username','Student login username','text',None),('password','Initial password (8+ characters)','password',None)],'students')

    @app.get('/students/<int:sid>')
    @roles(*ROLES)
    def profile(sid):
        student_access(sid)
        row=get_db().execute('SELECT s.*,h.name hall,r.number room FROM students s LEFT JOIN allocations a ON a.student_id=s.id LEFT JOIN rooms r ON r.id=a.room_id LEFT JOIN halls h ON h.id=r.hall_id WHERE s.id=%s',(sid,)).fetchone()
        if not row: abort(404)
        return render_template('profile.html',row=row)

    @app.get('/students/<int:sid>/document/<kind>')
    @roles('admin','student','warden','controlling_warden')
    def document(sid,kind):
        student_access(sid)
        if kind not in ('photo','admission_note'): abort(404)
        row=get_db().execute('SELECT * FROM students WHERE id=%s',(sid,)).fetchone()
        if not row: abort(404)
        document = get_db().execute(
            'SELECT content_type,data FROM documents WHERE name=%s', (row[kind],)
        ).fetchone()
        if not document:
            abort(404)
        response = send_file(
            BytesIO(bytes(document['data'])),
            mimetype=document['content_type'],
            download_name=row[kind],
            as_attachment=True,
            max_age=0,
        )
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.route('/allocate',methods=['GET','POST'])
    @roles('admin')
    def allocate():
        if request.method=='POST':
            AllocationService.allocate(positive_id('student_id'),positive_id('room_id'),g.user.id)
            flash('Room allocated. Open the student profile to print the letter.','success')
            return redirect(url_for('students'))
        return form('Allocate a room',[
            ('student_id','Student','select',options("SELECT s.id,s.roll||' — '||s.name FROM students s WHERE NOT EXISTS(SELECT 1 FROM allocations a WHERE a.student_id=s.id)")),
            ('room_id','Room','select',options("SELECT r.id,h.name||' / '||r.number||' ('||(r.capacity-count(a.id))||' beds free)' FROM rooms r JOIN halls h ON h.id=r.hall_id LEFT JOIN allocations a ON a.room_id=r.id GROUP BY r.id,h.name HAVING count(a.id)<r.capacity"))],'students')

    @app.get('/allotment/<int:sid>')
    @roles('admin','student','warden','controlling_warden')
    def allotment(sid):
        student_access(sid)
        row=get_db().execute('SELECT s.*,r.number room,h.name hall,a.created FROM allocations a JOIN students s ON s.id=a.student_id JOIN rooms r ON r.id=a.room_id JOIN halls h ON h.id=r.hall_id WHERE s.id=%s',(sid,)).fetchone()
        if not row: abort(404)
        return render_template('print.html',title='Room allotment letter',kind='allotment',row=row)

    @app.route('/mess-charges',methods=['GET','POST'])
    @roles('admin','mess_manager')
    def mess_charges():
        if request.method=='POST':
            sid=positive_id('student_id'); student_access(sid)
            month=month_value(required('month')); amount=money(required('amount'))
            with transaction():
                if get_db().execute('SELECT 1 FROM bills WHERE student_id=%s AND month=%s',(sid,month)).fetchone():
                    raise ValueError('A bill already exists. Posted bill charges cannot be changed.')
                get_db().execute('INSERT INTO mess_charges(student_id,month,amount) VALUES(%s,%s,%s) ON CONFLICT(student_id,month) DO UPDATE SET amount=excluded.amount',(sid,month,amount))
                audit(g.user.id,'MESS_CHARGE_SET',f'student={sid}; month={month}; paise={amount}')
            flash('Mess charge saved.','success')
            return redirect(url_for('mess_charges'))
        choices=options("SELECT s.id,s.roll||' — '||s.name FROM students s JOIN allocations a ON a.student_id=s.id JOIN rooms r ON r.id=a.room_id WHERE (CAST(%s AS INTEGER) IS NULL OR r.hall_id=%s)",(g.user.hall_id if g.user.role=='mess_manager' else None,g.user.hall_id))
        return form('Enter monthly mess charge',[('student_id','Student','select',choices),('month','Billing month','month',None),('amount','Mess charge (Rs.)','number',None)],note='Enter zero explicitly if there is no mess charge. Charges can be revised only before a bill is generated.')

    @app.route('/bills/generate',methods=['GET','POST'])
    @roles('admin')
    def generate_bill():
        if request.method=='POST':
            BillingService.generate(positive_id('student_id'),required('month'),g.user.id)
            flash('Monthly bill generated.','success')
            return redirect(url_for('bills'))
        return form('Generate monthly bill',[('student_id','Student','select',options("SELECT id,roll||' — '||name FROM students")),('month','Billing month','month',None)],'bills',note='Room rent and amenity charges are copied into this bill. Later rate changes will not alter it.')

    @app.get('/bills')
    @roles('admin','student','warden','controlling_warden')
    def bills():
        rows=get_db().execute('SELECT b.*,s.name,s.roll,b.rent+b.mess+b.amenity total,coalesce((SELECT sum(p.rent+p.mess+p.amenity) FROM payments p WHERE p.bill_id=b.id),0) paid FROM bills b JOIN students s ON s.id=b.student_id WHERE (CAST(%s AS INTEGER) IS NULL OR b.student_id=%s) AND (CAST(%s AS INTEGER) IS NULL OR b.hall_id=%s) ORDER BY b.month DESC,b.id DESC',(g.user.student_id if g.user.role=='student' else None,g.user.student_id,g.user.hall_id if g.user.role=='warden' else None,g.user.hall_id)).fetchall()
        return render_template('bills.html',rows=rows)

    @app.route('/bills/<int:bid>/pay',methods=['GET','POST'])
    @roles('admin')
    def pay(bid):
        row=get_db().execute('SELECT b.*,s.name,b.rent+b.mess+b.amenity-coalesce((SELECT sum(p.rent+p.mess+p.amenity) FROM payments p WHERE p.bill_id=b.id),0) balance FROM bills b JOIN students s ON s.id=b.student_id WHERE b.id=%s',(bid,)).fetchone()
        if not row: abort(404)
        if request.method=='POST':
            pid=BillingService.pay(bid,money(required('amount')),g.user.id)
            flash('Payment recorded.','success')
            return redirect(url_for('receipt',pid=pid))
        return form(f'Payment — {row["name"]}', [('amount','Payment amount (Rs.)','number',None)],'bills',note=f'Outstanding: Rs. {row["balance"]/100:.2f}. Payments cover mess first, then rent, then amenities.')

    @app.get('/receipts')
    @roles('admin','student','warden','controlling_warden')
    def receipts():
        rows=get_db().execute('SELECT p.*,s.name,b.month,p.rent+p.mess+p.amenity total FROM payments p JOIN bills b ON b.id=p.bill_id JOIN students s ON s.id=b.student_id WHERE (CAST(%s AS INTEGER) IS NULL OR b.student_id=%s) AND (CAST(%s AS INTEGER) IS NULL OR b.hall_id=%s) ORDER BY p.id DESC',(g.user.student_id if g.user.role=='student' else None,g.user.student_id,g.user.hall_id if g.user.role=='warden' else None,g.user.hall_id)).fetchall()
        return render_template('receipts.html',rows=rows)

    @app.get('/receipt/<int:pid>')
    @roles('admin','student','warden','controlling_warden')
    def receipt(pid):
        row=get_db().execute('SELECT p.*,b.student_id,b.hall_id,b.month,s.name,s.roll FROM payments p JOIN bills b ON b.id=p.bill_id JOIN students s ON s.id=b.student_id WHERE p.id=%s',(pid,)).fetchone()
        if not row: abort(404)
        if g.user.role=='student': student_access(row['student_id'])
        else: hall_access(row['hall_id'])
        return render_template('print.html',title='Payment receipt',kind='receipt',row=row)

    @app.route('/complaints/new',methods=['GET','POST'])
    @roles('student')
    def new_complaint():
        allocation=get_db().execute('SELECT r.hall_id FROM allocations a JOIN rooms r ON r.id=a.room_id WHERE a.student_id=%s',(g.user.student_id,)).fetchone()
        if not allocation: raise ValueError('A room allocation is needed before submitting a hall complaint.')
        categories=['Electrical','Plumbing','Water filter','Room repair','Staff behaviour','Mess','Other']
        if request.method=='POST':
            category=required('category')
            if category not in categories: raise ValueError('Choose a valid category.')
            with transaction():
                get_db().execute('INSERT INTO complaints(student_id,hall_id,category,description,created) VALUES(%s,%s,%s,%s,%s)',(g.user.student_id,allocation['hall_id'],category,required('description'),now()))
                audit(g.user.id,'COMPLAINT_SUBMITTED',category)
            return redirect(url_for('complaints'))
        return form('Submit complaint',[('category','Category','select',[(c,c) for c in categories]),('description','Explain the issue','textarea',None)],'complaints')

    @app.get('/complaints')
    @roles('admin','student','warden','controlling_warden')
    def complaints():
        rows=get_db().execute('SELECT c.*,s.name,h.name hall FROM complaints c JOIN students s ON s.id=c.student_id JOIN halls h ON h.id=c.hall_id WHERE (CAST(%s AS INTEGER) IS NULL OR c.student_id=%s) AND (CAST(%s AS INTEGER) IS NULL OR c.hall_id=%s) ORDER BY c.id DESC',(g.user.student_id if g.user.role=='student' else None,g.user.student_id,g.user.hall_id if g.user.role=='warden' else None,g.user.hall_id)).fetchall()
        return render_template('complaints.html',rows=rows)

    @app.route('/complaints/<int:cid>',methods=['GET','POST'])
    @roles('admin','student','warden','controlling_warden')
    def complaint_detail(cid):
        row=get_db().execute('SELECT c.*,s.name FROM complaints c JOIN students s ON s.id=c.student_id WHERE c.id=%s',(cid,)).fetchone()
        if not row: abort(404)
        if g.user.role=='student':
            if row['student_id']!=g.user.student_id: abort(403)
        else: hall_access(row['hall_id'])
        if request.method=='POST':
            if g.user.role not in ('admin','warden'): abort(403)
            status=required('status'); atr=required('atr')
            if status not in ('Open','In progress','Resolved'): raise ValueError('Invalid status.')
            with transaction():
                get_db().execute('UPDATE complaints SET status=%s,atr=%s WHERE id=%s',(status,atr,cid))
                audit(g.user.id,'ATR_UPDATED',f'complaint={cid}; status={status}; report={atr}')
            return redirect(url_for('complaint_detail',cid=cid))
        return render_template('complaint_detail.html',row=row)

    @app.get('/occupancy')
    @roles('admin','warden','controlling_warden')
    def occupancy():
        rows=get_db().execute('SELECT h.name hall,r.number,r.capacity,count(a.id) occupied FROM rooms r JOIN halls h ON h.id=r.hall_id LEFT JOIN allocations a ON a.room_id=r.id WHERE (CAST(%s AS INTEGER) IS NULL OR h.id=%s) GROUP BY r.id,h.name ORDER BY h.name,r.number',(g.user.hall_id if g.user.role=='warden' else None,g.user.hall_id)).fetchall()
        return render_template('occupancy.html',rows=rows)

    @app.route('/settlements',methods=['GET','POST'])
    @roles('admin','warden','controlling_warden','mess_manager')
    def settlements():
        if request.method=='POST':
            if g.user.role!='admin': abort(403)
            SettlementService.create(positive_id('hall_id'),required('month'),required('manager'),required('cheque'),g.user.id)
            flash('Settlement recorded. Print the cheque and obtain a signed acknowledgement.','success')
            return redirect(url_for('settlements'))
        rows=get_db().execute('SELECT t.*,h.name hall FROM settlements t JOIN halls h ON h.id=t.hall_id WHERE (CAST(%s AS INTEGER) IS NULL OR t.hall_id=%s) ORDER BY t.id DESC',(g.user.hall_id if g.user.role in ('warden','mess_manager') else None,g.user.hall_id)).fetchall()
        return render_template('settlements.html',rows=rows,halls=options('SELECT id,name FROM halls'))

    @app.post('/settlements/<int:tid>/acknowledge')
    @roles('mess_manager')
    def acknowledge(tid):
        row=get_db().execute('SELECT * FROM settlements WHERE id=%s',(tid,)).fetchone()
        if not row: abort(404)
        hall_access(row['hall_id'])
        with transaction():
            get_db().execute('UPDATE settlements SET acknowledged=1,acknowledged_at=%s WHERE id=%s',(now(),tid))
            audit(g.user.id,'SETTLEMENT_ACKNOWLEDGED',f'settlement={tid}')
        return redirect(url_for('settlements'))

    @app.get('/settlements/<int:tid>/print')
    @roles('admin','warden','controlling_warden','mess_manager')
    def settlement_print(tid):
        row=get_db().execute('SELECT t.*,h.name hall FROM settlements t JOIN halls h ON h.id=t.hall_id WHERE t.id=%s',(tid,)).fetchone()
        if not row: abort(404)
        hall_access(row['hall_id'])
        return render_template('print.html',title='Mess settlement sheet and cheque details',kind='settlement',row=row)

    @app.get('/accounts')
    @roles('admin','warden','controlling_warden')
    def accounts():
        year=request.args.get('year',now()[:4])
        if not year.isdigit() or not 2000<=int(year)<=2100: raise ValueError('Choose a valid year.')
        selected=g.user.hall_id if g.user.role=='warden' else None
        rows=[]
        for hall in get_db().execute('SELECT * FROM halls WHERE (CAST(%s AS INTEGER) IS NULL OR id=%s)',(selected,selected)):
            hid=hall['id']
            billed=get_db().execute('SELECT coalesce(sum(rent+mess+amenity),0) AS total FROM bills WHERE hall_id=%s AND substr(month,1,4)=%s',(hid,year)).fetchone()['total']
            paid_on_bills=get_db().execute('SELECT coalesce(sum(p.rent+p.mess+p.amenity),0) AS total FROM payments p JOIN bills b ON b.id=p.bill_id WHERE b.hall_id=%s AND substr(b.month,1,4)=%s',(hid,year)).fetchone()['total']
            cash=get_db().execute('SELECT coalesce(sum(p.rent+p.mess+p.amenity),0) AS total,coalesce(sum(p.mess),0) AS mess FROM payments p JOIN bills b ON b.id=p.bill_id WHERE b.hall_id=%s AND substr(p.created,1,4)=%s',(hid,year)).fetchone()
            settled=get_db().execute('SELECT coalesce(sum(amount),0) AS total FROM settlements WHERE hall_id=%s AND substr(created,1,4)=%s',(hid,year)).fetchone()['total']
            rows.append(dict(hall=hall['name'],billed=billed,paid=paid_on_bills,outstanding=billed-paid_on_bills,cash=cash['total'],mess=cash['mess'],settled=settled,retained=cash['total']-settled))
        return render_template('accounts.html',rows=rows,year=year)

    @app.get('/audit')
    @roles('admin')
    def audit_log():
        rows=get_db().execute('SELECT a.*,u.username FROM audit a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 300').fetchall()
        return render_template('audit.html',rows=rows)

    @app.route('/staff',methods=['GET','POST'])
    @roles('admin')
    def staff():
        if request.method=='POST':
            role=required('role')
            if role not in ('admin','warden','mess_manager','controlling_warden'):
                raise ValueError('Invalid staff role.')
            password=required('password')
            if len(password)<8: raise ValueError('Use at least 8 characters.')
            hall_id=positive_id('hall_id') if role in ('warden','mess_manager') else None
            with transaction():
                get_db().execute('INSERT INTO users(username,password_hash,role,hall_id) VALUES(%s,%s,%s,%s)',
                    (required('username'),generate_password_hash(password),role,hall_id))
                audit(g.user.id,'STAFF_ACCOUNT_CREATED',f'username={required("username")}; role={role}')
            flash('Staff account created.','success')
            return redirect(url_for('staff'))
        return form('Create staff account',[
            ('username','Username','text',None),('password','Initial password (8+ characters)','password',None),
            ('role','Role','select',[(r,r.replace('_',' ')) for r in ('warden','mess_manager','controlling_warden','admin')]),
            ('hall_id','Hall (used for warden and mess manager)','select',options('SELECT id,name FROM halls'))],
            note='Hall wardens and mess managers are restricted to their assigned hall. Student accounts are created during registration.')

    @app.route('/change-password',methods=['GET','POST'])
    @roles(*ROLES)
    def change_password():
        if request.method=='POST':
            if not g.user.verify_password(required('old_password')): raise ValueError('Current password is incorrect.')
            password=required('password')
            if len(password)<8: raise ValueError('Use at least 8 characters.')
            with transaction():
                get_db().execute('UPDATE users SET password_hash=%s WHERE id=%s',(generate_password_hash(password),g.user.id))
                audit(g.user.id,'PASSWORD_CHANGED','Password changed by account owner')
            flash('Password changed.','success')
            return redirect(url_for('dashboard'))
        return form('Change password',[('old_password','Current password','password',None),('password','New password (8+ characters)','password',None)])

    @app.errorhandler(ValueError)
    def invalid(error):
        get_db().rollback()
        return render_template('error.html',code=400,message=str(error)),400

    @app.errorhandler(psycopg.IntegrityError)
    def conflict(error):
        get_db().rollback()
        return render_template('error.html',code=409,message='This record already exists or refers to an invalid record. Check the roll number, username, room, billing month, or settlement month.'),409

    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(400)
    @app.errorhandler(413)
    def http_error(error):
        return render_template('error.html',code=error.code,message=error.description),error.code

    return app
