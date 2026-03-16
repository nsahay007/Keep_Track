from __future__ import annotations

import os
from datetime import datetime, date, timedelta

import pandas as pd
from flask import Flask, jsonify, request, render_template
from PIL import Image

from analytics import predict_future_expenses, generate_insights, generate_report
from config import CATEGORIES, PAYMENT_METHODS
from database import DatabaseManager, Expense
from ocr_scanner import ReceiptScanner
from ai_assistant import answer_question

APP_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder="static", template_folder="templates")

db = DatabaseManager()
scanner = ReceiptScanner()


def _to_df():
    df = db.get_all_expenses()
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    return df


def _month_bounds(d: date):
    start = d.replace(day=1)
    if d.month == 12:
        end = date(d.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(d.year, d.month + 1, 1) - timedelta(days=1)
    return start, end


def _parse_date(text: str | None):
    if not text:
        return None
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _resolve_range(df: pd.DataFrame, start: date | None, end: date | None, duration: str | None):
    today = date.today()

    if start or end:
        s = start or (df["date"].min() if not df.empty else today)
        e = end or today
        if s > e:
            s, e = e, s
        return s, e, f"{s.isoformat()} to {e.isoformat()}"

    if duration:
        if duration == "all":
            if not df.empty:
                s = df["date"].min()
                e = df["date"].max()
                return s, e, "All time"
            return today, today, "All time"
        if duration == "this_month":
            s, e = _month_bounds(today)
            return s, e, today.strftime("%B %Y")
        if duration == "last_month":
            last_end = _month_bounds(today)[0] - timedelta(days=1)
            s, e = _month_bounds(last_end)
            return s, e, s.strftime("%B %Y")
        if duration == "last_3m":
            s = (today.replace(day=1) - pd.DateOffset(months=2)).date()
            return s, today, "Last 3 months"
        if duration == "last_6m":
            s = (today.replace(day=1) - pd.DateOffset(months=5)).date()
            return s, today, "Last 6 months"
        if duration == "last_12m":
            s = (today.replace(day=1) - pd.DateOffset(months=11)).date()
            return s, today, "Last 12 months"
        if duration == "ytd":
            s = date(today.year, 1, 1)
            return s, today, "Year to date"

    # Default: current month, or latest month with data
    if not df.empty:
        current_start, current_end = _month_bounds(today)
        df_current = df[(df["date"] >= current_start) & (df["date"] <= current_end)]
        if not df_current.empty:
            return current_start, current_end, today.strftime("%B %Y")
        ref = df["date"].max()
        s, e = _month_bounds(ref)
        return s, e, ref.strftime("%B %Y")

    return today, today, today.strftime("%B %Y")


def _build_analytics(df: pd.DataFrame, start: date | None, end: date | None, duration: str | None):
    range_start, range_end, range_label = _resolve_range(df, start, end, duration)

    total_all = float(df["amount"].sum()) if not df.empty else 0.0
    df_range = df[(df["date"] >= range_start) & (df["date"] <= range_end)] if not df.empty else df
    total_range = float(df_range["amount"].sum()) if not df_range.empty else 0.0

    cat_totals = (
        df_range.groupby("category")["amount"].sum().reindex(CATEGORIES).fillna(0).tolist()
        if not df_range.empty
        else [0] * len(CATEGORIES)
    )

    months = []
    month_totals = []
    ref_date = range_end
    for i in range(5, -1, -1):
        d = (ref_date.replace(day=15) - pd.DateOffset(months=i)).date()
        ms, me = _month_bounds(d)
        months.append(d.strftime("%b %Y"))
        df_m = df[(df["date"] >= ms) & (df["date"] <= me)] if not df.empty else df
        month_totals.append(float(df_m["amount"].sum()) if not df_m.empty else 0.0)

    start_30 = ref_date - timedelta(days=29)
    if not df.empty:
        df_30 = df[(df["date"] >= start_30) & (df["date"] <= ref_date)]
        daily = df_30.groupby("date")["amount"].sum()
    else:
        daily = pd.Series(dtype=float)
    days = [(start_30 + timedelta(days=i)) for i in range(30)]
    trend_labels = [d.strftime("%b %d") for d in days]
    trend_values = [float(daily.get(d, 0.0)) for d in days]

    last_month_end = _month_bounds(ref_date)[0] - timedelta(days=1)
    last_start, last_end = _month_bounds(last_month_end)
    df_last = df[(df["date"] >= last_start) & (df["date"] <= last_end)] if not df.empty else df
    curr_by_cat = (
        df_range.groupby("category")["amount"].sum().reindex(CATEGORIES).fillna(0).tolist()
        if not df_range.empty
        else [0] * len(CATEGORIES)
    )
    last_by_cat = (
        df_last.groupby("category")["amount"].sum().reindex(CATEGORIES).fillna(0).tolist()
        if not df_last.empty
        else [0] * len(CATEGORIES)
    )

    insights = generate_insights(df_range) if not df_range.empty else ["No data in selected range."]

    return {
        "total_all": total_all,
        "total_range": total_range,
        "range_label": range_label,
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "categories": CATEGORIES,
        "category_totals": cat_totals,
        "months": months,
        "month_totals": month_totals,
        "trend_labels": trend_labels,
        "trend_values": trend_values,
        "comparison_current": curr_by_cat,
        "comparison_last": last_by_cat,
        "insights": insights,
    }


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/meta")
def meta():
    return jsonify({"categories": CATEGORIES, "payment_methods": PAYMENT_METHODS})


@app.route("/api/expenses", methods=["GET"])
def list_expenses():
    df = _to_df()

    start = _parse_date(request.args.get("start"))
    end = _parse_date(request.args.get("end"))
    category = request.args.get("category")
    sort = request.args.get("sort", "date")
    order = request.args.get("order", "desc")
    limit = request.args.get("limit")

    if start:
        df = df[df["date"] >= start]
    if end:
        df = df[df["date"] <= end]
    if category and category != "All":
        df = df[df["category"] == category]

    if sort in ["date", "amount", "category"]:
        df = df.sort_values(sort, ascending=(order == "asc"))

    if limit:
        try:
            lim = int(limit)
            if lim > 0:
                df = df.head(lim)
        except ValueError:
            pass

    return jsonify(df.to_dict(orient="records"))


@app.route("/api/expenses", methods=["POST"])
def add_expense():
    data = request.get_json(force=True)
    date_str = data.get("date")
    category = data.get("category")
    amount = data.get("amount")
    description = data.get("description", "")
    payment_method = data.get("payment_method", "Cash")
    entry_method = data.get("entry_method", "manual")

    if not date_str or category not in CATEGORIES:
        return jsonify({"error": "Invalid input"}), 400

    try:
        amount = float(amount)
    except (TypeError, ValueError):
        return jsonify({"error": "Amount must be a number"}), 400

    expense_id = db.add_expense(
        date=datetime.fromisoformat(date_str).date(),
        category=category,
        amount=amount,
        description=description,
        payment_method=payment_method,
        entry_method=entry_method,
    )
    return jsonify({"status": "ok", "id": expense_id})


@app.route("/api/expenses/<int:expense_id>", methods=["PUT"])
def update_expense(expense_id: int):
    data = request.get_json(force=True)
    update = {}
    for field in ["date", "category", "amount", "description", "payment_method"]:
        if field in data:
            update[field] = data[field]
    if "date" in update:
        update["date"] = datetime.fromisoformat(update["date"]).date()
    if "amount" in update:
        update["amount"] = float(update["amount"])
    ok = db.update_expense(expense_id, **update)
    return jsonify({"status": "ok" if ok else "not_found"})


@app.route("/api/expenses/<int:expense_id>", methods=["DELETE"])
def delete_expense(expense_id: int):
    ok = db.delete_expense(expense_id)
    return jsonify({"status": "ok" if ok else "not_found"})


@app.route("/api/seed", methods=["POST"])
def seed():
    sample_path = os.path.join(APP_DIR, "sample_data.csv")
    if not os.path.exists(sample_path):
        return jsonify({"error": "sample_data.csv not found"}), 404

    df = pd.read_csv(sample_path)

    db.session.query(Expense).delete()
    db.session.commit()

    for _, row in df.iterrows():
        db.add_expense(
            date=datetime.fromisoformat(row["date"]).date(),
            category=row["category"],
            amount=float(row["amount"]),
            description=row.get("description", ""),
            payment_method=row.get("payment_method", "Cash"),
            entry_method=row.get("entry_method", "manual"),
        )

    return jsonify({"status": "ok", "rows": len(df)})


@app.route("/api/analytics")
def analytics():
    df = _to_df()
    start = _parse_date(request.args.get("start"))
    end = _parse_date(request.args.get("end"))
    duration = request.args.get("duration")
    return jsonify(_build_analytics(df, start, end, duration))


@app.route("/api/predict", methods=["POST"])
def predict():
    data = request.get_json(force=True)
    days_ahead = int(data.get("days_ahead", 30))
    df = _to_df()
    pred_df, text = predict_future_expenses(df, days_ahead)
    if pred_df is None:
        return jsonify({"error": text}), 400
    return jsonify({
        "message": text,
        "dates": [d.isoformat() for d in pred_df["date"]],
        "values": pred_df["predicted_amount"].round(2).tolist(),
        "total": float(pred_df["predicted_amount"].sum()),
        "avg": float(pred_df["predicted_amount"].mean()),
    })


@app.route("/api/report")
def report():
    df = _to_df()
    return jsonify({"report": generate_report(df)})


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    query = data.get("query", "")
    df = _to_df()
    return jsonify({"answer": answer_question(query, df)})


@app.route("/api/ocr", methods=["POST"])
def ocr():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["file"]
    if not file:
        return jsonify({"error": "Invalid file"}), 400
    image = Image.open(file.stream)
    text = scanner.extract_text(image)
    parsed = scanner.parse_receipt(text)
    return jsonify({"text": text, "parsed": parsed})


@app.route("/api/budgets", methods=["GET", "POST"])
def budgets():
    if request.method == "GET":
        return jsonify(db.get_budgets())
    data = request.get_json(force=True)
    category = data.get("category")
    amount = data.get("amount")
    if category not in CATEGORIES:
        return jsonify({"error": "Invalid category"}), 400
    db.set_budget(category, float(amount))
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)
