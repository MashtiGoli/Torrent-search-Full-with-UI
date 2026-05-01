# VERSION: 5.0
# AUTHORS: Lima66
# CONTRIBUTORS: Diego de las Heras (ngosang@hotmail.es)
# UI: Advanced PyQt6/QML interface

import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta
from html.parser import HTMLParser
from typing import Callable, Dict, List, Mapping, Match, Tuple, Union
from urllib.parse import quote

from PyQt6.QtCore import (
    QObject, QThread, pyqtSignal, pyqtSlot, QUrl, Qt
)
from PyQt6.QtGui import QGuiApplication, QIcon
from PyQt6.QtQml import QQmlApplicationEngine


# ─────────────────────────────────────────────────────────────────────────────
#  HTTP helper
# ─────────────────────────────────────────────────────────────────────────────

def retrieve_url(url: str) -> str:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                                   "Chrome/124.0 Safari/537.36"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        return ""


# ─────────────────────────────────────────────────────────────────────────────
#  HTML Parser
# ─────────────────────────────────────────────────────────────────────────────

class LimeHTMLParser(HTMLParser):
    A, TD, TR, HREF = ("a", "td", "tr", "href")

    def error(self, message: str) -> None:
        pass

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.current_item: Dict[str, object] = {}
        self.page_items = 0
        self.inside_table = False
        self.inside_tr = False
        self.column_index = -1
        self.column_name: Union[str, None] = None
        self.columns = ["name", "pub_date", "size", "seeds", "leech"]
        self.results: List[Dict] = []

        now = datetime.now()
        self.date_parsers: Mapping[str, Callable[[Match], datetime]] = {
            r"yesterday":          lambda m: now - timedelta(days=1),
            r"last\s+month":       lambda m: now - timedelta(days=30),
            r"(\d+)\s+years?":     lambda m: now - timedelta(days=int(m[1]) * 365),
            r"(\d+)\s+months?":    lambda m: now - timedelta(days=int(m[1]) * 30),
            r"(\d+)\s+days?":      lambda m: now - timedelta(days=int(m[1])),
            r"(\d+)\s+hours?":     lambda m: now - timedelta(hours=int(m[1])),
            r"(\d+)\s+minutes?":   lambda m: now - timedelta(minutes=int(m[1])),
        }

    def handle_starttag(self, tag, attrs):
        params = dict(attrs)
        if params.get("class") == "table2":
            self.inside_table = True
        elif not self.inside_table:
            return

        if tag == self.TR and params.get("bgcolor") in ("#F4F4F4", "#FFFFFF"):
            self.inside_tr = True
            self.column_index = -1
            self.current_item = {"engine_url": self.url}
        elif not self.inside_tr:
            return

        if tag == self.TD:
            self.column_index += 1
            self.column_name = (
                self.columns[self.column_index]
                if self.column_index < len(self.columns)
                else None
            )

        if self.column_name == "name" and tag == self.A and self.HREF in params:
            link = params["href"]
            if link and link.endswith(".html"):
                try:
                    safe = quote(self.url + link, safe="/:")
                except KeyError:
                    safe = self.url + link
                self.current_item["link"] = safe
                self.current_item["desc_link"] = safe

    def handle_data(self, data):
        if not self.column_name:
            return
        if self.column_name in ("size", "seeds", "leech"):
            data = data.replace(",", "")
        elif self.column_name == "pub_date":
            ts = -1
            for pat, calc in self.date_parsers.items():
                m = re.match(pat, data, re.IGNORECASE)
                if m:
                    ts = int(calc(m).timestamp())
                    break
            data = str(ts)
        self.current_item[self.column_name] = data.strip()
        self.column_name = None

    def handle_endtag(self, tag):
        if tag == "table":
            self.inside_table = False
        if self.inside_tr and tag == self.TR:
            self.inside_tr = False
            self.column_name = None
            if "link" in self.current_item:
                self.results.append(dict(self.current_item))
                self.page_items += 1


# ─────────────────────────────────────────────────────────────────────────────
#  Search worker (runs in a separate thread)
# ─────────────────────────────────────────────────────────────────────────────

class SearchWorker(QObject):
    result_found   = pyqtSignal(str, str, str, str, str)   # name, size, seeds, leech, link
    search_done    = pyqtSignal(int)                        # total count
    error_occurred = pyqtSignal(str)

    BASE_URL = "https://www.limetorrents.lol"
    CATEGORIES = {
        "all": "all", "anime": "anime", "software": "applications",
        "games": "games", "movies": "movies", "music": "music", "tv": "tv"
    }

    def __init__(self, query: str, category: str):
        super().__init__()
        self.query = query
        self.category = category
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    @pyqtSlot()
    def run(self):
        try:
            cat = self.CATEGORIES.get(self.category, "all")
            q = self.query.replace("%20", "-")
            total = 0
            for page in range(1, 6):
                if self._cancelled:
                    break
                url = f"{self.BASE_URL}/search/{cat}/{q}/seeds/{page}/"
                html = retrieve_url(url)
                if not html:
                    break
                parser = LimeHTMLParser(self.BASE_URL)
                parser.feed(html)
                parser.close()
                for item in parser.results:
                    if self._cancelled:
                        break
                    self.result_found.emit(
                        item.get("name", ""),
                        item.get("size", ""),
                        item.get("seeds", "0"),
                        item.get("leech", "0"),
                        item.get("link", "")
                    )
                    total += 1
                if parser.page_items < 20:
                    break
            self.search_done.emit(total)
        except Exception as e:
            self.error_occurred.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────
#  Controller – exposed to QML
# ─────────────────────────────────────────────────────────────────────────────

class SearchController(QObject):
    resultFound    = pyqtSignal(str, str, str, str, str, arguments=["name", "size", "seeds", "leech", "link"])
    searchStarted  = pyqtSignal()
    searchFinished = pyqtSignal(int,  arguments=["total"])
    exportDone     = pyqtSignal(str,  arguments=["path"])
    errorOccurred  = pyqtSignal(str,  arguments=["msg"])

    def __init__(self):
        super().__init__()
        self._results: List[Dict] = []
        self._thread: Union[QThread, None] = None
        self._worker: Union[SearchWorker, None] = None

    @pyqtSlot(str, str)
    def startSearch(self, query: str, category: str):
        # Cancel any running search
        if self._thread and self._thread.isRunning():
            if self._worker:
                self._worker.cancel()
            self._thread.quit()
            self._thread.wait(2000)

        self._results.clear()
        self.searchStarted.emit()

        self._worker = SearchWorker(query, category)
        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.result_found.connect(self._on_result)
        self._worker.search_done.connect(self._on_done)
        self._worker.error_occurred.connect(self.errorOccurred)
        self._worker.search_done.connect(self._thread.quit)

        self._thread.start()

    def _on_result(self, name, size, seeds, leech, link):
        self._results.append({"name": name, "size": size, "seeds": seeds, "leech": leech, "link": link})
        self.resultFound.emit(name, size, seeds, leech, link)

    def _on_done(self, total):
        self.searchFinished.emit(total)

    @pyqtSlot()
    def exportToTxt(self):
        if not self._results:
            self.errorOccurred.emit("No results to export.")
            return
        try:
            exe_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            out_path = os.path.join(exe_dir, "limetorrents_output.txt")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(f"LimeTorrents Search Results\n")
                f.write(f"Exported: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                for item in self._results:
                    f.write(f"Name  : {item['name']}\n")
                    f.write(f"Size  : {item['size']}\n")
                    f.write(f"Seeds : {item['seeds']} | Leech: {item['leech']}\n")
                    f.write(f"Link  : {item['link']}\n")
                    f.write("-" * 60 + "\n")
            self.exportDone.emit(out_path)
        except Exception as e:
            self.errorOccurred.emit(f"Export failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────────────────────

def resource_path(rel: str) -> str:
    """Return absolute path – works both for script and PyInstaller .exe."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), rel)


if __name__ == "__main__":
    # High-DPI support
    os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

    app = QGuiApplication(sys.argv)
    app.setApplicationName("LimeTorrents")
    app.setOrganizationName("LimeTorrents")

    controller = SearchController()

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("controller", controller)

    qml_file = QUrl.fromLocalFile(resource_path("ui.qml"))
    engine.load(qml_file)

    if not engine.rootObjects():
        sys.exit(-1)

    sys.exit(app.exec())
