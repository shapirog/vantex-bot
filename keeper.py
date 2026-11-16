"""
Vantex Keeper - makes sure every Vantex bot actually starts, because GitHub keeps skipping scheduled runs.
Places NO trades itself. It only starts the other workflows (the same as tapping "Run workflow").

Runs non-stop: each run lasts ~5.5 h (GitHub's 6-hour limit) and then starts the next Keeper run itself.
Every minute it checks (Eastern time):
  scan.yml                         weekdays 4:00 AM-8:00 PM: start a scan every 15 minutes
  trade / momentum / options       weekdays 9:00 AM-3:30 PM: if the bot is not running or waiting, start it
                                   (at most 6 starts per bot per day, so a broken bot can't loop forever)
  earlybird.yml                    Sunday 6 PM -> Friday 4 PM: if Early Bird is not running or waiting, start it
  lab8-forward / lab9-forward      weekdays after 4:47 / 5:17 PM: start once a day if it hasn't run yet
Every start is logged in the run output.
"""
import os, sys, time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

ET = ZoneInfo('America/New_York')
REPO = os.environ.get('GITHUB_REPOSITORY', 'shapirog/vantex-bot')
TOK = os.environ.get('GH_TOKEN')
if not TOK: sys.exit('GH_TOKEN missing')
API = f'https://api.github.com/repos/{REPO}/actions/workflows'
HDR = {'Authorization': f'Bearer {TOK}', 'Accept': 'application/vnd.github+json'}
MAX_RUN_S = 330 * 60
SCAN_EVERY_MIN = 15
MAX_STARTS = 6
BOTS = ('trade.yml', 'momentum.yml', 'options.yml')

def log(*a): print(datetime.now(ET).strftime('%a %H:%M:%S'), *a, flush=True)

def active_set():
    """workflow files with a run in progress or waiting, from 2 API calls (GitHub allows ~1,000 calls/hour);
    None if GitHub could not be reached (then nothing is started)"""
    out = set()
    for st in ('in_progress', 'queued'):
        try:
            r = requests.get(f'https://api.github.com/repos/{REPO}/actions/runs', headers=HDR, params=dict(status=st, per_page=50), timeout=20)
            if not r.ok: log('runs check failed', r.status_code); return None
            out |= {os.path.basename(x.get('path', '').split('@')[0]) for x in r.json().get('workflow_runs', [])}
        except Exception as e:
            log('runs check failed', e); return None
    return out

def ran_today(wf, day):
    try:
        r = requests.get(f'{API}/{wf}/runs', headers=HDR, params=dict(created=f'>={day.isoformat()}', per_page=5), timeout=20)
        return r.json().get('total_count', 0) if r.ok else None
    except Exception: return None

def start(wf, inputs=None):
    try:
        r = requests.post(f'{API}/{wf}/dispatches', headers=HDR, json={'ref': 'main', **({'inputs': inputs} if inputs else {})}, timeout=20)
        log('started', wf, r.status_code, r.text[:120]); return r.status_code == 204
    except Exception as e:
        log('start failed', wf, e); return False

def main():
    t0 = time.time(); starts = {}; last_scan = 0.0; day = None
    while time.time() - t0 < MAX_RUN_S:
        now = datetime.now(ET); m = now.hour * 60 + now.minute; wd = now.weekday(); weekday = wd < 5
        if now.date() != day: day = now.date(); starts = {}
        act = active_set()
        if act is None: time.sleep(60); continue
        active = lambda wf: wf in act
        # market scanner every 15 minutes, 4 AM - 8 PM on weekdays
        if weekday and 240 <= m < 1200 and time.time() - last_scan >= SCAN_EVERY_MIN * 60 - 30:
            if not active('scan.yml'): start('scan.yml')
            last_scan = time.time()
        # trading bots must be running (or waiting) from 9:00 AM until 3:30 PM
        if weekday and 540 <= m < 930:
            for wf in BOTS:
                if starts.get(wf, 0) >= MAX_STARTS: continue
                if not active(wf):
                    if start(wf): starts[wf] = starts.get(wf, 0) + 1
        # Early Bird runs Sunday 6 PM -> Friday 4 PM
        eb_window = (wd == 6 and m >= 1080) or wd in (0, 1, 2, 3) or (wd == 4 and m < 960)
        if eb_window and m % 5 == 0 and not active('earlybird.yml') and starts.get('earlybird.yml', 0) < MAX_STARTS * 4:
            if start('earlybird.yml', {'force': '0'}): starts['earlybird.yml'] = starts.get('earlybird.yml', 0) + 1
        # daily forward tests after the close
        for wf, at in (('lab8-forward.yml', 16 * 60 + 47), ('lab9-forward.yml', 17 * 60 + 17)):
            if weekday and at <= m < 23 * 60 and not starts.get(wf):
                n = ran_today(wf, now.date())
                if n == 0 and not active(wf) and start(wf): starts[wf] = 1
                elif n: starts[wf] = 1
        time.sleep(max(5, 60 - (time.time() % 60)))
    start('keeper.yml')                                                  # hand over to a fresh Keeper run

if __name__ == '__main__':
    main()
