from datetime import date, datetime

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

EXCEL_COLUMN_MAPPING = {
    "date": ["成交日期", "日期", "date", "Date", "DATE", "交易日期", "成交日"],
    "code": ["代币代码", "代码", "币种", "code", "Code", "CODE", "symbol", "Symbol", "SYMBOL"],
    "platform": ["平台", "platform", "Platform", "PLATFORM", "交易平台", "交易所", "exchange", "Exchange", "EXCHANGE"],
    "side": ["买卖标志", "买卖方向", "方向", "side", "Side", "SIDE", "交易方向", "类型", "type", "Type"],
    "price": ["成交价格", "价格", "price", "Price", "PRICE", "单价"],
    "quantity": ["成交数量", "数量", "quantity", "Quantity", "QUANTITY", "数量(币)"],
}


def find_column_index(df, possible_names):
    for col in df.columns:
        col_str = str(col).strip()
        for name in possible_names:
            if col_str == name or col_str.lower() == name.lower():
                return col
    return None


def parse_excel_file(file_path):
    if not PANDAS_AVAILABLE:
        return [], [], {"error": "pandas库未安装，请运行: pip install pandas openpyxl"}
    try:
        df = pd.read_excel(file_path, engine="openpyxl")
        required = ["date", "code", "side", "price", "quantity"]
        column_map = {}
        for field in required:
            col = find_column_index(df, EXCEL_COLUMN_MAPPING[field])
            if col:
                column_map[field] = col
            else:
                return [], [], {"error": f"未找到必需的列：{EXCEL_COLUMN_MAPPING[field][0]}（支持的列名：{', '.join(EXCEL_COLUMN_MAPPING[field])}）"}
        platform_col = find_column_index(df, EXCEL_COLUMN_MAPPING["platform"])

        trades = []
        errors = []
        for idx, row in df.iterrows():
            row_num = idx + 2
            trade_dict = {}
            row_errors = []
            try:
                date_val = row[column_map["date"]]
                if pd.isna(date_val):
                    row_errors.append(f"第{row_num}行：成交日期为空")
                else:
                    if isinstance(date_val, datetime):
                        date_val = date_val.strftime("%Y%m%d")
                    elif isinstance(date_val, date):
                        date_val = date_val.strftime("%Y%m%d")
                    else:
                        try:
                            if isinstance(date_val, (int, float)) and not isinstance(date_val, bool):
                                iv = int(date_val)
                                s = str(iv)
                                if len(s) == 8 and s.isdigit():
                                    date_val = s
                                else:
                                    date_val = pd.to_datetime(date_val).strftime("%Y%m%d")
                            else:
                                s = str(date_val).strip()
                                digits = "".join(ch for ch in s if ch.isdigit())
                                if len(digits) == 8:
                                    date_val = digits
                                else:
                                    date_val = pd.to_datetime(s).strftime("%Y%m%d")
                        except Exception:
                            row_errors.append(f"第{row_num}行：成交日期格式不正确")
                            date_val = None
                trade_dict["date"] = date_val

                code_val = row[column_map["code"]]
                if pd.isna(code_val):
                    row_errors.append(f"第{row_num}行：代币代码为空")
                else:
                    trade_dict["code"] = str(code_val).strip()

                if platform_col:
                    platform_val = row[platform_col]
                    trade_dict["platform"] = "" if pd.isna(platform_val) else str(platform_val).strip()

                side_val = row[column_map["side"]]
                if pd.isna(side_val):
                    row_errors.append(f"第{row_num}行：买卖标志为空")
                else:
                    side_str = str(side_val).strip()
                    side_mapping = {
                        "买入": ["买入", "BUY", "buy", "Buy", "B", "b", "入"],
                        "卖出": ["卖出", "SELL", "sell", "Sell", "S", "s", "出"],
                    }
                    matched = False
                    for standard_side, variants in side_mapping.items():
                        if side_str == standard_side or side_str in variants:
                            trade_dict["side"] = standard_side
                            matched = True
                            break
                    if not matched:
                        row_errors.append(f"第{row_num}行：买卖标志格式不正确（应为：买入/卖出）")
                        trade_dict["side"] = side_str

                price_val = row[column_map["price"]]
                try:
                    price = float(price_val)
                    if price <= 0:
                        row_errors.append(f"第{row_num}行：成交价格必须大于0")
                    trade_dict["price"] = f"{price:.8f}"
                except (ValueError, TypeError):
                    row_errors.append(f"第{row_num}行：成交价格格式不正确")

                quantity_val = row[column_map["quantity"]]
                try:
                    quantity = float(quantity_val)
                    if quantity <= 0:
                        row_errors.append(f"第{row_num}行：成交数量必须大于0")
                    trade_dict["quantity"] = str(quantity)
                except (ValueError, TypeError):
                    row_errors.append(f"第{row_num}行：成交数量格式不正确")

                # 不再要求发生金额，底层数据结构无该字段

                if not row_errors:
                    trades.append(trade_dict)
                else:
                    errors.extend(row_errors)
            except Exception as e:
                errors.append(f"第{row_num}行：解析错误 - {str(e)}")

        summary = {
            "total_rows": len(df),
            "success_count": len(trades),
            "error_count": len(errors),
        }
        return trades, errors, summary
    except Exception as e:
        return [], [], {"error": f"读取Excel文件失败：{str(e)}"}
