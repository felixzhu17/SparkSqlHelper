import re

import pandas as pd


def add_day_filters(fs, days, day_column):
    filters = fs.copy()
    if isinstance(days, (list, tuple)):
        if days[0]:
            filters.append(f"""{day_column} >= '{days[0]}'""")
        if days[1]:
            filters.append(f"""{day_column} <='{days[1]}'""")
        message = f"between {days[0]} and {days[1]}"
    elif isinstance(days, str):
        filters.append(f"""{day_column} == '{days}'""")
        message = f"on {days}"
    else:
        raise ValueError
    return filters, message


def is_sql_column(str):
    exp = "^[a-zA-Z_][a-zA-Z0-9_]*$"
    return re.search(exp, str) is not None
