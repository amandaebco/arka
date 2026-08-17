# Panduan slide — presentasi ARKA, 10 menit

Untuk dimasukkan ke slide generator. **13 slide.** Alokasi waktunya mengikuti
`.context/arka-pitch.md`, jadi slide ini latar dari naskah yang sudah ada —
bukan naskah baru.

**Aturan yang menentukan tampilannya:**

- Teks di slide **sedikit**. Yang bicara Anda, bukan slide. Kalau satu slide
  butuh dibaca lebih dari 6 detik, ia terlalu ramai.
- Setiap angka di slide ini **terukur dari sistem yang berjalan** — kecuali satu
  yang ditandai asumsi. Jangan menambah angka baru saat mendesain.
- Slide demo (5–8) hanya bingkai penahan. Layar sesungguhnya adalah aplikasinya.
- Nama pabrik **fiktif**: Pabrik Utara, Barat, Timur, Selatan, Tengah. Jangan
  memakai nama kota nyata.

---

## Slide 1 — Hook (45 dtk)

**Tanpa judul. Tanpa perkenalan diri.** Yang tampil langsung artefaknya.

**Teks di slide:**
> **PLT-U/FIL-207 · Pabrik Utara**
> Pola kegagalan cocok dengan 5 preseden di 4 pabrik lain.
> Keyakinan 91% · **Menunggu putusan manusia**
>
> _Tidak ada yang memintanya. Ditemukan sendiri._

**Visual:** tangkapan layar memo terbitan ARKA (halaman pertama), atau kartu
peringatan bergaya notifikasi. Latar gelap, satu blok teks di tengah.

**Catatan panggung:** diam 3–4 detik setelah slide muncul. Biarkan juri membaca.
Jangan mengisi keheningan.

---

## Slide 2 — Masalah (1 mnt)

**Judul:** Solusinya sudah ada. Tak pernah sampai ke tangan yang tepat.

**Teks di slide (3 baris, jangan lebih):**
- Kegagalan yang sama terulang di pabrik berbeda
- Jawabannya ada — di laporan tahun lalu, di pabrik sebelah, di kepala orang senior
- Setiap kali, dibayar ulang dari nol

**Visual:** lima ikon pabrik berjajar, empat abu-abu satu menyala merah. Garis
putus-putus antar pabrik yang **tidak** tersambung — celahnya yang jadi pesan.

---

## Slide 3 — Kenapa cara sekarang gagal (1 mnt)

**Judul:** Pencarian kata kunci tidak menemukan hal yang sama disebut berbeda

**Teks di slide:**
> Teknisi A menulis: _"kebocoran produk di kepala pengisi"_
> Teknisi B menulis: _"produk merembes waktu pengisian"_
>
> **Masalah yang sama. Nol kata yang sama.**

**Visual:** dua kutipan bersebelahan, kata-kata disorot untuk menunjukkan tidak
ada yang beririsan. Di bawahnya satu baris kecil: `RAG biasa → 0 hasil`.

---

## Slide 3b — Kenapa knowledge graph, bukan RAG biasa (1 mnt)

**Judul:** Jawabannya tidak ada di dokumen mana pun

**Teks di slide:**
> Pabrik sudah punya catatan kegagalan yang pernah terjadi — penyebab yang
> terbukti, tindakan yang berhasil. Kasus baru hari ini sering sudah pernah
> dipecahkan, cuma di pabrik lain.
>
> **Entitas:** Plant · Equipment · Component · FailureEvent · Symptom · Cause ·
> FailureMode · WorkOrder · MaintenanceActivity
> **Relasi:** `LOCATED_IN` · `HAS_COMPONENT` · `HAS_FAILURE_EVENT` ·
> `HAS_SYMPTOM` · `HAS_VERIFIED_CAUSE` · `HAS_DAMAGE` · `HAS_ACTIVITY`
>
> Tidak ada satu laporan pun yang berbunyi *"kegagalan di Pabrik Utara hari ini
> sama dengan kasus Pabrik Barat delapan bulan lalu."* Kalimat itu lahir dari
> menyambungkan lima catatan terpisah.

**Yang diucapkan:**

> "ARKA menghubungkannya lewat knowledge graph: mesin terhubung ke komponennya,
> komponen ke kegagalannya, kegagalan ke gejala, penyebab terverifikasi, dan
> tindakan perbaikan yang dikerjakan. Jadi dari satu kegagalan yang terbuka hari
> ini, ia bisa berjalan ke kegagalan lain di pabrik berbeda yang **model
> mesinnya sama, komponennya sama, gejalanya muncul lagi, dan kasusnya sudah
> tuntas**.
>
> RAG biasa tidak bisa sampai ke sana, dan alasannya bukan kualitas model —
> jawabannya memang tidak ada di dokumen mana pun. RAG mengambil potongan teks
> yang mirip pertanyaannya. Ia tidak bisa menyaring 'yang statusnya sudah
> selesai', tidak bisa menghitung 'terulang tiga kali di tiga pabrik', dan tidak
> bisa meneruskan penelusurannya ke suku cadang beserta pemasoknya. Itu semua
> relasi, bukan kemiripan kalimat."

**Kalau ditekan lebih jauh — satu contoh yang biasanya menutup diskusi:**

> "Pertanyaan 'berapa pabrik yang memakai suku cadang ini dan berapa lead
> time-nya' tidak akan pernah terjawab oleh pencarian dokumen — tidak ada dokumen
> yang memuatnya. Itu hasil menelusuri graph dari komponen ke suku cadang ke
> pemasok. Dan justru angka itu yang mengubah temuan jadi tindakan."

⚠️ **Dua kata yang harus dijaga di slide ini:**

1. **Jangan bilang "similarity".** Skor deteksi memakai **irisan gejala kanonik**
   — cocok atau tidak, bukan kemiripan vektor. Menyebut "similarity" mengundang
   pertanyaan "embedding apa?" dan jawabannya akan terdengar mundur. Katakan
   *"gejala yang sama muncul lagi"*.
2. **Sebut "knowledge graph", bukan "GraphRAG"**, untuk penelusuran deterministik
   ini. GraphRAG di ARKA adalah lapisan tanya-jawab yang menggabungkan graph
   dengan potongan dokumen — mesin berbeda, babak berbeda.

**Visual:** graph kecil, satu FailureEvent terbuka di kiri menyala, jalur relasi
melintas ke tiga FailureEvent tuntas di pabrik berbeda. Di bawahnya satu baris:
`48.065 simpul · 49.093 relasi`.

---

## Slide 4 — Lima agent, lima keputusan (30 dtk)

**Judul:** Lima agent, masing-masing satu keputusan

**Teks di slide (tabel ringkas):**

| Agent | Keputusan miliknya |
|---|---|
| Scout | Mana yang layak diselidiki |
| Investigator | Langkah berikutnya, kapan menyerah ke manusia |
| Reporter | Blok mana yang masuk dokumen |
| Designer | Penekanan dan bentuk visual |
| Curator | Fakta mana yang aman disetujui otomatis |

**Visual:** rantai `Scout → Investigator → Reporter → Designer` mendatar, dengan
`Curator` terpisah di bawah (ortogonal, bukan bagian rantai).

**Catatan panggung:** cepat saja. Ini jembatan menuju demo, bukan tujuan.

---

# DEMO — 4 menit (slide 5–8 hanya bingkai penahan)

> Slide-slide ini nyaris kosong. Layar utama adalah aplikasi yang berjalan.
> Kalau demo langsung gagal, slide ini yang menahan cerita — jadi setiap slide
> punya satu angka cadangan.

---

## Slide 5 — Babak 1: menemukan tanpa diminta (30 dtk)

**Teks di slide:**
> **24** kegagalan terbuka dipindai
> **2** diangkat · **22** ditolak, berikut alasannya

**Visual:** tangkapan layar tab *Fleet & Scout Overview*.

**Catatan panggung:** tekankan **22 yang ditolak**. Daftar yang hanya memuat
temuan menarik tidak bisa dibantah; yang memuat penolakan bisa diperiksa.

---

## Slide 6 — Babak 2: kenapa? (1,5 mnt)

**Teks di slide:**
> **5** preseden · **4** pabrik · **4** sitasi resmi
> Penelusuran graf 4–5 hop

**Visual:** diagram hop: `Aset → Work Order → Dokumen Inspeksi → Sparepart →
Pabrik lain`. Setiap simpul membawa label nyata dari kasus.

---

## Slide 7 — Babak 3: rantai pasok (45 dtk) ← **pembeda**

**Judul:** Kekritisan yang dihitung ulang dari kondisi nyata

**Teks di slide:**

| | Master data ERP | Hitungan ARKA |
|---|---|---|
| Kekritisan `SP-SEAL-8801` | 0,30 _(rendah)_ | **0,87** _(kritis)_ |

> Vendor tunggal · lead time **6 minggu** · dipakai **5 pabrik**
> **Selisih +0,57** — baru terbaca saat mesin sudah berhenti

**Visual:** dua batang berdampingan, 0,30 abu-abu vs 0,87 merah. Selisihnya
diberi tanda.

**Catatan panggung:** inilah lapisan yang tidak dimiliki peserta lain. Beri
waktu.

---

## Slide 8 — Babak 4: mengaku tidak yakin (45 dtk)

**Judul:** Yang paling penting: ia berhenti

**Teks di slide:**
> Kandidat 1 — degradasi seal · **0,9070**
> Kandidat 2 — penyimpangan torsi · **0,8819**
>
> Selisih **0,0252** → di bawah ambang keyakinan
> **ESKALASI — menunggu putusan manusia**

**Visual:** dua batang nyaris sama tinggi, dengan pita "ambang 0,05" melintang.

**Catatan panggung:** kalimat kunci — *"Sistem yang tidak pernah bilang tidak
tahu, tidak bisa dipercaya waktu bilang tahu."*

---

## Slide 9 — Prinsip yang tidak bisa ditawar (45 dtk)

**Judul:** Model tidak pernah menyentuh angka

**Teks di slide (dua kolom):**

| Deterministik — kode | LLM |
|---|---|
| Skor, kekritisan, traversal | Memilih jalur penelusuran |
| Setiap angka & grafik | Menyusun narasi |
| Sitasi | Mengusulkan blok dokumen |

> Salah pilih urutan paragraf → diperbaiki putaran berikutnya
> Salah ketik angka → **fatal**

**Visual:** diagram dua jalur dari one-pager bagian 03 (bisa diambil langsung —
sudah SVG, tinggal ekspor). Garis putus-putus bertuliskan **"tidak ada angka
yang melintas"**.

---

## Slide 10 — Arsitektur (45 dtk)

**Judul:** Empat lapis, satu antarmuka penyimpanan

**Teks di slide:**
- Google ADK · 8 agent dilayani satu image
- PostgreSQL + Apache AGE + pgvector · **atau** BigQuery — hasil identik
- 39 tabel kanonik · 6.471 node · 10.094 edge · 104 potongan dokumen

**Visual:** diagram empat lapis dari one-pager bagian 07 (ekspor SVG).

**Catatan panggung:** satu kalimat yang layak disebut — rantai yang sama atas
data yang sama menghasilkan **angka identik** dari dua penyimpanan berbeda.
Portabilitasnya diukur, bukan diklaim.

---

## Slide 11 — Bisa diganti tanpa mengubah kode (30 dtk)

**Judul:** Penyedia model adalah setelan, bukan keputusan arsitektur

**Teks di slide:**
> `TEXT_PROVIDER` → Gemini 3.6 Flash **atau** DeepSeek v4
> `EMBED_PROVIDER` → gemini-embedding-2 **atau** text-embedding-3-large
> `ARKA_STORE` → PostgreSQL **atau** BigQuery
>
> **Angkanya tidak berubah sedikit pun** — karena angka memang tidak pernah
> lewat model.

**Visual:** tiga sakelar bergaya toggle. Sederhana.

**Catatan panggung:** ini jawaban untuk juri yang bertanya soal ketergantungan
vendor. Sudah dibuktikan hidup, bukan rencana.

---

## Slide 12 — Nilai bisnis (1 mnt)

**Judul:** Yang berubah untuk perusahaan

**Teks di slide:**
- Preseden ditemukan dalam **100 detik**, bukan lewat pencarian manual
- Preseden terkuat pernah menahan mesin **44 jam**
- Kekritisan sparepart terkoreksi **+0,57** sebelum stok habis
- Keputusan datang dengan **tingkat keyakinan**, bukan tebakan

**Visual:** empat kartu angka. Bersih, tanpa ikon berlebihan.

⚠️ Kalau menyebut rupiah, **sebut sebagai asumsi**: "asumsi biaya downtime
industri ~Rp750 juta/jam". Itu satu-satunya angka yang tidak diukur dari sistem,
dan seluruh kredibilitas angka lain bergantung pada Anda mengatakannya.

---

## Slide 13 — Penutup (30 dtk)

**Teks di slide (satu kalimat, besar):**
> **Pengetahuan yang sudah dibayar sekali,
> tidak perlu dibayar lagi.**

Di bawahnya, kecil:
> github.com/amandaebco/arka · 472 tes · data sintetis sepenuhnya

**Visual:** kosong selain teks. Jangan ada yang mengalihkan perhatian.

---

## Aset yang bisa langsung dipakai

| Kebutuhan | Sumber |
|---|---|
| Infografis satu halaman | `out/infografis/20260810-183730-arka-2026-0042/round-1-page.png` |
| Memo / nota dinas / laporan | `out/memo.pdf`, `out/nota_dinas.pdf`, `out/laporan.pdf` |
| Dashboard | `out/dashboard.html` (screenshot) |
| Diagram dua jalur (slide 9) | one-pager bagian 03 — SVG inline, tinggal ekspor |
| Diagram empat lapis (slide 10) | one-pager bagian 07 — SVG inline |
| Tangkapan layar armada (slide 5) | `http://127.0.0.1:5175` tab Fleet & Scout |

⚠️ **Jangan** memakai tab *GraphRAG Investigation* dan *Interactive Agent Chat*
untuk tangkapan layar sampai keduanya dibereskan — isinya masih data contoh yang
bertentangan dengan memo (`SP-BELT-1150`, pabrik `PLT-K` yang tidak ada).

---

## Kalau ditanya juri

**"Kenapa graph, bukan RAG biasa?"** → Batch pemasok yang sama terpasang di
5 pabrik adalah relasi, bukan kemiripan teks. Cosine tidak bisa menemukannya.

**"Datanya sintetis, bagaimana di data nyata?"** → Generatornya menulis ke tabel
kanonik yang bentuknya mengikuti CMMS sungguhan. Yang berganti implementasi
repository — satu berkas.

**"Angka 0,40 untuk ambang kemiripan, dari mana?"** → Diukur atas 54 dokumen
dengan sepuluh pertanyaan; dalam-domain 0,4736–0,6099, luar-domain berhenti di
0,3366. Sepuluh dari sepuluh benar. Ambang itu milik pasangan model dan korpus,
dan wajib diukur ulang kalau salah satunya berganti.

**"Kenapa endpoint publiknya mati?"** → Akun penagihan project dilepas. Arsitektur
GCP-nya sudah terbukti berjalan; demo hari ini dijalankan lokal di atas
PostgreSQL + Apache AGE, penyimpanan kedua yang paritas angkanya sudah diukur.
