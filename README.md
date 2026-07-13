# Otomatika

Aplikasi web yang membedah satu masalah nyata (menghitung ekspresi aritmatika) menjadi
empat tahapan Teori Bahasa dan Otomata: **Tokenizer (Finite State Automata)**,
**Regular Expression**, **Parser Ekspresi Aritmatika (Pushdown Automata & Context-Free
Grammar)**, dan **Transformasi Chomsky Normal Form**.

Dibangun untuk Capstone Project mata kuliah Teori Bahasa dan Otomata - Semester IV,
Tahun Akademik 2025/2026 Genap.

> **Live demo:** `https://[isi-nim-atau-nama-anda].my.id` *(isi setelah deploy)*
> **Video demo:** `https://youtube.com/...` *(isi setelah upload)*

---

## Daftar Fitur per Modul

### Modul 1 - Finite State Automata
- Tokenizer ekspresi aritmatika berbasis satu DFA (strategi *maximal munch*), lengkap
  dengan visualisasi diagram state dan jejak transisi per token (stepper animasi).
- Simulator DFA/NFA kustom: definisikan mesin sendiri via format teks, uji string apa pun,
  tipe mesin (DFA/NFA) terdeteksi otomatis.
- Konversi NFA → DFA (subset construction) lengkap dengan tabel langkah dan diagram
  sebelum/sesudah, termasuk contoh NFA dengan transisi-ε.
- **Bonus:** simulator Moore Machine dan Mealy Machine.

### Modul 2 - Regular Expression
- Mesin regex buatan sendiri (bukan modul `re` bawaan Python): parser → Thompson
  Construction (NFA) → Subset Construction (DFA).
- Mendukung union `|`, `*`, `+`, `?`, grup `()`, character class `[a-z0-9]`, shorthand
  `\d \w \s`.
- Menampilkan tata bahasa reguler (linear kanan) yang ekuivalen dengan DFA hasil kompilasi.
- Uji pencocokan string dengan visualisasi jejak state per karakter.

### Modul 3 - Pushdown Automata & CFG
- Parser ekspresi aritmatika (grammar `E/T/F` standar) dengan teknik *precedence
  climbing*, menghasilkan pohon penurunan, derivasi kiri **dan** kanan, serta simulasi
  stack PDA (shift-reduce) langkah demi langkah.
- **PDA generik:** terima CFG bebas yang didefinisikan pengguna, otomatis dikonversi ke
  CNF lalu diuji keanggotaannya dengan algoritma CYK; jika diterima, pohon penurunan dan
  jejak stack direkonstruksi dari hasil CYK.

### Modul 4 - Hierarki Chomsky & CNF
- Panel edukatif hierarki Chomsky (Tipe 0-3) dan kaitannya dengan tiap modul di atas.
- Konversi CFG sembarang → Chomsky Normal Form, menampilkan setiap langkah transformasi
  (START, eliminasi ε/nullable, eliminasi unit production, eliminasi simbol useless,
  TERM + BIN).
- **Bonus:** konversi ke Greibach Normal Form (bersifat eksperimental untuk grammar yang
  sangat kompleks - aplikasi akan memberi pesan yang jujur jika gagal, bukan hasil yang salah).

---

## Tech Stack

| Bagian | Teknologi |
|---|---|
| Backend | Python 3, Flask |
| Frontend | HTML5, CSS3 (custom), JavaScript (vanilla - tanpa framework), grid/utilitas CSS sendiri (tanpa CDN eksternal) |
| Visualisasi | SVG digambar dinamis di sisi klien (diagram automata, pohon penurunan, tabel CYK) - tanpa library diagram eksternal |
| Pengujian | `unittest` (41 test backend, `tests/test_app.py`) + regresi logika frontend murni via Node `vm` (`tests_js/run.js`) |

Seluruh algoritma inti (automata, regex engine, CYK, konversi CNF/GNF) ditulis manual
tanpa memakai modul `re` bawaan Python, untuk benar-benar mendemonstrasikan konsep
otomata dari mata kuliah, bukan menyerahkannya ke library pihak ketiga.

## Struktur Folder

```
otomatika/
├── app.py                 # seluruh logika Python & routing Flask
├── templates/
│   ├── base.html          # layout bersama (navbar, footer) dipakai semua halaman
│   ├── home.html          # beranda: pipeline demo + kartu navigasi ke 4 modul
│   ├── tokenizer.html     # halaman Modul 1: tokenizer & simulator FSA
│   ├── regex.html         # halaman Modul 2: regular expression
│   ├── parser.html        # halaman Modul 3: parser aritmatika & PDA generik
│   └── cnf.html           # halaman Modul 4: hierarki Chomsky & konversi CNF/GNF
├── static/
│   ├── grid.css            # grid & utilitas layout sendiri (tanpa CDN Bootstrap)
│   ├── style.css          # seluruh gaya CSS
│   └── script.js          # seluruh logika JavaScript sisi klien
├── tests/
│   └── test_app.py        # 41 test case backend
├── tests_js/
│   └── run.js              # test regresi logika frontend murni (Node vm)
├── docs/
│   ├── PROPOSAL_TEMPLATE.md
│   └── AI_USAGE_DISCLOSURE_TEMPLATE.md
├── requirements.txt
├── Procfile                # untuk deploy ke Railway/Render/Heroku-like platform
└── README.md
```

`app.py` dibagi jadi 5 bagian bertanda komentar (`# BAGIAN 1` s/d `# BAGIAN 5`) mengikuti
urutan modul, ditutup bagian `# ROUTES FLASK` untuk endpoint. Semua dalam satu file supaya
gampang diserahkan sebagai satu kesatuan, tapi tetap tersusun rapi per bagian.

## Cara Instalasi Lokal

```bash
git clone https://github.com/[username]/[nama-repo].git
cd [nama-repo]

python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -r requirements.txt
python app.py
```

Aplikasi berjalan di `http://127.0.0.1:5000`.

Menjalankan seluruh test:

```bash
python -m unittest tests.test_app -v   # 41 test backend (Python)
node tests_js/run.js                   # test regresi logika frontend (JS)
```

## Deployment ke Domain `.my.id`

Tech stack Flask ini **bukan** static site, jadi butuh hosting yang menjalankan proses
Python (bukan GitHub Pages/Vercel static). Beberapa opsi gratis/murah yang umum dipakai
mahasiswa:

**Opsi A - Railway / Render (paling mudah)**
1. Push repo ini ke GitHub (public).
2. Buat proyek baru di Railway atau Render, hubungkan ke repo GitHub Anda.
3. Platform akan otomatis mendeteksi `requirements.txt` dan `Procfile`.
4. Setelah deploy sukses, buka pengaturan domain proyek → tambahkan **Custom Domain**.
5. Daftarkan domain gratis di [is.my.id](https://is.my.id) (atau registrar `.my.id`
   berbayar pilihan Anda), lalu arahkan **CNAME** domain tersebut ke domain yang
   diberikan platform hosting.
6. Aktifkan/verifikasi HTTPS (biasanya otomatis via Let's Encrypt pada platform ini).

**Opsi B - VPS (mis. kontabo, IDCloudHost, dsb.)**
1. Install Python, lalu clone repo di server.
2. Jalankan dengan `gunicorn` di belakang **Nginx** sebagai reverse proxy.
3. Arahkan A record domain `.my.id` ke IP VPS.
4. Aktifkan HTTPS dengan `certbot` (Let's Encrypt) - pastikan `http://` di-redirect ke
   `https://` sesuai ketentuan tugas.

> **Penting:** ketentuan tugas mewajibkan HTTPS aktif dan domain dapat diakses **tanpa
> login** saat penilaian, serta tetap aktif minimal 2 minggu setelah batas waktu
> penilaian. Jangan matikan layanan hosting sebelum periode tersebut selesai.

## Catatan Integritas Akademik

Tugas ini bersifat individu. Lihat `docs/AI_USAGE_DISCLOSURE_TEMPLATE.md` untuk lampiran
wajib terkait penggunaan AI generatif dalam pengerjaan proyek ini - isi dengan jujur
sesuai proses Anda sendiri, karena Anda akan diminta menjelaskan konsep di balik kode ini
dengan kata-kata sendiri saat video demo maupun sesi klarifikasi lisan.

---

*README ini adalah template awal - lengkapi bagian bertanda `[isi ...]` sebelum
pengumpulan, dan perbarui daftar fitur bila Anda menambah/mengubah sesuatu.*
