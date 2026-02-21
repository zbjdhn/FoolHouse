from datetime import date, datetime

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

EXCEL_COLUMN_MAPPING = {
    "date": ["成交日期", "日期", "date", "Date", "DATE", "交易日期", "成交日"],
    "code": ["证券代码", "代码", "code", "Code", "CODE", "股票代码", "证券"],
    "side": ["买卖标志", "买卖方向", "方向", "side", "Side", "SIDE", "交易方向", "类型"],
    "price": ["成交价格", "价格", "price", "Price", "PRICE", "单价"],
    "quantity": ["成交数量", "数量", "quantity", "Quantity", "QUANTITY", "股数", "数量(股)"],
    "amount": ["发生金额", "金额", "amount", "Amount", "AMOUNT", "总金额", "金额(元)"],
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
        column_map = {}
        for field, possible_names in EXCEL_COLUMN_MAPPING.items():
            col = find_column_index(df, possible_names)
            if col:
                column_map[field] = col
            else:
                return [], [], {"error": f"未找到必需的列：{possible_names[0]}（支持的列名：{', '.join(possible_names)}）"}

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
                        except:
                            row_errors.append(f"第{row_num}行：成交日期格式不正确")
                            date_val = None
                    trade_dict["date"] = date_val

                code_val = row[column_map["code"]]
                if pd.isna(code_val):
                    row_errors.append(f"第{row_num}行：证券代码为空")
                else:
                    code_str = str(code_val).strip()
                    digits = "".join(ch for ch in code_str if ch.isdigit())
                    if len(digits) < 6:
                        digits = digits.zfill(6)
                    if len(digits) != 6:
                        row_errors.append(f"第{row_num}行：证券代码必须为6位数字")
                    else:
                        trade_dict["code"] = digits
                name_col = find_column_index(df, ["证券名称", "名称", "证券简称", "股票名称", "name", "Name", "NAME"])
                if name_col:
                    name_val = row[name_col]
                    if pd.isna(name_val):
                        trade_dict["name"] = ""
                    else:
                        trade_dict["name"] = str(name_val).strip()
                else:
                    trade_dict["name"] = ""

                side_val = row[column_map["side"]]
                if pd.isna(side_val):
                    row_errors.append(f"第{row_num}行：买卖标志为空")
                else:
                    side_str = str(side_val).strip()
                    side_mapping = {
                        "证券买入": ["证券买入", "买入", "买", "BUY", "buy", "Buy", "B", "b", "证券买"],
                        "证券卖出": ["证券卖出", "卖出", "卖", "SELL", "sell", "Sell", "S", "s", "证券卖"],
                        "配售申购": ["配售申购", "配售", "申购", "配股"],
                        "红股入账": ["红股入账", "红股", "送股", "分红"],
                    }
                    matched = False
                    for standard_side, variants in side_mapping.items():
                        if side_str in variants or side_str == standard_side:
                            trade_dict["side"] = standard_side
                            matched = True
                            break
                    if not matched:
                        row_errors.append(f"第{row_num}行：买卖标志格式不正确（应为：证券买入/证券卖出/配售申购/红股入账）")
                        trade_dict["side"] = side_str

                price_val = row[column_map["price"]]
                if trade_dict.get("side") == "红股入账":
                    if pd.isna(price_val) or str(price_val).strip() == "":
                        row_errors.append(f"第{row_num}行：红股入账的成交价格必须为0")
                    else:
                        try:
                            price = float(price_val)
                            if price != 0.0:
                                row_errors.append(f"第{row_num}行：红股入账的成交价格必须为0")
                            trade_dict["price"] = f"{0.0:.4f}"
                        except (ValueError, TypeError):
                            row_errors.append(f"第{row_num}行：成交价格格式不正确")
                else:
                    try:
                        price = float(price_val)
                        if price <= 0:
                            row_errors.append(f"第{row_num}行：成交价格必须大于0")
                        trade_dict["price"] = f"{price:.4f}"
                    except (ValueError, TypeError):
                        row_errors.append(f"第{row_num}行：成交价格格式不正确")

                quantity_val = row[column_map["quantity"]]
                if pd.isna(quantity_val):
                    row_errors.append(f"第{row_num}行：成交数量为空")
                else:
                    try:
                        quantity = int(float(quantity_val))
                        if quantity <= 0:
                            row_errors.append(f"第{row_num}行：成交数量必须大于0")
                        trade_dict["quantity"] = str(quantity)
                    except (ValueError, TypeError):
                        row_errors.append(f"第{row_num}行：成交数量格式不正确")

                amount_val = row[column_map["amount"]]
                if trade_dict.get("side") == "红股入账":
                    if pd.isna(amount_val) or str(amount_val).strip() == "":
                        row_errors.append(f"第{row_num}行：红股入账的发生金额必须为0")
                    else:
                        try:
                            parsed_amount = float(amount_val)
                            if parsed_amount != 0.0:
                                row_errors.append(f"第{row_num}行：红股入账的发生金额必须为0")
                            trade_dict["amount"] = f"{0.0:.2f}"
                            trade_dict["amount_auto"] = "0"
                        except (ValueError, TypeError):
                            row_errors.append(f"第{row_num}行：发生金额格式不正确")
                else:
                    if pd.isna(amount_val) or str(amount_val).strip() == "":
                        try:
                            price_f = float(trade_dict.get("price"))
                            qty_i = int(trade_dict.get("quantity"))
                            calc_amount = price_f * qty_i
                            trade_dict["amount"] = f"{calc_amount:.2f}"
                            trade_dict["amount_auto"] = "1"
                        except Exception:
                            row_errors.append(f"第{row_num}行：发生金额为空且无法自动计算")
                    else:
                        try:
                            parsed_amount = float(amount_val)
                            if abs(parsed_amount) <= 0:
                                row_errors.append(f"第{row_num}行：发生金额必须大于0")
                            trade_dict["amount"] = f"{abs(parsed_amount):.2f}"
                            trade_dict["amount_auto"] = "0"
                        except (ValueError, TypeError):
                            row_errors.append(f"第{row_num}行：发生金额格式不正确")

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
