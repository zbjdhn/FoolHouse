"""
股票数据 API 模块
使用 cachetools 实现专业级的 30 分钟缓存
支持多源切换和重试
"""
import re
import time
import urllib.request
import urllib.error
from typing import Optional, Dict, List
from cachetools import TTLCache
from utils.stock import normalize_stock_code
from utils.logger import logger

# 专业缓存：TTL=30分钟 (1800s), 最大容量 1000 条
# 同时保留一个"最近成功"的兜底存储，用于接口挂掉时显示过期数据
_PRICE_CACHE = TTLCache(maxsize=1000, ttl=1800)
_LAST_KNOWN_GOOD = {}

def _fetch_from_tencent(code: str) -> Dict[str, Optional[str]]:
    url = f"https://qt.gtimg.cn/q={code}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    req.add_header("Referer", "https://finance.qq.com/")
    with urllib.request.urlopen(req, timeout=5) as response:
        data = response.read().decode("gbk")
        match = re.search(r'v_[^=]+="([^"]+)"', data)
        if not match: return {}
        parts = match.group(1).split("~")
        if len(parts) < 4: return {}
        return {"name": parts[1], "current_price": parts[3]}

def _fetch_from_sina(code: str) -> Dict[str, Optional[str]]:
    url = f"https://hq.sinajs.cn/list={code}"
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0")
    req.add_header("Referer", "https://finance.sina.com.cn/")
    with urllib.request.urlopen(req, timeout=5) as response:
        data = response.read().decode("gbk")
        match = re.search(r'var hq_str_[^=]+="([^"]+)"', data)
        if not match: return {}
        parts = match.group(1).split(",")
        if len(parts) < 4: return {}
        return {"name": parts[0], "current_price": parts[3]}

def fetch_stock_info(code: str, retry_count: int = 2) -> Dict[str, Optional[str]]:
    # 1. 优先从 TTLCache 读取
    if code in _PRICE_CACHE:
        data = _PRICE_CACHE[code]
        return {"name": data["name"], "current_price": data["price"], "error": None, "cached": True}

    # 2. 缓存未命中或已过期，请求数据
    sources = [_fetch_from_tencent, _fetch_from_sina]
    last_error = "未知错误"
    for attempt in range(retry_count + 1):
        fetcher = sources[attempt % len(sources)]
        try:
            res = fetcher(code)
            if res and res.get("name") and res.get("current_price"):
                price = float(res["current_price"])
                if price > 0:
                    # 存入 TTLCache 和 兜底存储
                    _PRICE_CACHE[code] = {"name": res["name"], "price": str(price)}
                    _LAST_KNOWN_GOOD[code] = {"name": res["name"], "price": str(price)}
                    return {"name": res["name"], "current_price": str(price), "error": None, "cached": False}
        except Exception as e:
            last_error = str(e)
            logger.debug(f"从数据源获取股票 {code} 失败: {last_error}")
            time.sleep(0.3)

    # 3. 如果所有尝试都失败，且 TTLCache 已过期，从兜底存储获取过期数据
    if code in _LAST_KNOWN_GOOD:
        data = _LAST_KNOWN_GOOD[code]
        return {
            "name": data["name"],
            "current_price": data["price"],
            "error": f"实时获取失败，显示过期数据: {last_error}",
            "cached": True
        }

    return {"name": None, "current_price": None, "error": f"暂无法获取实时价格: {last_error}"}

def get_stock_info(user_input_code: str) -> Dict[str, Optional[str]]:
    nc = normalize_stock_code(user_input_code)
    if not nc: return {"name": None, "current_price": None, "error": "无效的代码"}
    return fetch_stock_info(nc)

def fetch_batch_stock_info(codes: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
    if not codes: return {}
    result = {}
    missing = []
    
    # 从缓存提取
    for c in codes:
        if c in _PRICE_CACHE:
            data = _PRICE_CACHE[c]
            result[c] = {"name": data["name"], "current_price": data["price"]}
        else:
            missing.append(c)
    
    if not missing: return result
    
    # 批量请求
    try:
        url = "https://qt.gtimg.cn/q=" + ",".join(missing)
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "Mozilla/5.0")
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read().decode("gbk", errors="ignore")
            for seg in data.split(";"):
                m = re.search(r'v_([a-z]{2}\d{6})="([^"]*)"', seg.strip())
                if not m: continue
                nc, parts = m.group(1), m.group(2).split("~")
                if len(parts) > 3:
                    name, price = parts[1], parts[3]
                    try:
                        if float(price) > 0:
                            item = {"name": name, "current_price": price}
                            result[nc] = item
                            _PRICE_CACHE[nc] = {"name": name, "price": price}
                            _LAST_KNOWN_GOOD[nc] = {"name": name, "price": price}
                    except Exception as e:
                        logger.warning(f"解析批量股票数据片段失败: {e}")
    except Exception as e:
        logger.error(f"批量请求股票数据失败: {e}")
        # 批量请求失败，降级为逐个重试模式
        for c in missing:
            info = fetch_stock_info(c, retry_count=1)
            if info.get("name"):
                result[c] = info
            
    return result

def get_batch_stock_info(user_codes: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
    mapping = {normalize_stock_code(c): c for c in user_codes if normalize_stock_code(c)}
    data = fetch_batch_stock_info(list(mapping.keys()))
    return {mapping[nc]: info for nc, info in data.items() if nc in mapping}
