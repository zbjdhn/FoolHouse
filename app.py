import os
from datetime import date, datetime
import json
import csv
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from io import BytesIO

from stock_api import get_stock_info, get_batch_stock_info
from validators.trade_rules import validate_and_build_trade as validate_trade
from validators.crypto_rules import validate_and_build_trade as validate_crypto_trade
from importers.excel_parser import parse_excel_file as parse_excel
from importers.crypto_excel_parser import parse_excel_file as parse_crypto_excel
import services.trade_store as trade_store
import services.crypto_store as crypto_store
import services.user_store as user_store
import services.analysis as analysis
import services.snapshot_store as snapshot_store
import services.crypto_tokens_store as crypto_tokens
import services.i18n as i18n
import services.sync_store as sync_store
from utils.date_utils import format_date_to_str
from utils.logger import logger

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


BASE_DIR = os.path.abspath(os.path.dirname(__file__))
from utils.paths import get_data_dir
UPLOAD_DIR = (
    os.environ.get("FULLHOUSE_UPLOAD_DIR")
    or os.environ.get("FOOLHOUSE_UPLOAD_DIR")
    or get_data_dir("uploads")
)


app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"

# 初始化数据库（确保在 Vercel 部署等 WSGI 环境下也能运行）
with app.app_context():
    try:
        user_store.ensure_users_file()
    except Exception as e:
        logger.error(f"应用启动初始化数据库失败: {e}")



def require_login():
    if not session.get("user"):
        return redirect(url_for("login", next=request.path))
    return None


@app.before_request
def _apply_lang():
    q_lang = (request.args.get("lang") or "").strip().lower()
    if q_lang:
        i18n.set_lang(q_lang)
    elif "lang" not in session:
        i18n.set_lang(i18n.DEFAULT_LANG)


@app.context_processor
def _inject_i18n():
    return {"t": i18n.t, "lang": i18n.get_lang()}


@app.route("/lang/<lang>")
def switch_lang(lang: str):
    i18n.set_lang(lang)
    next_url = request.args.get("next") or request.referrer or url_for("index")
    return redirect(next_url)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        user = user_store.authenticate_user(username, password)
        if user:
            session["user"] = username
            session["is_admin"] = bool(user.get("is_admin"))
            next_url = request.args.get("next") or url_for("list_trades")
            return redirect(next_url)
        else:
            flash("用户名或密码错误" if i18n.get_lang() == "zh" else "Invalid username or password")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/change_password", methods=["GET", "POST"])
def change_password():
    need = require_login()
    if need:
        return need
    
    if request.method == "POST":
        old_pwd = (request.form.get("old_password") or "").strip()
        new_pwd = (request.form.get("new_password") or "").strip()
        confirm_pwd = (request.form.get("confirm_password") or "").strip()
        
        username = session.get("user")
        
        if not user_store.verify_password(username, old_pwd):
            flash("当前密码错误" if i18n.get_lang() == "zh" else "Current password incorrect")
        elif not new_pwd:
            flash("新密码不能为空" if i18n.get_lang() == "zh" else "New password cannot be empty")
        elif new_pwd != confirm_pwd:
            flash("两次输入的新密码不一致" if i18n.get_lang() == "zh" else "New passwords do not match")
        else:
                success, msg = user_store.update_password(username, new_pwd)
                if success:
                    flash("密码修改成功" if i18n.get_lang() == "zh" else "Password updated successfully")
                    return redirect(url_for("list_trades"))
                else:
                    flash(msg)
                
    return render_template("change_password.html", is_profile=True)


@app.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    if not session.get("user"):
        return redirect(url_for("login", next=request.path))
    if not session.get("is_admin"):
        flash("无权限")
        return redirect(url_for("list_trades"))
    message = ""
    if request.method == "POST":
        op = (request.form.get("op") or "create").strip()
        if op == "create":
            new_user = (request.form.get("username") or "").strip()
            new_pwd = (request.form.get("password") or "").strip()
            is_admin_flag = True if (request.form.get("is_admin") == "on") else False
            ok, msg = user_store.create_user(new_user, new_pwd, is_admin_flag)
            message = msg
        elif op == "delete":
            target = (request.form.get("username") or "").strip()
            if target == session.get("user"):
                message = "不能删除当前登录账户"
            else:
                ok, msg = user_store.delete_user(target)
                message = msg
        elif op == "reset_pwd":
            target = (request.form.get("username") or "").strip()
            new_pwd = (request.form.get("password") or "").strip()
            confirm_pwd = (request.form.get("confirm_password") or "").strip()
            if not new_pwd:
                message = "新密码不能为空"
            elif new_pwd != confirm_pwd:
                message = "两次输入的新密码不一致"
            else:
                ok, msg = user_store.update_password(target, new_pwd)
                message = msg
    users = user_store.list_users()
    return render_template("admin_users.html", users=users, message=message, is_profile=True)


@app.route("/", methods=["GET", "POST"])
def index():
    if not session.get("user"):
        if request.method == "POST":
            return redirect(url_for("login", next=request.path))
        return render_template("home.html", full_width=True)

    errors: dict[str, str] = {}
    form_data = {
        "date": date.today().isoformat(),
        "code": "",
        "name": "",
        "side": "证券买入",
        "price": "",
        "quantity": "",
        "amount": "",
    }

    if request.method == "POST":
        # 用用户提交数据覆盖默认值，便于回显
        form_data.update(
            {
                "date": (request.form.get("date") or "").strip(),
                "code": (request.form.get("code") or "").strip(),
                "name": (request.form.get("name") or "").strip(),
                "side": (request.form.get("side") or "").strip(),
                "price": (request.form.get("price") or "").strip(),
                "quantity": (request.form.get("quantity") or "").strip(),
                "amount": (request.form.get("amount") or "").strip(),
            }
        )

        trade, errors = validate_trade(request.form)
        if not errors:
            trade["owner"] = session.get("user")
            trade_store.append_trade(trade)
            flash("交易记录已保存。")
            return redirect(url_for("list_trades"))

    return render_template("index.html", errors=errors, form_data=form_data, is_equity=True, equity_active="trades")


@app.route("/trades")
def list_trades():
    need = require_login()
    if need:
        return need
    trades = trade_store.load_trades(owner=session.get("user"))
    return render_template("trades.html", trades=trades, is_equity=True, equity_active="trades")


@app.route("/clear", methods=["POST"])
def clear_trades():
    need = require_login()
    if need:
        return need
    trade_store.clear_all_trades(owner=session.get("user"))
    flash("已清除所有历史交易数据。")
    return redirect(url_for("list_trades"))


@app.route("/edit/<int:index>", methods=["GET", "POST"])
def edit_trade(index: int):
    """Edit a trade record by its display index."""
    need = require_login()
    if need:
        return need
    
    orig_index, trade = trade_store.get_trade_by_display_index(index, owner=session.get("user"))
    
    if orig_index is None:
        flash("交易记录不存在。")
        return redirect(url_for("list_trades"))
    
    errors: dict[str, str] = {}
    form_data = {
        "date": trade.get("date", ""),
        "code": trade.get("code", ""),
        "name": trade.get("name", ""),
        "side": trade.get("side", "证券买入"),
        "price": trade.get("price", ""),
        "quantity": trade.get("quantity", ""),
        "amount": trade.get("amount", ""),
    }
    d = form_data.get("date") or ""
    if len(d) == 8 and d.isdigit():
        form_data["date"] = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
    
    if request.method == "POST":
        # 用用户提交数据覆盖默认值，便于回显
        form_data.update(
            {
                "date": (request.form.get("date") or "").strip(),
                "code": (request.form.get("code") or "").strip(),
                "name": (request.form.get("name") or "").strip(),
                "side": (request.form.get("side") or "").strip(),
                "price": (request.form.get("price") or "").strip(),
                "quantity": (request.form.get("quantity") or "").strip(),
                "amount": (request.form.get("amount") or "").strip(),
            }
        )
        
        updated_trade, errors = validate_trade(request.form)
        if not errors:
            updated_trade["owner"] = session.get("user")
            if trade_store.update_trade_by_index(orig_index, updated_trade):
                flash("交易记录已更新。")
                return redirect(url_for("list_trades"))
            else:
                errors["_general"] = "更新失败，请重试。"
    
    return render_template("edit.html", errors=errors, form_data=form_data, index=index, is_equity=True, equity_active="trades")


@app.route("/delete/<int:index>", methods=["POST"])
def delete_trade(index: int):
    """Delete a trade record by its display index."""
    need = require_login()
    if need:
        return need
    orig_index, _ = trade_store.get_trade_by_display_index(index, owner=session.get("user"))
    
    if orig_index is None:
        flash("交易记录不存在。")
        return redirect(url_for("list_trades"))
    
    if trade_store.delete_trade_by_index(orig_index):
        flash("交易记录已删除。")
    else:
        flash("删除失败，请重试。")
    
    return redirect(url_for("list_trades"))


@app.route("/api/stock/<code>")
def api_get_stock(code: str):
    """API 接口：根据股票代码获取股票信息"""
    result = get_stock_info(code)
    return jsonify(result)


@app.get("/api/stocks")
def api_get_stocks():
    """批量获取股票当前价格与名称，codes=600000,000001"""
    codes_param = (request.args.get("codes") or "").strip()
    if not codes_param:
        return jsonify({})
    codes = [c.strip() for c in codes_param.split(",") if c.strip()]
    data = get_batch_stock_info(codes)
    return jsonify(data)


@app.get("/api/snapshot/total-assets")
def api_get_total_assets_snapshot():
    """返回最新的总资产快照，若不存在则返回空对象"""
    v = snapshot_store.get_latest_total_assets()
    if v is None:
        return jsonify({})
    return jsonify({"total_assets": v})


@app.get("/api/bootstrap")
def api_bootstrap():
    """
    One-time bootstrap payload for local-first IndexedDB.
    Returns both equity and crypto records for the current user.
    """
    need = require_login()
    if need:
        return need
    owner = session.get("user")
    equity = trade_store.load_trades(owner=owner)
    crypto = crypto_store.load_trades(owner=owner)
    # Map server-side rows to client format (clientId may not exist yet)
    eq_out = []
    for t in equity:
        eq_out.append(
            {
                "clientId": (t.get("client_id") or t.get("clientId") or ""),
                "date": t.get("date") or "",
                "code": t.get("code") or "",
                "name": t.get("name") or "",
                "side": t.get("side") or "",
                "price": str(t.get("price") or ""),
                "quantity": str(t.get("quantity") or ""),
                "amount": str(t.get("amount") or ""),
                "amountAuto": str(t.get("amount_auto") or t.get("amountAuto") or "0"),
            }
        )
    cr_out = []
    for t in crypto:
        cr_out.append(
            {
                "clientId": (t.get("client_id") or t.get("clientId") or ""),
                "date": t.get("date") or "",
                "code": (t.get("code") or "").upper(),
                "platform": t.get("platform") or "",
                "side": t.get("side") or "",
                "price": str(t.get("price") or ""),
                "quantity": str(t.get("quantity") or ""),
            }
        )
    return jsonify({"equity": eq_out, "crypto": cr_out})


@app.post("/api/sync/equity")
def api_sync_equity():
    need = require_login()
    if need:
        return jsonify({"error": "not_logged_in"}), 401
    owner = session.get("user")
    body = request.get_json(silent=True) or {}
    device_id = (body.get("deviceId") or "").strip()
    records = body.get("records") or []
    if not device_id:
        return jsonify({"error": "missing deviceId"}), 400
    if not isinstance(records, list):
        return jsonify({"error": "records must be a list"}), 400

    accepted, errors = sync_store.upsert_equity_raw_and_normalized(owner, device_id, records)
    return jsonify({"accepted": accepted, "errors": errors})


@app.post("/api/sync/crypto")
def api_sync_crypto():
    need = require_login()
    if need:
        return jsonify({"error": "not_logged_in"}), 401
    owner = session.get("user")
    body = request.get_json(silent=True) or {}
    device_id = (body.get("deviceId") or "").strip()
    records = body.get("records") or []
    if not device_id:
        return jsonify({"error": "missing deviceId"}), 400
    if not isinstance(records, list):
        return jsonify({"error": "records must be a list"}), 400

    accepted, errors = sync_store.upsert_crypto_raw_and_normalized(owner, device_id, records)
    return jsonify({"accepted": accepted, "errors": errors})


@app.route("/export")
def export_trades():
    """导出所有交易记录为Excel文件"""
    need = require_login()
    if need:
        return need
    if not PANDAS_AVAILABLE:
        flash("导出功能需要pandas库，请运行: pip install pandas openpyxl")
        return redirect(url_for("list_trades"))
    
    try:
        trades = trade_store.load_trades(owner=session.get("user"))
        
        if not trades:
            flash("没有交易记录可导出。")
            return redirect(url_for("list_trades"))
        
        df = pd.DataFrame(trades)
        if "code" in df.columns:
            def _fmt_code(v):
                s = str(v or "").strip()
                if s.isdigit():
                    return s.zfill(6)
                return s
            df["code"] = df["code"].map(_fmt_code)
        if "name" not in df.columns:
            df["name"] = ""
        if "date" in df.columns:
            df["date"] = df["date"].map(lambda v: format_date_to_str(v))
        column_mapping = {
            "date": "成交日期",
            "code": "证券代码",
            "name": "证券名称",
            "side": "买卖标志",
            "price": "成交价格",
            "quantity": "成交数量",
            "amount": "发生金额",
        }
        df = df.rename(columns=column_mapping)
        df = df[["成交日期", "证券代码", "证券名称", "买卖标志", "成交价格", "成交数量", "发生金额"]]
        
        # 创建Excel文件到内存
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='交易记录')
            
            # 获取工作表以调整列宽
            worksheet = writer.sheets['交易记录']
            for idx, col in enumerate(df.columns):
                # 设置列宽（根据列名长度）
                max_length = max(
                    df[col].astype(str).map(len).max(),
                    len(col)
                ) + 2
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length, 20)
        
        output.seek(0)
        
        # 生成文件名（包含当前日期）
        from datetime import datetime
        filename = f"交易记录_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        flash(f"导出失败：{str(e)}")
        return redirect(url_for("list_trades"))

 


@app.route("/import", methods=["GET", "POST"])
def import_trades():
    """批量导入交易记录"""
    need = require_login()
    if need:
        return need
    if request.method == "GET":
        return render_template("import.html", is_equity=True, equity_active="trades")
    
    # 检查文件
    if "file" not in request.files:
        flash("请选择要上传的Excel文件。")
        return redirect(url_for("import_trades"))
    
    file = request.files["file"]
    if file.filename == "":
        flash("请选择要上传的Excel文件。")
        return redirect(url_for("import_trades"))
    
    # 检查文件扩展名
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        flash("只支持Excel文件格式（.xlsx 或 .xls）。")
        return redirect(url_for("import_trades"))
    
    # 保存文件
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, filename)
    file.save(file_path)
    
    try:
        trades, errors, summary = parse_excel(file_path)
        
        if "error" in summary:
            flash(f"导入失败：{summary['error']}")
            return redirect(url_for("import_trades"))
        
        # 批量导入成功的记录
        success_count = 0
        for trade in trades:
            trade_dict, validation_errors = validate_trade(trade)
            if not validation_errors:
                if "amount_auto" in trade and trade.get("amount_auto") in ("1", "true", "True", "TRUE"):
                    trade_dict["amount_auto"] = "1"
                else:
                    trade_dict["amount_auto"] = "0"
                trade_dict["owner"] = session.get("user")
                trade_store.append_trade(trade_dict)
                success_count += 1
        
        # 生成结果消息
        messages = []
        if success_count > 0:
            messages.append(f"成功导入 {success_count} 条交易记录。")
        if errors:
            messages.append(f"有 {len(errors)} 条记录存在错误，未导入。")
        if len(errors) > 0:
            messages.append("详细错误信息请查看导入结果。")
        
        flash(" ".join(messages))
        
        # 如果有错误，显示错误详情
        if errors:
            return render_template("import.html", errors=errors, summary=summary, is_equity=True, equity_active="trades")
        
        
        
    finally:
        # 删除临时文件
        if os.path.exists(file_path):
            os.remove(file_path)


@app.route("/equity/transfers")
def equity_transfers():
    need = require_login()
    if need:
        return need
    return render_template("equity/transfers.html", is_equity=True, equity_active="transfers")


@app.route("/equity/snapshot")
def equity_snapshot():
    need = require_login()
    if need:
        return need
    return render_template("equity/snapshot.html", is_equity=True, equity_active="snapshot")


@app.route("/equity/analysis/cost")
def equity_cost_analysis():
    need = require_login()
    if need:
        return need
    trades = trade_store.load_trades(owner=session.get("user"))
    positions = analysis.compute_positions(trades)
    return render_template("equity/cost_analysis.html", is_equity=True, equity_active="cost", positions=positions)


@app.route("/equity/analysis/simulator")
def equity_simulator():
    need = require_login()
    if need:
        return need
    return render_template("equity/simulator.html", is_equity=True, equity_active="simulator")


@app.route("/crypto")
def crypto_home():
    return redirect(url_for("crypto_list_trades"))


@app.route("/crypto/add", methods=["GET", "POST"])
def crypto_add():
    need = require_login()
    if need:
        return need
    crypto_store.ensure_data_file()
    errors: dict[str, str] = {}
    allowed = crypto_tokens.list_tokens()
    allowed_platforms = ["Binance", "OKX", "Bitget", "Other CEX", "DEX"]
    form_data = {
        "date": date.today().isoformat(),
        "code": "",
        "platform": "",
        "side": "买入",
        "price": "",
        "quantity": "",
    }
    if request.method == "POST":
        form_data.update(
            {
                "date": (request.form.get("date") or "").strip(),
                "code": (request.form.get("code") or "").strip(),
                "platform": (request.form.get("platform") or "").strip(),
                "side": (request.form.get("side") or "").strip(),
                "price": (request.form.get("price") or "").strip(),
                "quantity": (request.form.get("quantity") or "").strip(),
            }
        )
        trade, errors = validate_crypto_trade(request.form)
        if not errors:
            # 限制代币代码
            code_u = (trade.get("code") or "").upper()
            is_admin = session.get("is_admin")
            if not is_admin and code_u not in allowed:
                flash("该代币未在白名单中，请申请新增代币。")
                return redirect(url_for("crypto_add"))
            trade["code"] = code_u
            trade["owner"] = session.get("user")
            crypto_store.append_trade(trade)
            flash("Crypto 交易记录已保存。")
            return redirect(url_for("crypto_list_trades"))
    return render_template("crypto/index.html", errors=errors, form_data=form_data, tokens=allowed, platforms=allowed_platforms, is_crypto=True, crypto_active="trades")


@app.route("/crypto/trades")
def crypto_list_trades():
    need = require_login()
    if need:
        return need
    trades = crypto_store.load_trades(owner=session.get("user"))
    return render_template("crypto/trades.html", trades=trades, is_crypto=True, crypto_active="trades")


@app.route("/crypto/edit/<int:index>", methods=["GET", "POST"])
def crypto_edit_trade(index: int):
    need = require_login()
    if need:
        return need
    crypto_store.ensure_data_file()
    orig_index, trade = crypto_store.get_trade_by_display_index(index, owner=session.get("user"))
    if orig_index is None:
        flash("交易记录不存在。")
        return redirect(url_for("crypto_list_trades"))
    errors: dict[str, str] = {}
    allowed = crypto_tokens.list_tokens()
    allowed_platforms = ["Binance", "OKX", "Bitget", "Other CEX", "DEX"]
    form_data = {
        "date": trade.get("date", ""),
        "code": trade.get("code", ""),
        "platform": trade.get("platform", ""),
        "side": trade.get("side", "买入"),
        "price": trade.get("price", ""),
        "quantity": trade.get("quantity", ""),
    }
    d = form_data.get("date") or ""
    if len(d) == 8 and d.isdigit():
        form_data["date"] = f"{d[0:4]}-{d[4:6]}-{d[6:8]}"
    if request.method == "POST":
        form_data.update(
            {
                "date": (request.form.get("date") or "").strip(),
                "code": (request.form.get("code") or "").strip(),
                "platform": (request.form.get("platform") or "").strip(),
                "side": (request.form.get("side") or "").strip(),
                "price": (request.form.get("price") or "").strip(),
                "quantity": (request.form.get("quantity") or "").strip(),
            }
        )
        updated_trade, errors = validate_crypto_trade(request.form)
        if not errors:
            code_u = (updated_trade.get("code") or "").upper()
            is_admin = session.get("is_admin")
            if not is_admin and code_u not in allowed:
                errors["_general"] = "该代币未在白名单中，请申请新增代币。"
            else:
                if "platform" not in request.form or not (updated_trade.get("platform") or "").strip():
                    updated_trade["platform"] = trade.get("platform", "")
                updated_trade["code"] = code_u
                updated_trade["owner"] = session.get("user")
                if crypto_store.update_trade_by_index(orig_index, updated_trade):
                    flash("交易记录已更新。")
                    return redirect(url_for("crypto_list_trades"))
                else:
                    errors["_general"] = "更新失败，请重试。"
    return render_template("crypto/edit.html", errors=errors, form_data=form_data, index=index, tokens=allowed, platforms=allowed_platforms, is_crypto=True, crypto_active="trades")


@app.route("/crypto/delete/<int:index>", methods=["POST"])
def crypto_delete_trade(index: int):
    need = require_login()
    if need:
        return need
    ok = crypto_store.delete_trade_by_index(index)
    if ok:
        flash("已删除交易记录。")
    else:
        flash("删除失败。")
    return redirect(url_for("crypto_list_trades"))


@app.route("/crypto/clear", methods=["POST"])
def crypto_clear_trades():
    need = require_login()
    if need:
        return need
    trades = crypto_store.load_trades(owner=session.get("user"))
    remaining = [t for t in trades if (t.get("owner") or "") != session.get("user")]
    if remaining:
        with open(crypto_store.DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=crypto_store.CSV_HEADERS)
            writer.writeheader()
            for r in remaining:
                writer.writerow(r)
    else:
        with open(crypto_store.DATA_FILE, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(crypto_store.CSV_HEADERS)
    flash("已清除所有 Crypto 历史交易数据。")
    return redirect(url_for("crypto_list_trades"))


@app.route("/crypto/export")
def crypto_export_trades():
    need = require_login()
    if need:
        return need
    if not PANDAS_AVAILABLE:
        flash("导出功能需要pandas库，请运行: pip install pandas openpyxl")
        return redirect(url_for("crypto_list_trades"))
    try:
        trades = crypto_store.load_trades(owner=session.get("user"))
        if not trades:
            flash("没有交易记录可导出。")
            return redirect(url_for("crypto_list_trades"))
        df = pd.DataFrame(trades)
        # 统一代码大写
        if "code" in df.columns:
            df["code"] = df["code"].map(lambda x: (str(x or "")).upper())
        if "date" in df.columns:
            df["date"] = df["date"].map(lambda v: format_date_to_str(v))
        column_mapping = {
            "date": "成交日期",
            "code": "代币代码",
            "platform": "平台",
            "side": "买卖标志",
            "price": "成交价格",
            "quantity": "成交数量",
        }
        df = df.rename(columns=column_mapping)
        df = df[["成交日期", "代币代码", "平台", "买卖标志", "成交价格", "成交数量"]]
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='交易记录')
            ws = writer.sheets['交易记录']
            for idx, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).map(len).max(), len(col)) + 2
                ws.column_dimensions[chr(65 + idx)].width = min(max_length, 20)
        output.seek(0)
        from datetime import datetime
        filename = f"Crypto交易记录_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f"导出失败：{str(e)}")
        return redirect(url_for("crypto_list_trades"))


@app.route("/crypto/import", methods=["GET", "POST"])
def crypto_import_trades():
    need = require_login()
    if need:
        return need
    if request.method == "GET":
        return render_template("crypto/import.html", is_crypto=True, crypto_active="trades")
    if "file" not in request.files:
        flash("请选择要上传的Excel文件。")
        return redirect(url_for("crypto_import_trades"))
    file = request.files["file"]
    if file.filename == "":
        flash("请选择要上传的Excel文件。")
        return redirect(url_for("crypto_import_trades"))
    if not file.filename.lower().endswith((".xlsx", ".xls")):
        flash("只支持Excel文件格式（.xlsx 或 .xls）。")
        return redirect(url_for("crypto_import_trades"))
    filename = secure_filename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, filename)
    file.save(file_path)
    try:
        trades, errors, summary = parse_crypto_excel(file_path)
        if "error" in summary:
            flash(f"导入失败：{summary['error']}")
            return redirect(url_for("crypto_import_trades"))
        success_count = 0
        allowed = crypto_tokens.list_tokens()
        is_admin = session.get("is_admin")
        for trade in trades:
            trade_dict, validation_errors = validate_crypto_trade(trade)
            if not validation_errors:
                code_u = (trade_dict.get("code") or "").upper()
                if not is_admin and code_u not in allowed:
                    errors.append(f"代币 {code_u} 不在白名单中，已跳过（请申请新增）")
                    continue
                trade_dict["code"] = code_u
                trade_dict["owner"] = session.get("user")
                crypto_store.append_trade(trade_dict)
                success_count += 1
        messages = []
        if success_count > 0:
            messages.append(f"成功导入 {success_count} 条交易记录。")
        if errors:
            messages.append(f"有 {len(errors)} 条记录存在错误，未导入。")
        if len(errors) > 0:
            messages.append("详细错误信息请查看导入结果。")
        flash(" ".join(messages))
        if errors:
            return render_template("crypto/import.html", errors=errors, summary=summary, is_crypto=True, crypto_active="trades")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)
    return redirect(url_for("crypto_list_trades"))


@app.route("/crypto/transfers")
def crypto_transfers():
    need = require_login()
    if need:
        return need
    return render_template("crypto/transfers.html", is_crypto=True, crypto_active="transfers")


@app.post("/crypto/token-request")
def crypto_token_request():
    need = require_login()
    if need:
        return need
    code = (request.form.get("code") or "").strip().upper()
    name = (request.form.get("name") or "").strip()
    reason = (request.form.get("reason") or "").strip()
    if not code:
        flash("请输入代币代码")
        return redirect(url_for("crypto_add"))
    if crypto_tokens.submit_request(session.get("user"), code, name, reason):
        flash("已提交申请，管理员审核后可用")
    else:
        flash("申请已存在或代币已在白名单中")
    return redirect(url_for("crypto_add"))


@app.route("/admin/crypto/tokens", methods=["GET", "POST"])
def admin_crypto_tokens():
    if not session.get("user"):
        return redirect(url_for("login", next=request.path))
    if not session.get("is_admin"):
        flash("无权限")
        return redirect(url_for("list_trades"))
    message = ""
    if request.method == "POST":
        op = (request.form.get("op") or "").strip()
        code = (request.form.get("code") or "").strip().upper()
        if op == "add":
            ok = crypto_tokens.add_token(code)
            message = "添加成功" if ok else "已存在或无效"
        elif op == "remove":
            ok = crypto_tokens.remove_token(code)
            message = "已移除" if ok else "不存在"
        elif op == "approve":
            ok = crypto_tokens.approve_request(code)
            message = "已批准并加入白名单" if ok else "批准失败"
    tokens = crypto_tokens.list_tokens()
    requests = crypto_tokens.list_requests()
    return render_template("admin_crypto_tokens.html", tokens=tokens, requests=requests, message=message, is_profile=True)

if __name__ == "__main__":
    app.run(debug=True)
