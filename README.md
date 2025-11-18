# Nifty Intraday Bot — GitHub Actions (FREE)

This repo runs a one-shot Nifty intraday analyzer every 5 minutes using **GitHub Actions** (no cloud billing required).

**What it does**
- Fetches intraday data (yfinance)
- Computes EMA/RSI/ATR/VWAP
- Detects breakout-retest setups using previous day's high/low
- Recommends an ATM strike, stoploss (points), and two targets
- Sends notifications via Telegram, Email (SMTP), or Twilio WhatsApp (optional)

**How to use**
1. Create a GitHub repository (public or private).
2. Upload these files at repo root.
3. In the GitHub repo, go to **Settings → Secrets and variables → Actions** and add the following secrets you need:
   - `SYMBOL_UNDERLYING` (default: `^NSEI`)
   - `EMAIL_ENABLED` (`true` or `false`)
   - `EMAIL_SMTP`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASS`, `EMAIL_TO` (if using email)
   - `TELEGRAM_ENABLED`, `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID` (if using Telegram)
   - `TWILIO_ENABLED`, `TWILIO_SID`, `TWILIO_TOKEN`, `TWILIO_WHATSAPP_FROM`, `TWILIO_TO` (if using Twilio)
4. Commit and push. The Actions workflow will run every 5 minutes (cron).

**Notes & Limitations**
- GitHub Actions is great for scheduling jobs; free tier exists for public repos and limited credits for private repos. If your account hits usage limits, consider running hourly instead.
- yfinance intraday data is fine for signals but not guaranteed low-latency — for live execution use a broker API (Zerodha Kite, Upstox, etc.).
- Test with `EMAIL_ENABLED=false` first to avoid spam.

**Support**
If you want, I can help you set this up step-by-step on your GitHub account.