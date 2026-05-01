# TorrentSearch — Multi-Engine Aggregator

A standalone desktop application that searches **6 torrent engines simultaneously** with a modern dark-mode QML/PyQt6 UI.

## Features

- 🔍 **Multi-engine parallel search** — LimeTorrents, PirateBay, EZTV, TorLock, SolidTorrents, TorrentsCSV
- 📂 **Category filter** — all, movies, tv, music, games, anime, software, books
- ✅ **Engine toggle** — enable/disable individual engines per search
- 📅 **Sort by** Date, Seeds, Name, or Size (click column headers)
- ⬇️ **Grab .torrent** — downloads the actual `.torrent` file or saves a `.magnet` link file next to the exe
- 🌐 **Open in browser** — opens the torrent info page or launches your torrent client for magnets
- 💾 **Export TXT** — saves all results to `torrent_search_results.txt`
- ⚡ **Non-blocking UI** — all searches run in parallel background threads

## Requirements

- Python 3.10+
- PyQt6

```
pip install PyQt6
```

## Run from source

```
python engines/torrent_search.py
```

## Build standalone .exe

```
pip install pyinstaller
cd engines
pyinstaller --onefile --distpath . --windowed --add-data "torrent_search.qml;." --name TorrentSearch torrent_search.py
```

## Files

| File | Description |
|---|---|
| `engines/torrent_search.py` | Python backend — all 6 engine scrapers + PyQt6 controller |
| `engines/torrent_search.qml` | QML dark UI frontend |
| `engines/limetorrents.py` | LimeTorrents engine (original qBittorrent plugin, updated) |
| `engines/piratebay.py` | PirateBay engine (original) |
| `engines/eztv.py` | EZTV engine (original) |
| `engines/torlock.py` | TorLock engine (original) |
| `engines/solidtorrents.py` | SolidTorrents engine (original) |
| `engines/torrentscsv.py` | TorrentsCSV engine (original) |

## Usage

1. **Double-click `TorrentSearch.exe`** (no CMD needed)
2. Type your query in the search bar (e.g. `game of thrones`)
3. Select a category if needed
4. Toggle which engines to use via **Engines ▾**
5. Click **Search** or press Enter
6. Click any row to expand it — then use **Grab .torrent** or **Open in browser**
7. Click column headers to sort results
8. Click **Export TXT** to save all results to a text file
