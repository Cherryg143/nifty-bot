# nifty_core.py
"""Core analysis and notification module for Nifty intraday signals.
Designed to run as a one-shot job triggered by GitHub Actions every 5 minutes.
Configure notification channels using environment variables (GitHub Secrets recommended).
"""
import os
import json
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import yfinance as yf
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Optional integrations
try:
    from twilio.rest import Client as TwilioClient
except Exception:
    TwilioClient = None
try:
    from telegram import Bot as TelegramBot
except Exception:
    TelegramBot = None

# --- Indicators ---
def ema(series, n):
    return series.ewm(span=n, adjust=False).mean()

def rsi(series, n=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=n-1, adjust=False).mean()
    ma_down = down.ewm(com=n-1, adjust=False).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

def atr(df, n=14):
    high = df['High']
    low = df['Low']
    close = df['Close']
    tr = pd.concat([
        (high - low).abs(),
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    return tr.ewm(span=n, adjust=False).mean()

def vwap(df):
    typical = (df['High'] + df['Low'] + df['Close']) / 3
    tpv = typical * df['Volume']
    return tpv.cumsum() / df['Volume'].cumsum()

# --- Configuration from environment (use GitHub Secrets to set these) ---
CONFIG = {
    'SYMBOL_UNDERLYING': os.getenv('SYMBOL_UNDERLYING', '^NSEI'),
    'CAPITAL': float(os.getenv('CAPITAL', '15000')),
    'RISK_PER_TRADE': float(os.getenv('RISK_PER_TRADE', '250')),
    'YFINANCE_INTERVAL': os.getenv('YFINANCE_INTERVAL','5m'),
    'YFINANCE_PERIOD': os.getenv('YFINANCE_PERIOD','7d'),
}

NOTIFY = {
    'EMAIL_ENABLED': os.getenv('EMAIL_ENABLED','false').lower()=='true',
    'EMAIL_SMTP': os.getenv('EMAIL_SMTP','smtp.gmail.com'),
    'EMAIL_PORT': int(os.getenv('EMAIL_PORT',587)),
    'EMAIL_USER': os.getenv('EMAIL_USER',''),
    'EMAIL_PASS': os.getenv('EMAIL_PASS',''),
    'EMAIL_TO': os.getenv('EMAIL_TO',''),

    'TELEGRAM_ENABLED': os.getenv('TELEGRAM_ENABLED','false').lower()=='true',
    'TELEGRAM_TOKEN': os.getenv('TELEGRAM_TOKEN',''),
    'TELEGRAM_CHAT_ID': os.getenv('TELEGRAM_CHAT_ID',''),

    'TWILIO_ENABLED': os.getenv('TWILIO_ENABLED','false').lower()=='true',
    'TWILIO_SID': os.getenv('TWILIO_SID',''),
    'TWILIO_TOKEN': os.getenv('TWILIO_TOKEN',''),
    'TWILIO_WHATSAPP_FROM': os.getenv('TWILIO_WHATSAPP_FROM','whatsapp:+1415XXXX'),
    'TWILIO_TO': os.getenv('TWILIO_TO','whatsapp:+91XXXXXXXXXX'),
}

# --- Notification helpers ---
def send_email(subject, body):
    if not NOTIFY['EMAIL_ENABLED']:
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = NOTIFY['EMAIL_USER']
        msg['To'] = NOTIFY['EMAIL_TO']
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(NOTIFY['EMAIL_SMTP'], NOTIFY['EMAIL_PORT'])
        server.starttls()
        server.login(NOTIFY['EMAIL_USER'], NOTIFY['EMAIL_PASS'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print('Email send error:', e)
        return False

def send_telegram(message):
    if not NOTIFY['TELEGRAM_ENABLED'] or TelegramBot is None:
        return False
    try:
        bot = TelegramBot(NOTIFY['TELEGRAM_TOKEN'])
        bot.send_message(chat_id=NOTIFY['TELEGRAM_CHAT_ID'], text=message)
        return True
    except Exception as e:
        print('Telegram send error:', e)
        return False

def send_whatsapp_twilio(message):
    if not NOTIFY['TWILIO_ENABLED'] or TwilioClient is None:
        return False
    try:
        client = TwilioClient(NOTIFY['TWILIO_SID'], NOTIFY['TWILIO_TOKEN'])
        client.messages.create(body=message, from_=NOTIFY['TWILIO_WHATSAPP_FROM'], to=NOTIFY['TWILIO_TO'])
        return True
    except Exception as e:
        print('Twilio send error:', e)
        return False

def notify_all(subject, body):
    # Print for GitHub Actions logs and attempt notifications
    print("\n===== SIGNAL =====")
    print(subject)
    print(body)
    print("==================\n")
    send_email(subject, body)
    send_telegram(subject + "\n\n" + body)
    send_whatsapp_twilio(subject + "\n\n" + body)

# --- Market data functions ---
def fetch_intraday(symbol, interval='5m', period='7d'):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(interval=interval, period=period, actions=False)
        if df.empty:
            raise ValueError('Empty data from yfinance')
        df = df.reset_index()
        df['Datetime'] = pd.to_datetime(df['Datetime'])
        df = df[['Datetime','Open','High','Low','Close','Volume']]
        return df
    except Exception as e:
        print('fetch_intraday error', e)
        return pd.DataFrame()

def fetch_previous_day_levels(symbol):
    df = fetch_intraday(symbol, interval='1d', period='5d')
    if df.empty:
        return None
    last = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
    return {
        'prev_high': float(last['High']),
        'prev_low': float(last['Low']),
        'prev_close': float(last['Close']),
        'prev_open': float(last['Open']),
        'date': str(last['Datetime'].date())
    }

# --- Strategy: breakout-retest ---
def analyze_market_and_signal():
    symbol = CONFIG['SYMBOL_UNDERLYING']
    intraday = fetch_intraday(symbol, interval=CONFIG['YFINANCE_INTERVAL'], period=CONFIG['YFINANCE_PERIOD'])
    if intraday.empty:
        return None
    intraday.set_index('Datetime', inplace=True)
    intraday['EMA20'] = ema(intraday['Close'], 20)
    intraday['EMA50'] = ema(intraday['Close'], 50)
    intraday['RSI14'] = rsi(intraday['Close'], 14)
    intraday['ATR14'] = atr(intraday, 14)
    intraday['VWAP'] = vwap(intraday.reset_index()).values
    prev = fetch_previous_day_levels(symbol)
    if prev is None:
        return None
    prev_high = prev['prev_high']
    prev_low = prev['prev_low']
    latest = intraday.iloc[-1]
    mood = 'Neutral'
    if latest['Close'] > latest['EMA20'] and latest['RSI14'] > 55:
        mood = 'Bullish'
    elif latest['Close'] < latest['EMA20'] and latest['RSI14'] < 45:
        mood = 'Bearish'
    signals = []
    date_mask = intraday.index.date == intraday.index[-1].date()
    intraday_today = intraday[date_mask]
    if intraday_today.empty:
        return None
    broke_high_idx = intraday_today[intraday_today['High'] > prev_high]
    broke_low_idx = intraday_today[intraday_today['Low'] < prev_low]
    def find_breakout_retest(broke_df, side='bull'):
        if broke_df.empty:
            return None
        first_break_time = broke_df.index[0]
        retest_end = first_break_time + timedelta(minutes=60)
        retest_bars = intraday_today[(intraday_today.index > first_break_time) & (intraday_today.index <= retest_end)]
        if retest_bars.empty:
            return None
        level = prev_high if side=='bull' else prev_low
        tolerance = 0.0025 * level
        for idx, row in retest_bars.iterrows():
            close = row['Close']
            if abs(close - level) <= tolerance:
                body = row['Close'] - row['Open']
                if side == 'bull' and body > 0:
                    return {'entry_price_underlying': row['Close'], 'entry_bar_time': idx, 'level': level, 'side':'LONG'}
                if side == 'bear' and body < 0:
                    return {'entry_price_underlying': row['Close'], 'entry_bar_time': idx, 'level': level, 'side':'SHORT'}
        return None
    bull_setup = find_breakout_retest(broke_high_idx, 'bull')
    bear_setup = find_breakout_retest(broke_low_idx, 'bear')
    if bull_setup and not bear_setup:
        signals.append(bull_setup)
    if bear_setup and not bull_setup:
        signals.append(bear_setup)
    if bull_setup and bear_setup:
        signals = [bull_setup] if bull_setup['entry_bar_time'] < bear_setup['entry_bar_time'] else [bear_setup]
    def option_advice(signal):
        underlying_price = signal['entry_price_underlying']
        strike = int(round(underlying_price / 50.0) * 50)
        side = signal['side']
        option_type = 'CE' if side=='LONG' else 'PE'
        atr_val = latest['ATR14'] if 'ATR14' in latest else 10
        sl_points = max(10, int(atr_val * 0.6))
        tgt1 = int(sl_points * 1.2)
        tgt2 = int(sl_points * 2.0)
        return {
            'underlying': CONFIG['SYMBOL_UNDERLYING'],
            'side': side,
            'option_type': option_type,
            'suggested_strike': strike,
            'entry_underlying_price': round(underlying_price,2),
            'stoploss_points': sl_points,
            'targets_points': [tgt1, tgt2],
            'entry_time': str(signal['entry_bar_time'])
        }
    final_signals = [option_advice(s) for s in signals]
    result = {
        'timestamp': str(datetime.now()),
        'mood': mood,
        'prev_high': prev_high,
        'prev_low': prev_low,
        'latest_price': float(latest['Close']),
        'indicators': {
            'EMA20': float(latest['EMA20']),
            'EMA50': float(latest['EMA50']),
            'RSI14': float(latest['RSI14']),
            'ATR14': float(latest['ATR14']),
            'VWAP': float(latest['VWAP'])
        },
        'signals': final_signals
    }
    return result