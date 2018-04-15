from veml7700 import Controller
import logging
from logging import INFO, DEBUG
from collections import namedtuple
from time import sleep


logging.basicConfig(format='[%(asctime)s] %(message)s', datefmt='%H:%M:%S', level=DEBUG)
log = logging.getLogger().log


def dump_status(ic):
    Entry = namedtuple('Entry', ['desc', 'val', 'unit'])
    entries = [
        Entry('Lux', ic.lux, 'lux'),
        Entry('Output', ic.output, 'cnt'),
        Entry('Integration time', ic.integration_time, 's'),
        Entry('Gain', ic.gain, ''),
        Entry('White', ic.white_output, 'cnt'),
        Entry('Event', ic.last_threshold_event, None),
        Entry('Power', ic.power_status, None),
        Entry('Threshold', (ic.threshold_enabled, ic.threshold_low, ic.threshold_high), None),
        Entry('Refres', ic.estimated_refresh_time, 's'),
        Entry('Resolution', ic.lux_resolution, 'lux/cnt'),
        Entry('Performance', ic.sampling_performance, None),
    ]
    col_width_desc = max(map(lambda e: len(e.desc), entries))
    col_width_val = max(map(lambda e: len(str(e.val)), entries))

    def entry_to_str(entry, desc_col_w, val_col_w):
        fmt = '  {:<%d} {:>%d}{}' % (desc_col_w, val_col_w)
        unit_str = '' if entry.unit is None else ' [%s]' % entry.unit
        return fmt.format(entry.desc, str(entry.val), unit_str)

    return '\n'.join(map(lambda e: entry_to_str(e, col_width_desc, col_width_val), entries))


def main():
    ic = Controller(1)
    log(INFO, 'Power on')
    ic.power_on()
    log(INFO, 'Calibrating')
    ic.calibrate()
    log(INFO, 'Status: \n' + dump_status(ic))
    log(INFO, 'Refreshing.')
    ic.refresh(refresh_white_output=True)
    log(INFO, 'Status: \n' + dump_status(ic))
    log(INFO, 'Light level: ' + ic.human_readable_lux)
    log(INFO, 'Performing 10 samples.')
    for _ in range(10):
        ic.refresh()
        log(INFO, 'Lux: %f' % ic.lux)
        ic.calibrate()
    log(INFO, 'Progressively changing the sleep modes and sampling')
    for mode in range(1, 5):
        log(INFO, 'Entering power save mode %d.' % mode)
        ic.power_save(mode)
        for _ in range(10):
            ic.refresh()
            log(INFO, 'Lux: %f' % ic.lux)
            ic.calibrate()
    ic.power_on()
    log(INFO, 'Waiting for threshold events')
    ic.threshold_low = 60. / ic.lux_resolution
    ic.threshold_high = 230. / ic.lux_resolution
    ic.threshold_enabled = True
    for _  in range(10):
        sleep(ic.estimated_refresh_time)
        log(INFO, 'Poll event: {%s}' % str(ic.poll_threshold_event()))
    ic.threshold_enabled = False
    log(INFO, 'Status: \n' + dump_status(ic))
    log(INFO, 'Power off.')
    ic.power_off()


if __name__ == '__main__':
    main()

