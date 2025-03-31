FROM apache/airflow:2.10.5
USER airflow
RUN pip install --no-cache-dir apache-airflow==2.10.5 'apache-airflow[singularity]'
COPY ./airflow.cfg /opt/airflow/config/airflow.cfg
COPY --chown=airflow:root dags/ /opt/airflow/dags/