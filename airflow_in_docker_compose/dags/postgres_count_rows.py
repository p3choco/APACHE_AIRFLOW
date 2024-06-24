from airflow.models.baseoperator import BaseOperator
from airflow.hooks.postgres_hook import PostgresHook

class PostgreSQLCountRows(BaseOperator):
    def __init__(self,
                 table_name,
                 postgres_conn_id='postgres_default',
                 **kwargs) -> None:
        super().__init__(**kwargs)
        self.table_name = table_name
        self.postgres_conn_id = postgres_conn_id

    def execute(self, context):
        hook = PostgresHook(postgress_conn_id=self.postgres_conn_id)
        result = hook.get_first(f'SELECT COUNT(*) FROM {self.table_name};')
        rows_num = result[0] if result else 0
        context['ti'].xcom_push(key='rows_number', value=rows_num)