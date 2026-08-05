# Reporting

`Investigator` menghasilkan objek `Finding` terstruktur.
`Reporter` memilih blok dan urutannya, lalu renderer mengubahnya jadi keluaran.

| Renderer | Format | Prioritas |
|---|---|---|
| `memo` | PDF/teks 1 halaman | 1 |
| `infographic` | PNG (komposisi blok) | 2 |
| `deck` | PPTX rekap bulanan | 3 — pertama dibuang kalau waktu mepet |

Semua dikirim lewat **ADK Artifacts**.

**Aturan:** angka, grafik, diagram, dan sitasi di-render deterministik dari data.
Model bahasa hanya memilih blok dan menyusun kalimat narasi — tidak pernah menyentuh angka.
