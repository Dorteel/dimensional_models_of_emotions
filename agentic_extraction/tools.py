import time

def get_time() -> str:
    """Return a placeholder current time."""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

TOOLS = {
    "get_time": get_time
}