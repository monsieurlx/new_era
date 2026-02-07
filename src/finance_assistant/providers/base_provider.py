from abc import ABC, abstractmethod
from .models import FinancialMetrics

class DataProvider(ABC):
    """Abstract base class for financial data providers"""
    @abstractmethod
    def get_metrics(self, ticker: str) -> FinancialMetrics:
        pass
    @abstractmethod
    def is_available(self) -> bool:
        pass
    @property
    @abstractmethod
    def name(self) -> str:
        pass
