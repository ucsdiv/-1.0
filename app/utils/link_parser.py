import re

DISK_PATTERNS = {
    "baidu": [r"pan\.baidu\.com/s/", r"yun\.baidu\.com/s/"],
    "aliyun": [r"www\.aliyundrive\.com/s/", r"www\.alipan\.com/s/", r"alywp\.net/"],
    "quark": [r"pan\.quark\.cn/s/"],
    "tianyi": [r"cloud\.189\.cn/t/", r"cloud\.189\.cn/s/"],
    "uc": [r"drive\.uc\.cn/s/", r"uc\.cn/s/"],
    "mobile": [r"caiyun\.139\.com/"],
    "115": [r"115\.com/s/", r"115cdn\.com/s/"],
    "pikpak": [r"mypikpak\.com/s/"],
    "xunlei": [r"pan\.xunlei\.com/s/"],
    "123": [r"www\.123pan\.cn/s/", r"www\.123684\.com/s/", r"www\.123865\.com/s/"],
    "google": [r"drive\.google\.com/"],
    "magnet": [r"^magnet:\?"],
    "ed2k": [r"^ed2k://"],
}


def detect_disk_type(url: str) -> str:
    url = url.strip()
    for disk_type, patterns in DISK_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return disk_type
    return ""


def normalize_url(url: str) -> str:
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    return url


def extract_password(text: str) -> str:
    matches = re.findall(r"[提取码|密码|pwd|pass][\s:：]+([a-zA-Z0-9]{4,6})", text)
    return matches[0] if matches else ""
