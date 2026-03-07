"""
Find which tests have yield applied by testing different combinations.
Target: ~3 units in 105.6 hours with 30% yield
"""

from heapq import heappush, heappop
from itertools import combinations

# Test data (per unit times)
tests = [
    ('High Power Cal', 54, 3),           # 0.9 hrs
    ('ACLR-Test', 1188, 6),              # 19.8 hrs (longest)
    ('PNA-X', 882, 5),                   # 14.7 hrs
    ('Peanuts Phase Noise', 36, 1),      # 0.6 hrs
    ('X-Mod2', 90, 1),                   # 1.5 hrs
]

spins = 3  # 4 total iterations
yield_frac = 0.30
time_budget_min = 105.6 * 60.0  # 6336 minutes
target_units = 3

print("="*80)
print("SELECTIVE YIELD MODEL - Find which tests have yield applied")
print("="*80)
print(f"Target: {target_units} units in 105.6 hours")
print(f"Yield: {yield_frac*100}% (multiplier: {1/yield_frac:.2f}×)")
print(f"Spins: {spins} (4 iterations per unit)")
print("="*80)

def simulate_pipeline(yield_mask):
    """
    Simulate pipeline with yield applied only to tests where yield_mask[i] = True
    Returns number of units completed
    """
    # Build test sequence (4 iterations)
    test_sequence = []
    for iteration in range(spins + 1):
        for i, (name, time_min, count) in enumerate(tests):
            # Apply yield only if mask is True for this test
            if yield_mask[i]:
                adjusted_time = time_min / yield_frac
            else:
                adjusted_time = time_min
            
            test_sequence.append({
                'name': name,
                'time': adjusted_time,
                'station': name,
                'count': count
            })
    
    # Initialize station queues
    station_queues = {}
    for name, time_min, count in tests:
        station_queues[name] = [(0.0, i) for i in range(count)]
    
    # Simulate units
    max_units = 1000
    units_completed = 0
    
    for unit_idx in range(max_units):
        current_time = 0.0
        
        for test in test_sequence:
            station = test['station']
            test_time = test['time']
            
            # Get earliest available resource
            available_time, resource_idx = heappop(station_queues[station])
            
            # Start when both unit and station ready
            start_time = max(current_time, available_time)
            finish_time = start_time + test_time
            
            # Return resource to queue
            heappush(station_queues[station], (finish_time, resource_idx))
            
            # Update unit's time
            current_time = finish_time
        
        # Check if unit finished in budget
        if current_time <= time_budget_min:
            units_completed = unit_idx + 1
        else:
            break
    
    return units_completed

# Test all possible combinations of yield application
print("\nTesting all combinations of which tests have yield applied...\n")

best_match = None
best_diff = float('inf')
all_results = []

# Try all possible combinations (2^5 = 32 combinations)
for num_with_yield in range(len(tests) + 1):
    for combo in combinations(range(len(tests)), num_with_yield):
        # Create mask: True = yield applied, False = no yield
        yield_mask = [i in combo for i in range(len(tests))]
        
        # Simulate
        units = simulate_pipeline(yield_mask)
        
        # Calculate difference from target
        diff = abs(units - target_units)
        
        # Track result
        result = {
            'mask': yield_mask,
            'units': units,
            'diff': diff,
            'tests_with_yield': [tests[i][0] for i in range(len(tests)) if yield_mask[i]]
        }
        all_results.append(result)
        
        # Check if best match
        if diff < best_diff:
            best_diff = diff
            best_match = result

# Sort results by difference from target
all_results.sort(key=lambda x: x['diff'])

# Show top 10 closest matches
print("TOP 10 CLOSEST MATCHES:")
print("-" * 80)
for i, result in enumerate(all_results[:10]):
    print(f"\n{i+1}. Units: {result['units']} (diff: {result['diff']})")
    if result['tests_with_yield']:
        print(f"   Tests WITH yield adjustment:")
        for test_name in result['tests_with_yield']:
            print(f"     - {test_name}")
    else:
        print(f"   Tests WITH yield adjustment: NONE (all tests at normal speed)")
    
    # Show which tests DON'T have yield
    tests_without_yield = [tests[i][0] for i in range(len(tests)) if not result['mask'][i]]
    if tests_without_yield:
        print(f"   Tests WITHOUT yield (normal speed):")
        for test_name in tests_without_yield:
            print(f"     - {test_name}")

# Show the best match details
print("\n" + "="*80)
print("BEST MATCH DETAILS")
print("="*80)
print(f"Units completed: {best_match['units']} (target: {target_units})")
print(f"Difference: {best_match['diff']} units")

if best_match['tests_with_yield']:
    print(f"\nTests that HAVE yield adjustment (×{1/yield_frac:.2f}×):")
    for test_name in best_match['tests_with_yield']:
        # Find the test
        for name, time_min, count in tests:
            if name == test_name:
                adj_time = time_min / yield_frac
                print(f"  {name}: {time_min}min → {adj_time:.0f}min")
                break
else:
    print("\nNO tests have yield adjustment (all at normal speed)")

tests_without = [tests[i][0] for i in range(len(tests)) if not best_match['mask'][i]]
if tests_without:
    print(f"\nTests that DON'T have yield adjustment (normal speed):")
    for test_name in tests_without:
        for name, time_min, count in tests:
            if name == test_name:
                print(f"  {name}: {time_min}min (no change)")
                break

print("\n" + "="*80)
print("INTERPRETATION")
print("="*80)
print("Based on the simulation, to achieve ~3 units in 105.6 hours:")
if best_match['units'] == target_units:
    print("✓ EXACT MATCH FOUND!")
else:
    print(f"⚠ Best match gives {best_match['units']} units (off by {best_match['diff']})")

print("\nThis suggests yield should be applied ONLY to the tests listed above,")
print("likely because those are the tests that can actually fail and require retries.")
print("Other tests may be calibrations or deterministic steps that always pass.")
