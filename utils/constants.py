# 交易方向常量
SIDE_BUY = "证券买入"
SIDE_SELL = "证券卖出"
SIDE_SUBSCRIPTION = "配售申购"
SIDE_DIVIDEND = "红股入账"

VALID_TRADE_SIDES = (SIDE_BUY, SIDE_SELL, SIDE_SUBSCRIPTION, SIDE_DIVIDEND)

# 导入时的映射关系
SIDE_MAPPING = {
    SIDE_BUY: [SIDE_BUY, "买入", "买", "BUY", "buy", "Buy", "B", "b", "证券买"],
    SIDE_SELL: [SIDE_SELL, "卖出", "卖", "SELL", "sell", "Sell", "S", "s", "证券卖"],
    SIDE_SUBSCRIPTION: [SIDE_SUBSCRIPTION, "配售", "申购", "配股"],
    SIDE_DIVIDEND: [SIDE_DIVIDEND, "红股", "送股", "分红"],
}

# 加密货币交易方向
CRYPTO_SIDE_BUY = "买入"
CRYPTO_SIDE_SELL = "卖出"
VALID_CRYPTO_SIDES = (CRYPTO_SIDE_BUY, CRYPTO_SIDE_SELL)

CRYPTO_SIDE_MAPPING = {
    CRYPTO_SIDE_BUY: [CRYPTO_SIDE_BUY, "BUY", "buy", "Buy", "B", "b", "入"],
    CRYPTO_SIDE_SELL: [CRYPTO_SIDE_SELL, "SELL", "sell", "Sell", "S", "s", "出"],
}
