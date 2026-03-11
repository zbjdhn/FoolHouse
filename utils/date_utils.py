from datetime import date, datetime
import pandas as pd

def format_date_to_str(date_val, format_str="%Y%m%d") -> str:
    """
    将各种类型的日期输入统一格式化为指定的字符串。
    支持: datetime, date, int, float, str
    """
    if pd.isna(date_val):
        return ""
    
    if isinstance(date_val, (datetime, date)):
        return date_val.strftime(format_str)
    
    # 如果是数字（通常是 Excel 中的日期数字）
    if isinstance(date_val, (int, float)) and not isinstance(date_val, bool):
        try:
            # 可能是类似 20230101 的整数
            s = str(int(date_val))
            if len(s) == 8 and s.isdigit():
                return s
            # 可能是 Excel 内部日期序列
            return pd.to_datetime(date_val).strftime(format_str)
        except:
            return ""
            
    # 如果是字符串
    s = str(date_val).strip()
    if not s:
        return ""
        
    # 处理带分隔符的日期
    try:
        # 如果只有数字且长度为8
        digits = "".join(ch for ch in s if ch.isdigit())
        if len(digits) == 8:
            return digits
        
        # 尝试通用解析
        return pd.to_datetime(s).strftime(format_str)
    except:
        return ""
