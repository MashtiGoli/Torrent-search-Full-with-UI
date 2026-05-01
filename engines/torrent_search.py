# TorrentSearch — Multi-Engine Aggregator
# VERSION: 1.0

import datetime
import gzip
import html
import io
import json
import os
import re
import sys
import urllib.error
import urllib.request
from html.parser import HTMLParser
from typing import Dict, List, Union
from urllib.parse import quote, quote_plus, urlencode, unquote

from PyQt6.QtCore import QObject, QThread, QUrl, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlApplicationEngine

# ──────────────────────────────────────────────────────────────────
#  Shared HTTP helper
# ──────────────────────────────────────────────────────────────────

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36")


def fetch(url: str, post_data: bytes = None) -> str:
    try:
        req = urllib.request.Request(url, data=post_data, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            if raw[:2] == b'\x1f\x8b':
                with io.BytesIO(raw) as s, gzip.GzipFile(fileobj=s) as g:
                    raw = g.read()
            return raw.decode("utf-8", errors="ignore")
    except Exception:
        return ""


TRACKERS = "&".join(urlencode({"tr": t}) for t in [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://open.stealth.si:80/announce",
    "udp://exodus.desync.com:6969/announce",
])

# ──────────────────────────────────────────────────────────────────
#  Engine: LimeTorrents
# ──────────────────────────────────────────────────────────────────

class LimeParser(HTMLParser):
    CATS = {"all":"all","anime":"anime","software":"applications",
            "games":"games","movies":"movies","music":"music","tv":"tv","books":"all"}
    BASE = "https://www.limetorrents.lol"

    def __init__(self):
        super().__init__()
        self.results: List[Dict] = []
        self._item: Dict = {}
        self._in_table = False
        self._in_tr = False
        self._col_idx = -1
        self._col = None
        self._cols = ["name","pub_date","size","seeds","leech"]

    def handle_starttag(self, tag, attrs):
        p = dict(attrs)
        if p.get("class") == "table2": self._in_table = True
        elif not self._in_table: return
        if tag == "tr" and p.get("bgcolor") in ("#F4F4F4","#FFFFFF"):
            self._in_tr = True; self._col_idx = -1; self._item = {}
        elif not self._in_tr: return
        if tag == "td":
            self._col_idx += 1
            self._col = self._cols[self._col_idx] if self._col_idx < len(self._cols) else None
        if self._col == "name" and tag == "a" and "href" in p:
            lnk = p["href"]
            if lnk and lnk.endswith(".html"):
                self._item["link"] = self.BASE + lnk

    def handle_data(self, data):
        if not self._col: return
        if self._col in ("size","seeds","leech"): data = data.replace(",","")
        elif self._col == "pub_date":
            now = datetime.datetime.now()
            for pat, fn in [
                (r"yesterday",       lambda m: now - datetime.timedelta(days=1)),
                (r"(\d+)\s+days?",   lambda m: now - datetime.timedelta(days=int(m[1]))),
                (r"(\d+)\s+hours?",  lambda m: now - datetime.timedelta(hours=int(m[1]))),
                (r"(\d+)\s+months?", lambda m: now - datetime.timedelta(days=int(m[1])*30)),
                (r"(\d+)\s+years?",  lambda m: now - datetime.timedelta(days=int(m[1])*365)),
            ]:
                m = re.match(pat, data, re.IGNORECASE)
                if m: data = str(int(fn(m).timestamp())); break
            else: data = "-1"
        self._item[self._col] = data.strip(); self._col = None

    def handle_endtag(self, tag):
        if tag == "table": self._in_table = False
        if self._in_tr and tag == "tr":
            self._in_tr = False; self._col = None
            if "link" in self._item: self.results.append(dict(self._item))

    @classmethod
    def search(cls, query: str, cat: str) -> List[Dict]:
        cat_key = cls.CATS.get(cat, "all")
        # LimeTorrents uses dashes for spaces
        q = query.strip().replace(" ", "-").replace("%20", "-")
        out = []
        for page in range(1, 4):
            url = f"{cls.BASE}/search/{cat_key}/{q}/seeds/{page}/"
            p = cls(); p.feed(fetch(url)); p.close()
            out.extend(p.results)
            if len(p.results) < 20: break
        return out

# ──────────────────────────────────────────────────────────────────
#  Engine: PirateBay (JSON API)
# ──────────────────────────────────────────────────────────────────

class PirateBayEngine:
    CATS = {"all":"0","music":"100","movies":"200","games":"400","software":"300"}
    BASE = "https://thepiratebay.org"
    API  = "https://apibay.org/q.php?"

    @classmethod
    def search(cls, query: str, cat: str) -> List[Dict]:
        # PirateBay API accepts plain spaces
        params: dict = {"q": query.strip()}
        c = cls.CATS.get(cat, "0")
        if c != "0": params["cat"] = c
        raw = fetch(cls.API + urlencode(params))
        if not raw: return []
        try: data = json.loads(html.unescape(raw.replace("&quot;", '\\"')))
        except Exception: return []
        out = []
        for r in data:
            if r.get("info_hash","0"*40) == "0"*40: continue
            dn = urlencode({"dn": r["name"]})
            magnet = f"magnet:?xt=urn:btih:{r['info_hash']}&{dn}&{TRACKERS}"
            out.append({
                "name": r["name"], "size": str(r.get("size","0")) + " B",
                "seeds": str(r.get("seeders", 0)), "leech": str(r.get("leechers", 0)),
                "link": magnet, "pub_date": str(r.get("added", -1)),
            })
        return out

# ──────────────────────────────────────────────────────────────────
#  Engine: EZTV
# ──────────────────────────────────────────────────────────────────

class EZTVParser(HTMLParser):
    BASE = "https://eztvx.to"

    def __init__(self):
        super().__init__()
        self.results: List[Dict] = []
        self._in_row = False
        self._item: Dict = {}

    def handle_starttag(self, tag, attrs):
        p = dict(attrs)
        if p.get("class") == "forum_header_border" and p.get("name") == "hover":
            self._in_row = True
            self._item = {"seeds": "-1", "leech": "-1", "size": "-1", "pub_date": "-1", "link": ""}
        if not self._in_row: return
        if tag == "a" and p.get("class") == "magnet":
            self._item["link"] = p.get("href","")
        if tag == "a" and p.get("class") == "epinfo":
            self._item["name"] = p.get("title","").split(" (")[0]

    def handle_data(self, data):
        if not self._in_row: return
        data = data.replace(",","")
        if any(data.endswith(x) for x in (" KB"," MB"," GB")):
            self._item["size"] = data
        elif data.isnumeric():
            self._item["seeds"] = data

    def handle_endtag(self, tag):
        if self._in_row and tag == "tr":
            if self._item.get("link"): self.results.append(dict(self._item))
            self._in_row = False

    @classmethod
    def search(cls, query: str, cat: str) -> List[Dict]:
        if cat not in ("all", "tv"): return []
        # EZTV uses dashes for spaces
        q = query.strip().replace(" ", "-").replace("%20", "-")
        url = f"{cls.BASE}/search/{q}"
        p = cls(); p.feed(fetch(url, b"layout=def_wlinks")); p.close()
        return p.results

# ──────────────────────────────────────────────────────────────────
#  Engine: TorLock
# ──────────────────────────────────────────────────────────────────

class TorLockParser(HTMLParser):
    CATS = {"all":"all","anime":"anime","software":"software","games":"game",
            "movies":"movie","music":"music","tv":"television","books":"ebooks"}
    BASE = "https://www.torlock.com"

    def __init__(self):
        super().__init__()
        self.results: List[Dict] = []
        self._article = False; self._item_found = False
        self._item: Dict = {}; self._key = None; self._page_items = 0
        self._key_map = {"td":"pub_date","ts":"size","tul":"seeds","tdl":"leech"}

    def handle_starttag(self, tag, attrs):
        p = dict(attrs)
        if tag == "article": self._article = True; self._item = {}
        if self._item_found:
            if tag == "td":
                cls = p.get("class","")
                self._key = self._key_map.get(cls)
        elif self._article and tag == "a":
            lnk = p.get("href","")
            if lnk.startswith("/torrent"):
                tid = lnk.split("/")[2]
                self._item = {
                    "link": f"{self.BASE}/tor/{tid}.torrent",
                    "desc_link": self.BASE + lnk
                }
                self._item_found = True; self._key = "name"; self._item["name"] = ""

    def handle_data(self, data):
        if self._key: self._item[self._key] = self._item.get(self._key,"") + data

    def handle_endtag(self, tag):
        if tag == "article": self._article = False
        elif self._key and tag in ("a","td"): self._key = None
        elif self._item_found and tag == "tr":
            self._item_found = False
            try:
                pd = self._item.get("pub_date","")
                if pd == "Today": d = datetime.datetime.now()
                elif pd == "Yesterday": d = datetime.datetime.now() - datetime.timedelta(days=1)
                else: d = datetime.datetime.strptime(pd, "%m/%d/%Y")
                self._item["pub_date"] = str(int(d.timestamp()))
            except Exception: self._item["pub_date"] = "-1"
            if self._item.get("link"): self.results.append(dict(self._item))
            self._page_items += 1; self._item = {}

    @classmethod
    def search(cls, query: str, cat: str) -> List[Dict]:
        cat_key = cls.CATS.get(cat, "all")
        # TorLock uses dashes for spaces
        q = query.strip().replace(" ", "-").replace("%20", "-")
        out = []
        for page in range(1, 4):
            url = f"{cls.BASE}/{cat_key}/torrents/{q}.html?sort=seeds&page={page}"
            p = cls(); p.feed(fetch(url)); p.close()
            out.extend(p.results)
            if p._page_items < 20: break
        return out

# ──────────────────────────────────────────────────────────────────
#  Engine: SolidTorrents
# ──────────────────────────────────────────────────────────────────

class SolidParser(HTMLParser):
    CATS = {"all":"all","music":"Audio","books":"eBook"}
    BASE = "https://solidtorrents.to"

    def __init__(self):
        super().__init__()
        self.results: List[Dict] = []
        self._item: Dict = {}
        self._found = False; self._title = False; self._parse_title = False
        self._stats = False; self._col = 0
        self._parse_size = self._parse_seeds = self._parse_leech = self._parse_date = False
        self._ready = False; self._total = 0

    def _gs(self, d, k): v = d.get(k,""); return v if v else ""

    def handle_starttag(self, tag, attrs):
        p = dict(attrs)
        cls = self._gs(p,"class")
        if "search-result" in cls: self._found = True; return
        if self._found and "title" in cls and tag == "h5": self._title = True
        if self._title and tag == "a": self._item["desc_link"] = self.BASE + self._gs(p,"href"); self._parse_title = True
        if self._found and "stats" in cls: self._stats = True; self._col = -1
        if self._stats and tag == "div":
            self._col += 1
            if self._col == 2: self._parse_size = True
        if self._stats and tag == "font":
            if self._col == 3: self._parse_seeds = True
            if self._col == 4: self._parse_leech = True
        if self._stats and tag == "div" and self._col == 5: self._parse_date = True
        if self._found and "dl-magnet" in cls and tag == "a":
            self._item["link"] = p.get("href",""); self._found = False; self._ready = True

    def handle_endtag(self, tag):
        if self._ready:
            if self._item.get("link"): self.results.append(dict(self._item))
            self._ready = False; self._item = {}; self._total += 1

    def handle_data(self, data):
        if self._parse_title and data.strip() and data != "\n":
            self._item["name"] = data; self._parse_title = False; self._title = False
        if self._parse_size: self._item["size"] = data; self._parse_size = False
        if self._parse_seeds: self._item["seeds"] = data; self._parse_seeds = False
        if self._parse_leech: self._item["leech"] = data; self._parse_leech = False
        if self._parse_date:
            try:
                months = ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]
                mo, dy, yr = data.replace(",","").lower().split()
                self._item["pub_date"] = str(int(datetime.datetime(int(yr), months.index(mo)+1, int(dy)).timestamp()))
            except Exception: self._item["pub_date"] = "-1"
            self._parse_date = False; self._stats = False

    @classmethod
    def search(cls, query: str, cat: str) -> List[Dict]:
        cat_key = cls.CATS.get(cat, "all")
        # SolidTorrents needs URL-encoded query
        q = quote_plus(query.strip())
        out = []
        for page in range(1, 4):
            url = f"{cls.BASE}/search?q={q}&category={cat_key}&sort=seeders&sort=desc&page={page}"
            p = cls(); p.feed(fetch(url)); p.close()
            out.extend(p.results)
            if p._total < 15: break
        return out

# ──────────────────────────────────────────────────────────────────
#  Engine: TorrentsCSV
# ──────────────────────────────────────────────────────────────────

class TorrentsCSVEngine:
    BASE = "https://torrents-csv.com"

    @classmethod
    def search(cls, query: str, cat: str) -> List[Dict]:
        # TorrentsCSV needs URL-encoded query
        q = quote_plus(query.strip())
        url = f"{cls.BASE}/service/search?size=50&q={q}"
        raw = fetch(url)
        if not raw: return []
        try: data = json.loads(raw)
        except Exception: return []
        out = []
        for r in data.get("torrents", []):
            dn = urlencode({"dn": r["name"]})
            magnet = f"magnet:?xt=urn:btih:{r['infohash']}&{dn}&{TRACKERS}"
            out.append({
                "name": r["name"],
                "size": str(r.get("size_bytes", 0)) + " B",
                "seeds": str(r.get("seeders", 0)),
                "leech": str(r.get("leechers", 0)),
                "link": magnet,
                "pub_date": str(r.get("created_unix", -1)),
            })
        return out

# ──────────────────────────────────────────────────────────────────
#  Engine registry
# ──────────────────────────────────────────────────────────────────

ENGINES = {
    "LimeTorrents":  LimeParser,
    "PirateBay":     PirateBayEngine,
    "EZTV":          EZTVParser,
    "TorLock":       TorLockParser,
    "SolidTorrents": SolidParser,
    "TorrentsCSV":   TorrentsCSVEngine,
}

# ──────────────────────────────────────────────────────────────────
#  Per-engine worker thread
# ──────────────────────────────────────────────────────────────────

class EngineWorker(QThread):
    result_found    = pyqtSignal(str, str, str, str, str, str, str)  # engine,name,size,seeds,leech,link,pub_date
    engine_finished = pyqtSignal(str)
    error_occurred  = pyqtSignal(str)

    def __init__(self, engine_name: str, engine_cls, query: str, cat: str):
        super().__init__()
        self.engine_name = engine_name
        self.engine_cls  = engine_cls
        self.query = query
        self.cat   = cat

    def run(self):
        try:
            results = self.engine_cls.search(self.query, self.cat)
            for r in results:
                self.result_found.emit(
                    self.engine_name,
                    str(r.get("name", "")),
                    str(r.get("size", "")),
                    str(r.get("seeds", "0")),
                    str(r.get("leech", "0")),
                    str(r.get("link", "")),
                    str(r.get("pub_date", "-1")),
                )
        except Exception as e:
            self.error_occurred.emit(f"{self.engine_name}: {e}")
        finally:
            self.engine_finished.emit(self.engine_name)

# ──────────────────────────────────────────────────────────────────
#  Torrent download worker
# ──────────────────────────────────────────────────────────────────

class DownloadWorker(QThread):
    download_started = pyqtSignal(str)
    download_done    = pyqtSignal(str)
    error_occurred   = pyqtSignal(str)

    def __init__(self, name: str, link: str, dest_dir: str):
        super().__init__()
        self.name     = name
        self.link     = link
        self.dest_dir = dest_dir

    def run(self):
        self.download_started.emit(self.name)
        try:
            link = self.link

            # If it's a limetorrents info page, resolve magnet from the page
            if "limetorrents" in link and link.endswith(".html"):
                page = fetch(link)
                m = re.search(r'href\s*=\s*"(magnet[^"]+)"', page)
                if m:
                    link = m.group(1)
                else:
                    # Try direct .torrent guess
                    link = re.sub(r"-torrent-(\d+)\.html", r"/tor/\1.torrent", link)

            # Direct .torrent file
            if link.endswith(".torrent") or ("/tor/" in link):
                safe_name = re.sub(r'[\\/:*?"<>|]', "_", self.name)[:120]
                out_path = os.path.join(self.dest_dir, safe_name + ".torrent")
                req = urllib.request.Request(link, headers={"User-Agent": UA})
                with urllib.request.urlopen(req, timeout=20) as r:
                    data = r.read()
                with open(out_path, "wb") as f:
                    f.write(data)
                self.download_done.emit(out_path)

            elif link.startswith("magnet:"):
                # Save magnet as a .magnet text file
                safe_name = re.sub(r'[\\/:*?"<>|]', "_", self.name)[:120]
                out_path = os.path.join(self.dest_dir, safe_name + ".magnet")
                with open(out_path, "w", encoding="utf-8") as f:
                    f.write(link)
                self.download_done.emit(out_path + "  (magnet link saved)")
            else:
                self.error_occurred.emit("Cannot resolve torrent link.")
        except Exception as e:
            self.error_occurred.emit(f"Download failed: {e}")

# ──────────────────────────────────────────────────────────────────
#  Main controller exposed to QML
# ──────────────────────────────────────────────────────────────────

class AggregatorController(QObject):
    resultFound     = pyqtSignal(str, str, str, str, str, str, str,
                                 arguments=["engine","name","size","seeds","leech","link","pubDate"])
    engineFinished  = pyqtSignal(str,  arguments=["engine"])
    searchStarted   = pyqtSignal()
    searchFinished  = pyqtSignal(int,  arguments=["total"])
    downloadStarted = pyqtSignal(str,  arguments=["name"])
    downloadDone    = pyqtSignal(str,  arguments=["path"])
    exportDone      = pyqtSignal(str,  arguments=["path"])
    errorOccurred   = pyqtSignal(str,  arguments=["msg"])

    def __init__(self):
        super().__init__()
        self._workers: List[EngineWorker] = []
        self._dl_worker: Union[DownloadWorker, None] = None
        self._results: List[Dict] = []
        self._finished = 0
        self._total_engines = 0

    @pyqtSlot(str, str, "QVariantList")
    def startSearch(self, query: str, category: str, engines: list):
        # Stop existing workers
        for w in self._workers:
            w.quit(); w.wait(1000)
        self._workers.clear()
        self._results.clear()
        self._finished = 0
        self._total_engines = len(engines)
        self.searchStarted.emit()

        if not engines:
            self.searchFinished.emit(0)
            return

        for name in engines:
            cls = ENGINES.get(name)
            if not cls: continue
            w = EngineWorker(name, cls, query, category)
            w.result_found.connect(self._on_result)
            w.engine_finished.connect(self._on_engine_done)
            w.error_occurred.connect(self.errorOccurred)
            self._workers.append(w)
            w.start()

    def _on_result(self, engine, name, size, seeds, leech, link, pub_date):
        self._results.append({"engine": engine, "name": name, "size": size,
                               "seeds": seeds, "leech": leech, "link": link,
                               "pub_date": pub_date})
        self.resultFound.emit(engine, name, size, seeds, leech, link, pub_date)

    def _on_engine_done(self, engine):
        self._finished += 1
        self.engineFinished.emit(engine)
        if self._finished >= self._total_engines:
            self.searchFinished.emit(len(self._results))

    @pyqtSlot(str, str)
    def grabTorrent(self, name: str, link: str):
        if self._dl_worker and self._dl_worker.isRunning():
            return
        dest = os.path.dirname(os.path.abspath(sys.argv[0]))
        self._dl_worker = DownloadWorker(name, link, dest)
        self._dl_worker.download_started.connect(self.downloadStarted)
        self._dl_worker.download_done.connect(self.downloadDone)
        self._dl_worker.error_occurred.connect(self.errorOccurred)
        self._dl_worker.start()

    @pyqtSlot()
    def exportToTxt(self):
        if not self._results:
            self.errorOccurred.emit("No results to export.")
            return
        try:
            dest = os.path.dirname(os.path.abspath(sys.argv[0]))
            path = os.path.join(dest, "torrent_search_results.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"TorrentSearch Results\n")
                f.write(f"Exported: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 70 + "\n\n")
                for r in self._results:
                    ts = int(r.get("pub_date", -1))
                    date_str = (datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
                                if ts > 0 else "Unknown")
                    f.write(f"Name   : {r['name']}\n")
                    f.write(f"Engine : {r['engine']}\n")
                    f.write(f"Size   : {r['size']}\n")
                    f.write(f"Seeds  : {r['seeds']} | Leech: {r['leech']}\n")
                    f.write(f"Date   : {date_str}\n")
                    f.write(f"Link   : {r['link']}\n")
                    f.write("-" * 70 + "\n")
            self.exportDone.emit(path)
        except Exception as e:
            self.errorOccurred.emit(f"Export failed: {e}")

# ──────────────────────────────────────────────────────────────────
#  Resource path helper
# ──────────────────────────────────────────────────────────────────

def resource_path(rel: str) -> str:
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)

# ──────────────────────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")
    app = QGuiApplication(sys.argv)
    app.setApplicationName("TorrentSearch")

    ctrl = AggregatorController()
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", ctrl)
    engine.load(QUrl.fromLocalFile(resource_path("torrent_search.qml")))

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())
