from .backfill import SQLBackfill
from .base import SQLBase


class SQLHelper(SQLBackfill, SQLBase):
    def __init__(self, spark):
        SQLBase.__init__(self, spark)
        SQLBackfill.__init__(self, spark)
