# Agents

Empat agent ADK dengan serah-terima eksplisit:

| Agent | Keputusan miliknya | Serah-terima |
|---|---|---|
| `scout` | Mana yang layak diselidiki | → investigator |
| `investigator` | Langkah penelusuran berikutnya; kapan eskalasi ke manusia | → reporter |
| `reporter` | Blok/isi mana yang masuk dokumen dan urutannya | → artifact |
| `curator` | Pemetaan mana yang aman disetujui otomatis | → proyeksi ulang graph |

`scout → investigator → reporter` adalah rantai. `curator` berjalan ortogonal.

**Jangan bangun framework.** Empat modul sederhana dengan kontrak jelas.
