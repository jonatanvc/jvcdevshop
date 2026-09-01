import time
from typing import Dict

class RateLimiter:
    def __init__(self, limit_seconds: float = 0.4):
        self.limit_seconds = limit_seconds
        self.user_timestamps: Dict[int, float] = {}

    def is_rate_limited(self, user_id: int) -> bool:
        """Comprueba si el usuario está enviando solicitudes demasiado rápido con limpieza periódica de memoria"""
        now = time.time()
        last_time = self.user_timestamps.get(user_id, 0)
        if now - last_time < self.limit_seconds:
            return True
        self.user_timestamps[user_id] = now

        # Limpieza periódica de memoria si hay más de 5000 entradas
        if len(self.user_timestamps) > 5000:
            threshold = now - 60.0
            self.user_timestamps = {uid: ts for uid, ts in self.user_timestamps.items() if ts > threshold}

        return False

rate_limiter = RateLimiter(limit_seconds=0.4)
