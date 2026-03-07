"""
Test different yield application models to find which matches expected behavior.

Given data:
- 5 base tests: High Power Cal (54m), ACLR (1188m), PNA-X (882m), Peanuts (36m), X-Mod2 (90m)
- Total per iteration: 2250 min = 37.5 hours
- Spins = 3 (4 iterations total)
- Yield = 30%
- Time budget = 105.6 hours
- Station counts: HPC=3, ACLR=6, PNA=5, Peanuts=1, XMod=1
- Expected result: ~3 units

Models to test:
1. Per-test retry (current): Each test takes base_time / yield
2. Output filter: Normal speed, discard 70% of completed units
3. Per-iteration retry: Yield applies once per spin iteration
4. Pipeline-aware: Account for parallelism across multiple stations
5. Hybrid: Different yield application per station type
"""

from heapq import heappush, heappop

# Test data
tests = [
    ('High Power Cal', 54, 3),   # (name, time_min, station_count)
    ('ACLR-Test', 1188, 6),
    ('PNA-X', 882, 5),
    ('Peanuts Phase Noise', 36, 1),
    ('X-Mod2', 90, 1),
]

spins = 3  # 4 total iterations
yield_pct = 30.0
yield_frac = yield_pct / 100.0
time_budget_hours = 105.6
time_budget_min = time_budget_hours * 60.0

print("="*80)
print("YIELD MODEL EXPERIMENTS")
print("="*80)
print(f"Base tests: {len(tests)}")
print(f"Spins: {spins} (total iterations: {spins+1})")
print(f"Yield: {yield_pct}%")
print(f"Time budget: {time_budget_hours} hours ({time_budget_min:.0f} minutes)")
print(f"Expected result: ~3 units")
print("="*80)

# Calculate base metrics
base_time_per_iteration = sum(t[1] for t in tests)
print(f"\nBase time per iteration: {base_time_per_iteration} min = {base_time_per_iteration/60:.1f} hours")
print(f"Total iterations per unit: {spins+1}")
print(f"Base time per unit (no yield): {base_time_per_iteration * (spins+1) / 60:.1f} hours")


# ==============================================================================
# MODEL 1: Per-test retry (CURRENT MODEL)
# ==============================================================================
print("\n" + "="*80)
print("MODEL 1: Per-Test Retry (Current Implementation)")
print("Each test is retried until pass. Time per test = base_time / yield")
print("="*80)

total_adjusted_time = 0
for name, time_min, count in tests:
    adjusted = time_min / yield_frac
    total_adjusted_time += adjusted
    print(f"  {name}: {time_min}min → {adjusted:.0f}min (×{1/yield_frac:.2f})")

time_per_unit = total_adjusted_time * (spins + 1) / 60.0
units_possible = time_budget_hours / time_per_unit
print(f"\nTotal per iteration (adjusted): {total_adjusted_time:.0f} min = {total_adjusted_time/60:.1f} hours")
print(f"Time per unit: {time_per_unit:.1f} hours")
print(f"Units in {time_budget_hours} hours: {units_possible:.2f} → {int(units_possible)} units")


# ==============================================================================
# MODEL 2: Output Filter (Old Model)
# ==============================================================================
print("\n" + "="*80)
print("MODEL 2: Output Filter (Old/Incorrect Model)")
print("Tests run at normal speed. 70% of completed units are discarded.")
print("="*80)

# Simple serial execution
time_per_unit_base = base_time_per_iteration * (spins + 1) / 60.0
raw_units = time_budget_hours / time_per_unit_base
good_units_model2 = int(raw_units * yield_frac)

print(f"Time per unit (base): {time_per_unit_base:.1f} hours")
print(f"Raw units completed: {raw_units:.2f}")
print(f"Good units (×{yield_pct}%): {good_units_model2} units")
print(f"To get 3 good units, need {3/yield_frac:.1f} raw units = {3/yield_frac * time_per_unit_base:.1f} hours")


# ==============================================================================
# MODEL 3: Per-Iteration Retry
# ==============================================================================
print("\n" + "="*80)
print("MODEL 3: Per-Iteration Retry")
print("Each iteration (spin) is retried as a whole if any test fails.")
print("="*80)

# Each iteration has probability yield_frac^5 of all tests passing
# Expected attempts per iteration = 1 / (yield_frac^5)
prob_iteration_pass = yield_frac ** len(tests)
avg_attempts_per_iteration = 1.0 / prob_iteration_pass if prob_iteration_pass > 0 else float('inf')

time_per_iteration_adjusted = base_time_per_iteration * avg_attempts_per_iteration / 60.0
time_per_unit = time_per_iteration_adjusted * (spins + 1)
units_possible = time_budget_hours / time_per_unit

print(f"Probability all {len(tests)} tests pass: {prob_iteration_pass:.6f}")
print(f"Avg attempts per iteration: {avg_attempts_per_iteration:.1f}×")
print(f"Time per iteration (adjusted): {time_per_iteration_adjusted:.1f} hours")
print(f"Time per unit: {time_per_unit:.1f} hours")
print(f"Units in {time_budget_hours} hours: {units_possible:.2f} → {int(units_possible)} units")


# ==============================================================================
# MODEL 4: Pipeline with Parallelism
# ==============================================================================
print("\n" + "="*80)
print("MODEL 4: Pipeline with Station Parallelism")
print("Multiple units in flight. Each test retries, but stations can run parallel units.")
print("="*80)

# Build test sequence (4 iterations)
test_sequence = []
for iteration in range(spins + 1):
    for name, time_min, count in tests:
        # Adjust for yield
        adjusted_time = time_min / yield_frac
        test_sequence.append({
            'name': name,
            'time': adjusted_time,
            'station': name,
            'count': count
        })

# Simulate pipeline
station_queues = {}
for name, time_min, count in tests:
    station_queues[name] = [(0.0, i) for i in range(count)]

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

print(f"Simulated pipeline with {len(test_sequence)} tests per unit")
print(f"Bottleneck station: Peanuts Phase Noise (1 station)")
print(f"Units completed: {units_completed} units")

# Calculate theoretical bottleneck throughput
bottleneck = min(tests, key=lambda t: t[2])  # Peanuts with 1 station
bottleneck_time_per_unit = bottleneck[1] * (spins + 1) / yield_frac
bottleneck_throughput = time_budget_min / bottleneck_time_per_unit
print(f"\nBottleneck analysis:")
print(f"  Station: {bottleneck[0]} ({bottleneck[2]} stations)")
print(f"  Time per unit at bottleneck: {bottleneck_time_per_unit:.0f} min")
print(f"  Max throughput: {bottleneck_throughput:.2f} units")


# ==============================================================================
# MODEL 5: Yield per Unit (not per test)
# ==============================================================================
print("\n" + "="*80)
print("MODEL 5: Yield Applied Per Unit")
print("Each unit is retried as a whole if it fails. Time per unit = base × (1/yield)")
print("="*80)

base_time_per_unit_min = base_time_per_iteration * (spins + 1)
adjusted_time_per_unit_min = base_time_per_unit_min / yield_frac
adjusted_time_per_unit_hrs = adjusted_time_per_unit_min / 60.0
units_possible = time_budget_hours / adjusted_time_per_unit_hrs

print(f"Base time per unit: {base_time_per_unit_min / 60:.1f} hours")
print(f"Adjusted time per unit (×{1/yield_frac:.2f}): {adjusted_time_per_unit_hrs:.1f} hours")
print(f"Units in {time_budget_hours} hours: {units_possible:.2f} → {int(units_possible)} units")


# ==============================================================================
# MODEL 6: No yield adjustment on time (yield = throughput scaler)
# ==============================================================================
print("\n" + "="*80)
print("MODEL 6: Yield as Throughput Scaler")
print("Tests run at normal speed. Need to start 1/yield units to get 1 good unit.")
print("Pipeline simulation with normal times, output scaled by yield.")
print("="*80)

# Build test sequence (4 iterations) - NO yield adjustment
test_sequence_normal = []
for iteration in range(spins + 1):
    for name, time_min, count in tests:
        test_sequence_normal.append({
            'name': name,
            'time': time_min,  # Normal time!
            'station': name,
            'count': count
        })

# Simulate pipeline with NORMAL times
station_queues = {}
for name, time_min, count in tests:
    station_queues[name] = [(0.0, i) for i in range(count)]

max_units = 1000
raw_units_completed = 0

for unit_idx in range(max_units):
    current_time = 0.0
    
    for test in test_sequence_normal:
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
        raw_units_completed = unit_idx + 1
    else:
        break

good_units = int(raw_units_completed * yield_frac)

print(f"Pipeline simulation with NORMAL test times")
print(f"Raw units completed: {raw_units_completed}")
print(f"Good units (×{yield_pct}%): {good_units} units")
print(f"\nInterpretation: To get N good units, pipeline must process N/yield raw units")


# ==============================================================================
# SUMMARY
# ==============================================================================
print("\n" + "="*80)
print("SUMMARY")
print("="*80)
print(f"Target: ~3 units in {time_budget_hours} hours\n")
print(f"Model 1 (Per-test retry):       {int(time_budget_hours / (total_adjusted_time * (spins+1) / 60.0))} units")
print(f"Model 2 (Output filter):        {good_units_model2} units")
model3_units = int(time_budget_hours / (time_per_iteration_adjusted * (spins+1))) if time_per_iteration_adjusted < 1000 else 0
print(f"Model 3 (Per-iteration retry):  {model3_units} units")
print(f"Model 4 (Pipeline parallel):    {units_completed} units")  
model5_units = int(time_budget_hours / adjusted_time_per_unit_hrs)
print(f"Model 5 (Yield per unit):       {model5_units} units")
print(f"Model 6 (Throughput scaler):    {good_units} units")
print("="*80)
