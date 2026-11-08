"""SQLite connection and database schema."""
import sqlite3
from flask import current_app, g

SCHEMA = '''
CREATE TABLE IF NOT EXISTS halls (
 id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE,
 amenity INTEGER NOT NULL CHECK(amenity>=0), amenities TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rooms (
 id INTEGER PRIMARY KEY, hall_id INTEGER NOT NULL REFERENCES halls(id),
 number TEXT NOT NULL, capacity INTEGER NOT NULL CHECK(capacity BETWEEN 1 AND 4),
 rent INTEGER NOT NULL CHECK(rent>=0), UNIQUE(hall_id,number));
CREATE TABLE IF NOT EXISTS students (
 id INTEGER PRIMARY KEY, roll TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
 address TEXT NOT NULL, mobile TEXT NOT NULL, parent_phone TEXT NOT NULL,
 photo TEXT NOT NULL, admission_note TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS users (
 id INTEGER PRIMARY KEY, username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
 role TEXT NOT NULL, hall_id INTEGER REFERENCES halls(id),
 student_id INTEGER UNIQUE REFERENCES students(id));
CREATE TABLE IF NOT EXISTS allocations (
 id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL UNIQUE REFERENCES students(id),
 room_id INTEGER NOT NULL REFERENCES rooms(id), created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS mess_charges (
 id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
 month TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>=0),
 UNIQUE(student_id,month));
CREATE TABLE IF NOT EXISTS bills (
 id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
 hall_id INTEGER NOT NULL REFERENCES halls(id), month TEXT NOT NULL,
 rent INTEGER NOT NULL CHECK(rent>=0), mess INTEGER NOT NULL CHECK(mess>=0),
 amenity INTEGER NOT NULL CHECK(amenity>=0), created TEXT NOT NULL,
 UNIQUE(student_id,month));
CREATE TABLE IF NOT EXISTS payments (
 id INTEGER PRIMARY KEY, bill_id INTEGER NOT NULL REFERENCES bills(id),
 rent INTEGER NOT NULL CHECK(rent>=0), mess INTEGER NOT NULL CHECK(mess>=0),
 amenity INTEGER NOT NULL CHECK(amenity>=0), created TEXT NOT NULL,
 user_id INTEGER NOT NULL REFERENCES users(id),
 CHECK(rent+mess+amenity>0));
CREATE TABLE IF NOT EXISTS complaints (
 id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES students(id),
 hall_id INTEGER NOT NULL REFERENCES halls(id), category TEXT NOT NULL,
 description TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open',
 atr TEXT NOT NULL DEFAULT '', created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settlements (
 id INTEGER PRIMARY KEY, hall_id INTEGER NOT NULL REFERENCES halls(id),
 month TEXT NOT NULL, amount INTEGER NOT NULL CHECK(amount>0),
 manager TEXT NOT NULL, cheque TEXT NOT NULL UNIQUE, created TEXT NOT NULL,
 acknowledged INTEGER NOT NULL DEFAULT 0, acknowledged_at TEXT,
 UNIQUE(hall_id,month));
CREATE TABLE IF NOT EXISTS audit (
 id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id),
 action TEXT NOT NULL, detail TEXT NOT NULL, created TEXT NOT NULL);
'''

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys = ON')
    return g.db

def close_db(error=None):
    db = g.pop('db', None)
    if db:
        db.close()

def init_db():
    get_db().executescript(SCHEMA)
