import pandas as pd
from typing import List, Dict
from utils.constants import SIDE_BUY, SIDE_SELL, SIDE_DIVIDEND, SIDE_SUBSCRIPTION
from utils.logger import logger

def compute_positions(trades: List[Dict]) -> List[Dict]:
    if not trades:
        return []
    df = pd.DataFrame(trades)
    for col in ["code", "side", "name", "date", "quantity", "amount"]:
        if col not in df.columns:
            df[col] = None
    df["code"] = df["code"].astype(str).str.strip()
    df["side"] = df["side"].astype(str).str.strip()
    df["name"] = df["name"].astype(str).replace({"None": ""}).str.strip()
    df["date"] = df["date"].astype(str)
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0).astype(int)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0).astype(float)
    df = df.sort_values(["code", "date"])

    def _calc(group: pd.DataFrame) -> Dict:
        shares = 0
        cost = 0.0
        nm = ""
        net_cash_sum = 0.0  # 签名金额求和（买入负，卖出正）
        for _, row in group.iterrows():
            s = row.get("side", "")
            q = int(row.get("quantity", 0) or 0)
            a = float(row.get("amount", 0.0) or 0.0)
            n = str(row.get("name", "") or "").strip()
            if n and not nm:
                nm = n
            net_cash_sum += a
            if s in (SIDE_BUY, SIDE_SUBSCRIPTION):
                if q > 0:
                    cost += abs(a)
                    shares += q
            elif s == SIDE_SELL:
                if q > 0 and shares > 0:
                    avg = cost / shares if shares > 0 else 0.0
                    r = min(q, shares)
                    shares -= r
                    cost = max(0.0, cost - avg * r)
            elif s == SIDE_DIVIDEND:
                if q > 0:
                    shares += q
        # 绝对成本价：净投入金额 / 当前持股数，其中净投入= -签名金额求和（买入为投入）
        abs_cost_price = ((-net_cash_sum) / shares) if shares > 0 else 0.0
        return {"shares": shares, "cost": cost, "name": nm, "absolute_cost_price": abs_cost_price}

    results = []
    for code, g in df.groupby("code"):
        r = _calc(g)
        if r["shares"] > 0:
            cost_price = (r["cost"] / r["shares"]) if r["shares"] > 0 else 0.0
            results.append(
                {
                    "code": code,
                    "name": r["name"],
                    "shares": int(r["shares"]),
                    "cost_total": float(r["cost"]),
                    "cost_price": float(cost_price),
                    "absolute_cost_price": float(r["absolute_cost_price"]),
                }
            )
    results.sort(key=lambda x: x["code"])
    return results
