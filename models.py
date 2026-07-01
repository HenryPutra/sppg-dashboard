from datetime import datetime
import json

class Karyawan:
    def __init__(self, nik=None, nama=None, posisi=None, shift_dominan=None, pin=None, is_active=True, last_login=None, **kwargs):
        self.nik = nik
        self.nama = nama
        self.posisi = posisi
        self.shift_dominan = shift_dominan
        self.pin = pin
        self.is_active = is_active
        self.last_login = last_login
        
    def to_dict(self):
        return {
            'nik': self.nik,
            'nama': self.nama,
            'posisi': self.posisi,
            'shift_dominan': self.shift_dominan,
            'pin': self.pin,
            'is_active': self.is_active,
            'last_login': self.last_login
        }
        
    @staticmethod
    def from_dict(data, doc_id=None):
        if not data: return None
        return Karyawan(
            nik=doc_id or data.get('nik'),
            nama=data.get('nama'),
            posisi=data.get('posisi'),
            shift_dominan=data.get('shift_dominan'),
            pin=data.get('pin'),
            is_active=data.get('is_active', True),
            last_login=data.get('last_login')
        )

class MenuHarian:
    def __init__(self, id=None, nama_menu=None, tanggal=None, shift=None, sasaran=None, total_porsi=None, karbo_gr=None, proth_gr=None, protn_gr=None, sayur_gr=None, buah_gr=None, **kwargs):
        self.id = id
        self.nama_menu = nama_menu
        self.tanggal = tanggal
        self.shift = shift
        self.sasaran = sasaran
        self.total_porsi = total_porsi
        self.karbo_gr = karbo_gr
        self.proth_gr = proth_gr
        self.protn_gr = protn_gr
        self.sayur_gr = sayur_gr
        self.buah_gr = buah_gr

    def to_dict(self):
        return {
            'nama_menu': self.nama_menu,
            'tanggal': self.tanggal.isoformat() if hasattr(self.tanggal, 'isoformat') else self.tanggal,
            'shift': self.shift,
            'sasaran': self.sasaran,
            'total_porsi': self.total_porsi,
            'karbo_gr': self.karbo_gr,
            'proth_gr': self.proth_gr,
            'protn_gr': self.protn_gr,
            'sayur_gr': self.sayur_gr,
            'buah_gr': self.buah_gr
        }

    @staticmethod
    def from_dict(data, doc_id=None):
        if not data: return None
        
        # parse datetime if needed, or leave as string
        tanggal_str = data.get('tanggal')
        
        return MenuHarian(
            id=doc_id,
            nama_menu=data.get('nama_menu'),
            tanggal=tanggal_str,
            shift=data.get('shift'),
            sasaran=data.get('sasaran'),
            total_porsi=data.get('total_porsi'),
            karbo_gr=data.get('karbo_gr'),
            proth_gr=data.get('proth_gr'),
            protn_gr=data.get('protn_gr'),
            sayur_gr=data.get('sayur_gr'),
            buah_gr=data.get('buah_gr')
        )

class ScanLog:
    def __init__(self, id=None, nampan_id=None, timestamp=None, petugas_nik=None, items_json=None, items=None, **kwargs):
        self.id = id
        self.nampan_id = nampan_id
        self.timestamp = timestamp or datetime.utcnow()
        self.petugas_nik = petugas_nik
        if items is not None:
            self._items = items
            self.items_json = json.dumps(items)
        else:
            self.items_json = items_json
            self._items = json.loads(items_json) if items_json else []

    @property
    def items(self):
        return self._items
    
    @items.setter
    def items(self, value):
        self._items = value
        self.items_json = json.dumps(value)

    def to_dict(self):
        return {
            'nampan_id': self.nampan_id,
            'timestamp': self.timestamp,
            'petugas_nik': self.petugas_nik,
            'items_json': self.items_json
        }

    @staticmethod
    def from_dict(data, doc_id=None):
        if not data: return None
        return ScanLog(
            id=doc_id,
            nampan_id=data.get('nampan_id'),
            timestamp=data.get('timestamp'),
            petugas_nik=data.get('petugas_nik'),
            items_json=data.get('items_json')
        )
