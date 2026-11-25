from functools import wraps
import time

def timer(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        t1 = time.perf_counter()
        result = func(*args, **kwargs)
        t2 = time.perf_counter()
        print(f"The function {func.__name__} took {t2-t1:.4f} seconds to run.")
        return result
    return wrapper

def retry(times = 1):                        
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(times):
                try: 
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    if i == times-1:
                        raise
                    print(f"{func.__name__} failed ({e}), retrying ({i + 1}/{times})")
        return wrapper
    return decorator

def make_flaky(failures, result="ok"):
    """Return a function that raises ValueError `failures` times, then returns `result`."""
    calls = 0

    @retry(times = 3)
    def flaky():
        nonlocal calls
        calls += 1
        if calls <= failures:
            raise ValueError(f"failure #{calls}")
        return result

    flaky.call_count = lambda: calls      # lets a test ask "how many times was I called?"
    return flaky

@timer
def fun():
    time.sleep(1)
    return 0

if __name__ == "__main__":
    fun()
    flaky = make_flaky(failures=2)
    print(flaky())
    print("calls:", flaky.call_count())
