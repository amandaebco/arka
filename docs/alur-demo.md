# Alur demo ARKA — run of show

Berbeda dari `skenario-demo.md`, yang menjawab *"data apa yang harus ada"*.
Berkas ini menjawab *"apa yang dilakukan di layar, urutannya, dan apa yang
diucapkan"* — naskah panggung, bukan rencana data.

**Durasi sasaran 11 menit** — kelima agent tampil, ditambah penilai mutu dan
tanya-jawab. Rantai `Scout → Investigator → Reporter` dulu sampai tuntas, baru
dua agent ortogonal; memotong ke urutan lain membuat serah-terimanya hilang. Semua dijalankan **lokal** dengan
`ARKA_STORE=postgres`: billing GCP dilepas 12 Agustus, jadi Cloud Run, BigQuery,
dan Vertex tidak boleh masuk jalur demo. Ini bukan kompromi yang perlu
disembunyikan — seluruh rantai memang berjalan tanpa GCP, dan itu sendiri layak
disebut satu kalimat.

⚠️ **Jangan pernah menyebut angka dari sistem pihak ketiga mana pun** — skala
armada, jumlah edge, persentase cakupan milik proyek lain. Gagasannya boleh
dipakai; angkanya tidak pernah keluar dari mesin ini.

---

## Peta babak — satu agent, satu keputusan

| Babak | Agent | Keputusan yang dipamerkan | Durasi |
|---|---|---|---|
| 1 | `scout` | Mana yang layak diselidiki — dan mana yang tak bisa dinilai sama sekali | 90 dtk |
| 2 | `investigator` | Langkah penelusuran berikutnya, dan kapan menyerah ke manusia | 120 dtk |
| 3 | `reporter` | Blok mana yang masuk dokumen dan urutannya | 90 dtk |
| 4 | `qa` | Layak terbit atau harus diperbaiki | 75 dtk |
| 5 | `designer` | Penekanan dan bentuk visual tiap blok | 75 dtk |
| 6 | `curator` | Pemetaan mana yang aman disetujui otomatis | 75 dtk |
| 7 | `tanya_jawab` | Apa yang didukung bukti — dan apa yang ditolak | 60 dtk |

Babak 1–3 satu rantai berjalan; 4 menempel pada 3; 5–7 berdiri sendiri dan boleh
ditukar urutannya. **Kalau waktu habis, yang dipotong 5 lalu 7** — bukan 4 dan 6.
Babak 1 dan 7 menolak **masukan**: kasus lemah, pertanyaan di luar domain. Itu
penyaring, dan penyaring mudah dipercaya. Babak 4 dan 6 menolak **keluaran ARKA
sendiri** — dokumen yang baru ditulis reporter ditahan penilai, temuan yang baru
disimpulkan investigator tidak boleh masuk graph tanpa persetujuan. Sistem yang
tidak memperlakukan keyakinannya sendiri sebagai bukti jauh lebih sulit dibangun,
dan itulah yang dinilai.

---

## Pra-terbang (H-1, dan sekali lagi 15 menit sebelum tampil)

```bash
docker compose up -d                                   # AGE + pgvector
uv run pytest tests -q                                 # harus hijau seluruhnya
# ALLOW_ORIGINS wajib: tanpa itu peramban ditolak CORS walau alamatnya benar.
ARKA_STORE=postgres ALLOW_ORIGINS="http://localhost:5173,http://127.0.0.1:5173" \
  uv run uvicorn app.api:app --port 8080
curl -s localhost:8080/api/sehat                       # store aktif + kesegaran
curl -s localhost:8080/api/armada | head -c 400        # cache hangat sebelum tampil
cd ../arka-frontend && npm run dev                     # baca .env.local

# ⚠️ arka-frontend/.env.local harus memuat VITE_ARKA_API=http://localhost:8080.
# Tanpa berkas itu, `arka.ts` jatuh ke alamat Cloud Run yang billing-nya
# dilepas, dan seluruh layar berisi "Engine tidak terhubung: Failed to fetch".
# Vite membaca .env.local sekali saat start — kalau berkasnya baru dibuat,
# hentikan `npm run dev` lalu jalankan lagi.
```

Periksa enam hal, dan batalkan babak yang gagal alih-alih memperbaikinya di
depan penonton:

| Yang diperiksa | Harus |
|---|---|
| Header dasbor | `Target: localhost:8080`, bukan alamat Cloud Run |
| `/api/sehat` | `store: postgres`, data segar |
| Margin `PLT-U/FIL-207` | `0,0253` pada 17 Agt — skor `0,9066` dan `0,7399` (digit keempat meluruh sendiri) |
| Kekritisan seal | `0,8667` — angka ini **tidak** meluruh; kalau bergeser, ada regresi |
| `TEXT_PROVIDER` | terisi dan kuncinya hidup; rantai penuh butuh satu penyedia model |
| `VISION_PROVIDER` + `IMAGE_API_KEY` | terisi — tanpa keduanya babak penilai dan designer mati |
| `ARTIFACT_GCS_BUCKET` | **dikosongkan** — kalau terisi, tiap jejak designer mencoba unggah ke GCS dan gagal 403 di layar |
| Indeks pgvector | `ARKA_STORE=postgres uv run python scripts/build_pgvector_index.py` kalau dokumen berubah |

Dua babak terakhir punya kesiapan sendiri:

```bash
uv run python scripts/render_infografis.py --persona engineer   # H-1, bukan saat tampil
uv run python scripts/kurasi.py                                 # kering: melaporkan, tidak menulis
```

Infografis dirender **sebelum** naik panggung — panggilan gambar berbiaya menit,
dan tidak ada demo yang selamat dari menunggu selama itu. Kurasi dijalankan
kering dulu supaya isi antreannya diketahui, lalu `--terapkan` yang dipakai di
panggung.

**Sudah dimuat lebih dulu di tab terpisah**, supaya tidak ada layar menunggu:
memo PDF hasil terbitan terakhir, dan satu infografis contoh.

---

## Babak 0 — masalahnya, 45 detik, tanpa layar

Satu kalimat, bukan paragraf: *kegagalan yang sama berulang di pabrik berbeda,
dan tiap kali dibayar dari nol.* Seal filler rusak di Pabrik Barat, didiagnosis
tiga minggu, diperbaiki, laporannya ditulis — lalu kegagalan yang sama muncul di
Pabrik Utara dan tidak seorang pun di sana tahu semua itu pernah terjadi.

Pengetahuannya ada. Yang tidak ada adalah jalan dari kegagalan berikutnya menuju
pengetahuan itu.

---

## Babak 1 — Scout memindai tanpa diminta · 90 detik

**Di layar:** buka dasbor. Judulnya sudah terisi sebelum siapa pun mengetik
apa pun.

**Yang diucapkan.** Tidak ada manusia yang menyebut nomor aset. Scout memindai
seluruh armada terbuka, mengangkat yang layak, dan — ini bagian yang penting —
**menampilkan yang ditolak beserta alasannya**. Daftar yang hanya memuat temuan
menarik tidak bisa dibantah; daftar yang memuat penolakan bisa diperiksa.

**Tunjukkan waktu pindainya.** Seluruh armada, di bawah dua persepuluh detik,
nol panggilan model. Ini yang menjawab pertanyaan "bagaimana kalau asetnya
ratusan ribu": tahap deterministik menyapu semuanya dengan murah, model hanya
dibelanjakan pada segelintir yang lolos.

**Lalu berhenti sejenak di baris "tidak dapat dinilai".** Kasus-kasus itu tidak
berskor rendah — mereka tidak punya apa pun untuk ditimbang. Skor 0,00 akan
terbaca "sudah diperiksa, aman", padahal artinya "belum diperiksa sama sekali".
Aset yang paling tidak tercatat justru yang paling tidak terlihat, dan ARKA
menyebutnya, bukan menyembunyikannya di balik angka nol.

> Satu kalimat saja, lalu lanjut. Kalau juri mengejar, ada kedalamannya.

---

## Babak 2 — Investigator menelusuri, lalu menyerah ke manusia · 120 detik

**Di layar:** klik kasus teratas, `PLT-U/FIL-207`.

**Yang diucapkan.** Investigator menelusuri graf beberapa hop, menemukan
preseden di pabrik lain, dan mengumpulkan sitasi ke laporan inspeksi yang
ditulis manusia bertahun lalu.

**Puncak babak ini bukan jawabannya, melainkan penolakannya menjawab.** Dua
kandidat berselisih **0,0252** — di bawah ambang keyakinan. ARKA tidak memilih.
Ia mengeskalasi, dan mengatakan persis kenapa. Sistem yang selalu punya jawaban
tidak bisa dipercaya justru pada kasus yang paling mahal.

**Kalau ada waktu:** tunjukkan kekritisan sparepart **0,8667** berhadapan dengan
**0,30** di master data. Selisih 0,5667 pada suku cadang vendor tunggal dengan
lead time enam minggu — itu angka yang membangunkan orang gudang.

---

## Babak 3 — Reporter menerbitkan · 90 detik

**Di layar:** buka memo, lalu nota dinas, lalu laporan atas temuan yang sama.

**Yang diucapkan.** Bentuknya berbeda, angkanya identik — karena angkanya tidak
pernah lewat model. Kode menyusunnya dari `Finding`; model hanya memilih blok
dan menulis narasi di sekelilingnya, dan kalimat narasi yang mengandung angka
dibuang oleh penyaring sebelum terbit.

**Tunjukkan sitasinya.** Dokumen tanpa rujukan **ditolak terbit** — bukan
diberi peringatan, ditolak. Penjaga yang tidak pernah menolak sama saja dengan
tidak ada.

---

## Babak 4 — Penilai mutu menolak dulu, baru meluluskan · 75 detik

**Di layar:** jalankan penerbitan dan biarkan putaran QA terlihat.

**Yang diucapkan.** Sebelum dokumen sampai ke manusia, penilai **membaca halaman
hasil render lewat vision** — bukan memeriksa struktur data, melainkan melihat
apa yang benar-benar tercetak — lalu mencocokkan tiap string terhadap `Finding`.
Angka yang tidak berasal dari temuan tidak lolos, dan teks yang terpotong saat
dirender tertangkap di sini, bukan oleh pembaca dokumen.

Kalau putarannya menolak lebih dulu lalu lulus di putaran kedua, **jangan
buru-buru melewatinya** — sistem yang menangkap kesalahannya sendiri adalah
adegan terkuat di seluruh demo. Kalau ia lulus sekali jalan, sebutkan bahwa
`LoopAgent` memberi tiga kesempatan dan penolakan pernah terjadi pada uji hidup
pertama.

---

## Babak 5 — Designer memutuskan bentuk, bukan isi · 75 detik

**Di layar:** buka infografis yang sudah dirender di pra-terbang, bersanding
dengan memo dari Babak 3.

**Yang diucapkan.** Temuan yang sama, pembaca yang berbeda. Designer memutuskan
**penekanan dan bentuk visual** — dan hanya itu. Pemilihan bloknya tetap milik
Reporter; dua agent tidak boleh punya keputusan yang sama.

Di sinilah satu-satunya kelonggaran dalam konstitusi ARKA berlaku, dan lebih
baik disebut sendiri daripada ditemukan juri: pada infografis, **penggambaran
halaman** berasal dari model. Teks dan angkanya tetap disusun kode dari
`Finding`, tidak ada nilai yang hanya dibawa bentuk, penilai memeriksa tiap
string sebelum terbit, dan memo tetap catatan resmi untuk angka yang dipakai
mengambil keputusan. Yang dipertaruhkan pada infografis keterbacaan; pada memo,
kebenaran. Keduanya tidak ditukar.

**Kalau profil persona sempat ditampilkan:** setiap peran punya daftar hal yang
**tidak boleh diklaim** — nilai ROI, OEE, atau profitabilitas yang tidak ada di
sumber ditolak, boleh direkomendasikan tapi tidak boleh dinyatakan angkanya.
Itu menutup jenis halusinasi yang berbeda: bukan mengarang angka, melainkan
mengarang kategori.

---

## Babak 6 — Curator menyetujui yang aman, mengantre sisanya · 75 detik

**Di layar:**

```bash
uv run python scripts/kurasi.py --terapkan
```

**Yang diucapkan.** Ini satu-satunya agent yang tidak berada di rantai. Ia
menilai kandidat fakta hasil penelusuran: yang berkeyakinan tinggi disetujui
sendiri, yang rendah ditolak, sisanya **diantre ke pakar manusia**.

**Satu kalimat yang tidak boleh dilewatkan.** Agent tidak pernah menulis fakta
ke graph. Semua temuan masuk sebagai kandidat `unreviewed` dan menunggu
persetujuan. Sistem yang boleh menulis keyakinannya sendiri ke dalam
pengetahuannya sendiri akan mengeraskan tebakan pertamanya menjadi kebenaran.

Kode keluarnya pun bicara: **1 berarti ada yang menunggu keputusan manusia** —
antrean itu keluaran yang sah, bukan kegagalan.

---

## Babak 7 — Tanya-jawab menolak menjawab · 60 detik

**Di layar:** dua pertanyaan, dan yang kedua yang penting.

1. Pertanyaan dalam domain — dijawab dengan **sitasi ke dokumen asli**, lewat
   GraphRAG: traversal graf digabung potongan dokumen dari pgvector.
2. Pertanyaan di luar domain — *"berapa anggaran pemeliharaan tahun depan?"* —
   **ditolak**, karena tidak ada bukti yang mendukungnya.

**Yang diucapkan.** Ambangnya bukan milik sistem, melainkan milik pasangan model
dan korpus, dan diukur — bukan ditebak. Model tanpa pengukuran ditolak jalan.
Sebutkan juga bahwa seluruh indeks ini ada di PostgreSQL: tanya-jawab dulu hanya
bisa lewat cloud, sekarang tidak lagi.

---

## Babak 8 — penutup · 45 detik

Kembali ke dasbor. Empat kalimat:

1. Lima agent, masing-masing memegang **satu** keputusan — apa yang layak,
   sedalam apa, blok mana, bentuk apa, mana yang aman disetujui.
2. Tidak ada manusia yang menyebut kasusnya, memilih dokumennya, atau mengetik
   satu angka pun ke dalamnya.
3. ARKA mengatakan apa yang **tidak** bisa ia nilai, berhenti ketika bukti tidak
   cukup, dan menolak menulis fakta tanpa persetujuan.
4. Semua yang barusan berjalan di laptop ini, tanpa cloud.

---

## Alur yang sama, dijalankan dari dasbor

Naskah di atas berdasar agent. Yang di bawah berdasar **layar** — empat tab, dan
tiap tab kebetulan satu agent. Ini yang dipakai kalau demo dibawakan lewat
antarmuka, bukan lewat terminal.

`npm run dev` di `arka-frontend`, `VITE_ARKA_API` menunjuk ke API lokal.

| Tab | Agent | Yang dilakukan di layar |
|---|---|---|
| **Fleet & Scout Overview** | `scout` | Sudah terisi saat dibuka — kasus terbuka, yang layak, yang ditolak, cakupan |
| **GraphRAG Investigation** | `investigator` | Klik hop 0→4; tiap simpul membuka detail beserta sitasinya |
| **Deliverable Studio** | `reporter` + `designer` | Empat format atas temuan yang sama; tombol menjalankan rantai sungguhan |
| **Interactive Agent Chat** | `tanya_jawab` | Pertanyaan bebas, termasuk yang harus ditolak |

### Urutannya — 11 menit, per langkah

Waktunya sama dengan naskah agent; yang berubah cuma siapa yang memimpin, layar
atau terminal. **Langkah 5 adalah satu-satunya yang berjalan sendiri** — sisanya
membaca hasil yang sudah dihitung, jadi tidak ada langkah lain yang boleh
membuat penonton menunggu.

| # | Layar | Durasi | Kumulatif |
|---|---|---|---|
| 0 | Tanpa layar — masalahnya | 45 dtk | 0:45 |
| 1 | Fleet, sebelum disentuh | 60 dtk | 1:45 |
| 2 | Fleet, cakupan dan penolakan | 45 dtk | 2:30 |
| 3 | Graph, hop 0→4 | 75 dtk | 3:45 |
| 4 | Graph, eskalasi | 45 dtk | 4:30 |
| 5 | Studio, tekan terbitkan — rantai berjalan | 45 dtk | 5:15 |
| 6 | Studio, tukar empat format | 75 dtk | 6:30 |
| 7 | Terminal, kurasi | 45 dtk | 7:15 |
| 8 | Chat, pertanyaan yang ditolak | 60 dtk | 8:15 |
| 9 | Kembali ke Fleet — penutup | 45 dtk | 9:00 |

Sisa dua menit sengaja dibiarkan. Demo yang pas persis pada detiknya adalah
demo yang gagal begitu satu tab lambat memuat.

**0 · Masalahnya · 45 dtk.** Layar belum menyala. Kegagalan yang sama berulang
di pabrik berbeda, dan tiap kali dibayar dari nol.

**1 · Fleet, sebelum disentuh · 60 dtk.** Buka tab, **jangan klik apa pun**.
Angkanya sudah ada sebelum siapa pun mengetik — itu seluruh isi klaim "tidak ada
yang menyuruh". Sebut waktu pindainya: seluruh armada, di bawah dua persepuluh
detik, nol panggilan model. Itu jawaban untuk pertanyaan skala yang pasti datang
nanti, dan lebih baik dijawab sebelum ditanya.

**2 · Fleet, cakupan dan penolakan · 45 dtk.** Angka terukur 17 Agustus:
**148 kegagalan terbuka · 2 layak · 3 dari 148 dapat dinilai (2,0%)**. Turun ke
daftar yang ditolak.
Dua alasan yang berbeda, dan layar membedakannya: ada yang **dinilai lalu
diabaikan**, ada yang **tidak dapat dinilai sama sekali**. Yang kedua tidak
ditampilkan sebagai `0.00` — nol akan terbaca "sudah diperiksa, aman", padahal
artinya belum diperiksa. Aset yang paling tidak tercatat justru yang paling
tidak terlihat. Tutup langkah ini dengan mengklik kasus teratas.

**3 · Graph, hop 0→4 · 75 dtk.** Klik hop berurutan, jangan melompat. Tiap
simpul dirakit dari `Finding` yang sama yang dibaca reporter — tidak ada contoh
yang ditulis di kode untuk mengisi layar. Berhenti di hop yang memuat preseden
lintas pabrik dan **buka sitasinya**: laporan inspeksi yang ditulis manusia
bertahun lalu, di pabrik lain, yang tidak pernah sampai ke pabrik ini.

**4 · Graph, eskalasi · 45 dtk.** Dua kandidat, selisih **0,0252**, di bawah
ambang keyakinan. ARKA tidak memilih — ia mengeskalasi dan mengatakan kenapa.
Ini puncak babaknya, dan puncaknya adalah penolakan menjawab.

**5 · Studio, tekan terbitkan · 45 dtk.** Satu-satunya langkah yang menunggu.
Diukur 17 Agustus lewat jalur HTTP yang sama dengan tombolnya: **32 detik**,
scout → investigator → reporter, berakhir dengan PDF 504 KB. Katakan lebih dulu
bahwa ini berjalan sungguhan; penonton yang tahu sedang menunggu apa tidak
merasa demonya macet. Isi jedanya dengan tiga hal, berurutan:

- Kenapa dokumen tidak dirender di jalur permintaan — halaman yang menghitung
  ulang segalanya tiap dibuka akan mati di proxy sebelum sempat menghasilkan
  apa pun, jadi yang berat dihitung di luar dan layar tinggal membaca.
- Penyaring narasi bekerja di sini, dan pada uji 17 Agustus ia **memang
  memotong** satu kalimat bernomor yang ditulis model — reporter sendiri
  melaporkannya di keluaran. Kalau catatan itu muncul lagi saat demo, bacakan:
  itu prinsip yang tertangkap sedang bekerja, bukan cacat.

  ⚠️ **Jangan bilang penilai mutu sedang membaca halaman sekarang.** Rantai
  `arka` yang dipanggil tombol ini berisi scout, investigator, reporter — tanpa
  penilai. Penilai ada di aplikasi `penerbitan`, dan tempatnya di langkah 6.
- Angka tidak pernah lewat model. Kode menyusunnya dari `Finding`; kalimat
  narasi yang mengandung angka dibuang penyaring sebelum dokumen tersusun.

**6 · Studio, empat format · 75 dtk.** Tukar memo → nota dinas → infografis →
dasbor. Bentuknya berubah, **angka yang muncul** tidak — kalimat itu harus persis
begitu, karena memo memang tidak memuat blok sparepart yang ada di nota dinas dan
laporan. Yang identik nilainya, bukan daftar bloknya.

Di sinilah penilai mutu disebut, karena di sinilah ia bekerja. Uji 17 Agustus:
halaman infografis dirender, dibaca ulang lewat vision, **104 string terbaca**,
dua di antaranya tidak bisa ditelusuri ke `Finding` — dan itu dicatat sebagai
`PUBLISHED_WITH_FINDINGS`. Katakan apa adanya: pada infografis penilai
**melaporkan**, pada memo penjaga sitasi **menolak menerbitkan**. Keduanya
berbeda dengan sengaja, dan itu isi Constitution 1.2.0. Di infografis, sebut sendiri
kelonggaran konstitusi sebelum juri menemukannya: penggambaran halamannya dari
model, teks dan angkanya tetap dari kode, tidak ada nilai yang hanya dibawa
bentuk, dan memo tetap catatan resmi untuk angka yang dipakai memutuskan.

**7 · Terminal, kurasi · 45 dtk.** Pindah ke terminal sebentar —
`uv run python scripts/kurasi.py --terapkan`. Yang berkeyakinan tinggi disetujui
sendiri, yang rendah ditolak, sisanya diantre ke manusia. Kalimat yang tidak
boleh dilewatkan: **agent tidak pernah menulis fakta ke graph.** Semua masuk
sebagai kandidat `unreviewed`. Sistem yang boleh menulis keyakinannya sendiri ke
dalam pengetahuannya sendiri akan mengeraskan tebakan pertamanya jadi kebenaran.

**8 · Chat, yang ditolak · 60 dtk.** Satu pertanyaan dalam domain, dijawab
dengan sitasi. **Tanyakan lewat tag, bukan nama model** — *"Kenapa kepala
pengisi PLT-U/FIL-207 bocor, dan bagaimana pabrik lain menyelesaikannya?"*
Diuji 17 Agustus: jawabannya menyebut preseden Pabrik Barat berikut sitasi
dokumen dan jalur graph. Bertanya soal "RF-8000" membuat agent menjawab bahwa
entitas itu tidak ada di graph — perilaku yang benar, tayangan yang lemah. Lalu satu yang di luar domain — *"berapa anggaran pemeliharaan
tahun depan?"* — dan **ditolak**. Ambangnya diukur, bukan ditebak, dan milik
pasangan model dan korpus, bukan milik sistem. Preset persona ada sebagai jalan
pintas kalau tangan gemetar.

**9 · Penutup · 45 dtk.** Kembali ke Fleet. Empat kalimat: lima agent masing-
masing satu keputusan · tidak ada manusia yang menyebut kasusnya atau mengetik
satu angka pun · ARKA mengatakan apa yang tidak bisa ia nilai dan berhenti saat
bukti tidak cukup · semuanya berjalan di laptop ini, tanpa cloud.

### Yang tidak ada di layar

**Curator dan penilai mutu tidak punya tab** — dan justru keduanya yang menolak
keluaran ARKA sendiri. Karena itu keduanya tetap masuk alur di atas lewat pintu
yang berbeda: curator sebagai satu langkah terminal (7), penilai sebagai narasi
selama penerbitan berjalan (5), karena saat itu ia memang sedang bekerja.

Kalau berpindah ke terminal terasa memutus alur, langkah 7 boleh dijatuhkan
menjadi satu kalimat di langkah 5 — tetapi jangan dihilangkan sama sekali.
Penjaga yang tidak pernah terlihat menolak sama saja dengan tidak ada.

⚠️ **Modal "Closed-Loop SAP ERP Execution" jangan dipakai.** Nomor work order,
nomor part, dan lot vendornya ditulis di kode; tidak ada yang tersambung ke mana
pun. Sebuah eksekusi palsu ke sistem bernama vendor nyata adalah satu-satunya
hal di seluruh demo yang bisa terbaca sebagai integrasi yang dikarang — dan itu
merusak kredibilitas semua yang benar. Kalau aksi tindak lanjut memang ingin
ditunjukkan, sebut sebagai **rencana**, bukan sebagai sesuatu yang barusan
terjadi.

---

## Cadangan — kalau ada yang mati di panggung

| Gagal | Ganti |
|---|---|
| Rantai agent (penyedia model) | `/api/armada` dan `/api/temuan` tetap hidup — keduanya nol model |
| Dasbor tidak memuat | `curl` langsung ke `/api/armada`; JSON mentah justru memperkuat klaim determinisme |
| Render PDF | Dokumen HTML dari `/api/dokumen/{tag}`; PDF pra-terbit sudah dibuka di tab |
| Basis data | Berkas hasil pemindaian terjadwal terakhir |
| Penilai (vision) | Sebutkan penolakan pada uji hidup pertama; lanjut ke babak berikutnya |
| Designer (panggilan gambar) | Infografis pra-render dari `out/infografis/`; `--prompt-saja` memperlihatkan jalur deterministiknya |
| Tanya-jawab (embedding) | Lewati; sitasi sudah terlihat di Babak 3 |

Aturannya satu: **jangan memperbaiki apa pun di depan penonton.** Lewati babak
itu, sebutkan singkat apa yang seharusnya terlihat, lanjut.

---

## Pertanyaan yang paling mungkin datang

**"Ini chatbot?"** Bukan. Chat adalah salah satu antarmuka ke Investigator.
Pemicunya jadwal, bukan pertanyaan — Scout memindai pagi hari tanpa ada yang
membukanya.

**"Bagaimana kalau asetnya ratusan ribu?"** Corong dua tahap. Tahap
deterministik menyapu seluruh armada tanpa model, murah dan bisa diaudit; model
hanya menyentuh yang lolos. Memeriksa tiap aset dengan satu panggilan model
tidak akan pernah selesai, dan itu memang bukan rancangannya.

**"Bagaimana kalau modelnya berhalusinasi angka?"** Tidak ada jalur dari model
ke angka. Nilai dirender dari `Finding` lewat filter, dan kalimat narasi
berangka dibuang sebelum dokumen tersusun. Salah pilih blok tidak fatal; salah
ketik angka fatal.

**"Datanya nyata?"** Sintetis seluruhnya, sengaja. Yang dibuktikan di sini
mekanismenya, dan mekanismenya sama pada data mana pun.

**"Kenapa tidak di cloud?"** Jalur cloud sudah terbukti hidup dan bisa dijalankan
kembali; yang ditunjukkan hari ini sengaja lokal supaya seluruh rantai terlihat
tidak bergantung pada satu vendor.
