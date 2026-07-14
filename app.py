import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, flash
from functools import wraps
from dotenv import load_dotenv
from models import Karyawan, MenuHarian, ScanLog
import json
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'super-secret-key-123')

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Initialize Firebase
try:
    firebase_credentials = os.environ.get('FIREBASE_CREDENTIALS')
    if firebase_credentials:
        # Load from environment variable (Render)
        cred_dict = json.loads(firebase_credentials)
        cred = credentials.Certificate(cred_dict)
    else:
        # Load from file (Local)
        cred = credentials.Certificate('serviceAccountKey.json')
        
    firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"Warning: Firebase initialization failed. Error: {e}")
    db = None


def calculate_dashboard_stats(nik=None):
    if not db:
        return {}
        
    query = db.collection('scan_log')
    if nik:
        query = query.where('petugas_nik', '==', nik)
        
    all_scans = [ScanLog.from_dict(doc.to_dict(), doc_id=doc.id) for doc in query.stream()]
    all_scans.sort(key=lambda x: x.timestamp, reverse=True)
    
    recent_scans_raw = all_scans[:5]
    
    # Fetch settings
    settings = {}
    if db:
        docs = db.collection('pengaturan').limit(1).stream()
        for doc in docs:
            settings = doc.to_dict()
            break
            
    cat_weights = {
        'Karbohidrat': int(settings.get('berat_karbo', 250)) / 1000,
        'Protein Hewani': int(settings.get('berat_proth', 120)) / 1000,
        'Protein Nabati': int(settings.get('berat_protn', 80)) / 1000,
        'Sayur': int(settings.get('berat_sayur', 80)) / 1000,
        'Buah': int(settings.get('berat_buah', 100)) / 1000,
    }
    
    tol_normal = int(settings.get('tol_normal', 10))
    tol_kritis = int(settings.get('tol_kritis', 15))
    
    # Format recent scans
    recent_scans = []
    for s in recent_scans_raw:
        items = json.loads(s.items_json) if s.items_json else []
        formatted_items = []
        scan_total_items = 0
        for i in items:
            name = i.get('kategori', '')
            short_name = name
            color = 'blue'
            if name == 'Karbohidrat': short_name = 'Karbo'; color = 'blue'
            elif name == 'Protein Hewani': short_name = 'Prot.H'; color = 'red'
            elif name == 'Protein Nabati': short_name = 'Prot.N'; color = 'purple'
            elif name == 'Sayur': short_name = 'Sayur'; color = 'green'
            elif name == 'Buah': short_name = 'Buah'; color = 'yellow'
            
            qty = i.get('jumlah', 0)
            scan_total_items += qty
            formatted_items.append({'name': short_name, 'qty': qty, 'color': color})
            
        score = 100 - (scan_total_items * 5) # simple score heuristic
        if score < 0: score = 0
        recent_scans.append({
            'id': s.nampan_id,
            'time': s.timestamp.strftime('%H:%M') if s.timestamp and isinstance(s.timestamp, datetime) else '',
            'items': formatted_items,
            'score': f'{score}%'
        })
        
    # Calculate stats for today
    today_date = datetime.now().date()
    today_scans = [s for s in all_scans if s.timestamp and isinstance(s.timestamp, datetime) and s.timestamp.date() == today_date]

    total_scanned = len(today_scans)
    value_per_kg = 50000 # Asumsi Rp 50.000 per kg sisa
    
    cat_counts = {
        'Karbohidrat': 0, 'Protein Hewani': 0, 'Protein Nabati': 0, 'Sayur': 0, 'Buah': 0
    }
    
    for s in today_scans:
        items = json.loads(s.items_json) if s.items_json else []
        for i in items:
            cat = i.get('kategori')
            qty = i.get('jumlah', 0)
            if cat in cat_counts:
                cat_counts[cat] += qty
                
    total_items = sum(cat_counts.values())
    total_waste_kg = sum([cat_counts[k] * cat_weights[k] for k in cat_counts])
    total_value_rp = total_waste_kg * value_per_kg
    
    total_value_str = f"Rp {total_value_rp:,.0f}".replace(',', '.')
    if total_value_rp >= 1000000:
        total_value_str = f"Rp {total_value_rp/1000000:.2f} jt".replace('.', ',')
        
    most_wasted = max(cat_counts, key=cat_counts.get) if total_items > 0 else "-"
    most_wasted_pct = (cat_counts[most_wasted] / total_items * 100) if total_items > 0 else 0
    
    categories = []
    for cat_name, count in cat_counts.items():
        sisa_kg = count * cat_weights.get(cat_name, 0.05)
        pct = (count / total_items * 100) if total_items > 0 else 0
        
        status = 'Normal'
        if pct > tol_kritis: status = 'Kritis'
        elif pct > tol_normal: status = 'Perhatian'
        
        categories.append({
            'name': cat_name,
            'sisa_kg': sisa_kg,
            'persen': pct,
            'status': status
        })
        
    # Calculate 7-day trend
    trend_labels = []
    trend_data = []
    today = datetime.now().date()
    
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        trend_labels.append(d.strftime('%a %d/%m').replace('Mon', 'Sen').replace('Tue', 'Sel').replace('Wed', 'Rab').replace('Thu', 'Kam').replace('Fri', 'Jum').replace('Sat', 'Sab').replace('Sun', 'Min'))
        
        day_items = 0
        day_scans = 0
        for s in all_scans:
            if s.timestamp and isinstance(s.timestamp, datetime) and s.timestamp.date() == d:
                day_scans += 1
                items = json.loads(s.items_json) if s.items_json else []
                for it in items:
                    day_items += it.get('jumlah', 0)
        
        pct = (day_items / (day_scans * 5) * 100) if day_scans > 0 else 0
        trend_data.append(round(pct))

    return {
        'total_value': total_value_str,
        'value_change': 'Real Data',
        'total_waste': f"{total_waste_kg:.1f} kg".replace('.', ','),
        'waste_change': 'Real Data',
        'most_wasted': most_wasted,
        'most_wasted_desc': f"Sisa rata-rata {most_wasted_pct:.1f}%".replace('.', ','),
        'total_scanned': str(total_scanned),
        'scanned_desc': 'Sinkron mobile',
        'categories': categories,
        'recent_scans': recent_scans,
        'chart_labels': trend_labels,
        'chart_data': trend_data
    }


@app.route('/', methods=['GET', 'POST'])
def login():
    if 'admin_logged_in' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if db:
            docs = db.collection('admins').where('username', '==', username).where('password', '==', password).limit(1).stream()
            admin = None
            for doc in docs:
                admin = doc.to_dict()
                break
                
            if admin:
                session['admin_logged_in'] = True
                session['admin_username'] = username
                return redirect(url_for('dashboard'))
            else:
                flash('Username atau password salah', 'error')
        else:
            flash('Database tidak terhubung', 'error')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    data = calculate_dashboard_stats()
    return render_template('dashboard.html', data=data)

@app.route('/formulir')
@login_required
def formulir():
    filter_type = request.args.get('filter_type', 'hari')
    filter_date = request.args.get('filter_date', datetime.now().strftime('%Y-%m-%d'))
    filter_month = request.args.get('filter_month', datetime.now().strftime('%Y-%m'))
    
    # Handle week format (e.g. 2026-W24)
    filter_week = request.args.get('filter_week')
    if not filter_week:
        d = datetime.now()
        filter_week = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"

    formulir_data = []
    if db:
        docs = db.collection('menu_harian').order_by('tanggal', direction=firestore.Query.DESCENDING).stream()
        menus = []
        for doc in docs:
            m = MenuHarian.from_dict(doc.to_dict(), doc_id=doc.id)
            if not m.tanggal: continue
            
            if filter_type == 'hari':
                if m.tanggal == filter_date:
                    menus.append(m)
            elif filter_type == 'bulan':
                if m.tanggal.startswith(filter_month):
                    menus.append(m)
            elif filter_type == 'minggu':
                try:
                    d = datetime.strptime(m.tanggal, '%Y-%m-%d')
                    week_str = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
                    if week_str == filter_week:
                        menus.append(m)
                except:
                    pass
            
        all_scans = []
        scan_docs = db.collection('scan_log').stream()
        for sdoc in scan_docs:
            all_scans.append(ScanLog.from_dict(sdoc.to_dict(), sdoc.id))
            
        menu_dates = {m.tanggal for m in menus if m.tanggal}
        scan_dates_to_add = set()
        
        for scan in all_scans:
            scan_date = scan.timestamp.strftime('%Y-%m-%d') if hasattr(scan.timestamp, 'strftime') else (scan.timestamp.split('T')[0] if isinstance(scan.timestamp, str) else None)
            if not scan_date: continue
            
            if scan_date not in menu_dates:
                match = False
                if filter_type == 'hari' and scan_date == filter_date: match = True
                elif filter_type == 'bulan' and scan_date.startswith(filter_month): match = True
                elif filter_type == 'minggu':
                    try:
                        d = datetime.strptime(scan_date, '%Y-%m-%d')
                        week_str = f"{d.isocalendar()[0]}-W{d.isocalendar()[1]:02d}"
                        if week_str == filter_week: match = True
                    except: pass
                
                if match:
                    scan_dates_to_add.add(scan_date)
                    
        for d_date in scan_dates_to_add:
            dummy_menu = MenuHarian(
                nama_menu="Data Log (Belum ada Menu)",
                tanggal=d_date,
                sasaran="-",
                total_porsi=0,
                karbo_gr=0, proth_gr=0, protn_gr=0, sayur_gr=0, buah_gr=0
            )
            menus.append(dummy_menu)
            menu_dates.add(d_date)
            
        menus.sort(key=lambda x: x.tanggal if x.tanggal else "", reverse=True)
            
        for menu in menus:
            # Brt Masak
            karbo_ms = menu.karbo_gr or 0
            proth_ms = menu.proth_gr or 0
            protn_ms = menu.protn_gr or 0
            sayur_ms = menu.sayur_gr or 0
            buah_ms = menu.buah_gr or 0
            
            porsi = menu.total_porsi or 0
            
            # Brt Total (kg)
            karbo_tot = (karbo_ms * porsi) / 1000
            proth_tot = (proth_ms * porsi) / 1000
            protn_tot = (protn_ms * porsi) / 1000
            sayur_tot = (sayur_ms * porsi) / 1000
            buah_tot = (buah_ms * porsi) / 1000
            
            # Count waste from scans on that date
            menu_date = menu.tanggal
            karbo_waste = 0
            proth_waste = 0
            protn_waste = 0
            sayur_waste = 0
            buah_waste = 0
            
            if menu_date:
                for scan in all_scans:
                    scan_date = scan.timestamp.strftime('%Y-%m-%d') if hasattr(scan.timestamp, 'strftime') else (scan.timestamp.split('T')[0] if isinstance(scan.timestamp, str) else None)
                    # if date matches (or simple string match)
                    if scan_date == menu_date or scan_date == str(menu_date):
                        items = json.loads(scan.items_json) if scan.items_json else []
                        for item in items:
                            cat = item.get('kategori', '')
                            qty = item.get('jumlah', 0)
                            if cat == 'Karbohidrat': karbo_waste += qty
                            elif cat == 'Protein Hewani': proth_waste += qty
                            elif cat == 'Protein Nabati': protn_waste += qty
                            elif cat == 'Sayur': sayur_waste += qty
                            elif cat == 'Buah': buah_waste += qty
            
            weight_per_item = 0.05 # 50g per item
            karbo_sisa = karbo_waste * weight_per_item
            proth_sisa = proth_waste * weight_per_item
            protn_sisa = protn_waste * weight_per_item
            sayur_sisa = sayur_waste * weight_per_item
            buah_sisa = buah_waste * weight_per_item
            
            total_ms = karbo_ms + proth_ms + protn_ms + sayur_ms + buah_ms
            total_tot = karbo_tot + proth_tot + protn_tot + sayur_tot + buah_tot
            total_sisa = karbo_sisa + proth_sisa + protn_sisa + sayur_sisa + buah_sisa
            total_pct = (total_sisa / total_tot * 100) if total_tot > 0 else 0
            
            formulir_data.append({
                'tanggal_fmt': menu_date,
                'nama_menu': menu.nama_menu,
                'sasaran': menu.sasaran,
                'porsi': porsi,
                
                'karbo_ms': karbo_ms, 'karbo_tot': karbo_tot, 'karbo_sisa': karbo_sisa,
                'karbo_pct': (karbo_sisa / karbo_tot * 100) if karbo_tot > 0 else 0,
                
                'proth_ms': proth_ms, 'proth_tot': proth_tot, 'proth_sisa': proth_sisa,
                'proth_pct': (proth_sisa / proth_tot * 100) if proth_tot > 0 else 0,
                
                'protn_ms': protn_ms, 'protn_tot': protn_tot, 'protn_sisa': protn_sisa,
                'protn_pct': (protn_sisa / protn_tot * 100) if protn_tot > 0 else 0,
                
                'sayur_ms': sayur_ms, 'sayur_tot': sayur_tot, 'sayur_sisa': sayur_sisa,
                'sayur_pct': (sayur_sisa / sayur_tot * 100) if sayur_tot > 0 else 0,

                'buah_ms': buah_ms, 'buah_tot': buah_tot, 'buah_sisa': buah_sisa,
                'buah_pct': (buah_sisa / buah_tot * 100) if buah_tot > 0 else 0,

                'total_ms': total_ms, 'total_tot': total_tot, 'total_sisa': total_sisa,
                'total_pct': total_pct,
            })
            
    return render_template('formulir.html', data=formulir_data, filter_type=filter_type, filter_date=filter_date, filter_week=filter_week, filter_month=filter_month)

@app.route('/log-sinkronisasi')
@login_required
def log_sinkronisasi():
    filter_date = request.args.get('filter_date', datetime.now().strftime('%Y-%m-%d'))
    filter_shift = request.args.get('filter_shift', 'Semua Shift')
    filter_petugas = request.args.get('filter_petugas', 'Semua Petugas')
    search_nampan = request.args.get('search_nampan', '')

    db_scans_raw = []
    karyawans = []
    if db:
        docs = db.collection('scan_log').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        for doc in docs:
            db_scans_raw.append(ScanLog.from_dict(doc.to_dict(), doc_id=doc.id))
            
        k_docs = db.collection('karyawan').stream()
        for kd in k_docs:
            karyawans.append(Karyawan.from_dict(kd.to_dict(), doc_id=kd.id))
            
    db_scans = []
    for s in db_scans_raw:
        # filter date
        scan_date = s.timestamp.strftime('%Y-%m-%d') if hasattr(s.timestamp, 'strftime') else (s.timestamp.split('T')[0] if isinstance(s.timestamp, str) else None)
        if filter_date and scan_date != filter_date:
            continue
            
        # filter shift
        if filter_shift != 'Semua Shift':
            scan_time = s.timestamp.strftime('%H:%M') if hasattr(s.timestamp, 'strftime') else (s.timestamp.split('T')[1][:5] if isinstance(s.timestamp, str) and 'T' in s.timestamp else "00:00")
            h = int(scan_time.split(':')[0]) if ':' in scan_time else 0
            shift = 'Pagi' if 6 <= h < 14 else ('Siang' if 14 <= h < 22 else 'Malam')
            if filter_shift != shift:
                continue
                
        # filter petugas
        if filter_petugas != 'Semua Petugas':
            if s.petugas_nik != filter_petugas:
                continue
                
        # search nampan
        if search_nampan and search_nampan.lower() not in (s.nampan_id or '').lower():
            continue
            
        db_scans.append(s)
            
    cat_totals = {'Karbohidrat': 0, 'Protein Hewani': 0, 'Protein Nabati': 0, 'Sayur': 0, 'Buah': 0}
            
    scans = []
    for s in db_scans:
        items = json.loads(s.items_json) if s.items_json else []
        formatted_items = []
        scan_total = 0
        for i in items:
            name = i.get('kategori', '')
            qty = i.get('jumlah', 0)
            scan_total += qty
            if name in cat_totals:
                cat_totals[name] += qty
                
            short_name = name
            c = 'karbo'
            if name == 'Karbohidrat': short_name = 'Karbo'; c = 'karbo'
            elif name == 'Protein Hewani': short_name = 'Prot.H'; c = 'proth'
            elif name == 'Protein Nabati': short_name = 'Prot.N'; c = 'protn'
            elif name == 'Sayur': short_name = 'Sayur'; c = 'sayur'
            elif name == 'Buah': short_name = 'Buah'; c = 'buah'
            formatted_items.append({'n': short_name, 'q': qty, 'c': c})
            
        time_str = ''
        if s.timestamp:
            if isinstance(s.timestamp, datetime):
                time_str = s.timestamp.strftime('%H:%M')
            elif isinstance(s.timestamp, str) and 'T' in s.timestamp:
                time_str = s.timestamp.split('T')[1][:5]
                
        score = 100 - (scan_total * 5)
        if score < 0: score = 0
            
        petugas_nama = 'Tidak diketahui'
        for k in karyawans:
            if k.nik == s.petugas_nik:
                petugas_nama = k.nama
                break
                
        scans.append({
            'id': s.nampan_id,
            'time': time_str,
            'items': formatted_items,
            'pct': f'{score}%',
            'petugas_nik': s.petugas_nik,
            'petugas_nama': petugas_nama
        })
        
    total_all = sum(cat_totals.values())
    
    stats = {
        'karbo': {'val': cat_totals['Karbohidrat'], 'pct': (cat_totals['Karbohidrat'] / total_all * 100) if total_all > 0 else 0},
        'proth': {'val': cat_totals['Protein Hewani'], 'pct': (cat_totals['Protein Hewani'] / total_all * 100) if total_all > 0 else 0},
        'protn': {'val': cat_totals['Protein Nabati'], 'pct': (cat_totals['Protein Nabati'] / total_all * 100) if total_all > 0 else 0},
        'sayur': {'val': cat_totals['Sayur'], 'pct': (cat_totals['Sayur'] / total_all * 100) if total_all > 0 else 0},
        'buah': {'val': cat_totals['Buah'], 'pct': (cat_totals['Buah'] / total_all * 100) if total_all > 0 else 0},
    }
        
    return render_template('log.html', scans=scans, stats=stats, filter_date=filter_date, filter_shift=filter_shift, filter_petugas=filter_petugas, search_nampan=search_nampan, karyawans=karyawans)

@app.route('/master-menu')
@login_required
def master_menu():
    menus = []
    if db:
        docs = db.collection('menu_harian').order_by('tanggal', direction=firestore.Query.DESCENDING).stream()
        for doc in docs:
            menus.append(MenuHarian.from_dict(doc.to_dict(), doc_id=doc.id))
    return render_template('master_menu.html', menus=menus)

@app.route('/karyawan')
@login_required
def karyawan():
    karyawans = []
    if db:
        docs = db.collection('karyawan').stream()
        for doc in docs:
            karyawans.append(Karyawan.from_dict(doc.to_dict(), doc_id=doc.id))
            
    aktif = sum(1 for k in karyawans if k.is_active)
    nonaktif = sum(1 for k in karyawans if not k.is_active)
    total = len(karyawans)
            
    return render_template('karyawan.html', karyawans=karyawans, stats={'aktif': aktif, 'nonaktif': nonaktif, 'total': total})

@app.route('/pengaturan')
@login_required
def pengaturan():
    settings = {}
    if db:
        docs = db.collection('pengaturan').limit(1).stream()
        for doc in docs:
            settings = doc.to_dict()
            settings['id'] = doc.id
            break
            
    if not settings:
        settings = {
            'berat_karbo': 250,
            'berat_proth': 120,
            'berat_protn': 80,
            'berat_sayur': 80,
            'berat_buah': 100,
            'tol_normal': 10,
            'tol_kritis': 15,
            'notif_sisa': True,
            'notif_laporan': False
        }
    return render_template('settings.html', settings=settings)

@app.route('/api/settings/update', methods=['POST'])
@login_required
def update_settings():
    if not db:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
        
    try:
        data = request.get_json()
        doc_id = data.pop('id', 'main_config')
        db.collection('pengaturan').document(doc_id).set(data, merge=True)
        return jsonify({'status': 'success', 'message': 'Pengaturan berhasil disimpan'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


@app.route('/api/karyawan/add', methods=['POST'])
def add_karyawan():
    if not db:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
        
    try:
        data = request.get_json()
        if not data or not data.get('nik') or not data.get('nama'):
            return jsonify({'status': 'error', 'message': 'NIK dan Nama wajib diisi'}), 400
        
        doc_ref = db.collection('karyawan').document(data['nik'])
        if doc_ref.get().exists:
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
        
        doc_ref.set(new_karyawan.to_dict())
        return jsonify({'status': 'success', 'message': 'Karyawan berhasil ditambahkan'}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/menu/add', methods=['POST'])
@login_required
def add_menu():
    if not db:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
        
    try:
        data = request.get_json()
        if not data or not data.get('nama_menu') or not data.get('tanggal'):
            return jsonify({'status': 'error', 'message': 'Nama menu dan tanggal wajib diisi'}), 400
            
        new_menu = MenuHarian(
            nama_menu=data.get('nama_menu'),
            tanggal=data.get('tanggal'),
            shift=data.get('shift', 'Pagi'),
            sasaran=data.get('sasaran'),
            total_porsi=int(data.get('total_porsi', 0)) if data.get('total_porsi') else None,
            karbo_gr=int(data.get('karbo_gr')) if data.get('karbo_gr') else None,
            proth_gr=int(data.get('proth_gr')) if data.get('proth_gr') else None,
            protn_gr=int(data.get('protn_gr')) if data.get('protn_gr') else None,
            sayur_gr=int(data.get('sayur_gr')) if data.get('sayur_gr') else None,
            buah_gr=int(data.get('buah_gr')) if data.get('buah_gr') else None
        )
        
        db.collection('menu_harian').add(new_menu.to_dict())
        return jsonify({'status': 'success', 'message': 'Menu berhasil ditambahkan'}), 201
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/karyawan/update/<nik>', methods=['POST'])
@login_required
def update_karyawan(nik):
    if not db:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
        
    try:
        data = request.get_json()
        doc_ref = db.collection('karyawan').document(nik)
        if not doc_ref.get().exists:
            return jsonify({'status': 'error', 'message': 'Karyawan tidak ditemukan'}), 404
            
        update_data = {
            'nama': data.get('nama'),
            'posisi': data.get('posisi'),
            'shift_dominan': data.get('shift_dominan'),
            'pin': data.get('pin')
        }
        # filter out none
        update_data = {k: v for k, v in update_data.items() if v is not None}
        if 'is_active' in data:
            update_data['is_active'] = data['is_active']
            
        doc_ref.update(update_data)
        return jsonify({'status': 'success', 'message': 'Data karyawan berhasil diperbarui'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/karyawan/delete/<nik>', methods=['DELETE'])
@login_required
def delete_karyawan(nik):
    if not db:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
        
    try:
        db.collection('karyawan').document(nik).delete()
        return jsonify({'status': 'success', 'message': 'Karyawan berhasil dihapus'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/menu/update/<menu_id>', methods=['POST'])
@login_required
def update_menu_api(menu_id):
    if not db:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
        
    try:
        data = request.get_json()
        doc_ref = db.collection('menu_harian').document(menu_id)
        if not doc_ref.get().exists:
            return jsonify({'status': 'error', 'message': 'Menu tidak ditemukan'}), 404
            
        update_data = {
            'nama_menu': data.get('nama_menu'),
            'tanggal': data.get('tanggal'),
            'shift': data.get('shift'),
            'sasaran': data.get('sasaran'),
            'total_porsi': int(data.get('total_porsi', 0)) if data.get('total_porsi') else None,
            'karbo_gr': int(data.get('karbo_gr')) if data.get('karbo_gr') else None,
            'proth_gr': int(data.get('proth_gr')) if data.get('proth_gr') else None,
            'protn_gr': int(data.get('protn_gr')) if data.get('protn_gr') else None,
            'sayur_gr': int(data.get('sayur_gr')) if data.get('sayur_gr') else None,
            'buah_gr': int(data.get('buah_gr')) if data.get('buah_gr') else None
        }
        update_data = {k: v for k, v in update_data.items() if v is not None}
        
        doc_ref.update(update_data)
        return jsonify({'status': 'success', 'message': 'Menu berhasil diperbarui'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/menu/delete/<menu_id>', methods=['DELETE'])
@login_required
def delete_menu_api(menu_id):
    if not db:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
        
    try:
        db.collection('menu_harian').document(menu_id).delete()
        return jsonify({'status': 'success', 'message': 'Menu berhasil dihapus'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# --- API ENDPOINTS UNTUK APLIKASI MOBILE (SIGIZA) ---

@app.route('/api/login', methods=['POST'])
def api_login():
    if not db:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
        
    data = request.get_json()
    if not data or 'nik' not in data or 'pin' not in data:
        return jsonify({'status': 'error', 'message': 'NIK dan PIN wajib diisi'}), 400
    
    docs = db.collection('karyawan').where('nik', '==', data['nik']).where('pin', '==', data['pin']).where('is_active', '==', True).limit(1).stream()
    petugas = None
    for doc in docs:
        petugas = Karyawan.from_dict(doc.to_dict(), doc_id=doc.id)
        break
    
    if petugas:
        db.collection('karyawan').document(petugas.nik).update({'last_login': datetime.now()})
        return jsonify({
            'status': 'success', 
            'message': 'Login berhasil',
            'data': {
                'nik': petugas.nik,
                'nama': petugas.nama,
                'posisi': petugas.posisi,
                'shift_dominan': petugas.shift_dominan,
                'token': 'dummy_jwt_token_12345'
            }
        }), 200
    else:
        return jsonify({'status': 'error', 'message': 'NIK atau PIN salah, atau akun tidak aktif'}), 401

@app.route('/api/menu', methods=['GET'])
def api_menu():
    if not db:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
        
    today_str = datetime.now().date().isoformat()
    docs = db.collection('menu_harian').where('tanggal', '==', today_str).stream()
    
    menu_data = []
    for d in docs:
        m = MenuHarian.from_dict(d.to_dict(), doc_id=d.id)
        menu_data.append({
            'id': m.id,
            'nama_menu': m.nama_menu,
            'tanggal': m.tanggal,
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
@app.route('/api/scans', methods=['POST'])
def api_scan():
    if not db:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
        
    data = request.get_json()
    if not data or 'items' not in data:
        return jsonify({'status': 'error', 'message': 'Format data tidak valid'}), 400
    
    petugas_nik = data.get('petugas_nik') or 'NIK-2024-087'
    nampan_id = data.get('nampan_id')
    if not nampan_id:
        nampan_id = f"NMP-{int(datetime.now().timestamp() * 1000)}"
        
    timestamp_str = data.get('timestamp')
    
    try:
        scan_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00')) if timestamp_str else datetime.now()
    except (ValueError, AttributeError):
        scan_time = datetime.now()
        
    new_scan = ScanLog(
        nampan_id=nampan_id,
        timestamp=scan_time,
        petugas_nik=petugas_nik,
        items=data['items']
    )
    
    try:
        db.collection('scan_log').add(new_scan.to_dict())
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'Gagal menyimpan data: {str(e)}'}), 500
        
    return jsonify({
        'status': 'success',
        'message': f"Data scan untuk nampan {nampan_id} berhasil diterima dan disimpan",
        'received_items': len(data['items'])
    }), 201

@app.route('/api/dashboard', methods=['GET'])
def api_dashboard():
    nik = request.args.get('nik')
    data = calculate_dashboard_stats(nik)
    if not data:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
    
    return jsonify({
        'status': 'success',
        'data': data
    }), 200

@app.route('/api/history', methods=['GET'])
def api_history():
    if not db:
        return jsonify({'status': 'error', 'message': 'Database tidak terhubung'}), 500
        
    try:
        nik = request.args.get('nik')
        query = db.collection('scan_log')
        if nik:
            query = query.where('petugas_nik', '==', nik)
        
        docs = query.order_by('timestamp', direction=firestore.Query.DESCENDING).limit(50).stream()
        history_data = []
        for d in docs:
            log_data = d.to_dict()
            items = []
            if 'items_json' in log_data and log_data['items_json']:
                items = json.loads(log_data['items_json'])
                
            history_data.append({
                'id': d.id,
                'scanTime': log_data.get('timestamp').isoformat() if hasattr(log_data.get('timestamp'), 'isoformat') else str(log_data.get('timestamp')),
                'detectedItems': items,
                'shift': 'Shift Pagi', 
                'nampanLabel': log_data.get('nampan_id', '')
            })
            
        return jsonify({
            'status': 'success',
            'data': history_data
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/api/queue', methods=['GET'])
def api_queue():
    nik = request.args.get('nik')
    # Since queue (antrean) is usually local data awaiting sync, we return empty here 
    # to let the mobile app start fresh for a newly logged in user.
    # We could fetch unsynced items from DB if we tracked sync status there,
    # but for now, returning empty ensures a new user doesn't see dummy data.
    return jsonify({
        'status': 'success',
        'data': []
    }), 200

@app.route('/api/food-categories', methods=['GET'])
def api_food_categories():
    nik = request.args.get('nik')
    categories = [
      {'id': 'karbo', 'name': 'Karbo', 'category': 'Karbohidrat', 'subtitle': 'Nasi, roti, mie', 'count': 0, 'color': 4293467747, 'emoji': '🍚'},
      {'id': 'pro_hewani', 'name': 'P. Hewani', 'category': 'Protein Hewani', 'subtitle': 'Ayam, ikan, daging', 'count': 0, 'color': 4294198070, 'emoji': '🍗'},
      {'id': 'pro_nabati', 'name': 'P. Nabati', 'category': 'Protein Nabati', 'subtitle': 'Tahu, tempe', 'count': 0, 'color': 4283215696, 'emoji': '🥬'},
      {'id': 'sayur', 'name': 'Sayur', 'category': 'Sayuran', 'subtitle': 'Sayur mayur', 'count': 0, 'color': 4286105417, 'emoji': '🥗'},
      {'id': 'buah', 'name': 'Buah', 'category': 'Buah-buahan', 'subtitle': 'Pisang, pepaya', 'count': 0, 'color': 4294940672, 'emoji': '🍌'}
    ]
    
    if db and nik:
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        docs = db.collection('scan_log').where('petugas_nik', '==', nik).where('timestamp', '>=', today_start).stream()
        
        for d in docs:
            log_data = d.to_dict()
            items = []
            if 'items_json' in log_data and log_data['items_json']:
                items = json.loads(log_data['items_json'])
            
            for item in items:
                cat_name = item.get('kategori')
                qty = item.get('jumlah', 0)
                for cat in categories:
                    if cat['category'] == cat_name:
                        cat['count'] += qty
                        break
                        
    return jsonify({
        'status': 'success',
        'data': categories
    }), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)
