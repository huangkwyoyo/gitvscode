from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd


class DataSourceAdapter(ABC):
    @abstractmethod
    def can_load(self, source: Path) -> bool:
        raise NotImplementedError

    @abstractmethod
    def load(self, source: Path) -> pd.DataFrame:
        raise NotImplementedError

