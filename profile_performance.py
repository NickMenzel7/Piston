"""Profile Piston performance to identify bottlenecks."""
import cProfile
import pstats
import io
from pstats import SortKey
import time


def profile_startup():
    """Profile application startup."""
    print("Profiling startup...")
    pr = cProfile.Profile()
    pr.enable()
    
    # Import and create app (but don't run mainloop)
    import Piston
    app = Piston.PlannerApp()
    
    pr.disable()
    
    # Print stats
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats(SortKey.CUMULATIVE)
    ps.print_stats(30)  # Top 30 functions
    
    print("\n=== STARTUP PROFILE (Top 30 by cumulative time) ===")
    print(s.getvalue())
    
    return app


def profile_calculation(app):
    """Profile a calculation operation."""
    print("\n\nProfiling calculation...")
    
    # Ensure we have data loaded
    if not hasattr(app, 'imported_tests_df') or app.imported_tests_df is None:
        print("No data loaded, skipping calculation profile")
        return
    
    # Set up calculation parameters
    app.mode_var.set('time_for_n')
    app.n_var.set('10')
    app.single_var.set('1')
    app.dual_var.set('0')
    app.quad_var.set('0')
    app.spins_var.set('0')
    app.yield_var.set('100')
    
    pr = cProfile.Profile()
    pr.enable()
    
    # Run calculation
    try:
        app.calculate()
    except Exception as e:
        print(f"Calculation error: {e}")
    
    pr.disable()
    
    # Print stats
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats(SortKey.CUMULATIVE)
    ps.print_stats(30)  # Top 30 functions
    
    print("\n=== CALCULATION PROFILE (Top 30 by cumulative time) ===")
    print(s.getvalue())


if __name__ == '__main__':
    start = time.time()
    
    # Profile startup
    app = profile_startup()
    
    startup_time = time.time() - start
    print(f"\n\nTotal startup time: {startup_time:.2f} seconds")
    
    # Profile calculation
    profile_calculation(app)
    
    total_time = time.time() - start
    print(f"\n\nTotal profiling time: {total_time:.2f} seconds")
    
    # Keep window open briefly to see results
    print("\nClosing in 2 seconds...")
    time.sleep(2)
    
    try:
        app.quit()
    except:
        pass
