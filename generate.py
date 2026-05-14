import sys
import os
import re
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
            # data 格式: "681ms"
            ms_str = str(data["data"]).replace("ms", "").strip()
            return int(ms_str)
    except Exception as e:
        log("  [CHINA_API_ERR] {} -> {}".format(url[:50], str(e)))
    return None


def check_all_china_speeds(sources):
    """阶段1：通过国内 API 批量检测所有线路的国内延迟"""
    log("Phase 1: China speed test for {} sources...".format(len(sources)))
    speed_map = {}  # name -> china_ms

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
        # 域名用 IDNA 编码
        ascii_host = parsed.hostname.encode("idna").decode("ascii")
        port_str = ":" + str(parsed.port) if parsed.port else ""
        # 路径和查询参数中的非 ASCII 字符用 percent-encoding
        path = quote(parsed.path or "", safe="/")
        query = "?" + quote(parsed.query, safe="&=") if parsed.query else ""
        return "{}://{}{}{}{}".format(parsed.scheme, ascii_host, port_str, path, query)
    except Exception as e:
        log("  [WARN] url_to_ascii failed for {}: {}".format(repr(url), str(e)))
        return url


def is_valid_tvbox_content(content_type, data):
    """判断返回的内容是否可能是有效的 TVBox 配置（而非普通网页）。

    TVBox 配置的有效格式：
    - JSON 对象（直接返回配置）
    - Base64 编码的文本（编码后的 JSON 配置）
    - 二进制伪装文件（.bmp/.gif/.jpg 等后缀，实际内容是 base64 或 JSON）
    - 纯文本配置

    无效内容：
    - HTML 网页（普通网页、错误页、跳转页）
    """
    if not data:
        return False, "empty"

    # 先检查内容本身是否是有效格式（JSON/base64/二进制），再判断 Content-Type
    # 这样即使服务器错误地返回 text/html 也不会误杀 JSON 配置
    sample = data[:200]
    try:
        text = sample.decode("utf-8", errors="replace").strip()
    except Exception:
        # 二进制内容，可能是伪装文件，视为有效
        return True, "binary"

    text_lower = text.lower()
    # 如果内容以 JSON 的 { 或 [ 开头，是有效配置（无视 Content-Type）
    if text.startswith("{") or text.startswith("["):
        return True, "json_like"

    # 如果内容看起来是 base64（纯字母数字+/=且长度>20），视为有效
    if len(text) > 20 and re.match(r'^[A-Za-z0-9+/=\s]+$', text):
        return True, "base64_like"

    # 检查 Content-Type: text/html
    ct = (content_type or "").lower()
    if "text/html" in ct:
        return False, "html_content_type"

    # 检查内容是否包含 HTML 标签
    html_markers = ["<html", "<head", "<!doctype", "<body", "<meta ", "<script"]
    for marker in html_markers:
        if marker in text_lower:
            return False, "html_content"

    return True, "ok"


def check_url_alive(item):
    url = item["url"]
    name = item["name"]
    ascii_url = url_to_ascii(url)
    t0 = time.time()

    try:
        # GET 请求并跟随重定向，检查是否有有效响应内容
        get_req = Request(ascii_url, method="GET")
        get_req.add_header("User-Agent", "Mozilla/5.0")
        resp = urlopen(get_req, timeout=TIMEOUT)
        status = resp.status
        content_type = resp.headers.get("Content-Type", "")
        data = resp.read()
        resp.close()

        ms = int((time.time() - t0) * 1000)

        content_len = len(data)
        if content_len == 0:
            log("  [WARN] [{}] {} -> {} ({}ms, empty)".format(status, name, repr(url), ms))
            return item, False, "empty_response", ms

        # 验证内容是否为有效 TVBox 配置
        valid, reason = is_valid_tvbox_content(content_type, data)
        if not valid:
            snippet = data[:100].decode("utf-8", errors="replace").strip()
            log("  [INVALID] [{}] {} -> {} ({}ms, {}bytes, {}): {}".format(
                status, name, repr(url), ms, content_len, reason, snippet[:60]))
            return item, False, "invalid_content({})".format(reason), ms

        # 取前100字节作为内容摘要用于日志
        snippet = data[:100].decode("utf-8", errors="replace").strip()
        log("  [OK] [{}] {} -> {} ({}ms, {}bytes)".format(status, name, repr(url), ms, content_len))
        return item, True, str(status), ms
    except Exception as e:
        ms = int((time.time() - t0) * 1000)
        err = type(e).__name__
        log("  [FAIL] [{}] {} -> {} ({}ms)".format(err, name, repr(url), ms))
        return item, False, err, ms


def check_all_sources(sources, china_speed_map=None):
    log("Phase 2: Content validation for {} sources (timeout {}s, workers {})...".format(
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

    # 分类 alive / dead
    alive = []
    dead = []
    for i in sorted(results.keys()):
        item_result = results[i]
        item = item_result[0]
        name = item["name"]
        if item_result[1]:
            # 优先用国内延迟排序，fallback 到 GitHub Actions 延迟
            china_ms = china_speed_map.get(name) if china_speed_map else None
            sort_ms = china_ms if china_ms is not None else item_result[3]
            speed_label = "{}ms(CN)".format(china_ms) if china_ms else "{}ms(US)".format(item_result[3])
            alive.append((item, sort_ms))
        else:
            dead.append((item, item_result[2]))

    # 按国内延迟从快到慢排序
    alive.sort(key=lambda x: x[1])
    log("Result: {} alive (sorted by speed), {} dead".format(len(alive), len(dead)))
    for rank, (item, ms) in enumerate(alive, 1):
        china_ms = china_speed_map.get(item["name"]) if china_speed_map else None
        label = "{}ms(CN)".format(china_ms) if china_ms else "{}ms(US-fallback)".format(ms)
        log("  #{} {} -> {}".format(rank, item["name"], label))
    return [x[0] for x in alive], dead


def generate_json(alive_sources, dead_sources):
    config = {
        "notice": NOTICE_TEXT,
        "urls": alive_sources,
        "backup_urls": [x[0] for x in dead_sources]  # 临时故障线路放入备用，下次聚合可能恢复
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
        # 加载内置线路 + 自定义接口
        custom_sources = load_custom_sources()
        all_sources = CANDIDATE_SOURCES + custom_sources
        log("Total sources: {} (built-in: {}, custom: {})".format(
            len(all_sources), len(CANDIDATE_SOURCES), len(custom_sources)))

        # 阶段1：国内节点测速排序
        china_speed_map = check_all_china_speeds(all_sources)
        log("China speed test done: {}/{} sources got CN latency".format(
            len(china_speed_map), len(all_sources)))

        # 阶段2：内容有效性验证 + 按国内速度排序
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
