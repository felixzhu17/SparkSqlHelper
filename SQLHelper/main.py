from .backfill import SQLBackfill
from .base import SQLBase
from .utils import *


class SQLHelper(SQLBackfill, SQLBase):
    def __init__(self, spark, print_query=True):
        SQLBase.__init__(self, spark, print_query)
        SQLBackfill.__init__(self, spark, print_query)

    def print_selection(self, features, table_name=None):
        if table_name:
            print(", ".join([f"{table_name}.{i} \n" for i in features]))

        else:
            print(", ".join([f"{i} \n" for i in features]))

    def get_exploded_identifiers_query(self, query, identifiers_dict, all_value="All"):
        def get_exploded_query(field_dict):
            return query.replace("{{IDENTIFIERS}}", get_selection_query(field_dict))

        return "\n\n UNION ALL \n\n".join(
            [
                get_exploded_query(field_dict)
                for field_dict in permutate_dictionary(identifiers_dict, all_value)
            ]
        )
