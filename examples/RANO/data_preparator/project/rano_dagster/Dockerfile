FROM python:3.12-slim

ENV DAGSTER_HOME=/project/dagster_home/
RUN mkdir -p $DAGSTER_HOME && mkdir -p /project
COPY requirements.txt /project/requirements.txt
RUN pip install -r /project/requirements.txt

COPY /dagster_home/ $DAGSTER_HOME/
COPY assets.py definitions.py /project/
COPY .env /project/.env

WORKDIR /project
EXPOSE 3000
ENTRYPOINT [ "dagster", "dev", "-w", "/project/dagster_home/workspace.yaml", "-h", "0.0.0.0", "-p", "3000" ]