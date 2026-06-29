from app import app, db
from models import Karyawan

def add_empty_user():
    with app.app_context():
        new_user = Karyawan(
            nik='SPG-999',
            nama='Petugas Baru (Kosong)',
            posisi='Tester',
            shift_dominan='Pagi',
            pin='123123',
            is_active=True,
            last_login=None
        )
        # Check if exists
        existing = Karyawan.query.filter_by(nik='SPG-999').first()
        if not existing:
            db.session.add(new_user)
            db.session.commit()
            print("User SPG-999 berhasil ditambahkan!")
        else:
            print("User SPG-999 sudah ada di database.")

if __name__ == '__main__':
    add_empty_user()
