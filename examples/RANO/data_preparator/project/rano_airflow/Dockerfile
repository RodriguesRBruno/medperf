FROM apache/airflow:2.10.5
ARG WORKSPACE_DIR
ARG ROOT_PREP_DIR

RUN pip install --no-cache-dir apache-airflow==2.10.5 'apache-airflow[singularity]'
COPY --chown=airflow:root dags/ /opt/airflow/dags/