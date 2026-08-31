import time
from typing import Dict

class RateLimiter:
    def __init__(self, limit_seconds: float = 0.4):
        self.limit_seconds = limit_seconds
        self.user_timestamps: Dict[int, float] = {}

    def is_rate_limited(self, user_id: int) -> bool:
        """Comprueba si el usuario está enviando solicitudes demasiado rápido"""
        now = time.time()
        last_time = self.user_timestamps.get(user_id, 0)
        if now - last_time < self.limit_seconds:
            return True
        self.user_timestamps[user_id] = now
        return False

rate_limiter = RateLimiter(limit_seconds=0.4)
