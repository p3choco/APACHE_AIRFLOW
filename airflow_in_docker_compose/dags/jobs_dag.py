from datetime import timedelta
from airflow import DAG
from airflow.decorators import task
from datetime import datetime
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.hooks.postgres_hook import PostgresHook
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
import uuid
from postgres_count_rows import PostgreSQLCountRows

config = {
    'xdag_id_1': {"start_date": datetime(2024, 5, 27, 15, 3),
                  'table_name': 'table_name_1'},
    'xdag_id_2': {"start_date": datetime(2024, 5, 27, 14),
                  'table_name': 'table_name_2'},
    'xdag_id_3': {
                  "start_date": datetime(2024, 5, 27, 14),
                  'table_name': 'table_name_3'}}

def push_message(**kwargs):
    ti = kwargs['ti']
    run_id = kwargs['run_id']
    ti.xcom_push(key='message_sended', value=f'{run_id} ended')

def log_info(dag_id, database):
    print(f'{dag_id} start processing tables in database: {database}')

@task.branch(task_id='check_if_table_exists')
def check_table_exist(sql_to_check_table_exist,
                      table_name):
    """ callable function to get schema name and after that check if table exist """
    schema = 'public'
    hook = PostgresHook()

    query = hook.get_first(sql=sql_to_check_table_exist.format(schema, table_name))

    if query:
        return 'insert_new_row'
    else:
        return 'create_table'

for dag_id, dag_config in config.items():

    table_name_success = 'table_name_1'
    branch_op = check_table_exist("SELECT * FROM information_schema.tables "
                                           "WHERE table_schema = '{}'"
                                           "AND table_name = '{}';", table_name_success)

    with DAG(dag_id=dag_id,
             schedule=None,
             ) as dag:

        log_info_task = PythonOperator(
            task_id="log_info",
            python_callable=log_info,
            op_args=[dag_id, dag_config['table_name']],
            dag=dag
        )

        gett_current_user = BashOperator(
            task_id='gett_current_user',
            bash_command='whoami',
            dag=dag
        )

        create_table = SQLExecuteQueryOperator(
            task_id='create_table',
            conn_id='postgres_default',
            sql=f'CREATE TABLE {table_name_success}(custom_id integer NOT NULL, user_name VARCHAR (50) NOT NULL, timestamp TIMESTAMP NOT NULL); ',
            dag=dag
        )

        insert_new_row = SQLExecuteQueryOperator(
            task_id='insert_new_row',
            conn_id='postgres_default',
            sql=f'INSERT INTO {table_name_success} VALUES(%s, %s, %s);',
            parameters=(uuid.uuid4().int % 1234,
                        "{{task_instance.xcom_pull(task_ids='gett_current_user')}}",
                        datetime.now()),
            dag=dag,
            trigger_rule=TriggerRule.NONE_FAILED
        )

        query_the_table = PostgreSQLCountRows(
            task_id='query_the_table',
            table_name=table_name_success,
            postgres_conn_id='postgres_default',
            dag=dag
        )

        send_message = PythonOperator(
            task_id='send_message',
            python_callable=push_message,
            provide_context=True,
            dag=dag
        )

        log_info_task >> gett_current_user >> branch_op
        branch_op >> [create_table, insert_new_row]
        create_table >> insert_new_row
        insert_new_row >> query_the_table >> send_message

