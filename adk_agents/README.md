# Titik masuk ADK

`adk api_server` dan `adk web` menuntut satu direktori per agent, masing-masing
berisi `agent.py` yang mengekspor `root_agent`. Struktur itu tidak cocok dengan
tata letak `app/` kita, jadi direktori ini berisi pembungkus tipis saja —
logikanya tetap tinggal di `app/agents/`.
