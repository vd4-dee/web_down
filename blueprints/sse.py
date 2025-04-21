from flask import Blueprint, Response
from globals import status_messages, is_running, lock
import time

sse_bp = Blueprint('sse', __name__, template_folder='../templates')

@sse_bp.route('/stream-status')
def stream_status():
    def event_stream():
        last_yielded_index = 0
        keep_running = True
        try:
            while keep_running:
                with lock:
                    current_message_count = len(status_messages)
                    is_process_active = is_running
                    messages_to_yield = status_messages[last_yielded_index:current_message_count]
                if messages_to_yield:
                    for message in messages_to_yield:
                        yield f"data: {message}\n\n"
                    last_yielded_index = current_message_count
                if not is_process_active and last_yielded_index == current_message_count:
                    time.sleep(0.1)
                    with lock:
                        final_process_check = is_running
                        final_message_count = len(status_messages)
                    if not final_process_check and last_yielded_index == final_message_count:
                        yield f"data: FINISHED\n\n"
                        keep_running = False
                        break
                time.sleep(0.5)
        except GeneratorExit:
            keep_running = False
        finally:
            pass
    return Response(event_stream(), mimetype='text/event-stream')
