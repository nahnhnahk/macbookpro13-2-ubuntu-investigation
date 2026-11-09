#!/usr/bin/env python3
"""Verify this test kernel; optionally request one explicit timed S3 cycle.

Default mode is read-only. Only --suspend-seconds requests suspend, through
systemd and the existing guarded T1 integration. No raw ACPI calls are made.
"""
import argparse
import datetime
import json
import os
from pathlib import Path
import runpy
import subprocess
import tempfile
import time

RELEASE = '7.0.14-mbp132-tb1'
BASE = Path(__file__).resolve().parent
CONTROLLERS = ('0000:06:00.0', '0000:7c:00.0')


def command(args, timeout=15):
    r = subprocess.run(args, text=True, capture_output=True, timeout=timeout)
    return {'returncode': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr}


def suspend_stats():
    base = Path('/sys/power/suspend_stats')
    return {key: int((base / key).read_text()) for key in ('success', 'fail')}


def sleep_clock_sample():
    return {'monotonic': time.clock_gettime(time.CLOCK_MONOTONIC),
            'boottime': time.clock_gettime(time.CLOCK_BOOTTIME)}


def sleep_timing(before, after, requested):
    # BOOTTIME includes suspend; MONOTONIC excludes it. Active preparation
    # and the 15-second post-resume recovery therefore cancel out.
    elapsed = after['boottime'] - before['boottime']
    awake = after['monotonic'] - before['monotonic']
    suspended = max(0.0, elapsed - awake)
    # The RTC alarm starts before the systemd and device suspend phases.
    minimum = max(1, requested - 15)
    return {'schema': 1, 'requested_alarm_seconds': requested,
            'total_elapsed_seconds': round(elapsed, 3),
            'awake_seconds': round(awake, 3),
            'system_suspended_seconds': round(suspended, 3),
            'minimum_suspended_seconds': minimum,
            'duration_met': suspended >= minimum}


def wake_snapshot():
    data = {'gpe_counts': {}, 'files': {}}
    for path in Path('/sys/firmware/acpi/interrupts').glob('gpe*'):
        try:
            value = path.read_text()
            data['gpe_counts'][path.name] = int(value.split()[0])
        except (OSError, ValueError, IndexError):
            pass
    for name in ['/sys/kernel/debug/wakeup_sources', '/sys/power/pm_wakeup_irq',
                 '/proc/acpi/wakeup', '/proc/interrupts', '/proc/driver/rtc']:
        try:
            data['files'][name] = Path(name).read_text()
        except OSError as error:
            data['files'][name] = str(error)
    return data


def qualified_cycle(data, release):
    """Do not promote old reports that never measured suspend duration."""
    timing = data.get('timing', {})
    requested = data.get('suspend_requested')
    return bool(data.get('passed') and isinstance(requested, (int, float))
                and requested >= 30 and data.get('after', {}).get('kernel') == release
                and data.get('checks', {}).get('sleep_duration_met') is True
                and timing.get('schema') == 1 and timing.get('duration_met') is True
                and timing.get('system_suspended_seconds', -1) >= max(1, requested - 15))


def qualified_lid_comparison(before, after, verification, kernel_log, service_log, release):
    """Validate a manual lid cycle from raw clock/counter snapshots and logs."""
    try:
        if (not before.get('boot_id') or before['boot_id'] != after['boot_id']
                or after['suspend_stats']['success'] != before['suspend_stats']['success'] + 1
                or after['suspend_stats']['fail'] != before['suspend_stats']['fail']
                or verification.get('passed') is not True
                or verification.get('suspend_requested') is not None
                or verification['before']['kernel'] != release
                or verification['before']['errors'] != []):
            return None
        if (after['clocks']['boottime'] < before['clocks']['boottime']
                or after['clocks']['monotonic'] < before['clocks']['monotonic']):
            return None
        timing = sleep_timing(before['clocks'], after['clocks'], 30)
        if (timing['system_suspended_seconds'] < 30
                or kernel_log.count('PM: suspend entry (deep)') != 1
                or kernel_log.count('PM: suspend exit') != 1
                or 'kernel: WARNING:' in kernel_log
                or service_log.count('firmware sleep acknowledged') != 1
                or service_log.count('firmware wake acknowledged') != 1
                or service_log.count('Lid closed.') != 1
                or service_log.count('Lid opened.') != 1):
            return None
        # This is a passive measurement, with no requested RTC alarm.
        timing.pop('requested_alarm_seconds')
        timing.update(minimum_suspended_seconds=30, duration_met=True)
        return {'trigger': 'manual-lid', 'timing': timing,
                'boot_id': before['boot_id'],
                'success_index': after['suspend_stats']['success']}
    except (KeyError, TypeError, ValueError):
        return None


def wait_for_suspend(before, read_stats=suspend_stats, run=command,
                     pause=time.sleep, clock=time.monotonic):
    # systemctl suspend can return after queueing the job. Keep the RTC alarm
    # armed until the kernel has resumed and the T1 ExecStartPost has finished.
    limit = clock() + 120
    current = read_stats()
    while current == before:
        state = run(['systemctl', 'show', '-p', 'ActiveState', '--value', 'systemd-suspend.service'])['stdout'].strip()
        if state == 'failed':
            raise RuntimeError('The suspend service failed before a kernel cycle completed')
        if clock() >= limit:
            raise RuntimeError('No kernel suspend completion was recorded')
        pause(1)
        current = read_stats()
    if current['success'] != before['success'] + 1 or current['fail'] != before['fail']:
        raise RuntimeError('The kernel did not record exactly one successful suspend cycle')
    limit = clock() + 60
    while True:
        state = run(['systemctl', 'show', '-p', 'ActiveState', '--value', 'systemd-suspend.service'])['stdout'].strip()
        if state == 'failed':
            raise RuntimeError('The suspend service or its recovery phase failed')
        if state not in ('activating', 'active', 'deactivating'):
            return current
        if clock() >= limit:
            raise RuntimeError('The post-resume recovery service has not completed')
        pause(1)


def collect(iface):
    data = {'time': datetime.datetime.now().astimezone().isoformat(),
            'kernel': os.uname().release, 'errors': [], 'pci': {}}
    if data['kernel'] != RELEASE:
        data['errors'].append('Expected test kernel ' + RELEASE)
        return data
    try:
        helper = runpy.run_path('/usr/local/sbin/mbp-t1-s3-handshake', run_name='mbp_t1_installed')
        helper['validate']()
        data['t1_guard'] = 'passed'
        data['planned_sleep_mode'] = helper['planned_mode']()
        if data['planned_sleep_mode'] != 'deep':
            data['errors'].append('Effective sleep configuration is not deep')
    except Exception as error:
        data['errors'].append('T1 recovery guard: ' + str(error))
    for name in CONTROLLERS:
        p = Path('/sys/bus/pci/devices') / name
        info = {'present': p.exists()}
        if p.exists():
            for field in ['vendor', 'device', 'power_state', 'power/control', 'power/runtime_status']:
                try:
                    info[field] = (p / field).read_text().strip()
                except OSError as error:
                    info[field] = str(error)
            try:
                with (p / 'config').open('rb') as f:
                    header = f.read(4)
                info['config_id'] = header.hex()
                if header != bytes.fromhex('8680d415'):
                    data['errors'].append(name + ' has inaccessible or unexpected PCI config')
            except OSError as error:
                data['errors'].append(name + ': ' + str(error))
        else:
            data['errors'].append('Missing USB 3 controller ' + name)
        data['pci'][name] = info
    net = Path('/sys/class/net') / iface
    if not net.exists():
        data['errors'].append('Ethernet interface is absent; plug in the EDUP adapter')
    else:
        try:
            data['ethernet_carrier'] = (net / 'carrier').read_text().strip()
            data['ethernet_speed_mbps'] = (net / 'speed').read_text().strip()
            usb = (net / 'device').resolve(strict=True).parent
            data['usb_speed_mbps'] = (usb / 'speed').read_text().strip()
            if data['ethernet_carrier'] != '1' or float(data['usb_speed_mbps']) < 5000:
                data['errors'].append('Ethernet is not linked over SuperSpeed USB')
        except (OSError, ValueError) as error:
            data['errors'].append('Ethernet/USB link: ' + str(error))
    data['route'] = command(['ip', '-4', 'route', 'get', '1.1.1.1'])
    if ('dev ' + iface + ' ') not in data['route']['stdout']:
        data['errors'].append('Default IPv4 traffic is not using Ethernet')
    if not data['errors']:
        data['https'] = command(['curl', '--fail', '--head', '--silent', '--show-error',
                                 '--interface', iface, '--connect-timeout', '5',
                                 '--max-time', '10', 'https://example.com'])
        if data['https']['returncode']:
            data['errors'].append('Ethernet-bound HTTPS failed')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface', default='enx020000000001')
    parser.add_argument('--suspend-seconds', type=int)
    args = parser.parse_args()
    if os.geteuid() != 0:
        parser.error('Run with sudo; PCI state and the installed recovery guard need administrator read access.')
    if args.suspend_seconds is not None and not 30 <= args.suspend_seconds <= 3600:
        parser.error('Suspend duration must be 30–3600 seconds.')
    out = Path(tempfile.mkdtemp(prefix='validation-', dir=BASE))
    report = {'suspend_requested': args.suspend_seconds,
              'boot_id': Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
    try:
        before = collect(args.interface)
        report['before'] = before
        if before['errors']:
            raise RuntimeError('; '.join(before['errors']))
        if args.suspend_seconds is not None:
            service = command(['systemctl', 'show', '-p', 'ActiveState', '--value',
                               'systemd-suspend.service'])
            if service['returncode'] or service['stdout'].strip() in ('activating', 'active', 'deactivating'):
                raise RuntimeError('Cannot start test while a suspend operation is in progress')
            if Path('/run/mbp-t1-s3-handshake/pending.json').exists():
                raise RuntimeError('A T1 firmware wake is already pending')
            if '[none]' not in Path('/sys/power/pm_test').read_text():
                raise RuntimeError('pm_test is enabled; refusing a misleading suspend test')
            # Do not suspend with block devices below either Thunderbolt tree.
            for block in Path('/sys/class/block').iterdir():
                if any(part in str(block.resolve()) for part in ['0000:03:00.0', '0000:79:00.0']):
                    raise RuntimeError('Thunderbolt storage is attached: ' + block.name)
            alarm = Path('/sys/class/rtc/rtc0/wakealarm')
            if alarm.read_text().strip() not in ('', '0'):
                raise RuntimeError('An RTC alarm is already scheduled; leaving it untouched')
            debug = Path('/sys/kernel/debug/dynamic_debug/control')
            matching = [line for line in debug.read_text().splitlines()
                        if ']tb_acpi_force_power ' in line]
            if not matching:
                raise RuntimeError('The patched Thunderbolt function is not in dynamic debug metadata')
            already_enabled = all('p' in line.split('=', 1)[1].split(' ', 1)[0] for line in matching)
            since = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            wake_before = wake_snapshot()
            (out / 'wake-before.json').write_text(json.dumps(wake_before, indent=2) + '\n')
            deadline = int(time.time()) + args.suspend_seconds
            counters = suspend_stats()
            report['suspend_stats_before'] = counters
            try:
                debug.write_text('func tb_acpi_force_power +p\n')
                alarm.write_text(str(deadline))
                report['rtc_alarm_deadline_epoch'] = deadline
                clocks_before = sleep_clock_sample()
                print('Requesting one deep-sleep cycle through systemd. Leave the lid open.', flush=True)
                r = command(['systemctl', 'suspend'], timeout=args.suspend_seconds + 180)
                report['systemctl'] = r
                if r['returncode']:
                    raise RuntimeError('systemd suspend failed: ' + r['stderr'])
                report['suspend_stats_after'] = wait_for_suspend(counters)
                report['timing'] = sleep_timing(clocks_before, sleep_clock_sample(), args.suspend_seconds)
                report['rtc_alarm_after_resume'] = alarm.read_text().strip()
            finally:
                wake_after = wake_snapshot()
                (out / 'wake-after.json').write_text(json.dumps(wake_after, indent=2) + '\n')
                report['gpe_count_changes'] = {
                    name: value - wake_before['gpe_counts'][name]
                    for name, value in wake_after['gpe_counts'].items()
                    if name in wake_before['gpe_counts'] and value != wake_before['gpe_counts'][name]}
                if alarm.read_text().strip() in ('', '0', str(deadline)):
                    alarm.write_text('0')
                if not already_enabled:
                    debug.write_text('func tb_acpi_force_power -p\n')
            # The helper's ExecStartPost already performs the validated T1 wake.
            # Allow DHCP to settle after that job completes; no firmware retries.
            settle_until = time.monotonic() + 30
            while time.monotonic() < settle_until:
                state = command(['nmcli', '-g', 'GENERAL.STATE', 'device', 'show', args.interface])
                if state['stdout'].startswith('100'):
                    break
                time.sleep(2)
            report['after'] = collect(args.interface)
            kernel = command(['journalctl', '-k', '-b', '--no-pager', '--since', since])
            unit = command(['journalctl', '-b', '-u', 'systemd-suspend.service', '--no-pager', '--since', since])
            (out / 'kernel.log').write_text(kernel['stdout'] + kernel['stderr'])
            (out / 'suspend-unit.log').write_text(unit['stdout'] + unit['stderr'])
            checks = {
                'actual_deep_sleep': 'PM: suspend entry (deep)' in kernel['stdout'],
                'both_thunderbolt_hooks': kernel['stdout'].count('ACPI: calling SXFP') >= 2,
                't1_sleep_acknowledged': 'firmware sleep acknowledged' in unit['stdout'],
                't1_wake_acknowledged': 'firmware wake acknowledged' in unit['stdout'],
                'no_kernel_warning': 'kernel: WARNING:' not in kernel['stdout'],
                'final_hardware_and_network': not report['after']['errors'],
                'sleep_duration_met': report['timing']['duration_met'],
            }
            report['checks'] = checks
            report['passed'] = all(checks.values())
            if not checks['sleep_duration_met']:
                report['error'] = ('Woke early: measured '
                    + str(report['timing']['system_suspended_seconds'])
                    + ' seconds suspended for a ' + str(args.suspend_seconds) + '-second alarm')
        else:
            report['passed'] = True
    except Exception as error:
        report['passed'] = False
        report['error'] = str(error)
    finally:
        if 'since' in locals():
            for filename, args_cmd in {
                'kernel.log': ['journalctl', '-k', '-b', '--no-pager', '--since', since],
                'suspend-unit.log': ['journalctl', '-b', '-u', 'systemd-suspend.service', '--no-pager', '--since', since],
            }.items():
                if not (out / filename).exists():
                    try:
                        r = command(args_cmd)
                        (out / filename).write_text(r['stdout'] + r['stderr'])
                    except Exception as error:
                        (out / filename).write_text(str(error))
        (out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        uid = int(os.environ.get('SUDO_UID', '0'))
        gid = int(os.environ.get('SUDO_GID', '0'))
        for p in out.iterdir():
            os.chown(p, uid, gid)
        os.chown(out, uid, gid)
        print(json.dumps(report, indent=2))
        print('Results:', out)
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
