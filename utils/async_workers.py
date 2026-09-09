from concurrent.futures import ThreadPoolExecutor
import threading
import logging

logger = logging.getLogger(__name__)

class BackgroundProcessor:
    """
    Singleton ThreadPoolExecutor for background tasks.
    Capped at 2 workers to avoid starving Gunicorn threads on EC2.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        # Strict cap of 2 workers to avoid cannibalizing web threads
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="BGWorker")
        self._queue_size = 0
        self._q_lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
        return cls._instance

    def submit_task(self, fn, *args, **kwargs):
        with self._q_lock:
            self._queue_size += 1
            
        def wrapper():
            try:
                fn(*args, **kwargs)
            except Exception as e:
                logger.error(f"Background task failed: {e}")
            finally:
                with self._q_lock:
                    self._queue_size -= 1
                    
        return self.executor.submit(wrapper)

    def get_queue_size(self):
        with self._q_lock:
            return self._queue_size

    def shutdown(self):
        logger.info("Shutting down BackgroundProcessor...")
        self.executor.shutdown(wait=True)
