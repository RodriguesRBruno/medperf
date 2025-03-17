import dagster as dg
from assets import file_sensor
import assets
from dagster_docker import PipesDockerClient

rano_assets = dg.load_assets_from_modules([assets])

defs = dg.Definitions(
    assets=rano_assets,
    sensors=[file_sensor],
    resources={"docker_pipes_client": PipesDockerClient()},
)
