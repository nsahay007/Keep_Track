"""
Natural-language question answering for expenses
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

import pandas as pd


def month_bounds(d: date):
    start = d.replace(day=1)
    if d.month == 12:
        end = date(d.year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(d.year, d.month + 1, 1) - timedelta(days=1)
    return start, end


def _parse_iso_date(text: str):
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def answer_question(query: str, df: pd.DataFrame) -> str:
    q = (query or "").lower().strip()
    today = date.today()

    if not q:
        return "Please ask a question about your expenses."

    if df.empty:
        return "You have no expenses yet. Add some data or load a sample to ask questions."

    def parse_range(qtext: str):
        # Explicit date range: 2026-01-01 to 2026-01-15
        date_matches = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", qtext)
        if len(date_matches) >= 2:
            start = _parse_iso_date(date_matches[0])
            end = _parse_iso_date(date_matches[1])
            if start and end:
                if start > end:
                    start, end = end, start
                return start, end, f"{start.isoformat()} to {end.isoformat()}"
        if len(date_matches) == 1 and ("since" in qtext or "from" in qtext):
            start = _parse_iso_date(date_matches[0])
            if start:
                return start, today, f"{start.isoformat()} to today"

        month_map = {
            "january": 1, "jan": 1,
            "february": 2, "feb": 2,
            "march": 3, "mar": 3,
            "april": 4, "apr": 4,
            "may": 5,
            "june": 6, "jun": 6,
            "july": 7, "jul": 7,
            "august": 8, "aug": 8,
            "september": 9, "sep": 9, "sept": 9,
            "october": 10, "oct": 10,
            "november": 11, "nov": 11,
            "december": 12, "dec": 12,
        }
        m = re.search(
            r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b",
            qtext,
        )
        if m:
            month = month_map[m.group(1)]
            y = re.search(r"\b(20\d{2})\b", qtext)
            year = int(y.group(1)) if y else today.year
            start = date(year, month, 1)
            end = date(year + 1, 1, 1) - timedelta(days=1) if month == 12 else date(year, month + 1, 1) - timedelta(days=1)
            return start, end, start.strftime("%B %Y")

        if "today" in qtext:
            return today, today, "today"
        if "yesterday" in qtext:
            d = today - timedelta(days=1)
            return d, d, "yesterday"
        if "this week" in qtext:
            start = today - timedelta(days=today.weekday())
            return start, today, "this week"
        if "last week" in qtext:
            end = today - timedelta(days=today.weekday() + 1)
            start = end - timedelta(days=6)
            return start, end, "last week"
        if "last 7 days" in qtext:
            start = today - timedelta(days=6)
            return start, today, "the last 7 days"
        if "last 30 days" in qtext:
            start = today - timedelta(days=29)
            return start, today, "the last 30 days"
        if "month to date" in qtext or "month-to-date" in qtext or "mtd" in qtext:
            start, _ = month_bounds(today)
            return start, today, "month to date"
        if "this month" in qtext:
            start, end = month_bounds(today)
            return start, end, today.strftime("%B %Y")
        if "last month" in qtext:
            end = month_bounds(today)[0] - timedelta(days=1)
            start, end = month_bounds(end)
            return start, end, start.strftime("%B %Y")
        if "this year" in qtext:
            start = date(today.year, 1, 1)
            return start, today, "this year"
        if "last year" in qtext:
            start = date(today.year - 1, 1, 1)
            end = date(today.year - 1, 12, 31)
            return start, end, str(today.year - 1)
        return None

    def detect_category(qtext: str):
        mapping = {
            "food": "Food & Dining",
            "dining": "Food & Dining",
            "restaurant": "Food & Dining",
            "groceries": "Food & Dining",
            "transport": "Transportation",
            "commute": "Transportation",
            "fuel": "Transportation",
            "travel": "Travel",
            "shopping": "Shopping",
            "entertainment": "Entertainment",
            "movies": "Entertainment",
            "bills": "Bills & Utilities",
            "utilities": "Bills & Utilities",
            "electric": "Bills & Utilities",
            "internet": "Bills & Utilities",
            "health": "Healthcare",
            "medical": "Healthcare",
            "education": "Education",
            "school": "Education",
            "other": "Other",
        }
        for key, val in mapping.items():
            if key in qtext:
                return val
        return None

    rng = parse_range(q)
    dfc = df.copy()
    if "date" in dfc.columns:
        dfc["date"] = pd.to_datetime(dfc["date"]).dt.date

    if rng is not None:
        start, end, label = rng
        dfc = dfc[(dfc["date"] >= start) & (dfc["date"] <= end)]
    else:
        label = "the selected period"

    if dfc.empty:
        return "No expenses found for that period."

    total = dfc["amount"].sum()
    count = len(dfc)

    if "compare" in q or "comparison" in q or "increase" in q or "decrease" in q:
        if "last month" in q or "previous month" in q:
            curr_start, curr_end = month_bounds(today)
            last_end = curr_start - timedelta(days=1)
            last_start, last_end = month_bounds(last_end)
            curr_total = df[(pd.to_datetime(df["date"]).dt.date >= curr_start) & (pd.to_datetime(df["date"]).dt.date <= curr_end)]["amount"].sum()
            last_total = df[(pd.to_datetime(df["date"]).dt.date >= last_start) & (pd.to_datetime(df["date"]).dt.date <= last_end)]["amount"].sum()
            if last_total == 0:
                return "There were no expenses last month to compare with."
            change_pct = ((curr_total - last_total) / last_total) * 100
            trend = "higher" if change_pct >= 0 else "lower"
            return f"This month is {abs(change_pct):.0f}% {trend} than last month."

    cat = detect_category(q)
    if cat and ("percent" in q or "percentage" in q):
        cat_total = dfc[dfc["category"] == cat]["amount"].sum()
        pct = (cat_total / total) * 100 if total else 0
        return f"{cat} is {pct:.0f}% of your spending in {label}."

    if cat:
        cat_total = dfc[dfc["category"] == cat]["amount"].sum()
        return f"You spent {cat_total:.2f} on {cat} in {label}."

    if "top 3" in q or "top three" in q:
        by_cat = dfc.groupby("category")["amount"].sum().sort_values(ascending=False).head(3)
        parts = [f"{k} ({v:.2f})" for k, v in by_cat.items()]
        return "Top categories: " + ", ".join(parts) + "."

    if "top" in q or "most" in q or "highest category" in q:
        by_cat = dfc.groupby("category")["amount"].sum().sort_values(ascending=False)
        return f"Your top category is {by_cat.index[0]} with {by_cat.iloc[0]:.2f}."

    if "lowest" in q or "least" in q:
        by_cat = dfc.groupby("category")["amount"].sum().sort_values()
        return f"Your lowest category is {by_cat.index[0]} with {by_cat.iloc[0]:.2f}."

    if "largest" in q or "biggest" in q or "highest" in q:
        row = dfc.sort_values("amount", ascending=False).iloc[0]
        return f"Your largest expense was {row['amount']:.2f} on {row['category']} on {row['date']}."

    if "smallest" in q or "lowest" in q:
        row = dfc.sort_values("amount", ascending=True).iloc[0]
        return f"Your smallest expense was {row['amount']:.2f} on {row['category']} on {row['date']}."

    if "average transaction" in q or "avg transaction" in q:
        return f"Your average transaction size is {total / max(count, 1):.2f}."

    if "average daily" in q or "per day" in q:
        days = max((dfc["date"].max() - dfc["date"].min()).days + 1, 1)
        return f"Your average daily spending is {total / days:.2f}."

    if "average weekly" in q:
        days = max((dfc["date"].max() - dfc["date"].min()).days + 1, 1)
        weeks = max(days / 7, 1)
        return f"Your average weekly spending is {total / weeks:.2f}."

    if "average monthly" in q:
        return f"Your average monthly spending in {label} is {total:.2f}."

    if "weekend" in q or "weekday" in q:
        weekend = dfc[pd.to_datetime(dfc["date"]).dt.weekday >= 5]["amount"].sum()
        weekday = dfc[pd.to_datetime(dfc["date"]).dt.weekday < 5]["amount"].sum()
        if "percent" in q or "percentage" in q:
            pct = (weekend / (weekend + weekday)) * 100 if (weekend + weekday) else 0
            return f"About {pct:.0f}% of your spending happened on weekends."
        return f"Weekend spend is {weekend:.2f}, weekday spend is {weekday:.2f}."

    if "how many" in q or "count" in q or "transactions" in q:
        return f"You logged {count} expenses in {label}."

    if "when" in q and "most" in q:
        daily = dfc.groupby("date")["amount"].sum().sort_values(ascending=False)
        peak_day = daily.index[0]
        return f"You spent the most on {peak_day} with {daily.iloc[0]:.2f}."

    if "trend" in q:
        df_sorted = dfc.sort_values("date")
        if len(df_sorted) >= 14:
            first = df_sorted.head(7)["amount"].sum()
            last = df_sorted.tail(7)["amount"].sum()
            if first > 0:
                change = ((last - first) / first) * 100
                trend = "increasing" if change > 0 else "decreasing"
                return f"Your spending trend is {trend} by {abs(change):.1f}% over the last two weeks."
        return "Your spending is fairly steady recently."

    if "summary" in q or "insight" in q:
        by_cat = dfc.groupby("category")["amount"].sum().sort_values(ascending=False)
        top_cat = by_cat.index[0]
        avg_txn = total / max(count, 1)
        return (
            f"Summary for {label}: total {total:.2f} across {count} transactions. "
            f"Top category is {top_cat}. Average transaction is {avg_txn:.2f}."
        )

    if "recent" in q or "last" in q:
        m = re.search(r"last\s+(\d+)", q)
        count = 5
        if m:
            count = max(1, min(int(m.group(1)), 20))
        rows = dfc.sort_values("date", ascending=False).head(count)
        parts = [f"{r['date']} {r['category']} {r['amount']:.2f}" for _, r in rows.iterrows()]
        return "Recent transactions: " + "; ".join(parts) + "."

    if "total" in q or "how much" in q or "expenses" in q or "spend" in q:
        return f"Your total spending in {label} is {total:.2f}."

    return (
        "I can answer totals, category breakdowns, trends, comparisons, and recent transactions. "
        "Try asking about a category, a month, or a date range."
    )
