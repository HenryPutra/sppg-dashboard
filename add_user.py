from app import db
from models import Karyawan

def add_empty_user():
    if not db:
        print("Error: Database not connected. Check serviceAccountKey.json")
        return

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
    doc_ref = db.collection('karyawan').document('SPG-999')
    if not doc_ref.get().exists:
        doc_ref.set(new_user.to_dict())
        print("User SPG-999 berhasil ditambahkan ke Firestore!")
    else:
        print("User SPG-999 sudah ada di database Firestore.")

if __name__ == '__main__':
    add_empty_user()
