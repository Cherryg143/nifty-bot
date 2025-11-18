# run_once.py
# Simple wrapper that runs analysis and prints JSON result (and triggers notifications)
import json
from nifty_core import analyze_market_and_signal, notify_all
def main():
    report = analyze_market_and_signal()
    if report is None:
        print(json.dumps({'status':'no-data'}))
        return
    # If there are signals, notify
    if report.get('signals'):
        for s in report['signals']:
            subj = f"TRADE SIGNAL: {s['side']} {s['underlying']} {s['option_type']} Strike {s['suggested_strike']}"
            msg = json.dumps(s, indent=2)
            notify_all(subj, msg)
    else:
        notify_all('NO TRADE SIGNAL - Market Summary', json.dumps(report, indent=2))
    print(json.dumps({'status':'ok','signals':report.get('signals',[])}))
if __name__ == '__main__':
    main()