1|# Cashflow Journal v1.5.2 (Bug Fixed)
2|
3|Catatan keuangan personal berbasis web: dashboard single-page untuk mencatat pemasukan, pengeluaran, mutasi, dan hutang. Dibangun dengan **Flask + SQLite per-user** dan di-deploy via **Docker** di port `9102`.
4|
5|## Fitur v1.5.2 (Bug Fixed)
6|
7|- Perbaikan alignment tabel di seluruh halaman (Dashboard, Transaksi, Hutang, Pengaturan)
8|- Pemisahan tabel Kategori menjadi card grid (Pemasukan & Pengeluaran terpisah)
9|- Tombol **Hapus Akun** dipindahkan ke tab **Extra** (Zona Bahaya)
10|- Kolom **Aksi** di tabel Hutang digabung dengan tombol **Bayar** dan **Hapus** dalam satu kolom kompak
11|- Validasi **overpayment**: peringatan jika jumlah bayar melebihi sisa hutang
12|- **Hutang Bawaan (opening)** tidak bisa dihapus — tombol hapus disembunyikan, backend tolak dengan error
13|- Fungsi API helper yang lebih robust: timeout, log, error handling untuk HTML response
14|- Perbaikan konsistensi field payload (`amount`) pada pembayaran hutang
15|- Halaman **Transaksi** sudah memiliki alignment yang konsisten dengan dashboard
16|- Badge tipe pada card kategori dihilangkan karena sudah dipisah berdasarkan tipe
17|
## Fitur v1.5.1

- Perbaikan inisialisasi halaman **Pengaturan** agar list rekening tampil otomatis saat halaman dibuka
- Perbaikan listener JavaScript yang rentan `null reference` pada beberapa elemen UI
- Perbaikan tampilan **tab Kategori** dengan badge tipe pemasukan/pengeluaran
- Pemindahan tombol **Hapus Akun** ke tab **Extra** agar sesuai struktur UI
- Perapihan render data pada dashboard, transaksi, dan settings agar lebih stabil

## Fitur Utama

- Dashboard single-page: ringkasan rekening, form input transaksi, riwayat, dan daftar hutang
- Multi-user auth dengan session dan database SQLite terpisah per user (`data/user_{id}.db`)
- Tipe transaksi: **Pemasukan**, **Pengeluaran**, **Mutasi**
- Biaya admin per transaksi (`amount` = nominal murni, `admin_fee` terpisah)
- Mutasi dan pembayaran hutang antar-rekening diseragamkan ke pola **single transfer record**
- Pengelolaan hutang biasa dan **hutang bawaan** (opsional saat first-time setup)
- First-time onboarding flow: **Rekening + Saldo Awal → Kategori → Hutang Bawaan → Dashboard**
- Account detail modal: Saldo Saat Ini, Saldo Awal, Saldo Masuk, Saldo Keluar, Mutasi Masuk, Mutasi Keluar
- Pengaturan: kelola akun, kategori, dan hapus akun sendiri
- Tema warm minimalis, modal fullscreen (viewport - 24px)
- Favicon 🏦 bank
- Portable: cukup `docker compose up -d` di server baru

## Stack

- Python 3.11
- Flask 3.1 + Gunicorn
- SQLite (per-user)
- Docker + Docker Compose
- Frontend: HTML + CSS + vanilla JavaScript

## Struktur Project

```text
.
├── app
│   ├── main.py                # Flask routes + API
│   ├── db.py                  # SQLite loader + schema init + migrations
│   ├── models.py              # User auth + user-level DB management
│   ├── static
│   │   ├── app.js             # Frontend logic
│   │   ├── transactions.js    # Frontend logic (transactions page)
│   │   └── style.css          # Warm theme
│   └── templates
│       ├── index.html         # Dashboard (main page)
│       ├── login.html         # Login / Register
│       ├── transactions.html  # Full transaction history
│       ├── settings.html      # Account, category & extra settings
│       └── _sidebar.html      # Sidebar component (included via Jinja)
├── data                       # Per-user SQLite databases (runtime)
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## Cara Menjalankan

### Development (tanpa Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app/main.py
```

Buka `http://localhost:8000`.

### Docker (recommended)

```bash
docker compose up -d --build
```

Buka `http://localhost:9102`.

Volume yang di-mount:
- `./app` → `/app/app`
- `./data` → `/app/data`

## Akun Pertama

Saat pertama kali login, kamu akan diminta menyelesaikan setup:
1. Tambah minimal 1 rekening (saldo awal opsional)
2. Tambah minimal 1 kategori pemasukan/pengeluaran
3. Tambah hutang bawaan (opsional)
4. Dashboard aktif

## API Endpoints

Auth:
- `GET /login`
- `POST /login` (`action=login` atau `action=register`)
- `GET /logout`
- `GET /dashboard`

Transactions:
- `GET /api/transactions`
- `POST /api/transactions`
- `DELETE /api/transactions/<id>`

Debts:
- `GET /api/debts`
- `POST /api/debts`
- `POST /api/debts/<id>/pay`
- `DELETE /api/debts/<id>`

Accounts & Categories:
- `GET /api/accounts`
- `POST /api/accounts`
- `PUT /api/accounts/<id>`
- `DELETE /api/accounts/<id>`
- `GET /api/accounts/count`
- `GET /api/categories`
- `POST /api/categories`
- `DELETE /api/categories/<id>`

User:
- `DELETE /api/user` — hapus akun sendiri (semua data user ikut terhapus)

Summary:
- `GET /api/summary`

## Catatan Desain

- Saldo rekening dihitung dari: `opening_balance + income - expense - transfer_out + transfer_in`
- Mutasi keluar: saldo berkurang `amount + admin_fee`
- Mutasi masuk: saldo bertambah `amount` saja
- Hutang biasa: otomatis membuat transaksi pengeluaran saat dibuat
- Hutang bawaan: tidak membuat transaksi saat dibuat; saat dibayar, terkait kredit ke rekening terkait. **Tidak bisa dihapus** untuk menjaga integritas data awal
- Pembayaran hutang dari rekening berbeda tercatat sebagai satu transfer record
- Hapus akun: menghapus user dari `users.db` + menghapus file `data/user_{id}.db`
