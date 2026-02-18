from enum import Enum


class SortField(Enum):
    CREATED_AT = "created_at"
    UPDATED_AT = "updated_at"
    THUMBS_UP_COUNT = "thumbs_up_count"
    THUMBS_DOWN_COUNT = "thumbs_down_count"
    ID = "id"