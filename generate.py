import os
import json
import random
import string

def random_name(n=6):
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(n))

# 免责声明（TVBox 忽略 notice 字段，人看 JSON 时可见）
notice_text = (
    "阁下好手段！本资源均来源于网络公开收集整理，仅供个人学习交流使用，"
    "严禁私自售卖、二次倒卖及商用，下载后请 24 小时内自行删除，"
    "使用产生一切后果均由使用者自行承担，与本人无关，特此警示！"
    "此多仓接口列表为公众号【杰翔易达】为粉丝提供便利整理而成，"
    "如有冒犯各位接口所属大神，请联系删除。"
)

# 多仓接口列表（和 d.kstore.dev 样品格式一致）
config = {
    "notice": notice_text,
    "urls": [
        # ⚠️ 免责声明条目（在 APP 多仓列表顶部可见）
        {"url": "#", "name": "⚠️ 免责声明（阁下好手段！详见 JSON 内 notice 字段）"},
        {"url": "https://tv.菜妮丝.top", "name": "小苹果盒子"},
        {"url": "http://tvbox.王二小放牛娃.top", "name": "王二小"},
        {"url": "http://肥猫.com", "name": "肥猫"},
        {"url": "https://盒子迷.top/禁止贩卖", "name": "盒子迷"},
        {"url": "https://tv.菜妮丝.top", "name": "菜妮丝线路"},
        {"url": "https://gh-proxy.com/https://raw.githubusercontent.com/guot55/yg/main/pg/bh.json", "name": "寳盒"},
        {"url": "http://www.饭太硬.com/tv", "name": "饭太硬1"},
        {"url": "http://www.饭太硬.net/tv", "name": "饭太硬2"},
        {"url": "http://www.饭太硬.art/tv", "name": "饭太硬3"},
        {"url": "http://fty.xxooo.cf/tv", "name": "饭太硬4"},
        {"url": "http://fty.888484.xyz/tv", "name": "饭太硬5"}
    ]
}

# 生成目录结构（和 d.kstore.dev 一模一样）
os.makedirs("download/1/tvbox", exist_ok=True)
fname = "download/1/tvbox/source.json"   # 固定文件名，URL 不变

with open(fname, "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=4)

print("✅ 生成成功:", fname)

# 验证 JSON 合法性
with open(fname, "r", encoding="utf-8") as f:
    data = json.load(f)
    print("✅ JSON 验证通过，共", len(data["urls"]), "条接口（含免责声明条目）")
    print("✅ notice 字段已写入，长度:", len(data.get("notice", "")), "字")
