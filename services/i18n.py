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
    "home_badge": {"zh": "量化工作台", "en": "Quant Workspace"},
    "home_title": {"zh": "FullHouse: 你的交易记录与分析中枢", "en": "FullHouse: Your Trading Record & Analytics Hub"},
    "home_subtitle": {
        "zh": "覆盖 A 股与 Crypto 的交易录入、批量导入、快照与持仓分析，用一套高性能数据底座连接你的执行与复盘。",
        "en": "Cover A-share and crypto workflows with trade entry, bulk import, snapshots, and position analytics on one high-performance data base.",
    },
    "home_login_now": {"zh": "立即登录", "en": "Login Now"},
    "home_snapshot_title": {"zh": "系统概览", "en": "System Snapshot"},
    "home_asset_scope": {"zh": "资产范围", "en": "Asset Scope"},
    "home_input_mode": {"zh": "录入方式", "en": "Input Mode"},
    "home_analysis": {"zh": "分析能力", "en": "Analysis"},
    "home_access": {"zh": "访问控制", "en": "Access"},
    "home_asset_scope_value": {"zh": "A股 + Crypto", "en": "A-Share + Crypto"},
    "home_input_mode_value": {"zh": "手动 + 导入", "en": "Manual + Import"},
    "home_analysis_value": {"zh": "成本 / 快照 / 模拟器", "en": "Cost / Snapshot / Simulator"},
    "home_access_value": {"zh": "多用户 + 管理员", "en": "Multi-user + Admin"},
    "home_features_title": {"zh": "核心功能", "en": "Core Features"},
    "home_feature_1_title": {"zh": "交易数据中台", "en": "Trading Data Hub"},
    "home_feature_1_desc": {"zh": "统一记录买卖、分红、配售与转账，按用户隔离数据，便于团队协作。", "en": "Unify buys, sells, dividends, allotments, and transfers with user-level data isolation for collaboration."},
    "home_feature_2_title": {"zh": "批量导入", "en": "Bulk Import"},
    "home_feature_2_desc": {"zh": "支持 Excel 数据导入，快速把历史成交写入系统，减少手工录入成本。", "en": "Import Excel data to quickly ingest historical trades and reduce manual input costs."},
    "home_feature_3_title": {"zh": "实时行情联动", "en": "Live Quote Sync"},
    "home_feature_3_desc": {"zh": "录入时自动拉取股票名称与价格，提升数据准确性与录入效率。", "en": "Auto-fetch symbol names and prices during entry to improve data accuracy and speed."},
    "home_feature_4_title": {"zh": "分析与回测视角", "en": "Analytics & Replay View"},
    "home_feature_4_desc": {"zh": "持仓成本、快照和模拟器联动，形成执行、复盘、再决策闭环。", "en": "Connect cost, snapshots, and simulator into a closed loop of execution, review, and decision."},
    "home_roadmap_title": {"zh": "Roadmap", "en": "Roadmap"},
    "home_phase_1": {"zh": "数据基础设施", "en": "Data Infrastructure"},
    "home_phase_1_desc": {"zh": "完成多资产交易记录、导入导出、权限管理与稳定持久化。", "en": "Complete multi-asset records, import/export, access control, and durable persistence."},
    "home_phase_2": {"zh": "分析能力扩展", "en": "Analytics Expansion"},
    "home_phase_2_desc": {"zh": "增加收益归因、策略标签、风险暴露与自定义看板。", "en": "Add PnL attribution, strategy tags, risk exposure, and customizable dashboards."},
    "home_phase_3": {"zh": "自动化与智能化", "en": "Automation & Intelligence"},
    "home_phase_3_desc": {"zh": "接入定时任务、预警规则与 AI 复盘助手，提升决策效率。", "en": "Integrate schedules, alert rules, and an AI review assistant to accelerate decisions."},
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
