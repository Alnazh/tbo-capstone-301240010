# Proposal Mini - Otomatika
*(Template. Lengkapi dan sesuaikan sebelum dikumpulkan - maksimal 5 halaman ketika dijadikan PDF.)*

**Nama :** _____________________
**NIM  :** _____________________
**Kelas / Semester :** IV

## 1. Latar Belakang Singkat
Jelaskan mengapa ekspresi aritmatika dipilih sebagai studi kasus untuk mendemonstrasikan
empat topik Teori Bahasa dan Otomata (FSA, Regular Expression, PDA/CFG, dan CNF).

## 2. Rancangan Sistem
- **Modul 1 - Tokenizer (FSA):** satu DFA dengan strategi *maximal munch* mengubah
  karakter ekspresi menjadi token (NUMBER, PLUS, MINUS, STAR, SLASH, LPAREN, RPAREN).
- **Modul 2 - Regular Expression:** mesin regex buatan sendiri (parser → Thompson NFA →
  subset construction DFA) untuk menguji pola token, termasuk pola bilangan `[0-9]+(\.[0-9]+)?`.
- **Modul 3 - PDA & CFG:** grammar `E -> E + T | E - T | T`, `T -> T * F | T / F | F`,
  `F -> ( E ) | id` diparsing dengan teknik *precedence climbing*, lalu direpresentasikan
  ulang sebagai simulasi PDA (shift-reduce) beserta derivasi kiri/kanan.
- **Modul 4 - Hierarki Chomsky & CNF:** konversi CFG sembarang ke Chomsky Normal Form
  (langkah START, DEL, UNIT, useless-symbol removal, TERM+BIN), dengan CYK sebagai
  pengenal keanggotaan bahasa, serta konversi Greibach Normal Form.

*(Sisipkan diagram state / pohon derivasi / diagram arsitektur di sini.)*

## 3. Tech Stack
- Backend: Python 3 + Flask
- Frontend: HTML5, CSS3 (custom, tema "blueprint schematic"), JavaScript (vanilla, tanpa framework)
- Visualisasi: SVG digambar dinamis di sisi klien (tanpa library diagram eksternal)
- Deployment: `.my.id` + HTTPS (isi platform yang dipakai, mis. Railway / Render / VPS)

## 4. Rencana Deploy
1. Daftarkan domain di is.my.id (gratis) atau registrar berbayar pilihan Anda.
2. Deploy aplikasi Flask ke layanan hosting pilihan (lihat README.md bagian "Deployment").
3. Arahkan domain `.my.id` ke hosting tersebut, aktifkan HTTPS.

## 5. Timeline Pribadi
| Minggu | Aktivitas |
|---|---|
| 1 | Setup repo, proposal, deploy awal |
| 2 | Modul 1 & 2 |
| 3 | Modul 3 & 4 |
| 4 | Integrasi, pengujian, laporan |
| 5 | Video demo & pengumpulan final |
