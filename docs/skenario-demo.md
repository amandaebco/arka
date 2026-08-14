# Skenario demo per agent — dan data yang harus ada agar tiap babak maksimal

Disusun terbalik: mulai dari **apa yang harus terlihat di layar**, baru mundur ke
**data apa yang harus ada** supaya adegan itu bisa terjadi. Angka "sekarang" di
bawah diukur langsung dari database 12 Agustus, bukan diperkirakan.

## Keadaan data hari ini

| | Sekarang | Target rencana | Cukup? |
|---|---|---|---|
| Equipment | 505 | ~5.000 | kurang |
| Work order | 3.009 | ~20.000 | kurang |
| **Notifikasi** | **8** | ~15.000 | **jauh kurang** |
| **WO tanpa equipment (kotor)** | **0** | ~8% | **tidak ada sama sekali** |
| Pabrik | 5 | 6–8 | cukup |
| Unit RF-8000 (armada seragam) | 5 | ≥5 | cukup |
| Dokumen / potongan | 54 / 104 | 3–5 min | cukup |
| Failure event | 63 | — | cukup |
| Klaim curator | 5 (semua `unreviewed`) | — | cukup |
| Alarm / sensor | 0 / 0 | — | kosong |

Dua kekurangan yang paling merugikan demo: **notifikasi teks bebas** dan
**data kotor**. Keduanya justru bahan bakar adegan paling meyakinkan.

---

## Babak 1 — Scout : "tidak ada yang menyuruh"

**Yang terlihat.** Tanpa ada manusia menyebut nomor aset, Scout memindai armada
dan mengangkat 2 kasus dari 24 kegagalan terbuka. Yang **ditolak** ikut
ditampilkan beserta alasannya.

**Keputusan yang dipamerkan.** Mana yang layak diselidiki.

**Kenapa penolakan itu penting.** Daftar yang hanya memuat temuan menarik tidak
bisa dibantah. Daftar yang memuat penolakan bisa diperiksa — dan itulah yang
membedakan penyaring dari pajangan.

**Data sekarang:** 24 kasus terbuka · 2 diangkat · 22 ditolak · `PLT-S/FIL-118`
di 0,28 sebagai penolakan yang jelas. **Sudah cukup.**

**Tambahan yang membuatnya lebih kuat:**
- 3–4 kasus di **zona abu-abu 0,45–0,55**, tepat mengapit ambang 0,50. Sekarang
  lompatannya terlalu lebar (0,74 → 0,28), sehingga ambang terkesan tidak pernah
  benar-benar diuji.
- Satu kasus yang **dulu ditolak lalu naik** setelah preseden baru masuk. Ini
  memperlihatkan skor sebagai fungsi bukti, bukan label tetap.

---

## Babak 2 — Investigator : "membaca yang ditulis manusia"

**Yang terlihat.** Investigator menelusuri graf 4–5 hop, menemukan 5 preseden di
4 pabrik, mengumpulkan 4 sitasi, lalu berhenti dan **minta putusan manusia**
karena dua kandidat berselisih 0,0252.

**Keputusan yang dipamerkan.** Langkah penelusuran berikutnya, dan kapan menyerah
ke manusia.

**⚠️ Ini babak yang paling dirugikan kekurangan data.** Tugas model di sini
adalah **menafsirkan teks bebas notifikasi** — dan notifikasi yang ada cuma **8**.
Penonton tidak akan pernah melihat kemampuan itu bekerja.

**Yang perlu ditambahkan — prioritas tertinggi:**
- **300–500 notifikasi teks bebas** pada armada RF-8000, ditulis dengan gaya
  teknisi sungguhan: singkatan, huruf kecil semua, kalimat terpotong.
- **Kosakata yang berbeda untuk gejala yang sama.** Ini inti argumen "kenapa
  bukan pencarian kata kunci":
  - "kebocoran produk di kepala pengisi"
  - "produk merembes wkt filling"
  - "bocor halus di nozzle, kena conveyor"
  - "drip di head 3, operator lap tiap shift"
- **Notifikasi yang menyesatkan**: keluhan yang terdengar mirip tetapi berakar
  lain (mis. kebocoran karena gasket kendor, bukan seal aus), supaya Investigator
  terlihat **menyingkirkan** kandidat, bukan hanya mengumpulkan.

---

## Babak 3 — Reporter : "bentuk berubah, angka tidak"

**Yang terlihat.** Temuan yang sama diterbitkan sebagai memo, nota dinas, dan
laporan. Blok dan urutannya berbeda; setiap angka identik.

**Keputusan yang dipamerkan.** Blok mana yang masuk dan urutannya.

**Data sekarang: sudah cukup.** Tiga jenis dokumen hidup, 8 blok, 4 sitasi.

**Tambahan yang membuatnya lebih tajam:**
- Satu temuan dengan **blok yang sengaja kosong** — misalnya kasus tanpa preseden
  sama sekali. Reporter harus **menghilangkan** blok itu, bukan mengisinya dengan
  contoh. Adegan "blok yang tidak punya data dibiarkan hilang" jauh lebih
  meyakinkan daripada dokumen yang selalu penuh.
- Satu kasus **tanpa sitasi** untuk memperlihatkan `DokumenTanpaSitasi` menolak
  menerbitkan. Penjaga yang tidak pernah terlihat menolak tidak bisa dipercaya.

---

## Babak 4 — Designer : "penekanan, bukan angka"

**Yang terlihat.** Infografis satu halaman, 7 blok visual, dengan penekanan
berbeda untuk persona berbeda.

**Keputusan yang dipamerkan.** Bentuk dan penekanan visual.

**⛔ Terhalang kredit gpt-image**, bukan data. Data untuk ini sudah lengkap.

**Tambahan kalau kredit terisi:** dua persona atas temuan yang sama — versi
*engineer_diagnosis* dan versi eksekutif. Perbedaan bentuk dengan angka identik
adalah demonstrasi Constitution 1.2.0 dalam satu layar.

---

## Babak 5 — Curator : "yang aman disetujui sendiri"

**Yang terlihat.** 5 klaim baru dinilai: yang berkeyakinan tinggi disetujui
otomatis, yang rendah ditolak, sisanya diantre ke pakar.

**Keputusan yang dipamerkan.** Pemetaan mana yang aman disetujui otomatis.

**Data sekarang:** 5 klaim, keyakinan 0,90 · 0,72 · 0,70 · 0,50 · 0,40, semuanya
`unreviewed`. Sebarannya bagus. **Cukup untuk satu putaran.**

**Tambahan:**
- **Satu klaim yang bertentangan dengan fakta yang sudah ada di graph.** Curator
  yang hanya pernah menerima tidak membuktikan apa pun; yang pernah menolak
  kontradiksi membuktikan ia membaca.
- Klaim di **0,60–0,65**, tepat di sekitar ambang persetujuan otomatis.
- `claim_reviews` masih **0 baris** — setelah demo, jejak keputusannya harus
  tersimpan, kalau tidak babak ini tidak meninggalkan bukti.

---

## Babak 6 — Penilai / QA : "penjaga yang pernah menolak"

**Yang terlihat.** Penilai membaca halaman PDF hasil render lewat vision,
mencocokkan setiap string dengan `Finding`, lalu `selesai` menghentikan putaran.

**Keputusan yang dipamerkan.** Layak terbit atau harus diperbaiki.

**⚠️ Kelemahan demo saat ini: penilai selalu meluluskan.** Penjaga yang tidak
pernah terlihat menolak sama saja dengan tidak ada.

**Yang perlu ditambahkan:** satu putaran yang **sengaja gagal dulu** — misalnya
temuan dengan nama unit sangat panjang yang membuat teks terpotong saat dirender.
Penilai menolak di putaran 1, reporter memperbaiki, lulus di putaran 2. Itu
adegan terkuat di seluruh demo: sistem yang menangkap kesalahannya sendiri.

---

## Babak 7 — Tanya-jawab / GraphRAG : "jawaban dengan rujukan"

**Yang terlihat.** Pertanyaan bebas dijawab dengan sitasi ke dokumen asli, dan
pertanyaan di luar domain **ditolak** alih-alih dikarang.

**⛔ Terhalang embedding** (billing GCP), bukan data. 104 potongan sudah ada.

**Tambahan:** 2–3 pertanyaan uji yang **seharusnya tidak terjawab** ("berapa
anggaran pemeliharaan tahun depan?"), untuk memperlihatkan ambang 0,60 menolak.

---

## Data kotor — yang sekarang sama sekali belum ada

Nol dari yang dijanjikan. Padahal ini pembeda "demo yang jujur" dari "demo yang
mulus mencurigakan": setiap penilai berpengalaman tahu data lapangan tidak pernah
bersih, dan sistem yang hanya jalan di data bersih tidak berarti apa-apa.

Usulan, urut dari yang paling bernilai untuk ditampilkan:

1. **~8% WO tanpa `equipment_id`** (sekarang 0). Perlihatkan Scout tetap bekerja
   dan **melaporkan berapa banyak yang tidak bisa dipetakan** — bukan diam-diam
   membuangnya.
2. **Tag aset dengan typo ala OCR**: `PLT-U/FIL-2O7` (huruf O, bukan nol),
   `PLT-U/FlL-207` (huruf l kecil). Perlihatkan pencocokan tetap menemukannya.
3. **Tag ambigu**: dua unit berbeda pernah memakai nomor yang sama di masa lalu.
4. **Notifikasi tanpa isi** atau berisi `"-"`, `"tes"`, `"asdf"` — kenyataan di
   setiap CMMS.
5. **Tanggal tidak masuk akal**: WO selesai sebelum dibuka, atau bertahun 1900.
6. **Duplikat**: notifikasi sama dikirim dua kali dengan selisih menit.

Semuanya harus **di luar jalur emas** supaya angka `PLT-U/FIL-207` yang sudah
terkalibrasi tidak bergeser. Jalur emas adalah kontrak yang sudah diuji; data
kotor menumpang di sekitarnya, bukan menembusnya.

---

## Urutan pengerjaan yang saya sarankan

| Prioritas | Pekerjaan | Kenapa |
|---|---|---|
| 1 | 300–500 notifikasi teks bebas, kosakata beragam | Membuka satu-satunya kemampuan Investigator yang belum pernah terlihat |
| 2 | Data kotor 1–3 (WO yatim, typo OCR, tag ambigu) | Mengubah demo mulus jadi demo yang dipercaya |
| 3 | Putaran QA yang gagal dulu lalu lulus | Adegan terkuat, dan paling murah dibuat |
| 4 | Kasus zona abu-abu 0,45–0,55 untuk Scout | Membuktikan ambang benar-benar diuji |
| 5 | Klaim kontradiktif untuk Curator | Membuktikan curator membaca, bukan menyetujui |
| 6 | Volume latar ke ~5.000 equipment | Kredibilitas skala; paling mahal, paling tidak terlihat |

⚠️ **Setelah data berubah, wajib**: jalankan ulang kalibrasi dan pastikan margin
eskalasi `PLT-U/FIL-207` tetap 0,0252. Bobot dan ambang **tidak boleh disentuh** —
keduanya kebijakan yang sudah diterbitkan. Yang disetel selalu datanya.
