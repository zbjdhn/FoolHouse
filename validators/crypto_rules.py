def validate_and_build_trade(form) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    trade: dict[str, str] = {}

    date_value = (form.get("date") or "").strip()
    code = (form.get("code") or "").strip().upper()
    platform = (form.get("platform") or "").strip()
    side = (form.get("side") or "").strip()
    price_raw = (form.get("price") or "").strip()
    quantity_raw = (form.get("quantity") or "").strip()

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
        errors["code"] = "代币代码不能为空。"

    allowed_platforms = ("Binance", "OKX", "Bitget", "Other CEX", "DEX")
    if "platform" in form:
        if not platform:
            errors["platform"] = "请选择平台。"
        elif platform not in allowed_platforms:
            errors["platform"] = "平台不在允许范围内。"

    valid_sides = ("买入", "卖出")
    if side not in valid_sides:
        errors["side"] = "请选择买卖标志。"

    price = None
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
            quantity = float(quantity_raw)
            if quantity <= 0:
                raise ValueError
        except ValueError:
            errors["quantity"] = "成交数量必须为大于 0 的数字。"

    if not errors:
        trade = {
            "date": date_value,
            "code": code,
            "platform": platform,
            "side": side,
            "price": f"{price:.4f}" if price is not None else "",
            "quantity": str(quantity) if quantity is not None else "",
        }

    return trade, errors
