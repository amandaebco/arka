"""Pembungkus `AdkApp` untuk deploy berbasis kode sumber.

Jalur sumber memuat objek entrypoint apa adanya, jadi yang diekspor harus
sudah berupa aplikasi ADK. Agent mentah ditolak saat container start dengan
keluhan `Class LlmAgent is missing all methods query/stream_query/...` —
kesalahan yang mahal dicari kalau tidak dicatat.
"""

from vertexai import agent_engines

from app.agents.hello import root_agent

aplikasi = agent_engines.AdkApp(agent=root_agent)
