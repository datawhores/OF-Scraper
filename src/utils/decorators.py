from ..constants import debug



def debuging(func):
    def wrapper(*args, **kwargs):
        if debug:
            print(f"Running {func.__name__}")
            # The idea is to soon be able to print internals of the function and allow for tracebacks.
        return func(*args, **kwargs)

    return wrapper


