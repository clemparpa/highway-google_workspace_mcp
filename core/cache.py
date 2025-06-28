import logging
import time
import threading
from typing import Dict, Tuple, Optional, Any

logger = logging.getLogger(__name__)

class _Cache: 
    """Classe pour gérer le cache des credentials et des services avec TTL et taille maximale."""
    def __init__(self, max_size: int, ttl_seconds: int):
        """Initialise le cache avec une taille maximale et un TTL."""
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}
        self._lock = threading.Lock()


    def _cleanup_cache(self) -> None:
        """Nettoie le cache en supprimant les entrées expirées et en limitant la taille."""
        current_time = time.time()
        
        # Supprimer les entrées expirées
        expired_keys = [
            id for id, (_, timestamp) in self._cache.items()
            if current_time - timestamp > self.ttl_seconds
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        # Si le cache dépasse encore la limite, supprimer les plus anciennes
        if len(self._cache) > self.max_size:
            # Trier par timestamp et garder seulement les plus récentes
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: x[1][1],  # Trier par timestamp
                reverse=True
            )
            
            # Garder seulement les _CACHE_MAX_SIZE plus récentes
            self._cache.clear()
            for id, (item, timestamp) in sorted_items[:self.max_size]:
                self._cache[id] = (item, timestamp)


    def get_cached_item(self, _id: str | list[str]) -> Optional[Any]:
        """Récupère les objets depuis le cache si elles sont valides."""
        id = _id if isinstance(_id, str) else "-".join(_id)

        with self._lock:
            if id not in self._cache:
                return None
            
            cached, timestamp = self._cache[id]
            current_time = time.time()
            
            # Vérifier si l'entrée n'est pas expirée
            if current_time - timestamp > self.ttl_seconds:
                del self._cache[id]
                return None
            
            logger.debug(f"Cache hit for id: {id}")
            return cached


    def cache_item(self, _id: str | list[str], to_cache: Any) -> None:
        """Met en cache pour un utilisateur."""
        id = _id if isinstance(_id, str) else "-".join(_id)

        with self._lock:
            current_time = time.time()
            self._cache[id] = (to_cache, current_time)
            
            # Nettoyer le cache si nécessaire
            self._cleanup_cache()
            
            logger.debug(f"Cached for id: {id}")


CredentialsCache = _Cache(max_size=100, ttl_seconds=30)
ServiceCache = _Cache(max_size=100, ttl_seconds=30)