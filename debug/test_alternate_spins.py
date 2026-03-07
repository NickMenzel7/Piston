"""
Test alternate interpretations of Spins and test execution
"""

from heapq import heappush, heappop

# Test data
tests = [
    ('High Power Cal', 54, 3),
    ('ACLR-Test', 1188, 6),
    ('PNA-X', 882, 5),
    ('Peanuts Phase Noise', 36, 1),
    ('X-Mod2', 90, 1),
]

yield_frac = 0.30
time_budget_min = 105.6 * 60.0
target_units = 3

print("="*80)
print("ALTERNATE INTERPRETATIONS TEST")
print("="*80)

def simulate(iterations_per_unit, yield_applied=False):
    """Simulate with different interpretations"""
    test_sequence = []
    for iteration in range(iterations_per_unit):
        for name, time_min, count in tests:
            if yield_applied:
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
    
    return units_completed

print("\nINTERPRETATION 1: Spins=3 means 3 ADDITIONAL spins (4 total iterations)")
units = simulate(4, yield_applied=False)
print(f"  No yield: {units} units")
units = simulate(4, yield_applied=True)
print(f"  With yield: {units} units")

print("\nINTERPRETATION 2: Spins=3 means 3 TOTAL iterations")
units = simulate(3, yield_applied=False)
print(f"  No yield: {units} units")
units = simulate(3, yield_applied=True)
print(f"  With yield: {units} units")

print("\nINTERPRETATION 3: Spins=0 (only 1 iteration)")
units = simulate(1, yield_applied=False)
print(f"  No yield: {units} units")
units = simulate(1, yield_applied=True)
print(f"  With yield: {units} units")

print("\nINTERPRETATION 4: Only SOME tests run multiple times")
print("  (e.g., only ACLR and PNA-X run 4 times, others once)")
test_sequence = []
for name, time_min, count in tests:
    if name in ['ACLR-Test', 'PNA-X']:
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

print(f"  Result: {units_completed} units")

print("\n" + "="*80)
print("BASE TIME ANALYSIS")
print("="*80)
base_total = sum(t[1] for t in tests)
print(f"One pass through all tests: {base_total/60:.1f} hours")
print(f"With 4 iterations: {base_total*4/60:.1f} hours")
print(f"With 3 iterations: {base_total*3/60:.1f} hours")
print(f"With 1 iteration: {base_total/60:.1f} hours")
print(f"\nTime budget: 105.6 hours")
print(f"Units possible (1 iteration, no yield): {105.6 / (base_total/60):.2f}")
print(f"Units possible (3 iterations, no yield): {105.6 / (base_total*3/60):.2f}")
print(f"Units possible (4 iterations, no yield): {105.6 / (base_total*4/60):.2f}")
