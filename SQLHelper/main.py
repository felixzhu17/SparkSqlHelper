from .backfill import SQLBackfill
from .base import SQLBase


class SQLHelper(SQLBackfill, SQLBase):
    def __init__(self, spark):
        SQLBase.__init__(self, spark)
        SQLBackfill.__init__(self, spark)

    def print_selection(self, features, table_name=None):
        if table_name:
            print(", ".join([f"{table_name}.{i} \n" for i in features]))

        else:
            print(", ".join([f"{i} \n" for i in features]))
