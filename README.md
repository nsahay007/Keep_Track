# ExpenseTracker Revamp (Web)

A modern web-based expense tracker with smart analytics, voice assistant, OCR receipt scanning, and predictions.

## Features
- Dashboard with charts and insights
- Expense CRUD
- Receipt OCR (upload image)
- Voice entry (browser speech recognition)
- AI voice assistant (question answering)
- Predictions (trend + weekday seasonality)
- Budgets

## How to Run

```bash
cd "/Users/nishant/Downloads/ExpenseTracker-Revamp"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Notes
- Voice features require a browser with Web Speech API support (Chrome works best).
- OCR requires Tesseract installed and accessible on your system.
