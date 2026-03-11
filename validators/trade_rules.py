from utils.date_utils import format_date_to_str
from utils.stock import normalize_stock_code
from utils.constants import VALID_TRADE_SIDES, SIDE_DIVIDEND, SIDE_BUY, SIDE_SELL

def validate_and_build_trade(form) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    trade: dict[str, str] = {}

    date_value = (form.get("date") or "").strip()
    code = (form.get("code") or "").strip()
    name_value = (form.get("name") or "").strip()
    side = (form.get("side") or "").strip()
    price_raw = (form.get("price") or "").strip()
    quantity_raw = (form.get("quantity") or "").strip()
    amount_raw = (form.get("amount") or "").strip()
    amount_auto_raw = (form.get("amount_auto") or "").strip()

    if not date_value:
        errors["date"] = "成交日期不能为空。"
    else:
        formatted_date = format_date_to_str(date_value)
        if formatted_date:
            date_value = formatted_date
        else:
            errors["date"] = "日期格式不正确。"

    if not code:
        errors["code"] = "证券代码不能为空。"
    else:
        normalized_code = normalize_stock_code(code)
        if not normalized_code:
            errors["code"] = "证券代码格式不正确，请输入有效的6位数字代码（可带sh/sz前缀）。"
        else:
            # 统一存储为6位数字格式
            code = normalized_code[2:]

    if side not in VALID_TRADE_SIDES:
        errors["side"] = "请选择买卖标志。"

    price = None
    if side == SIDE_DIVIDEND:
        price = 0.0
    else:
        if not price_raw:
            errors["price"] = "成交价格不能为空。"
        else:
            try:
                price = float(price_raw)
                if price <= 0:
                    raise ValueError
            except ValueError:
                errors["price"] = "成交价格必须为大于 0 的数字。"

    quantity = None
    if not quantity_raw:
        errors["quantity"] = "成交数量不能为空。"
    else:
        try:
            quantity = int(quantity_raw)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            errors["quantity"] = "成交数量必须为大于 0 的整数。"

    amount = None
    if side == SIDE_DIVIDEND:
        amount = 0.0
    else:
        if amount_raw:
            try:
                amount_val = float(amount_raw)
                if amount_val <= 0:
                    raise ValueError
                amount = abs(amount_val)
            except ValueError:
                errors["amount"] = "发生金额必须为大于 0 的数字。"
        else:
            if price is not None and quantity is not None:
                amount = price * quantity
            else:
                errors["amount"] = "发生金额不能为空。"

    if not errors:
        signed_amount = amount
        if side == SIDE_BUY:
            signed_amount = -abs(amount) if amount is not None else None
        elif side == SIDE_SELL:
            signed_amount = abs(amount) if amount is not None else None
        trade = {
            "date": date_value,
            "code": code,
            "name": name_value,
            "side": side,
            "price": f"{price:.4f}" if price is not None else "",
            "quantity": str(quantity) if quantity is not None else "",
            "amount": f"{signed_amount:.2f}" if amount is not None else "",
        }
        if amount_auto_raw:
            trade["amount_auto"] = "1" if amount_auto_raw in ("1", "true", "True", "TRUE") else "0"
        else:
            trade["amount_auto"] = trade.get("amount_auto", "0")

    return trade, errors
