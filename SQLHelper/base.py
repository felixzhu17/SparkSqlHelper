import re

import pandas as pd
from pyspark.sql.utils import AnalysisException
from tqdm import tqdm

from .logging import Logging
from .utils import *


class SQLBase(Logging):
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
            filters, day_message = add_day_filters(filters, days, day_column)
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
        verbose: bool = True,
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
            verbose (bool): Whether to log

        """

        if days:
            filters, day_message = add_day_filters(filters, days, day_column)
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
        if verbose:
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
            filters, day_message = add_day_filters(filters, days, day_column)

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
        cols = list(set(i for i in column_df["col_name"] if is_sql_column(i)))
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
            filters, day_message = add_day_filters(filters, days, day_column)

        filter_info = f"""WHERE {' and '.join(filters)}""" if len(filters) > 0 else ""

        query = f"""
          SELECT distinct {column_info}
          FROM {dataset}
          {filter_info}
          """
        if self.print_query:
            print(query)
        return self.run_query(query)

    def create_table(self, table, query):
        """Create table using a query

        Args:
            table (str): Name of table to backfill
            query (str): Query to create the table
        """

        query = f"""CREATE TABLE {table} as ({query})"""
        self.run_query(query)
        return

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
