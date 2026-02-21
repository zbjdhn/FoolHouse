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
        if len(date_value) == 10 and date_value[4] == "-" and date_value[7] == "-":
            date_value = date_value.replace("-", "")
        elif len(date_value) == 8 and date_value.isdigit():
            date_value = date_value
        else:
            errors["date"] = "日期格式应为YYYYMMDD。"

    if not code:
        errors["code"] = "证券代码不能为空。"
    else:
        if not (len(code) == 6 and code.isdigit()):
            errors["code"] = "证券代码必须为6位数字。"

    valid_sides = ("证券买入", "证券卖出", "配售申购", "红股入账")
    if side not in valid_sides:
        errors["side"] = "请选择买卖标志。"

    price = None
    if side == "红股入账":
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
    if side == "红股入账":
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
        if side == "证券买入":
            signed_amount = -abs(amount) if amount is not None else None
        elif side == "证券卖出":
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
