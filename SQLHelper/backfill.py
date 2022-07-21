from typing import List

import pandas as pd
from pyspark.sql.utils import AnalysisException
from tqdm import tqdm

from .base import SQLBase
from .utils import *


class SQLBackfill(SQLBase):
    def __init__(self, spark):
        SQLBase.__init__(self, spark)

    def backfill_workflow(
        self,
        table_names: List[str],
        queries: List[str],
        start_date: str,
        end_date: str,
        freq: str = "d",
        delta: bool = True,
        overwrite: bool = True,
        break_on_fail: bool = True,
    ):
        """Back-fill tables partitioned by day. Automatically creates tables if does not exist.

        Args:
            table_names (list): Name of tables to backfill
            query (list): Queries to backfill with. Date formats should be wrapped in {{}} to be replaced. e.g {{%Y-%m-%d}}
            start_date (str): Start date of backfill
            end_date (str): End date of backfill
            freq (str): Frequency of backfill
            delta (bool): Whether to use delta format
            overwrite (bool): Whether to overwrite existing days
            return_log (bool): Whether to return log of backfill
            break_on_fail (bool): Whether to raise error if query does not run

        """

        if len(table_names) != len(queries):
            raise ValueError("Number of queries must be equal to number of table names")

        for table_name, query in zip(table_names, queries):
            self.logger.info("Backfilling {table_name}")
            self.backfill_table(
                table_name=table_name,
                query=query,
                start_date=start_date,
                end_date=end_date,
                freq=freq,
                delta=delta,
                overwrite=overwrite,
                break_on_fail=break_on_fail,
            )

    def backfill_table(
        self,
        table_name: str,
        query: str,
        start_date: str,
        end_date: str,
        freq: str = "d",
        delta: bool = True,
        overwrite: bool = True,
        break_on_fail: bool = True,
    ):
        """Back-fill a table partitioned by day. Automatically creates table if does not exist.

        Args:
            table_name (str): Name of table to backfill
            query (str): Query to backfill with. Date formats should be wrapped in {{}} to be replaced. e.g {{%Y-%m-%d}}
            start_date (str): Start date of backfill
            end_date (str): End date of backfill
            freq (str): Frequency of backfill
            delta (bool): Whether to use delta format
            overwrite (bool): Whether to overwrite existing days
            return_log (bool): Whether to return log of backfill
            break_on_fail (bool): Whether to raise error if query does not run

        """
        table_creation_sql = (
            self.delta_table_creation_sql if delta else self.parquet_table_creation_sql
        )

        table_append_sql = (
            self.delta_table_append_sql
            if delta and overwrite
            else self.parquet_table_append_sql
        )

        create_table = self._table_does_not_exist(table_name)

        def run_query(table_name, query, date):
            try:
                self.logger.info(f"Backfilling {date.strftime('%Y-%m-%d')}")
                self.run_query(table_append_sql(table_name, query, date))
            except Exception as e:
                if break_on_fail:
                    raise e
                else:
                    self.logger.error(f"{date.strftime('%Y-%m-%d')}: {e}")

        def run_query_with_day_check(table_name, query, date):
            if self._day_does_not_exist(table_name, date):
                run_query(table_name, query, date)
            else:
                self.logger.info(
                    f"Skipping {date.strftime('%Y-%m-%d')} as it already exists"
                )

        pbar = tqdm(pd.date_range(start=start_date, end=end_date, freq=freq))
        for date in pbar:
            pbar.set_description(f"Backfilling {date.strftime('%Y-%m-%d')}")
            if create_table:
                self.logger.info(
                    f"Creating new table {table_name} using {'delta' if delta else 'parquet'}"
                )
                self.run_query(table_creation_sql(table_name, query, date))
                create_table = False
            else:
                if overwrite:
                    run_query(table_name, query, date)
                else:
                    run_query_with_day_check(table_name, query, date)
        return

    def parquet_table_creation_sql(self, table, query, day):
        return f"""
        create table if not exists {table}
        using parquet
        partitioned by (day)
        as
        select *
        from (
        {self.format_query_date(query ,day)}
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
        {self.format_query_date(query ,day)}
        )
        """

    def parquet_table_append_sql(self, table, query, day):
        return f"""
        insert into table {table}
        select *
        from (
        {self.format_query_date(query ,day)}
        )
        """

    def delta_table_append_sql(self, table, query, day):
        return (
            f"""delete from {table} where day = '{day}'""",
            f"""insert into table {table}
        select *
        from (
        {self.format_query_date(query ,day)}
        )
        """,
        )

    def _table_does_not_exist(self, dataset):
        """Check if dataset exists"""
        try:
            _ = self.sample(dataset, verbose=False)
            return False
        except AnalysisException:
            return True

    def _day_does_not_exist(self, dataset, day):
        return (
            len(self.sample(dataset, days=day.strftime("%Y-%m-%d"), verbose=False)) == 0
        )

    def format_query_date(self, query, day):
        """Format dates wrapped in {{}}"""

        def replace(match):
            date_format = match.group()[2:-2]
            return day.strftime(date_format)

        return re.sub(r"\{{.*?\}}", replace, query)
