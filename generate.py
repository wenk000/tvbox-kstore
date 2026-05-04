import os
import json

# 生成配置文件（TVBox 多仓接口）
config = {
    "notice": "阁下好手段！本资源均来源于网络公开收集整理，仅供个人学习交流使用，严禁私自售卖、二次倒卖及商用，下载后请 24 小时内自行删除，使用产生一切后果均由使用者自行承担，与本人无关，特此警示！如有冒犯，请联系删除。",
    "urls": [
        {
            "url": "https://tv.菜妮丝.top",
            "name": "小苹果"
        },
        {
            "url": "http://tvbox.王二小放牛娃.top",
            "name": "王二小"
        },
        {
            "url": "http://肥猫.com",
            "name": "肥猫"
        },
        {
            "url": "https://盒子迷.top/禁止贩卖",
            "name": "盒子迷"
        },
        {
            "url": "https://tv.菜妮丝.top",
            "name": "菜妮丝线路"
        },
        {
            "url": "https://gh-proxy.com/https://raw.githubusercontent.com/guot55/yg/main/pg/bh.json",
            "name": "寳盒"
        },
        {
            "url": "http://www.饭太硬.com/tv",
            "name": "饭太硬1"
        },
        {
            "url": "http://www.饭太硬.net/tv",
            "name": "饭太硬2"
        },
        {
            "url": "http://www.饭太硬.art/tv",
            "name": "饭太硬3"
        },
        {
            "url": "http://fty.xxooo.cf/tv",
            "name": "饭太硬4"
        },
        {
            "url": "http://fty.888484.xyz/tv",
            "name": "饭太硬5"
        }
    ]
}

# 生成输出目录
os.makedirs("download/1/tvbox", exist_ok=True)
fname = "download/1/tvbox/source.json"

with open(fname, "w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=4)

print("✅ 生成成功:", fname)

# 验证 JSON 合法性
with open(fname, "r", encoding="utf-8") as f:
    data = json.load(f)
    print("✅ JSON 验证通过，共", len(data["urls"]), "条线路")
    print("✅ notice 长度:", len(data.get("notice", "")), "字")
