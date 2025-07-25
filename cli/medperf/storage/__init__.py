import os
import shutil
import time

from medperf import config
from medperf.config_management import read_config, write_config, ConfigManager

from .utils import full_folder_path


def override_storage_config_paths():
    for folder in config.storage:
        setattr(config, folder, full_folder_path(folder))


def init_storage():
    """Builds the general medperf folder structure."""
    for folder in config.storage:
        folder = getattr(config, folder)
        os.makedirs(folder, exist_ok=True)


def __apply_logs_migrations(config_p: ConfigManager):
    if "logs_folder" not in config_p.storage:
        return

    src_dir = os.path.join(config_p.storage["logs_folder"], "logs")
    tgt_dir = config.logs_storage

    shutil.move(src_dir, tgt_dir)

    del config_p.storage["logs_folder"]


def __apply_training_migrations(config_p: ConfigManager):

    for folder in [
        "aggregators_folder",
        "cas_folder",
        "training_events_folder",
        "training_folder",
    ]:
        if folder not in config_p.storage:
            # Assuming for now all folders are always moved together
            # I used here "benchmarks_folder" arbitrarily
            config_p.storage[folder] = config_p.storage["benchmarks_folder"]


def __apply_login_tracking_migrations(config_p: ConfigManager):
    # Migration for tracking the login timestamp (i.e., refresh token issuance timestamp)
    if config.credentials_keyword in config_p.active_profile:
        # So the user is logged in
        if "logged_in_at" not in config_p.active_profile[config.credentials_keyword]:
            # Apply migration. We will set it to an old time to make sure users no longer
            # face a confusing error about refresh token expiration.
            config_p.active_profile[config.credentials_keyword]["logged_in_at"] = (
                time.time() - 2 * config.token_absolute_expiry
            )


def __apply_results_to_executions_migrations(config_p):
    if "results_folder" not in config_p.storage:
        return

    results_base = config_p.storage["results_folder"]
    execs_folder = os.path.join(results_base, config.executions_folder)

    # Move old results into the execution path
    results_folder = os.path.join(results_base, "results")
    results_exist = os.path.exists(results_folder) and os.listdir(results_folder)
    if results_exist:
        shutil.move(results_folder, execs_folder)

    del config_p.storage["results_folder"]
    config_p.storage["executions_folder"] = results_base


def apply_configuration_migrations():
    if not os.path.exists(config.config_path):
        return

    config_p = read_config()
    __apply_logs_migrations(config_p)
    __apply_training_migrations(config_p)
    __apply_login_tracking_migrations(config_p)
    __apply_results_to_executions_migrations(config_p)

    write_config(config_p)
