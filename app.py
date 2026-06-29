import os
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from models import db, Karyawan, MenuHarian, ScanLog
import json
from datetime import datetime

load_dotenv()

app = Flask(__name__)

# Use DATABASE_URL from environment if available (for Render/Supabase), otherwise fallback to local SQLite
database_url = os.environ.get('DATABASE_URL', 'sqlite:///sppg_local.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Buat tabel jika belum ada (sementara taruh di sini, untuk production biasanya pakai Flask-Migrate)
with app.app_context():
    db.create_all()

@app.route('/')
def login():
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    # Fetch recent scans from DB
    db_scans = ScanLog.query.order_by(ScanLog.timestamp.desc()).limit(5).all()
    recent_scans = []
    for s in db_scans:
        items = json.loads(s.items_json) if s.items_json else []
        formatted_items = []
        for i in items:
            name = i.get('kategori', '')
            short_name = name
            color = 'blue'
            if name == 'Karbohidrat': short_name = 'Karbo'; color = 'blue'
            elif name == 'Protein Hewani': short_name = 'Prot.H'; color = 'red'
            elif name == 'Protein Nabati': short_name = 'Prot.N'; color = 'purple'
            elif name == 'Sayur': short_name = 'Sayur'; color = 'green'
            elif name == 'Buah': short_name = 'Buah'; color = 'yellow'
            
            formatted_items.append({'name': short_name, 'qty': i.get('jumlah', 0), 'color': color})
            
        recent_scans.append({
            'id': s.nampan_id,
            'time': s.timestamp.strftime('%H:%M') if s.timestamp else '',
            'items': formatted_items,
            'score': '95%' # Dummy score
        })

    data = {
        'total_value': 'Rp 1,24 jt',
        'value_change': '+ 14% vs kemarin',
        'total_waste': '54,7 kg',
        'waste_change': '+ 7,3 kg',
        'most_wasted': 'Protein Hewani',
        'most_wasted_desc': 'Sisa rata-rata 17%',
        'total_scanned': '312',
        'scanned_desc': 'Sinkron mobile',
        'categories': [
            {'name': 'Karbohidrat', 'sisa_kg': 12.4, 'persen': 7.1, 'status': 'Normal', 'color': 'blue'},
            {'name': 'Protein Hewani', 'sisa_kg': 18.6, 'persen': 17.0, 'status': 'Kritis', 'color': 'red'},
            {'name': 'Protein Nabati', 'sisa_kg': 9.3, 'persen': 12.4, 'status': 'Perhatian', 'color': 'purple'},
            {'name': 'Sayur', 'sisa_kg': 11.0, 'persen': 11.8, 'status': 'Perhatian', 'color': 'green'},
            {'name': 'Buah', 'sisa_kg': 3.4, 'persen': 8.3, 'status': 'Normal', 'color': 'yellow'}
        ],
        'recent_scans': recent_scans
    }
    return render_template('dashboard.html', data=data)

@app.route('/formulir')
def formulir():
    return render_template('formulir.html')

@app.route('/log-sinkronisasi')
def log_sinkronisasi():
    db_scans = ScanLog.query.order_by(ScanLog.timestamp.desc()).all()
    scans = []
    for s in db_scans:
        items = json.loads(s.items_json) if s.items_json else []
        formatted_items = []
        for i in items:
            name = i.get('kategori', '')
            short_name = name
            c = 'karbo'
            if name == 'Karbohidrat': short_name = 'Karbo'; c = 'karbo'
            elif name == 'Protein Hewani': short_name = 'Prot.H'; c = 'proth'
            elif name == 'Protein Nabati': short_name = 'Prot.N'; c = 'protn'
            elif name == 'Sayur': short_name = 'Sayur'; c = 'sayur'
            elif name == 'Buah': short_name = 'Buah'; c = 'buah'
            formatted_items.append({'n': short_name, 'q': i.get('jumlah', 0), 'c': c})
            
        scans.append({
            'id': s.nampan_id,
            'time': s.timestamp.strftime('%H:%M') if s.timestamp else '',
            'items': formatted_items,
            'pct': '95%'
        })
    return render_template('log.html', scans=scans)

@app.route('/pengaturan')
def pengaturan():
    return render_template('settings.html')

@app.route('/master-menu')
def master_menu():
    menus = MenuHarian.query.order_by(MenuHarian.tanggal.desc()).all()
    return render_template('master_menu.html', menus=menus)

@app.route('/karyawan')
def karyawan():
    karyawans = Karyawan.query.all()
    return render_template('karyawan.html', karyawans=karyawans)

@app.route('/api/karyawan/add', methods=['POST'])
def add_karyawan():
    try:
        data = request.get_json()
        if not data or not data.get('nik') or not data.get('nama'):
            return jsonify({'status': 'error', 'message': 'NIK dan Nama wajib diisi'}), 400
        
        # Cek apakah NIK sudah ada
        existing = Karyawan.query.filter_by(nik=data['nik']).first()
        if existing:
            return jsonify({'status': 'error', 'message': 'NIK sudah terdaftar'}), 400
            
        new_karyawan = Karyawan(
            nik=data['nik'],
            nama=data['nama'],
            posisi=data.get('posisi', 'Petugas Dapur'),
            shift_dominan=data.get('shift_dominan', 'Pagi'),
            pin=data.get('pin', '123456'),
            is_active=True,
            last_login=None
        )
        
        db.session.add(new_karyawan)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Karyawan berhasil ditambahkan'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- API ENDPOINTS UNTUK APLIKASI MOBILE (SIGIZA) ---

@app.route('/api/login', methods=['POST'])
def api_login():
    """Endpoint untuk login petugas dari aplikasi mobile menggunakan NIK dan PIN"""
    data = request.get_json()
    if not data or 'nik' not in data or 'pin' not in data:
        return jsonify({'status': 'error', 'message': 'NIK dan PIN wajib diisi'}), 400
    
    petugas = Karyawan.query.filter_by(nik=data['nik'], pin=data['pin'], is_active=True).first()
    
    if petugas:
        petugas.last_login = datetime.now()
        db.session.commit()
        
        return jsonify({
            'status': 'success', 
            'message': 'Login berhasil',
            'data': {
                'nik': petugas.nik,
                'nama': petugas.nama,
                'posisi': petugas.posisi,
                'token': 'dummy_jwt_token_12345'
            }
        }), 200
    else:
        return jsonify({'status': 'error', 'message': 'NIK atau PIN salah, atau akun tidak aktif'}), 401

@app.route('/api/menu', methods=['GET'])
def api_menu():
    """Endpoint untuk mengambil daftar menu harian dari server ke mobile"""
    today = datetime.now().date()
    menus = MenuHarian.query.filter_by(tanggal=today).all()
    
    menu_data = []
    for m in menus:
        menu_data.append({
            'id': m.id,
            'nama_menu': m.nama_menu,
            'tanggal': m.tanggal.strftime('%Y-%m-%d'),
            'shift': m.shift,
            'komposisi_standar': {
                'karbohidrat': m.karbo_gr or 0,
                'protein_hewani': m.proth_gr or 0,
                'protein_nabati': m.protn_gr or 0,
                'sayur': m.sayur_gr or 0,
                'buah': m.buah_gr or 0
            }
        })
        
    return jsonify({
        'status': 'success',
        'data': menu_data
    }), 200

@app.route('/api/scan', methods=['POST'])
def api_scan():
    """Endpoint untuk menerima data mentah object counting dari aplikasi mobile"""
    data = request.get_json()
    if not data or 'nampan_id' not in data or 'items' not in data:
        return jsonify({'status': 'error', 'message': 'Format data tidak valid'}), 400
    
    petugas_nik = data.get('petugas_nik')
    timestamp_str = data.get('timestamp')
    
    try:
        scan_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')) if timestamp_str else datetime.now()
    except (ValueError, AttributeError):
        scan_time = datetime.now()
        
    new_scan = ScanLog(
        nampan_id=data['nampan_id'],
        timestamp=scan_time,
        petugas_nik=petugas_nik,
        items_json=json.dumps(data['items'])
    )
    
    db.session.add(new_scan)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': f'Gagal menyimpan data: {str(e)}'}), 500
        
    return jsonify({
        'status': 'success',
        'message': f"Data scan untuk nampan {data['nampan_id']} berhasil diterima dan disimpan",
        'received_items': len(data['items'])
    }), 201

@app.route('/api/dashboard', methods=['GET'])
def api_dashboard():
    """Endpoint untuk mengambil data dashboard untuk mobile app, bisa difilter berdasarkan petugas"""
    nik = request.args.get('nik')
    
    # Base query for recent scans
    query = ScanLog.query.order_by(ScanLog.timestamp.desc())
    if nik:
        query = query.filter_by(petugas_nik=nik)
        
    db_scans = query.limit(5).all()
    
    recent_scans = []
    for s in db_scans:
        items = json.loads(s.items_json) if s.items_json else []
        formatted_items = []
        for i in items:
            name = i.get('kategori', '')
            short_name = name
            color = 'blue'
            if name == 'Karbohidrat': short_name = 'Karbo'; color = 'blue'
            elif name == 'Protein Hewani': short_name = 'Prot.H'; color = 'red'
            elif name == 'Protein Nabati': short_name = 'Prot.N'; color = 'purple'
            elif name == 'Sayur': short_name = 'Sayur'; color = 'green'
            elif name == 'Buah': short_name = 'Buah'; color = 'yellow'
            
            formatted_items.append({'name': short_name, 'qty': i.get('jumlah', 0), 'color': color})
            
        recent_scans.append({
            'id': s.nampan_id,
            'time': s.timestamp.strftime('%H:%M') if s.timestamp else '',
            'items': formatted_items,
            'score': '95%' # Dummy score
        })

    # Get total scanned count
    total_query = ScanLog.query
    if nik:
        total_query = total_query.filter_by(petugas_nik=nik)
    total_scanned = total_query.count()

    # Using dummy data for other statistics to match the web dashboard
    data = {
        'total_value': 'Rp 1,24 jt',
        'value_change': '+ 14% vs kemarin',
        'total_waste': '54,7 kg',
        'waste_change': '+ 7,3 kg',
        'most_wasted': 'Protein Hewani',
        'most_wasted_desc': 'Sisa rata-rata 17%',
        'total_scanned': str(total_scanned),
        'scanned_desc': 'Sinkron mobile',
        'categories': [
            {'name': 'Karbohidrat', 'sisa_kg': 12.4, 'persen': 7.1, 'status': 'Normal', 'color': 'blue'},
            {'name': 'Protein Hewani', 'sisa_kg': 18.6, 'persen': 17.0, 'status': 'Kritis', 'color': 'red'},
            {'name': 'Protein Nabati', 'sisa_kg': 9.3, 'persen': 12.4, 'status': 'Perhatian', 'color': 'purple'},
            {'name': 'Sayur', 'sisa_kg': 11.0, 'persen': 11.8, 'status': 'Perhatian', 'color': 'green'},
            {'name': 'Buah', 'sisa_kg': 3.4, 'persen': 8.3, 'status': 'Normal', 'color': 'yellow'}
        ],
        'recent_scans': recent_scans
    }
    
    return jsonify({
        'status': 'success',
        'data': data
    }), 200

# --- END OF API ENDPOINTS ---

if __name__ == '__main__':
    app.run(debug=True, port=5000)
