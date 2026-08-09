"""Agent ARKA.

Mengimpor paket ini menyalin setelan Vertex dari `.env` ke lingkungan proses.
Dilakukan di sini, bukan di tiap skrip, karena setiap jalur yang memanggil model
pasti melewati paket ini — sedangkan tiap skrip belum tentu ingat.
"""

from app.core.config import terapkan_env_vertex

terapkan_env_vertex()
