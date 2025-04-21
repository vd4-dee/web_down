import threading

status_messages = []
is_running = False
download_thread = None
lock = threading.Lock()
