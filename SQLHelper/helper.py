import re

import pandas as pd
from pyspark.sql.utils import AnalysisException
from tqdm import tqdm

from .logging import Logging


class SQLHelper(Logging):
    def __init__(self, spark):
        self.spark = spark
        self.spark.conf.set(
            "spark.sql.legacy.allowCreatingManagedTableUsingNonemptyLocation", "true"
        )
        self.print_query = True
        Logging.__init__(self)

    def run_query(self, query: str or list):
        """Run query or list of queries in SQL

        Args:
            query (str or list): SQL query

        """
        if isinstance(query, str):
            return self.spark.sql(query).toPandas()
        else:
            return [self.run_query(i) for i in query]

    def get_all(
        self,
        dataset: str,
        days: str or list or tuple = None,
        day_column: str = "day",
        columns: list = [],
        filters: list = [],
        _return_query=False,
    ):
        """Get all rows in a SQL dataset

        Args:
            dataset (str): Name of SQL dataset
            days (str or list or Tuple): Day or list/tuple of days to filter
            day_column (str): Name of column to filter day on
            columns (list): List of columns to return. If empty, return all
            filters (list): List of SQL filters. If empty, no filter

        """

        if days:
            filters, day_message = self._add_day_filters(filters, days, day_column)
        else:
            day_message = ""

        column_info = ", ".join(columns) if len(columns) > 0 else "*"
        filter_info = f"""WHERE {' and '.join(filters)}""" if len(filters) > 0 else ""
        query = f"""
        SELECT {column_info}
        FROM {dataset}
        {filter_info}
        """
        self.logger.info(f"Downloading {dataset} {day_message}")
        if self.print_query:
            print(query)
        if _return_query:
            return query
        return self.run_query(query)

    def sample(
        self,
        dataset: str,
        n: int = 1,
        days: str or list or tuple = None,
        day_column: str = "day",
        columns: list = [],
        filters: list = [],
        random: bool = False,
    ):
        """Get a sample of rows in SQL dataset

        Args:
            dataset (str): Name of SQL dataset
            n (int): Number of rows
            days (str or list or Tuple): Day or list/tuple of days to filter
            day_column (str): Name of column to filter day on
            columns (list): List of columns to return. If empty, return all
            filters (list): List of SQL filters. If empty, no filter
            random (bool): Whether to select a random sample

        """

        if days:
            filters, day_message = self._add_day_filters(filters, days, day_column)
        else:
            day_message = ""

        column_info = ", ".join(columns) if len(columns) > 0 else "*"
        filter_info = f"""WHERE {' and '.join(filters)}""" if len(filters) > 0 else ""
        random_filter = "ORDER BY RAND()" if random else ""

        query = f"""
        SELECT {column_info}
        FROM {dataset}
        {filter_info}
        {random_filter}
        LIMIT {n}
        """
        self.logger.info(f"Downloading {n} samples of {dataset} {day_message}")
        if self.print_query:
            print(query)
        return self.run_query(query)

    def nrows(
        self,
        dataset: str,
        days: str or list or tuple = None,
        day_column: str = "day",
        filters: list = [],
        distinct: list = [],
    ):
        """Get number of rows in SQL dataset

        Args:
            dataset (str): Name of SQL dataset
            days (str or list or Tuple): Day or list/tuple of days to filter
            day_column (str): Name of column to filter day on
            filters (list): List of SQL filters. If empty, no filter
            distinct (list): Get the distinct value of a column

        """

        if days:
            filters, day_message = self._add_day_filters(filters, days, day_column)

        filter_info = f"""WHERE {' and '.join(filters)}""" if len(filters) > 0 else ""
        selection = f"""distinct {", ".join(distinct)}""" if len(distinct) > 0 else "*"

        query = f"""
        SELECT COUNT({selection})
        FROM {dataset}
        {filter_info}
        """
        if self.print_query:
            print(query)
        return self.run_query(query).iloc[0][0]

    def cols(self, dataset: str, return_day=True):
        """Get columns in the dataset

        Args:
            dataset (str): Name of SQL dataset
            return_day (bool): Whether to include day in columns
        """
        query = f"describe {dataset}"
        column_df = self.run_query(query)
        cols = list(set(i for i in column_df["col_name"] if self._is_column(i)))
        if return_day:
            return cols
        else:
            return [i for i in cols if i != "day"]

    def day_range(self, dataset: str):
        """Get the minimum and maximum day in dataset

        Args:
            dataset (str): Name of SQL dataset
        """
        query = f"""
        SELECT min(day), max(day)
        FROM {dataset}"""
        return self.run_query(query)

    def distinct(
        self,
        dataset: str,
        column: str,
        days: str or list or tuple = None,
        day_column: str = "day",
        filters: list = [],
    ):
        """Get the distinct values in a column of SQL dataset

        Args:
            dataset (str): Name of SQL dataset
            column (str): Name of column
            days (str or list or Tuple): Day or list/tuple of days to filter
            day_column (str): Name of column to filter day on
            filters (list): List of SQL filters. If empty, no filter

        """
        if isinstance(column, list):
            column_info = ",".join(column)
        else:
            column_info = column

        if days:
            filters, day_message = self._add_day_filters(filters, days, day_column)

        filter_info = f"""WHERE {' and '.join(filters)}""" if len(filters) > 0 else ""

        query = f"""
          SELECT distinct {column_info}
          FROM {dataset}
          {filter_info}
          """
        if self.print_query:
            print(query)
        return self.run_query(query)

    def insert_df(self, df: pd.DataFrame, table_name: str):
        """Insert a Pandas Dataframe into SQL

        Args:
            df (pd.DataFrame): Pandas Dataframe to upload
            table_name (str): Name of SQL dataset

        """

        if self._table_does_not_exist(table_name):
            sql_table = self.spark.createDataFrame(df)
            sql_table.createOrReplaceTempView("sql_table")
            query = f"""
            CREATE TABLE IF NOT EXISTS {table_name} as 
            (SELECT * FROM sql_table)
            """
            self.logger.info(f"Inserting into {table_name}")
            return self.run_query(query)
        else:
            self.update_df(df, table_name)

    def update_df(self, df: pd.DataFrame, table_name: str):
        """Update SQL dataset from Pandas Dataframe

        Args:
            df (pd.DataFrame): Pandas Dataframe to upload
            table_name (str): Name of SQL dataset

        """

        sql_table = self.spark.createDataFrame(df)
        sql_table.createOrReplaceTempView("sql_table")
        query = f"""
        INSERT INTO {table_name}
        SELECT * FROM sql_table
        """
        self.logger.info(f"Updating {table_name}")
        return self.run_query(query)

    def update_df_partition(
        self, df: pd.DataFrame, table_name: str, partition: str, partition_value
    ):
        """Update SQL dataset with partition from Pandas Dataframe

        Args:
            df (pd.DataFrame): Pandas Dataframe to upload
            table_name (str): Name of SQL dataset
            partition (str): Name of partition column
            partition_value: Value of partition column

        """
        sql_table = self.spark.createDataFrame(df)
        sql_table.createOrReplaceTempView("sql_table")
        query = f"""
        INSERT INTO {table_name}
        PARTITION({partition}= {partition_value}) 
        SELECT * FROM sql_table;
        """
        self.logger.info(f"Updating {table_name} with {partition_value} on {partition}")
        return self.run_query(query)

    def count_union(self, table_a, table_b, field_a, field_b):
        """Count the union of the fields of two tables

        Args:
            table_a (str): Name of first SQL dataset
            table_b (str): Name of second SQL dataset
            field_a (str): Name of field in first SQL dataset
            field_b (str): Name of field in second SQL dataset

        """
        query = f"""SELECT count(distinct field)
                FROM 
                (
                SELECT {field_a} as field
                FROM {table_a}
                UNION 
                SELECT {field_b} as field
                FROM {table_b}
                )"""
        return self.run_query(query).iloc[0][0]

    def _add_day_filters(self, fs, days, day_column):
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

    def backfill_table(
        self, table, query, start_date, end_date, freq="d", delta=True, overwrite=False
    ):
        """Back-fill a table partitioned by day. Automatically creates table if does not exist. Skips days which already exists.

        Args:
            table (str): Name of table to backfill
            query (func): Function taking the parameter day which returns a sql query to backfill with
            start_date (str): Start date of backfill
            end_date (str): End date of backfill
            freq (str): Frequency of dates

        """
        table_creation_sql = (
            self.delta_table_creation_sql if delta else self.parquet_table_creation_sql
        )
        table_append_sql = (
            self.delta_table_append_sql if delta else self.parquet_table_append_sql
        )
        create_table = self._table_does_not_exist(table)

        def run_query():
            try:
                self.run_query(table_append_sql(table, query, date))
            except Exception as e:
                print(e)
                pass

        def run_query_with_day_check():
            if self._day_does_not_exist(table, date):
                run_query()
            else:
                self.logger.info(f"Skipping {date} as it already exists")
                pass

        for date in tqdm(self.chunk_dates(start_date, end_date, freq)):
            if create_table:
                self.logger.info(
                    f"Creating new table {table} using {'delta' if delta else 'parquet'}"
                )
                self.run_query(table_creation_sql(table, query, date))
                create_table = False
            else:
                if overwrite:
                    run_query()
                else:
                    if delta:
                        run_query()
                    else:
                        run_query_with_day_check

    def create_table(self, table, query):
        """Create table using a query

        Args:
            table (str): Name of table to backfill
            query (str): Query to create the table
        """

        query = f"""CREATE TABLE {table} as ({query})"""
        self.run_query(query)
        return

    def parquet_table_creation_sql(self, table, query, day):
        return f"""
        create table if not exists {table}
        using parquet
        partitioned by (day)
        as
        select *
        from (
        {query(day)}
        )
        """

    def delta_table_creation_sql(self, table, query, day):
        return f"""
        create table if not exists {table}
        using delta
        partitioned by (day)
        as
        select *
        from (
        {query(day)}
        )
        """

    def parquet_table_append_sql(self, table, query, day):
        return f"""
        insert into table {table}
        select *
        from (
        {query(day)}
        )
        """

    def delta_table_append_sql(self, table, query, day):
        return (
            f"""delete from {table} where day = '{day}'""",
            f"""insert into table {table}
        select *
        from (
        {query(day)}
        )
        """,
        )

    def chunk_dates(self, start_date, end_date, freq, return_range=False):
        dates = [
            i.strftime("%Y-%m-%d")
            for i in pd.date_range(start=start_date, end=end_date, freq=freq)
        ]
        if return_range:
            for start, end in zip(dates[:-1], dates[1:]):
                yield start, end
        else:
            for date in dates:
                yield date

    def _table_does_not_exist(self, dataset):
        """Check if dataset exists"""
        try:
            _ = self.sample(dataset)
            return False
        except AnalysisException:
            return True

    def _day_does_not_exist(self, dataset, day):
        return len(self.sample(dataset, days=day)) == 0

    def _is_column(self, str):
        exp = "^[a-zA-Z_][a-zA-Z0-9_]*$"
        return re.search(exp, str) is not None
