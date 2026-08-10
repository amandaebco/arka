# Tasks: Modul `designer`

**Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md) · **Constitution**: 1.2.0

## Catatan kejujuran urutan

Berkas ini ditulis **setelah** sebagian tugas dikerjakan. Alur yang ditetapkan
Constitution adalah `specify → plan → tasks → implement`, dan langkah `tasks`
dilewati: peta pemindahan di `plan.md` sudah cukup rinci untuk langsung
dikerjakan, jadi implementasi berjalan lebih dulu.

Constitution mengatur situasi ini pada bagian Alur Kerja — komponen yang sudah
berjalan didokumentasikan apa adanya, dan tidak ada klaim bahwa ia lahir dari
spesifikasi. Status di bawah karena itu ditandai terbuka. Riwayat commit terbuka
bagi penilai dan harus cocok dengan yang dinyatakan di sini.

## Status

| | Tugas | Status | Berkas |
|---|---|---|---|
| T001 | Pindahkan pustaka desain dan pemuatnya; validasi lolos di repo ini | ✅ | `app/designer/design/`, `app/designer/knowledge/` |
| T002 | Susun isi kanvas dari `Blok`, verbatim, dengan format angka terpusat | ✅ | `app/designer/content.py` |
| T003 | Spesifikasi penyajian + validator yang menolak blok di luar pilihan reporter | ✅ | `app/designer/presentation.py` |
| T004 | Composer: spesifikasi → prompt, deterministik | ✅ | `app/designer/composer.py` |
| T005 | Penggambar halaman; gagal terang-terangan, tanpa jalur mundur diam-diam | ✅ | `app/designer/image.py` |
| T006 | Bungkus designer sebagai `LlmAgent` dengan dua tool | ✅ | `app/agents/designer.py` |
| T007 | Pemeriksa infografis pada penilai — imbangan kedua Prinsip I | ✅ | `app/agents/qa.py` |
| T008 | Rangkai `designer_terjaga` sebagai `LoopAgent`, maksimum tiga putaran | ✅ | `app/agents/qa.py` |
| T009 | Pengujian bagian deterministik | ✅ | `tests/designer/` (31 tes) |
| T010 | Pembaca halaman berbasis vision — imbangan kedua yang sesungguhnya | ✅ | `app/designer/inspection.py` |
| T011 | Jejak audit per run (FR-018) | ✅ | `app/designer/trail.py` |
| T012 | Rangkai `reporter → designer` dalam satu sesi | ✅ | `penerbitan_lengkap`, `adk_agents/penerbitan/` |
| T013 | Selaraskan bagian prinsip pada `CLAUDE.md` | ✅ | `CLAUDE.md` |
| T014 | Terbitkan infografis dari data ARKA | ✅ | `scripts/render_infografis.py` |
| T015 | Persona `engineer` dan `reliability_manager` diuji | ✅ | keduanya menghasilkan halaman berbeda |
| T016 | Jalankan `penerbitan_lengkap` pada sesi ADK hidup | ✅ | `scripts/jalankan_penerbitan.py` |
| T017 | `RunTrail` dipakai jalur agent, bukan hanya skrip | ✅ | `app/agents/designer.py` |
| T018 | Tekan parafrase label oleh penggambar | ✅ | subjudul dipisah dari arahan gaya |
| T019 | Urutan kartu pada kanvas kadang tidak mengikuti nomornya | ⬜ | terdeteksi, belum ditutup |

## Yang sudah terbukti

Infografis terbit dari `Finding` milik ARKA, untuk kedua persona, dengan seluruh
nilai verbatim dan jejak audit lengkap per run.

Pembaca halaman berbasis vision terbukti menangkap cacat nyata: satu run lebih
awal mengarang chip "Lokasi Fungsional" dari judul dokumen sitasi, dan
pemeriksaan hulu meloloskannya karena string itu memang ada di temuan. Hanya
membaca gambarnya yang menangkapnya.

## Rantai agent terbukti berjalan

`penerbitan_lengkap` dijalankan pada sesi ADK in-memory: reporter menerbitkan memo,
penilai meluluskannya, designer membaca blok dari state, penilai visual membaca
gambarnya. 66 teks terbaca, seluruhnya berasal dari isi kanvas, satu putaran.

Dua cacat ditemukan justru karena rantai itu dijalankan, dan keduanya tidak akan
pernah terlihat dari pengujian deterministik:

1. **`KUNCI_BERKAS_INFOGRAFIS` tidak pernah diisi.** Pemeriksa teks tergambar
   menjawab "belum ada infografis" dan penilai **tetap meluluskan halaman**.
   Pemeriksaan terkuat tidak berjalan, dan tidak ada yang protes.
2. **Pemeriksaan yang tidak berjalan diperlakukan seperti yang lulus.** Kini
   alatnya menjawab `GAGAL PERIKSA`, dan instruksi penilai menyatakan bahwa
   pemeriksaan yang tidak berjalan bukan pemeriksaan yang lulus.

T018 ditutup dengan memisahkan `presentation.reference` — arahan gaya untuk
penggambar, tidak pernah dicetak — dari `presentation.subtitle`, teks yang benar
benar tampil di bawah judul dalam bahasa laporan. Sebelumnya keduanya satu field,
sehingga arahan "McKinsey-style reliability strategy brief" tercetak ke kanvas.

## Yang belum terbukti

**T019** — nomor kartu benar, tetapi penempatannya di kanvas kadang tidak
mengikuti urutan itu (2, 3, 1 pada satu baris). Pemeriksa visual tidak
menangkapnya karena ia menilai kesetiaan teks dan penekanan, bukan urutan
penempatan.

## Urutan pemotongan bila waktu menipis

Mengikuti Governance: yang dipotong adalah cakupan, bukan prinsip.

1. T013 — persona kedua. Satu persona sudah cukup untuk membuktikan mekanismenya.
2. Bentuk visual pilihan pada `visualization_patterns` — blok dirender sebagai
   teks biasa, yang selalu aman.
3. **Tidak pernah dipotong**: T007. Tanpa pemeriksa kesetiaan teks, pengecualian
   Prinsip I kehilangan penjaganya, dan infografis kehilangan dasar untuk
   dipercaya.
