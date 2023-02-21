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


def permutate_dictionary(d, all_value="All"):
    output = []
    keys = list(d.keys())
    values = list(d.values())
    n = len(keys)

    for i in range(2**n):
        binary = bin(i)[2:].zfill(n)
        new_dict = {}
        for j in range(n):
            if binary[j] == "0":
                new_dict[keys[j]] = f"'{all_value}'"
            else:
                new_dict[keys[j]] = values[j]
        output.append(new_dict)
    return output


def get_selection_query(fields):
    return "\n  , ".join([f"{v} as {k}" for k, v in fields.items()])
