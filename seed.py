from app import db
from models import Karyawan, MenuHarian, ScanLog
from datetime import date, datetime, timedelta
import json

def seed_data():
    if not db:
        print("Error: Database not connected. Check serviceAccountKey.json")
        return

    print("Seeding Karyawan...")
    karyawans = [
        Karyawan(nik='SPG-001', nama='Ahmad Kurniawan', posisi='Petugas Dapur', shift_dominan='Pagi', pin='123456', is_active=True, last_login=datetime.now() - timedelta(hours=2)),
        Karyawan(nik='SPG-002', nama='Rina Sulistyowati', posisi='Pengawas Gizi', shift_dominan='Siang', pin='112233', is_active=True, last_login=datetime.now() - timedelta(hours=5)),
        Karyawan(nik='SPG-003', nama='Dodi Rahmat', posisi='Petugas Dapur', shift_dominan='Sore', pin='556677', is_active=True, last_login=datetime.now() - timedelta(minutes=45)),
        Karyawan(nik='SPG-004', nama='Siti Nurazizah', posisi='Koordinator', shift_dominan='Pagi', pin='998877', is_active=False, last_login=datetime.now() - timedelta(days=5)),
    ]
    for k in karyawans:
        db.collection('karyawan').document(k.nik).set(k.to_dict())

    print("Seeding Menu Harian...")
    menus = [
        MenuHarian(nama_menu='Nasi Goreng Spesial', tanggal=date(2026, 6, 10), shift='Pagi', sasaran='Siswa SD N 1 Debong', total_porsi=820, karbo_gr=250, proth_gr=120, protn_gr=80, sayur_gr=80, buah_gr=100),
        MenuHarian(nama_menu='Nasi Ayam Bakar', tanggal=date(2026, 6, 10), shift='Siang', sasaran='Siswa SD N 1 Debong', total_porsi=820, karbo_gr=250, proth_gr=150, protn_gr=0, sayur_gr=100, buah_gr=0),
        MenuHarian(nama_menu='Nasi Ikan + Tempe', tanggal=date(2026, 6, 9), shift='Pagi', sasaran='Siswa SD N 1 Debong', total_porsi=820, karbo_gr=250, proth_gr=100, protn_gr=80, sayur_gr=80, buah_gr=100),
    ]
    for m in menus:
        db.collection('menu_harian').add(m.to_dict())
    
    print("Seeding Scan Log...")
    # Items list: Karbohidrat, Protein Hewani, Protein Nabati, Sayur, Buah
    scans = [
        ScanLog(nampan_id='NPG-0312', timestamp=datetime.now() - timedelta(minutes=5), petugas_nik='SPG-001', items=[{'kategori': 'Karbohidrat', 'jumlah': 1}, {'kategori': 'Protein Hewani', 'jumlah': 1}, {'kategori': 'Sayur', 'jumlah': 1}, {'kategori': 'Buah', 'jumlah': 1}]),
        ScanLog(nampan_id='NPG-0311', timestamp=datetime.now() - timedelta(minutes=8), petugas_nik='SPG-001', items=[{'kategori': 'Karbohidrat', 'jumlah': 1}, {'kategori': 'Protein Nabati', 'jumlah': 1}, {'kategori': 'Sayur', 'jumlah': 1}]),
        ScanLog(nampan_id='NPG-0310', timestamp=datetime.now() - timedelta(minutes=11), petugas_nik='SPG-001', items=[{'kategori': 'Karbohidrat', 'jumlah': 1}, {'kategori': 'Protein Hewani', 'jumlah': 2}, {'kategori': 'Sayur', 'jumlah': 1}]),
        ScanLog(nampan_id='NPG-0309', timestamp=datetime.now() - timedelta(minutes=14), petugas_nik='SPG-002', items=[{'kategori': 'Karbohidrat', 'jumlah': 1}, {'kategori': 'Protein Hewani', 'jumlah': 1}]),
        ScanLog(nampan_id='NPG-0308', timestamp=datetime.now() - timedelta(minutes=17), petugas_nik='SPG-002', items=[{'kategori': 'Karbohidrat', 'jumlah': 1}, {'kategori': 'Protein Nabati', 'jumlah': 1}, {'kategori': 'Sayur', 'jumlah': 2}, {'kategori': 'Buah', 'jumlah': 1}]),
    ]
    for s in scans:
        db.collection('scan_log').add(s.to_dict())

    print("Seeding Admin User...")
    db.collection('admins').document('admin').set({
        'username': 'admin',
        'password': 'password123',
        'nama': 'Administrator Utama'
    })

    print("Database seeded successfully to Firestore!")

if __name__ == '__main__':
    seed_data()
