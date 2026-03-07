import argparse
import json
import logging
import sys
from datetime import datetime
from piston_core.scheduler import schedule_n_units, critical_path_hours

logging.basicConfig(level=logging.DEBUG, filename='sched_debug.log', filemode='w', format='%(asctime)s %(levelname)s %(message)s')


def _safe_dump(obj):
    """Return a JSON-serializable version of obj using default stringification for unknown types."""
    try:
        json.dumps(obj)
        return obj
    except Exception:
        # Fallback: convert recursively where needed
        if isinstance(obj, dict):
            return {str(k): _safe_dump(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [_safe_dump(v) for v in obj]
        return str(obj)


def run_trace(plan_file: str, out_prefix: str, n_units_arg=None, channels_arg=None, biases=None):
    try:
        with open(plan_file, 'r') as f:
            plan = json.load(f)
    except Exception as ex:
        logging.exception('Failed loading plan file')
        print(f'Error loading plan file {plan_file}: {ex}', file=sys.stderr)
        return 1

    n_units = n_units_arg if n_units_arg is not None else plan.get('n_units', 1)
    channels = channels_arg if channels_arg is not None else plan.get('channels_per_unit', 1)
    tests_info = plan.get('tests_info')
    topo = plan.get('topo')
    st_map = plan.get('st_map')
    biases = biases or plan.get('biases', {'weak': 0.01, 'strong': 0.05})

    print(f"Running plan from {plan_file}: n_units={n_units} channels={channels}")

    results = {'meta': {'plan_file': plan_file, 'timestamp': datetime.utcnow().isoformat()}}

    try:
        mk_w, finishes_w, util_w, events_w = schedule_n_units(tests_info, topo, st_map, n_units, channels_per_unit=channels, unit_bias=biases.get('weak', None), trace=True)
        results['weak'] = {
            'mk': mk_w,
            'finishes': finishes_w,
            'util': util_w,
            'events': events_w,
            'cp_hours': critical_path_hours(tests_info, topo, st_map),
        }
        print('weak makespan:', mk_w)
    except Exception:
        logging.exception('Weak-bias run failed')
        results['weak'] = {'error': str(sys.exc_info()[1])}

    try:
        mk_s, finishes_s, util_s, events_s = schedule_n_units(tests_info, topo, st_map, n_units, channels_per_unit=channels, unit_bias=biases.get('strong', None), trace=True)
        results['strong'] = {
            'mk': mk_s,
            'finishes': finishes_s,
            'util': util_s,
            'events': events_s,
            'cp_hours': critical_path_hours(tests_info, topo, st_map),
        }
        print('strong makespan:', mk_s)
    except Exception:
        logging.exception('Strong-bias run failed')
        results['strong'] = {'error': str(sys.exc_info()[1])}

    # Write combined JSON output
    out_file = f"{out_prefix}_trace.json"
    try:
        with open(out_file, 'w') as f:
            json.dump(_safe_dump(results), f, indent=2)
        print(f'Wrote {out_file} and sched_debug.log')
    except Exception:
        logging.exception('Failed writing trace output')
        print(f'Failed writing output: {sys.exc_info()[1]}', file=sys.stderr)

    return 0


def main():
    p = argparse.ArgumentParser(description='Run scheduler traces and save events.')
    p.add_argument('--plan', default='plan.json', help='Path to plan JSON file')
    p.add_argument('--out', default='trace', help='Output prefix for trace JSON')
    p.add_argument('--n', type=int, help='Override n_units')
    p.add_argument('--channels', help='Override channels_per_unit (int or JSON list)')
    args = p.parse_args()

    channels = None
    if args.channels:
        try:
            channels = json.loads(args.channels)
        except Exception:
            try:
                channels = int(args.channels)
            except Exception:
                channels = args.channels

    sys.exit(run_trace(args.plan, args.out, n_units_arg=args.n, channels_arg=channels))


if __name__ == '__main__':
    main()
