from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Karyawan(db.Model):
    __tablename__ = 'karyawan'
    nik = db.Column(db.String(20), primary_key=True)
    nama = db.Column(db.String(100), nullable=False)
    posisi = db.Column(db.String(50))
    shift_dominan = db.Column(db.String(20))
    pin = db.Column(db.String(6))
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime, nullable=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class MenuHarian(db.Model):
    __tablename__ = 'menu_harian'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_menu = db.Column(db.String(150), nullable=False)
    tanggal = db.Column(db.Date, nullable=False)
    shift = db.Column(db.String(20), nullable=False)
    sasaran = db.Column(db.String(100))
    total_porsi = db.Column(db.Integer)
    karbo_gr = db.Column(db.Integer)
    proth_gr = db.Column(db.Integer)
    protn_gr = db.Column(db.Integer)
    sayur_gr = db.Column(db.Integer)
    buah_gr = db.Column(db.Integer)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class ScanLog(db.Model):
    __tablename__ = 'scan_log'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nampan_id = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    petugas_nik = db.Column(db.String(20), db.ForeignKey('karyawan.nik'))
    items_json = db.Column(db.Text) # Storing JSON string for simplicity
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    
    @property
    def items(self):
        if self.items_json:
            return json.loads(self.items_json)
        return []
    
    @items.setter
    def items(self, value):
        self.items_json = json.dumps(value)
