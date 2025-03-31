# Setting up the Local Airflow server for the pipeline

- Run `docker build . -t <your_desired_image_name_here>` to build the local Airflow image
- In this directory, edit the `.env.example` file according to the Airflow image named above, your directory paths, desired username/password for the Airflow admin user and your user's UID/GID in the host system.
  - If you built the pipeline image with a non-standard name, also edit the `RANO_DOCKER_IMAGE_NAME` field according to the name you used.
- Rename the `.env.example` file to `.env`
- Run `docker compose up` to start the required Containers for Airflow