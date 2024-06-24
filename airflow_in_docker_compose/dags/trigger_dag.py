from datetime import timedelta
from airflow import DAG
from airflow.decorators import task
from datetime import datetime
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator
from airflow.utils.trigger_rule import TriggerRule
from airflow.sensors.filesystem import FileSensor
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.operators.subdag import SubDagOperator
from airflow.models import Variable
from airflow.sensors.external_task import ExternalTaskSensor
import pendulum
from airflow.utils.task_group import TaskGroup
from airflow import settings
from airflow.models import DagRun
from slack import WebClient
from slack.errors import SlackApiError
from airflow.models import Connection
from airflow.hooks.base_hook import BaseHook
import json
import os
from airflow.models import Variable
from custom_file_sensor import CustomFileSensor

Variable.set('path_variable', '/opt/airflow/TRIGGER_FILE')

def send_log_to_slack(**kwargs):

    dag_id = kwargs['task'].dag_id
    execution_date = kwargs['execution_date']
    message = f'dag_id: {dag_id}; execution_date: {execution_date}'
    token = Variable.get('slack_token')

    slack_token = token
    client = WebClient(token=slack_token)
    os.environ["AIRFLOW__CORE__HIDE_SENSITIVE_VAR_CONN_FIELDS"] = "True"
    try:
        response = client.chat_postMessage(
            channel="random",
            text=message)
    except SlackApiError as e:
        assert e.response["error"]

def get_execution_date(dt, **kwargs):
    session = settings.Session()
    dr = session.query(DagRun)\
        .filter(DagRun.dag_id == kwargs['task'].external_dag_id)\
        .order_by(DagRun.execution_date.desc())\
        .first()
    return dr.execution_date

def show_message(**kwargs):
    ti = kwargs['ti']
    message = ti.xcom_pull(key='message_sended', dag_id='xdag_id_1', include_prior_dates=True)
    print(message)
    print(kwargs)

with DAG(dag_id='trigger_dag_id',
         schedule=None,
         ) as dag:

    path_variable = Variable.get('path_variable', default_var='file.txt')

    file_sensor = CustomFileSensor(
        task_id='file_sensor',
        filepath=f'{path_variable}/file.txt',
        fs_conn_id='fs_default',
        dag=dag
    )

    triger_dag_run_operator = TriggerDagRunOperator(
        task_id='triger_dag_run_operator',
        trigger_dag_id='xdag_id_1',
        dag=dag
    )

    with TaskGroup('task_troup') as task_group:

        external_task_sensor = ExternalTaskSensor(
            external_task_id=None,
            external_dag_id='xdag_id_1',
            task_id='dag_1_task_sensor',
            execution_date_fn=get_execution_date
        )

        show_message = PythonOperator(
                task_id='show_message_operator',
                python_callable=show_message,
                provide_context=True,
                dag=dag
            )

        rm_bash_operator = BashOperator(
            task_id='rm_bash_operator',
            bash_command=f'rm {path_variable}/file.txt',
            dag=dag
        )

        cr_bash_operator = BashOperator(
            task_id='cr_bash_operator',
            bash_command=f'touch {path_variable}/finished_'+'{{ts_nodash}}',
            dag=dag
        )

        external_task_sensor >> show_message >> rm_bash_operator >> cr_bash_operator

    send_slack = PythonOperator(
        task_id='send_slack',
        python_callable=send_log_to_slack,
        dag=dag,
    )

    file_sensor >> triger_dag_run_operator >> task_group >> send_slack


