"""
股票数据 API 模块
用于从外部接口获取股票信息，与主应用解耦
"""
import re
from typing import Optional, Dict
import urllib.request
import urllib.error


def normalize_stock_code(code: str) -> Optional[str]:
    """
    标准化股票代码格式
    
    Args:
        code: 用户输入的股票代码（如 "600900" 或 "sh600900"）
    
    Returns:
        标准化后的代码（如 "sh600900" 或 "sz000001"），如果格式无效则返回 None
    """
    code = code.strip().upper()
    
    # 如果已经包含前缀，直接返回
    if code.startswith(("SH", "SZ")):
        return code.lower()
    
    # 判断是上海还是深圳
    # 上海：600xxx, 601xxx, 603xxx, 605xxx, 688xxx
    # 深圳：000xxx, 001xxx, 002xxx, 003xxx, 300xxx
    if re.match(r"^(600|601|603|605|688)\d{3}$", code):
        return f"sh{code}"
    elif re.match(r"^(000|001|002|003|300)\d{3}$", code):
        return f"sz{code}"
    
    return None


def fetch_stock_info(code: str, retry_count: int = 2) -> Dict[str, Optional[str]]:
    """
    从腾讯股票接口获取股票信息
    
    Args:
        code: 标准化后的股票代码（如 "sh600900"）
        retry_count: 重试次数（默认2次）
    
    Returns:
        包含股票信息的字典：
        {
            "name": 股票名称（如 "长江电力"），
            "current_price": 当前价格（如 "26.00"），
            "error": 错误信息（如果有）
        }
    """
    url = f"https://qt.gtimg.cn/q={code}"
    
    # 创建请求，添加User-Agent头避免被拒绝
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
    req.add_header("Referer", "https://finance.qq.com/")
    
    last_error = None
    
    # 重试机制
    for attempt in range(retry_count + 1):
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                data = response.read().decode("gbk")  # 接口返回 GBK 编码
                
                # 解析返回数据
                # 格式：v_sh600900="1~股票名称~600900~当前价格~..."
                match = re.search(r'v_[^=]+="([^"]+)"', data)
                if not match:
                    return {
                        "name": None,
                        "current_price": None,
                        "error": "无法解析股票数据，请检查股票代码是否正确"
                    }
                
                parts = match.group(1).split("~")
                if len(parts) < 4:
                    return {
                        "name": None,
                        "current_price": None,
                        "error": "股票数据格式错误"
                    }
                
                stock_name = parts[1] if parts[1] else None
                current_price = parts[3] if parts[3] else None
                
                # 验证价格是否为有效数字
                if current_price:
                    try:
                        float(current_price)
                    except ValueError:
                        current_price = None
                
                return {
                    "name": stock_name,
                    "current_price": current_price,
                    "error": None
                }
                
        except urllib.error.URLError as e:
            last_error = e
            # 如果是最后一次尝试，返回错误
            if attempt == retry_count:
                error_msg = str(e)
                if "Connection reset" in error_msg or "54" in error_msg:
                    return {
                        "name": None,
                        "current_price": None,
                        "error": "网络连接被重置，可能是网络不稳定或接口限制，请稍后重试"
                    }
                elif "timeout" in error_msg.lower():
                    return {
                        "name": None,
                        "current_price": None,
                        "error": "请求超时，请检查网络连接后重试"
                    }
                else:
                    return {
                        "name": None,
                        "current_price": None,
                        "error": f"网络请求失败，请检查网络连接或稍后重试"
                    }
            # 否则等待一下再重试
            import time
            time.sleep(0.5)
            
        except Exception as e:
            return {
                "name": None,
                "current_price": None,
                "error": f"获取股票信息失败: {str(e)}"
            }
    
    # 如果所有重试都失败
    return {
        "name": None,
        "current_price": None,
        "error": "网络请求失败，请检查网络连接或稍后重试"
    }


def get_stock_info(user_input_code: str) -> Dict[str, Optional[str]]:
    """
    根据用户输入的股票代码获取股票信息（对外统一接口）
    
    Args:
        user_input_code: 用户输入的股票代码
    
    Returns:
        包含股票信息的字典
    """
    normalized_code = normalize_stock_code(user_input_code)
    if not normalized_code:
        return {
            "name": None,
            "current_price": None,
            "error": "股票代码格式不正确，请输入6位数字（如：600900）"
        }
    
    return fetch_stock_info(normalized_code)
