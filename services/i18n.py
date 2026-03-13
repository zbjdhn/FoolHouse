from flask import session
from utils.logger import logger

SUPPORTED_LANGS = {"zh", "en"}
DEFAULT_LANG = "zh"

MESSAGES = {
    "brand_slogan": {"zh": "一个面向交易者的数据分析系统", "en": "a da system for traders"},
    "nav_a_share": {"zh": "A股", "en": "A-Share"},
    "nav_crypto": {"zh": "Crypto", "en": "Crypto"},
    "nav_user_admin": {"zh": "用户管理", "en": "User Admin"},
    "nav_crypto_whitelist": {"zh": "Crypto 白名单", "en": "Crypto Whitelist"},
    "nav_hello": {"zh": "您好", "en": "Hi"},
    "nav_profile": {"zh": "个人中心", "en": "Profile"},
    "nav_change_password": {"zh": "修改密码", "en": "Change Password"},
    "nav_logout": {"zh": "退出", "en": "Logout"},
    "nav_login": {"zh": "登录", "en": "Login"},
    "nav_lang_zh": {"zh": "中文", "en": "中文"},
    "nav_lang_en": {"zh": "English", "en": "English"},
    "sidebar_database": {"zh": "数据库", "en": "Database"},
    "sidebar_trade_records": {"zh": "交易记录", "en": "Trades"},
    "sidebar_transfers": {"zh": "充提记录", "en": "Transfers"},
    "sidebar_snapshot": {"zh": "持仓快照", "en": "Position Snapshot"},
    "sidebar_analysis": {"zh": "数据分析", "en": "Analytics"},
    "sidebar_cost": {"zh": "持仓成本", "en": "Position Cost"},
    "sidebar_simulator": {"zh": "持仓模拟器", "en": "Position Simulator"},
    "sidebar_fiat_transfers": {"zh": "出入金记录", "en": "Deposit/Withdrawals"},
    "home_badge": {"zh": "数据驱动交易中枢", "en": "Data-Driven Trading Hub"},
    "home_title": {"zh": "交易数据智能中枢", "en": "Trading Data Intelligence Hub"},
    "home_subtitle": {
        "zh": "统一交易、行情、仓位与策略信号，构建可追溯的数据链路，让执行、复盘与决策更快闭环。",
        "en": "Unify trades, quotes, positions, and signals into a traceable data pipeline that closes the loop between execution and review.",
    },
    "home_login_now": {"zh": "立即登录", "en": "Login Now"},
    "home_snapshot_title": {"zh": "实时数据面板", "en": "Live Data Panel"},
    "home_board_title": {"zh": "信号趋势与风险视图", "en": "Signal Trend & Risk View"},
    "home_board_status": {"zh": "实时", "en": "Live"},
    "home_asset_scope": {"zh": "资产范围", "en": "Asset Scope"},
    "home_input_mode": {"zh": "录入方式", "en": "Input Mode"},
    "home_analysis": {"zh": "分析维度", "en": "Analytics Dimensions"},
    "home_access": {"zh": "访问控制", "en": "Access"},
    "home_asset_scope_value": {"zh": "A股 + Crypto", "en": "A-Share + Crypto"},
    "home_input_mode_value": {"zh": "手动 + 批量导入", "en": "Manual + Bulk Import"},
    "home_analysis_value": {"zh": "成本 / 风险 / 归因", "en": "Cost / Risk / Attribution"},
    "home_access_value": {"zh": "多用户隔离", "en": "Multi-user Isolation"},
    "home_metric_1_label": {"zh": "数据延迟", "en": "Latency"},
    "home_metric_1_value": {"zh": "< 1s", "en": "< 1s"},
    "home_metric_2_label": {"zh": "覆盖资产", "en": "Coverage"},
    "home_metric_2_value": {"zh": "A股 / Crypto", "en": "A-Share / Crypto"},
    "home_metric_3_label": {"zh": "信号维度", "en": "Signal Axes"},
    "home_metric_3_value": {"zh": "成本 · 风险 · 归因", "en": "Cost · Risk · Attribution"},
    "home_metric_4_label": {"zh": "更新策略", "en": "Refresh"},
    "home_metric_4_value": {"zh": "实时 / 批量", "en": "Real-time / Batch"},
    "home_features_title": {"zh": "核心功能", "en": "Core Features"},
    "home_features_note": {"zh": "把数据链路与策略执行固化为标准化流程。", "en": "Turn the data pipeline into a standardized workflow."},
    "home_feature_1_title": {"zh": "多源交易采集", "en": "Multi-Source Ingestion"},
    "home_feature_1_desc": {"zh": "统一买卖、分红、配售与转账，跨资产类型按用户隔离数据。", "en": "Unify buys, sells, dividends, allotments, and transfers with user-level isolation across assets."},
    "home_feature_2_title": {"zh": "批量与实时同步", "en": "Batch + Real-time Sync"},
    "home_feature_2_desc": {"zh": "Excel 批量导入 + 行情自动补全，保持历史与实时一致性。", "en": "Excel bulk import plus live quote enrichment keeps history and real-time aligned."},
    "home_feature_3_title": {"zh": "信号与风险看板", "en": "Signal & Risk Boards"},
    "home_feature_3_desc": {"zh": "把成本、风险与收益归因映射到可追踪指标，直接驱动复盘。", "en": "Map cost, risk, and attribution into traceable indicators that power reviews."},
    "home_feature_4_title": {"zh": "策略闭环", "en": "Strategy Feedback Loop"},
    "home_feature_4_desc": {"zh": "从执行到复盘的指标闭环，让策略迭代更可控、更高效。", "en": "Close the loop from execution to review with measurable feedback."},
    "home_roadmap_title": {"zh": "Roadmap", "en": "Roadmap"},
    "home_phase_1": {"zh": "A股充提记录", "en": "A-Share Transfers"},
    "home_phase_1_desc": {"zh": "补齐 A 股资金流入流出与转账记录，支持对账与追溯。", "en": "Add A-share cash inflow/outflow and transfer records with audit trails."},
    "home_phase_2": {"zh": "A股 Snapshot 数据", "en": "A-Share Snapshot"},
    "home_phase_2_desc": {"zh": "形成多时间点持仓快照，支撑对比分析与回溯。", "en": "Build multi-point position snapshots for comparisons and backtracking."},
    "home_phase_3": {"zh": "Crypto 数据", "en": "Crypto Data"},
    "home_phase_3_desc": {"zh": "完善链上/交易所数据接入与对账流程。", "en": "Complete on-chain/exchange data ingestion and reconciliation."},
    "login_title": {"zh": "登录", "en": "Login"},
    "login_username": {"zh": "用户名", "en": "Username"},
    "login_password": {"zh": "密码", "en": "Password"},
    "login_submit": {"zh": "登录", "en": "Sign In"},
}


def get_lang() -> str:
    lang = (session.get("lang") or DEFAULT_LANG).lower()
    if lang not in SUPPORTED_LANGS:
        return DEFAULT_LANG
    return lang


def set_lang(lang: str) -> str:
    if not lang:
        session["lang"] = DEFAULT_LANG
        return DEFAULT_LANG
    lang = lang.lower()
    if lang not in SUPPORTED_LANGS:
        logger.warning(f"不支持的语言: {lang}，回退到默认语言: {DEFAULT_LANG}")
        lang = DEFAULT_LANG
    else:
        logger.debug(f"设置语言为: {lang}")
    session["lang"] = lang
    return lang


def t(key: str, lang: str | None = None) -> str:
    use_lang = lang or get_lang()
    node = MESSAGES.get(key)
    if not node:
        return key
    return node.get(use_lang) or node.get(DEFAULT_LANG) or key
