from enum import Enum, auto


class Order(Enum):
    SHUFFLE = auto(),
    CHRONOLOGICAL_DESCENDING = auto()
    CHRONOLOGICAL_ASCENDING = auto()

    def to_sql(self) -> tuple[str, str]:
        match self:
            case Order.SHUFFLE:
                return 'RANDOM()', None
            case Order.CHRONOLOGICAL_DESCENDING:
                return 'datetime(capture_date) DESC', 'capture_date IS NOT NULL'
            case Order.CHRONOLOGICAL_ASCENDING:
                return 'datetime(capture_date) ASC', 'capture_date IS NOT NULL'
            case other:
                raise ValueError(other)
