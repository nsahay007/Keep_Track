"""
Analytics and prediction functions
"""

from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.linear_model import LinearRegression


def _prepare_daily_series(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df['date'] = pd.to_datetime(df['date']).dt.date
    daily = df.groupby('date')['amount'].sum().reset_index()
    if daily.empty:
        return daily
    full_range = pd.date_range(daily['date'].min(), daily['date'].max(), freq='D')
    daily = daily.set_index('date').reindex(full_range, fill_value=0).rename_axis('date').reset_index()
    daily['date'] = pd.to_datetime(daily['date']).dt.date
    return daily


def predict_future_expenses(df: pd.DataFrame, days_ahead: int = 30):
    """Predict future expenses using trend + weekday seasonality."""
    if df.empty or len(df) < 14:
        return None, "Need at least 14 days of data for predictions"

    daily = _prepare_daily_series(df)
    if len(daily) < 14:
        return None, "Need more data points for accurate predictions"

    daily['day_index'] = (pd.to_datetime(daily['date']) - pd.to_datetime(daily['date']).min()).dt.days
    daily['weekday'] = pd.to_datetime(daily['date']).dt.weekday

    X = pd.get_dummies(daily[['day_index', 'weekday']], columns=['weekday'], drop_first=True)
    y = daily['amount'].values

    model = LinearRegression()
    model.fit(X, y)

    last_day = daily['day_index'].max()
    future_dates = [daily['date'].max() + timedelta(days=i) for i in range(1, days_ahead + 1)]
    future_index = np.array([last_day + i for i in range(1, days_ahead + 1)])
    future_weekday = [pd.to_datetime(d).weekday() for d in future_dates]

    X_future = pd.get_dummies(pd.DataFrame({
        'day_index': future_index,
        'weekday': future_weekday
    }), columns=['weekday'], drop_first=True)

    # Align columns
    for col in X.columns:
        if col not in X_future.columns:
            X_future[col] = 0
    X_future = X_future[X.columns]

    predictions = model.predict(X_future)
    predictions = np.maximum(predictions, 0)

    prediction_df = pd.DataFrame({
        'date': future_dates,
        'predicted_amount': predictions
    })

    total_predicted = predictions.sum()
    avg_daily = predictions.mean()

    spoken_text = (
        f"Based on your recent patterns, you may spend around {total_predicted:.2f} dollars in the next {days_ahead} days. "
        f"That is roughly {avg_daily:.2f} per day."
    )

    return prediction_df, spoken_text


def generate_insights(df: pd.DataFrame):
    """Generate text insights from expense data"""
    insights = []

    if df.empty:
        return ["No expenses recorded yet. Start tracking to get insights!"]

    total = df['amount'].sum()
    insights.append(f"💰 **Total Spending**: ${total:,.2f}")

    avg_transaction = df['amount'].mean()
    insights.append(f"📊 **Average Transaction**: ${avg_transaction:.2f}")

    category_spending = df.groupby('category')['amount'].sum().sort_values(ascending=False)
    if not category_spending.empty:
        top_category = category_spending.index[0]
        top_amount = category_spending.values[0]
        percentage = (top_amount / total) * 100
        insights.append(f"🏆 **Top Category**: {top_category} (${top_amount:,.2f} - {percentage:.1f}%)")

    if len(df) >= 14:
        df_sorted = df.sort_values('date')
        first_week = df_sorted.head(7)['amount'].sum()
        last_week = df_sorted.tail(7)['amount'].sum()
        if first_week > 0:
            change = ((last_week - first_week) / first_week) * 100
            trend = "📈 increasing" if change > 0 else "📉 decreasing"
            insights.append(f"**Spending Trend**: {trend} by {abs(change):.1f}%")

    return insights


def generate_report(df: pd.DataFrame):
    """Generate comprehensive text report"""
    if df.empty:
        return "No data available for report generation."

    report = "# 📊 EXPENSE REPORT\n\n"
    report += f"**Report Generated**: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n\n"

    report += "## Summary\n"
    report += f"- **Total Transactions**: {len(df)}\n"
    report += f"- **Total Amount**: ${df['amount'].sum():,.2f}\n"
    report += f"- **Average Transaction**: ${df['amount'].mean():.2f}\n"
    report += f"- **Largest Transaction**: ${df['amount'].max():.2f}\n"
    report += f"- **Smallest Transaction**: ${df['amount'].min():.2f}\n\n"

    report += "## Category Breakdown\n"
    category_stats = df.groupby('category')['amount'].agg(['sum', 'count', 'mean'])
    for category, row in category_stats.iterrows():
        report += f"- **{category}**: ${row['sum']:,.2f} ({int(row['count'])} transactions, avg ${row['mean']:.2f})\n"

    report += "\n## Monthly Trend\n"
    df['month'] = pd.to_datetime(df['date']).dt.to_period('M')
    monthly = df.groupby('month')['amount'].sum()
    for month, amount in monthly.items():
        report += f"- **{month}**: ${amount:,.2f}\n"

    return report


def generate_spoken_insights(df: pd.DataFrame):
    """Generate insights optimized for voice"""
    insights = []

    if df.empty:
        return ["No expenses recorded yet."]

    total = df['amount'].sum()

    category_spending = df.groupby('category')['amount'].sum().sort_values(ascending=False)
    if not category_spending.empty:
        top_category = category_spending.index[0]
        top_amount = category_spending.values[0]
        percentage = (top_amount / total) * 100
        insights.append(
            f"Your highest spending category is {top_category} with {top_amount:.2f} dollars, "
            f"representing {percentage:.1f} percent of total expenses."
        )

    current_month = datetime.now().month
    month_expenses = df[pd.to_datetime(df['date']).dt.month == current_month]
    if not month_expenses.empty:
        month_total = month_expenses['amount'].sum()
        count = len(month_expenses)
        insights.append(f"This month you've spent {month_total:.2f} dollars across {count} transactions.")

    return insights
