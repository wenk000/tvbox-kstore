import sys
import os
import json
import time
import concurrent.futures
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlparse, quote
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
CHINA_SPEED_API = "https://v2.xxapi.cn/api/speed"  # 国内测速 API
# ============================================================


def check_speed_china(url):
    """通过国内 API 检测 URL 的国内访问延迟，返回毫秒数，失败返回 None"""
    try:
        api_url = CHINA_SPEED_API + "?url=" + quote(url, safe=":/")
        req = Request(api_url, method="GET")
        req.add_header("User-Agent", "Mozilla/5.0")
        resp = urlopen(req, timeout=TIMEOUT * 2)
        data = json.loads(resp.read().decode("utf-8"))
        resp.close()
        if data.get("code") == 200 and data.get("data"):
            ms_str = str(data["data"]).replace("ms", "").strip()
            return int(ms_str)
    except Exception as e:
        log("  [CHINA_API_ERR] {} -> {}".format(url[:50], str(e)))
    return None


def check_all_china_speeds(sources):
    """阶段1：通过国内 API 批量检测所有线路的国内延迟"""
    log("Phase 1: China speed test for {} sources...".format(len(sources)))
    speed_map = {}

    for item in sources:
        name = item["name"]
        url = item["url"]
        ms = check_speed_china(url)
        if ms is not None:
            speed_map[name] = ms
            log("  [CHINA] {} -> {}ms".format(name, ms))
        else:
            log("  [CHINA] {} -> N/A (API failed, will use fallback)".format(name))

    return speed_map


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
        path = quote(parsed.path or "", safe="/")
        query = "?" + quote(parsed.query, safe="&=") if parsed.query else ""
        return "{}://{}{}{}{}".format(parsed.scheme, ascii_host, port_str, path, query)
    except Exception as e:
        log("  [WARN] url_to_ascii failed for {}: {}".format(repr(url), str(e)))
        return url


def check_url_alive(item):
    """HTTP 连通性检测：HTTP < 400 + 非空响应 = 存活。

    不做内容格式验证，原因：
    1. GitHub Actions 美国节点访问国内 CDN 时经常返回 HTML 劫持页（区域限制）
    2. 国内 CDN 常用 text/html Content-Type 返回 JSON/base64 配置
    3. TVBox 客户端会自动跳过无法解析的源，无需在这里做严格过滤
    """
    url = item["url"]
    name = item["name"]
    ascii_url = url_to_ascii(url)
    t0 = time.time()

    try:
        get_req = Request(ascii_url, method="GET")
        get_req.add_header("User-Agent", "Mozilla/5.0")
        resp = urlopen(get_req, timeout=TIMEOUT)
        status = resp.status
        data = resp.read()
        resp.close()

        ms = int((time.time() - t0) * 1000)

        if len(data) > 0:
            log("  [OK] [{}] {} -> {} ({}ms, {}bytes)".format(status, name, repr(url), ms, len(data)))
            return item, True, str(status), ms
        else:
            log("  [WARN] [{}] {} -> {} ({}ms, empty)".format(status, name, repr(url), ms))
            return item, False, "empty_response", ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        err = type(e).__name__
        log("  [FAIL] [{}] {} -> {} ({}ms)".format(err, name, repr(url), ms))
        return item, False, err, ms


def check_all_sources(sources, china_speed_map=None):
    """检测所有线路的可用性。

    策略：
    - 国内测速成功的线路 -> 直接视为存活（国内能用就是能用）
    - 国内测速失败的线路 -> 走 HTTP 连通性检测（超时/DNS失败/HTTP错误 = 死亡）
    - 只有 HTTP 请求异常的才放入 backup_urls
    """
    # 国内测速成功的直接存活
    need_us_check = []
    alive_from_china = []

    for i, item in enumerate(sources):
        name = item["name"]
        china_ms = china_speed_map.get(name) if china_speed_map else None
        if china_ms is not None:
            alive_from_china.append((i, item, china_ms))
            log("  [CN_ALIVE] {} -> {}ms (skipped US check)".format(name, china_ms))
        else:
            need_us_check.append((i, item))

    log("Phase 2: HTTP connectivity check for {} sources ({} already alive from CN)...".format(
        len(need_us_check), len(alive_from_china)))

    # 对国内测速失败的线路做 HTTP 连通性检测
    results = {}
    if need_us_check:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_map = {}
            for idx, (i, item) in enumerate(need_us_check):
                future_map[executor.submit(check_url_alive, item)] = i
            done, not_done = concurrent.futures.wait(
                future_map.keys(), timeout=TIMEOUT * 3,
                return_when=concurrent.futures.ALL_COMPLETED)
            for future in done:
                try:
                    item_result = future.result(timeout=1)
                    results[future_map[future]] = item_result
                except concurrent.futures.TimeoutError:
                    i = future_map[future]
                    item = sources[i]
                    log("  [RESULT_TIMEOUT] {} -> getting result timed out".format(item["name"]))
                    results[i] = (item, False, "ResultTimeout", 99999)
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

    # 合并结果
    alive = []
    dead = []
    for i, item, china_ms in alive_from_china:
        alive.append((item, china_ms))
    for i in sorted(results.keys()):
        item_result = results[i]
        item = item_result[0]
        if item_result[1]:
            alive.append((item, item_result[3]))
        else:
            dead.append((item, item_result[2]))

    # 按延迟排序
    alive.sort(key=lambda x: x[1])
    log("Result: {} alive (sorted by speed), {} backup".format(len(alive), len(dead)))
    for rank, (item, ms) in enumerate(alive, 1):
        china_ms = china_speed_map.get(item["name"]) if china_speed_map else None
        label = "{}ms(CN)".format(china_ms) if china_ms else "{}ms(US-fallback)".format(ms)
        log("  #{} {} -> {}".format(rank, item["name"], label))
    return [x[0] for x in alive], dead


def generate_json(alive_sources, dead_sources):
    config = {
        "notice": NOTICE_TEXT,
        "urls": alive_sources,
        "backup_urls": [x[0] for x in dead_sources]
    }
    out_dir = "download/1/tvbox"
    os.makedirs(out_dir, exist_ok=True)
    fname = os.path.join(out_dir, "source.json")
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)
    log("Generated: {} ({} alive, {} backup)".format(fname, len(alive_sources), len(dead_sources)))
    return fname


if __name__ == "__main__":
    t0 = time.time()
    try:
        custom_sources = load_custom_sources()
        all_sources = CANDIDATE_SOURCES + custom_sources
        log("Total sources: {} (built-in: {}, custom: {})".format(
            len(all_sources), len(CANDIDATE_SOURCES), len(custom_sources)))

        # 阶段1：国内节点测速
        china_speed_map = check_all_china_speeds(all_sources)
        log("China speed test done: {}/{} sources got CN latency".format(
            len(china_speed_map), len(all_sources)))

        # 阶段2：HTTP 连通性检测 + 排序
        alive_sources, dead_sources = check_all_sources(all_sources, china_speed_map)
        fname = generate_json(alive_sources, dead_sources)
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
