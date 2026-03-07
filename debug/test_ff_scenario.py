"""
Test Factory Floor (FF) scenario to find which yield model gives 4 units in 187.2 hours
"""

from heapq import heappush, heappop

# FF scenario data
tests = [
    ('High Power Cal', 3*60, 3),        # 3 hrs = 180 min
    ('ACLR-Test', 28.5*60, 5),          # 28.5 hrs = 1710 min
    ('PNA-X', 12*60, 5),                # 12 hrs = 720 min
    ('Peanuts Phase Noise', 1*60, 1),   # 1 hrs = 60 min
    ('X-Mod2', 2.5*60, 1),              # 2.5 hrs = 150 min
]

# Manual model shows: Total (YS only) = 47 hrs per iteration
base_total = sum(t[1] for t in tests)
print(f"Calculated base total: {base_total/60:.1f} hours")
print(f"Manual model shows: 47 hours")
print()

time_budget_hours = 187.2
time_budget_min = time_budget_hours * 60.0
spins_value = 4
yield_frac = 0.30
target_units = 4  # From batch plan: 7.8 days / 1.95 days per unit

print("="*80)
print("FACTORY FLOOR SCENARIO TEST")
print("="*80)
print(f"Target: {target_units} units in {time_budget_hours} hours")
print(f"Spins: {spins_value}")
print(f"Yield: {yield_frac*100}%")
print(f"Base time per iteration: {base_total/60:.1f} hours")
print("="*80)

def simulate(iterations_per_unit, yield_applied=False, yield_on_time=True):
    """
    Simulate with different yield models
    yield_on_time: If True, multiply test time by 1/yield. If False, filter output.
    """
    test_sequence = []
    for iteration in range(iterations_per_unit):
        for name, time_min, count in tests:
            if yield_applied and yield_on_time:
                adj_time = time_min / yield_frac
            else:
                adj_time = time_min
            test_sequence.append({
                'name': name,
                'time': adj_time,
                'station': name,
                'count': count
            })
    
    station_queues = {}
    for name, time_min, count in tests:
        station_queues[name] = [(0.0, i) for i in range(count)]
    
    units_completed = 0
    for unit_idx in range(1000):
        current_time = 0.0
        for test in test_sequence:
            available_time, resource_idx = heappop(station_queues[test['station']])
            start_time = max(current_time, available_time)
            finish_time = start_time + test['time']
            heappush(station_queues[test['station']], (finish_time, resource_idx))
            current_time = finish_time
        
        if current_time <= time_budget_min:
            units_completed = unit_idx + 1
        else:
            break
    
    if yield_applied and not yield_on_time:
        # Output filter model
        return int(units_completed * yield_frac)
    return units_completed

print("\n" + "="*80)
print("TEST 1: Spins=4 means 4 ADDITIONAL spins (5 total iterations)")
print("="*80)
units = simulate(5, yield_applied=False)
print(f"No yield, 5 iterations: {units} units")
print(f"  Time per unit: {base_total * 5 / 60:.1f} hours")

units = simulate(5, yield_applied=True, yield_on_time=True)
print(f"Yield on time, 5 iterations: {units} units")

units = simulate(5, yield_applied=True, yield_on_time=False)
print(f"Yield as filter, 5 iterations: {units} units")

print("\n" + "="*80)
print("TEST 2: Spins=4 means 4 TOTAL iterations")
print("="*80)
units = simulate(4, yield_applied=False)
print(f"No yield, 4 iterations: {units} units")
print(f"  Time per unit: {base_total * 4 / 60:.1f} hours")

units = simulate(4, yield_applied=True, yield_on_time=True)
print(f"Yield on time, 4 iterations: {units} units")

units = simulate(4, yield_applied=True, yield_on_time=False)
print(f"Yield as filter, 4 iterations: {units} units")

print("\n" + "="*80)
print("TEST 3: Spins=4 but only 1 iteration per unit")
print("="*80)
units = simulate(1, yield_applied=False)
print(f"No yield, 1 iteration: {units} units")
print(f"  Time per unit: {base_total / 60:.1f} hours")

units = simulate(1, yield_applied=True, yield_on_time=True)
print(f"Yield on time, 1 iteration: {units} units")

units = simulate(1, yield_applied=True, yield_on_time=False)
print(f"Yield as filter, 1 iteration: {units} units")

print("\n" + "="*80)
print("TEST 4: What if 'Spins' affects yield, not iterations?")
print("Maybe: effective_yield = base_yield^spins = 30%^4 = 0.81%")
print("="*80)
effective_yield = yield_frac ** spins_value
print(f"Effective yield: {effective_yield*100:.2f}%")
# This would make yield WORSE, not better, so probably not it

print("\n" + "="*80)
print("TEST 5: Maybe tests don't all run the same number of times?")
print("What if spins only applies to certain tests?")
print("="*80)
# Try: only ACLR runs 4 times, others run once
test_sequence = []
for name, time_min, count in tests:
    if 'ACLR' in name:
        iterations = 4
    else:
        iterations = 1
    for _ in range(iterations):
        test_sequence.append({
            'name': name,
            'time': time_min,
            'station': name,
            'count': count
        })

station_queues = {}
for name, time_min, count in tests:
    station_queues[name] = [(0.0, i) for i in range(count)]

units_completed = 0
total_time_per_unit = sum(t[1] for t in test_sequence)
print(f"Time per unit if only ACLR runs 4 times: {total_time_per_unit/60:.1f} hours")

for unit_idx in range(1000):
    current_time = 0.0
    for test in test_sequence:
        available_time, resource_idx = heappop(station_queues[test['station']])
        start_time = max(current_time, available_time)
        finish_time = start_time + test['time']
        heappush(station_queues[test['station']], (finish_time, resource_idx))
        current_time = finish_time
    
    if current_time <= time_budget_min:
        units_completed = unit_idx + 1
    else:
        break

print(f"Result: {units_completed} units")

print("\n" + "="*80)
print("TEST 6: Yield = 30% might mean '70% yield loss'")
print("So actual pass rate = 100% - 30% = 70%")
print("="*80)
actual_yield = 1.0 - yield_frac  # 70%
print(f"If yield=30% means 30% loss, actual yield = {actual_yield*100}%")
units = simulate(4, yield_applied=False)
good_units_filter = int(units * actual_yield)
print(f"4 iterations, no time adj, 70% filter: {units} raw → {good_units_filter} good")

# Time adjustment version
test_sequence = []
for iteration in range(4):
    for name, time_min, count in tests:
        adj_time = time_min / actual_yield  # 70% yield
        test_sequence.append({
            'name': name,
            'time': adj_time,
            'station': name,
            'count': count
        })

station_queues = {}
for name, time_min, count in tests:
    station_queues[name] = [(0.0, i) for i in range(count)]

units_completed = 0
for unit_idx in range(1000):
    current_time = 0.0
    for test in test_sequence:
        available_time, resource_idx = heappop(station_queues[test['station']])
        start_time = max(current_time, available_time)
        finish_time = start_time + test['time']
        heappush(station_queues[test['station']], (finish_time, resource_idx))
        current_time = finish_time
    
    if current_time <= time_budget_min:
        units_completed = unit_idx + 1
    else:
        break

print(f"4 iterations, time × 1/{actual_yield:.0f}%: {units_completed} units")

print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Target: {target_units} units")
print(f"Closest match(es) highlighted above")
