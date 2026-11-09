#!/usr/bin/env python3
"""Compare EDUP hotplug with a temporary parent-hub runtime-PM hold.

Run interactively with sudo. Changes only power/control on Genesys 05e3:0610
hubs, and restores the previous value in finally. No resets, unbinds, firmware
calls, persistent rules, network changes, or system sleep are performed.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import signal
import subprocess
import time

USB = Path('/sys/bus/usb/devices')
BASE = Path(__file__).resolve().parent


def read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return None


def hubs():
    return [p for p in USB.iterdir()
            if read(p / 'idVendor') == '05e3'
            and read(p / 'idProduct') == '0610']


def nic_present(hub):
    return any(read(p / 'idVendor') == '0bda'
               and read(p / 'idProduct') == '8153'
               for p in USB.glob(hub.name + '.*'))


def snapshot():
    result = {}
    for p in USB.iterdir():
        if read(p / 'idVendor') not in ('05e3', '0bda', '1d6b'):
            continue
        result[p.name] = {a: read(p / a) for a in (
            'idVendor', 'idProduct', 'devnum', 'product', 'speed', 'quirks',
            'power/control', 'power/runtime_status', 'power/autosuspend_delay_ms')}
        result[p.name]['ports'] = {
            port.name: read(port / 'state') for port in p.glob('*/*-port*')}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', action='store_true',
                        help='Test the current failed state without unplugging; use while Ethernet is missing.')
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Administrator access is needed for the temporary sysfs write; run with sudo.')
    if not hubs():
        parser.error('Plug in the EDUP adapter first; no Genesys 05e3:0610 hub is present.')
    stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
    out = BASE / ('usb-test-' + stamp)
    out.mkdir(mode=0o700)
    started = datetime.datetime.now().astimezone().isoformat(timespec='seconds')
    journal_since = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log = {'started': started, 'before': snapshot(), 'changes': []}
    changed = []

    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        if not args.current:
            input('Unplug the EDUP adapter and any power attached to it. Wait 10 seconds, '
                  'reconnect it to the SAME USB-C port, then press Enter here. ')
            time.sleep(5)
        current = hubs()
        log['current_state' if args.current else 'after_replug'] = snapshot()
        if not current:
            log['result'] = 'No hub after reconnect; hub runtime-PM test unavailable.'
        elif any(nic_present(p) for p in current):
            log['result'] = ('Ethernet chip is already present; no missing-device fault to test. No settings changed.'
                             if args.current else
                             'Ethernet chip appeared after replug; failure did not reproduce. No settings changed.')
        else:
            print('Hub returned without Ethernet. Keeping only this hub awake for 15 seconds.', flush=True)
            for p in current:
                old = read(p / 'power/control')
                devnum = read(p / 'devnum')
                if old not in ('auto', 'on') or devnum is None:
                    raise RuntimeError('Cannot read hub power state; refusing to change it.')
                # Record the rollback before the write so signals/errors still restore it.
                changed.append((p, devnum, old))
                (p / 'power/control').write_text('on\n')
                log['changes'].append({'hub': p.name, 'devnum': devnum, 'old': old, 'new': 'on'})
            recovered = False
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                if any(nic_present(p) for p in current):
                    recovered = True
                    break
                time.sleep(0.2)
            log['held_awake'] = snapshot()
            log['result'] = ('Ethernet chip appeared while hub was held awake.' if recovered else
                             'Ethernet chip still absent while hub was held awake; this did not recover it.')
        print(log['result'], flush=True)
    except (KeyboardInterrupt, EOFError):
        log['result'] = 'Interrupted; restoring recorded hub power settings.'
        print(log['result'], flush=True)
    except Exception as exc:
        log['error'] = repr(exc)
        raise
    finally:
        for p, devnum, old in reversed(changed):
            try:
                if read(p / 'devnum') == devnum and read(p / 'idVendor') == '05e3' and read(p / 'idProduct') == '0610':
                    (p / 'power/control').write_text(old + '\n')
                    log['changes'].append({'hub': p.name, 'restored': old})
            except OSError as exc:
                log['changes'].append({'hub': p.name, 'restore_error': str(exc)})
                print('RESTORE FAILED:', p / 'power/control', 'expected:', old, exc, flush=True)
        log['after_restore'] = snapshot()
        (out / 'result.json').write_text(json.dumps(log, indent=2) + '\n')
        for name, cmd in {
            'kernel.log': ['journalctl', '-k', '-b', '--no-pager', '--since', journal_since],
            'usb-tree.txt': ['lsusb', '-t'],
        }.items():
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                (out / name).write_text(r.stdout + r.stderr)
            except (OSError, subprocess.TimeoutExpired) as exc:
                (out / name).write_text(str(exc))
        uid = int(os.environ.get('SUDO_UID', '0'))
        gid = int(os.environ.get('SUDO_GID', '0'))
        for p in out.iterdir():
            os.chown(p, uid, gid)
        os.chown(out, uid, gid)
        print('Results saved to:', out, flush=True)


if __name__ == '__main__':
    main()
