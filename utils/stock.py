import re
from typing import Optional

def normalize_stock_code(code: str) -> Optional[str]:
    """
    标准化股票代码格式。
    
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
    # 上海主板/科创板：600xxx, 601xxx, 603xxx, 605xxx, 688xxx
    # 上海ETF常见：510xxx, 511xxx, 512xxx, 513xxx, 515xxx, 516xxx, 518xxx, 588xxx
    # 深圳主板/创业板：000xxx, 001xxx, 002xxx, 003xxx, 300xxx
    # 深圳ETF常见：159xxx
    if re.match(r"^(600|601|603|605|688|510|511|512|513|515|516|518|588)\d{3}$", code):
        return f"sh{code}"
    elif re.match(r"^(000|001|002|003|300|159)\d{3}$", code):
        return f"sz{code}"
    
    return None

def is_valid_stock_code(code: str) -> bool:
    """
    检查是否为有效的6位数字股票代码。
    """
    return bool(re.match(r"^\d{6}$", code.strip()))

def format_to_6_digits(code: str) -> str:
    """
    将代码格式化为6位数字（不足6位则补零）。
    """
    digits = "".join(ch for ch in str(code) if ch.isdigit())
    return digits.zfill(6)
