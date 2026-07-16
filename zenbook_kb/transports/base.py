"""Transport interface for keyboard backlight backends."""

from __future__ import annotations

from abc import ABC, abstractmethod


class TransportError(RuntimeError):
    pass


class Transport(ABC):
    name: str

    @abstractmethod
    def set_brightness(self, level: int) -> None:
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        raise NotImplementedError
