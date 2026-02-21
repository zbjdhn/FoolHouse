import os
from datetime import date, datetime
import json
from werkzeug.utils import secure_filename

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_file, session
from io import BytesIO

from stock_api import get_stock_info
from validators.trade_rules import validate_and_build_trade as validate_trade
from importers.excel_parser import parse_excel_file as parse_excel
import services.trade_store as trade_store
import services.user_store as user_store

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False


BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def _choose_dir(env_key: str, default_subdir: str) -> str:
    env_path = os.environ.get(env_key)
    if env_path:
        try:
            os.makedirs(env_path, exist_ok=True)
            return env_path
        except OSError:
            pass
    default_path = os.path.join(BASE_DIR, default_subdir)
    try:
        os.makedirs(default_path, exist_ok=True)
        return default_path
    except OSError:
        tmp_path = os.path.join("/tmp", "foolhouse", default_subdir)
        os.makedirs(tmp_path, exist_ok=True)
        return tmp_path

UPLOAD_DIR = _choose_dir("FOOLHOUSE_UPLOAD_DIR", "uploads")


app = Flask(__name__)
app.secret_key = "dev-secret-key-change-me"



def require_login():
    if not session.get("user"):
        return redirect(url_for("login", next=request.path))
    return None


@app.before_request
def _ensure_users():
    user_store.ensure_users_file()


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = (request.form.get("password") or "").strip()
        if user_store.verify_password(username, password):
            session["user"] = username
            session["is_admin"] = user_store.is_admin(username)
            next_url = request.args.get("next") or url_for("list_trades")
            return redirect(next_url)
        else:
            flash("用户名或密码错误")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/admin/users", methods=["GET", "POST"])
def admin_users():
    if not session.get("user"):
        return redirect(url_for("login", next=request.path))
    if not session.get("is_admin"):
        flash("无权限")
        return redirect(url_for("list_trades"))
    message = ""
    if request.method == "POST":
        new_user = (request.form.get("username") or "").strip()
        new_pwd = (request.form.get("password") or "").strip()
        is_admin_flag = True if (request.form.get("is_admin") == "on") else False
        if user_store.create_user(new_user, new_pwd, is_admin_flag):
            message = "用户创建成功"
        else:
            message = "用户已存在或信息不完整"
    users = user_store.list_users()
    return render_template("admin_users.html", users=users, message=message)


@app.route("/", methods=["GET", "POST"])
def index():
    need = require_login()
    if need:
        return need
    trade_store.ensure_data_file()

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

    return render_template("index.html", errors=errors, form_data=form_data)


@app.route("/trades")
def list_trades():
    need = require_login()
    if need:
        return need
    trades = trade_store.load_trades(owner=session.get("user"))
    return render_template("trades.html", trades=trades)


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
    trade_store.ensure_data_file()
    
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
    
    return render_template("edit.html", errors=errors, form_data=form_data, index=index)


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
            def _fmt(v):
                s = str(v or "").strip()
                if len(s) == 10 and s[4] == "-" and s[7] == "-":
                    return s.replace("-", "")
                elif len(s) == 8 and s.isdigit():
                    return s
                else:
                    return s
            df["date"] = df["date"].map(_fmt)
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
        return render_template("import.html")
    
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
            return render_template("import.html", errors=errors, summary=summary)
        
        return redirect(url_for("list_trades"))
        
    finally:
        # 删除临时文件
        if os.path.exists(file_path):
            os.remove(file_path)


if __name__ == "__main__":
    app.run(debug=True)
