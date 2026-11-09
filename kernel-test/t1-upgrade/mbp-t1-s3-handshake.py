#!/usr/bin/python3
"""One firmware sleep/wake pair for ordinary S3 suspend, outside driver callbacks."""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

STATE = Path('/run/mbp-t1-s3-handshake')
METHOD = r'\_SB.PCI0.XHC1.RHUB.ASOC.SOCW'
ACPIDBG = Path('/usr/local/libexec/mbp-t1/acpidbg')
ACPIDBG_APPROVAL = Path('/etc/mbp-t1/acpidbg.json')


class HandshakeError(RuntimeError):
    pass


def selected_mode(config, mem_sleep):
    section = None
    modes = []
    for raw in config.splitlines():
        line = raw.strip()
        if not line or line.startswith(('#', ';')):
            continue
        if line.startswith('[') and line.endswith(']'):
            section = line[1:-1]
        elif section == 'Sleep' and '=' in line:
            key, value = line.split('=', 1)
            if key.strip() == 'MemorySleepMode':
                modes = value.split()
    available = mem_sleep.replace('[', '').replace(']', '').split()
    if modes:
        for mode in modes:
            if mode in available:
                return mode
        raise HandshakeError('Configured MemorySleepMode is unavailable')
    match = re.search(r'\[([^]]+)\]', mem_sleep)
    if not match:
        raise HandshakeError('Cannot determine selected sleep mode')
    return match[1]


def planned_mode():
    config = subprocess.check_output(
        ['/usr/bin/systemd-analyze', 'cat-config', 'systemd/sleep.conf'], text=True)
    return selected_mode(config, Path('/sys/power/mem_sleep').read_text())


def validate():
    checks = {
        '/sys/class/dmi/id/product_name': 'MacBookPro13,2',
        '/sys/module/apple_ibridge/parameters/skip_acpi_power': '1',
        '/sys/bus/acpi/devices/APP7777:00/path': r'\_SB_.PCI0.XHC1.RHUB.ASOC',
    }
    for name, expected in checks.items():
        if Path(name).read_text().strip() != expected:
            raise HandshakeError(f'Guard failed: {name}')
    if 'pcie_port_pm=off' not in Path('/proc/cmdline').read_text().split():
        raise HandshakeError('Required PCIe workaround missing')
    if not os.access('/sys/kernel/debug/acpi/acpidbg', os.R_OK | os.W_OK):
        raise HandshakeError('ACPI debugger interface unavailable')
    # Accept only a verified rebuild of the reviewed source for this kernel.
    sys.path.insert(0, '/usr/local/lib/mbp-t1')
    from mbp_t1_guard import validate_running_build
    validate_running_build()
    validate_acpidbg()


def validate_acpidbg():
    # Ubuntu's /usr/bin/acpidbg dispatches by uname and cannot resolve a
    # custom kernel. Pin a standalone client independently of kernel names.
    from mbp_t1_guard import trusted, digest
    trusted(ACPIDBG_APPROVAL)
    approval = json.loads(ACPIDBG_APPROVAL.read_text())
    trusted(ACPIDBG)
    if (approval.get('schema') != 1 or approval.get('path') != str(ACPIDBG)
            or digest(ACPIDBG) != approval.get('sha256')):
        raise HandshakeError('Standalone acpidbg does not match its approval')
    with ACPIDBG.open('rb') as file:
        if file.read(4) != b'\x7fELF':
            raise HandshakeError('Standalone acpidbg must be a native executable')
    # The reviewed client's -h branch exits before opening the debugger.
    # Check readiness before phase() creates a pending firmware marker.
    result = subprocess.run([str(ACPIDBG), '-h'], capture_output=True,
                            text=True, timeout=5)
    if result.returncode or 'Specify command to be executed in batch mode' not in result.stdout:
        raise HandshakeError('Standalone acpidbg help/readiness check failed')


def call_socw(value):
    print(f'mbp-t1: SOCW({value}) once', flush=True)
    # A userspace timeout cannot make this firmware operation safe from a freeze.
    result = subprocess.run([str(ACPIDBG), '-b', f'execute {METHOD} {value}'],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(result.stdout, end='', flush=True)
    values = re.findall(r'\[Integer\]\s*=\s*([0-9A-Fa-f]+)', result.stdout)
    if result.returncode != 0 or len(values) != 1 or int(values[0], 16) != 0:
        raise HandshakeError(f'SOCW({value}) did not report Integer 0')


def phase(action, state=STATE, mode=None, check=validate, call=call_socw, pause=time.sleep):
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    pending = state / 'pending.json'
    if action == 'pre':
        if pending.exists():
            raise HandshakeError('A previous firmware wake is still pending; refusing another sleep')
        if (mode if mode is not None else planned_mode()) != 'deep':
            print('mbp-t1: suspend is not deep; no firmware call', flush=True)
            return
        check()
        pending.write_text(json.dumps({'phase': 'sleep-attempted', 'time': time.time()}))
        try:
            call(0)
        except Exception:
            # Cancel suspend and compensate once; ExecStopPost will see no marker.
            pending.unlink(missing_ok=True)
            try:
                call(1)
            except Exception as recovery:
                print(f'mbp-t1: compensating wake failed: {recovery}', file=sys.stderr, flush=True)
            raise
        print('mbp-t1: firmware sleep acknowledged', flush=True)
    elif action == 'post':
        if not pending.exists():
            return
        check()
        # Consume the marker before calling firmware: never retry automatically.
        pending.unlink()
        print('mbp-t1: waiting 15 seconds before firmware wake, matching validated test', flush=True)
        pause(15)
        call(1)
        print('mbp-t1: firmware wake acknowledged', flush=True)
    else:
        raise HandshakeError('Expected pre or post')


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2:
        raise HandshakeError('Run as root with pre or post')
    with open('/run/lock/mbp-t1-firmware-test.lock', 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        phase(sys.argv[1])


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(f'mbp-t1: ERROR: {error}', file=sys.stderr, flush=True)
        sys.exit(1)
