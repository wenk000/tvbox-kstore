import sys
import os
import json
import time
import concurrent.futures
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse
import traceback

LOG_FILE = "generate.log"

def log(msg):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    try:
        print(msg)
    except Exception:
        pass

log("=== generate.py START ===")
log("Python {}.{}".format(sys.version_info.major, sys.version_info.minor))

# ============================================================
NOTICE_TEXT = (
    "阁下好手段！本资源均来源于网络公开收集整理，仅供个人学习交流使用，"
    "严禁私自售卖、二次倒卖及商用，下载后请 24 小时内自行删除，"
    "使用产生一切后果均由使用者自行承担，与本人无关，特此警示！"
    "如有冒犯，请联系删除。"
)

CANDIDATE_SOURCES = [
    {"url": "https://tv.菜妮丝.top",                     "name": "杰翔"},
    {"url": "http://tvbox.王二小放牛娃.top",              "name": "王二小"},
    {"url": "http://肥猫.com",                            "name": "肥猫"},
    {"url": "http://feimao.pro",                          "name": "肥猫2"},
    {"url": "https://6296.kstore.vip/fm.gif",             "name": "肥猫3"},
    {"url": "https://盒子迷.top/禁止贩卖",                 "name": "盒子迷"},
    {"url": "https://tv.菜妮丝.top",                      "name": "菜妮丝"},
    {"url": "https://gh-proxy.com/https://raw.githubusercontent.com/guot55/yg/main/pg/bh.json", "name": "寳盒"},
    {"url": "http://www.饭太硬.cc/tv",                    "name": "饭太硬1"},
    {"url": "http://www.饭太硬.net/tv",                   "name": "饭太硬2"},
    {"url": "http://www.饭太硬.art/tv",                   "name": "饭太硬3"},
    {"url": "http://fty.xxooo.cf/tv",                     "name": "饭太硬4"},
    {"url": "http://fty.888484.xyz/tv",                   "name": "饭太硬5"},
    {"url": "http://fty.333232.xyz/tv",                   "name": "饭太硬6"},
    {"url": "https://raw.atomgit.com/xxxooo/fan/blobs/cef5f441c422cffe4852e0fc8b102f9be6d2bb2b/in.bmp", "name": "饭太硬江苏郑州"},
]

TIMEOUT = 8
MAX_WORKERS = 10
CUSTOM_SOURCES_FILE = "custom_sources.json"
# ============================================================


def load_custom_sources():
    """从 custom_sources.json 读取用户自定义接口"""
    if not os.path.exists(CUSTOM_SOURCES_FILE):
        log("Custom sources file not found: {}".format(CUSTOM_SOURCES_FILE))
        return []
    try:
        with open(CUSTOM_SOURCES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            log("  [WARN] custom_sources.json is not an array, skipping")
            return []
        sources = []
        for item in data:
            if isinstance(item, dict) and "url" in item and "name" in item:
                sources.append({"url": item["url"], "name": item["name"]})
            else:
                log("  [WARN] skipping invalid custom source: {}".format(repr(item)))
        log("Loaded {} custom sources from {}".format(len(sources), CUSTOM_SOURCES_FILE))
        return sources
    except Exception as e:
        log("  [WARN] failed to load {}: {}".format(CUSTOM_SOURCES_FILE, str(e)))
        return []


def url_to_ascii(url):
    try:
        parsed = urlparse(url)
        if not parsed.hostname:
            return url
        ascii_host = parsed.hostname.encode("idna").decode("ascii")
        port_str = ":" + str(parsed.port) if parsed.port else ""
        path = parsed.path or ""
        query = "?" + parsed.query if parsed.query else ""
        return "{}://{}{}{}{}".format(parsed.scheme, ascii_host, port_str, path, query)
    except Exception as e:
        log("  [WARN] url_to_ascii failed for {}: {}".format(repr(url), str(e)))
        return url


def check_url_alive(item):
    url = item["url"]
    name = item["name"]
    ascii_url = url_to_ascii(url)
    t0 = time.time()

    try:
        req = Request(ascii_url, method="HEAD")
        req.add_header("User-Agent", "Mozilla/5.0")
        try:
            resp = urlopen(req, timeout=TIMEOUT)
            status = resp.status
            resp.close()
        except (URLError, HTTPError):
            get_req = Request(ascii_url, method="GET")
            get_req.add_header("User-Agent", "Mozilla/5.0")
            get_req.add_header("Range", "bytes=0-0")
            resp = urlopen(get_req, timeout=TIMEOUT)
            status = resp.status
            resp.close()

        ms = int((time.time() - t0) * 1000)
        if status < 400:
            log("  [OK] [{}] {} -> {} ({}ms)".format(status, name, repr(url), ms))
            return item, True, str(status), ms
        else:
            log("  [WARN] [{}] {} -> {} ({}ms)".format(status, name, repr(url), ms))
            return item, False, str(status), ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        err = type(e).__name__
        log("  [FAIL] [{}] {} -> {} ({}ms)".format(err, name, repr(url), ms))
        return item, False, err, ms


def check_all_sources(sources):
    log("Scanning {} sources (timeout {}s, workers {})...".format(
        len(sources), TIMEOUT, MAX_WORKERS))
    # results: index -> (item, is_alive, info)
    results = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_map = {}
        for i, item in enumerate(sources):
            future_map[executor.submit(check_url_alive, item)] = i
        done, not_done = concurrent.futures.wait(
            future_map.keys(), timeout=TIMEOUT * 3,
            return_when=concurrent.futures.ALL_COMPLETED)
        for future in done:
            try:
                item_result = future.result()
                results[future_map[future]] = item_result
            except Exception as e:
                i = future_map[future]
                item = sources[i]
                log("  [FUTURE_ERR] {} -> {}".format(item["name"], str(e)))
                results[i] = (item, False, "FutureError", 99999)
        for future in not_done:
            i = future_map[future]
            item = sources[i]
            log("  [TIMEOUT] {} -> {}".format(item["name"], repr(item["url"])))
            results[i] = (item, False, "Timeout", 99999)

    # 按响应速度从快到慢排序
    alive = []
    dead = []
    for i in sorted(results.keys()):
        item_result = results[i]
        if item_result[1]:
            alive.append((item_result[0], item_result[3]))
        else:
            dead.append((item_result[0], item_result[2]))

    alive.sort(key=lambda x: x[1])
    log("Result: {} alive (sorted by speed), {} dead".format(len(alive), len(dead)))
    for rank, (item, ms) in enumerate(alive, 1):
        log("  #{} {} -> {}ms".format(rank, item["name"], ms))
    return [x[0] for x in alive], dead


def generate_json(alive_sources):
    config = {"notice": NOTICE_TEXT, "urls": alive_sources}
    out_dir = "download/1/tvbox"
    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.join(out_dir, "source.json")
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    log("Generated: {} ({} entries)".format(fname, len(alive_sources)))
    return fname


if __name__ == "__main__":
    t0 = time.time()
    try:
        # 加载内置线路 + 自定义接口
        custom_sources = load_custom_sources()
        all_sources = CANDIDATE_SOURCES + custom_sources
        log("Total sources: {} (built-in: {}, custom: {})".format(
            len(all_sources), len(CANDIDATE_SOURCES), len(custom_sources)))

        alive_sources, dead_sources = check_all_sources(all_sources)
        fname = generate_json(alive_sources)
        with open(fname, "r", encoding="utf-8") as f:
            data = json.load(f)
        log("JSON verified OK: {} entries, notice {} chars".format(
            len(data["urls"]), len(data.get("notice", ""))))
    except Exception as e:
        log("FATAL ERROR: {}".format(e))
        log(traceback.format_exc())
    elapsed = time.time() - t0
    log("Done in {:.1f}s".format(elapsed))
    log("=== END ===")
