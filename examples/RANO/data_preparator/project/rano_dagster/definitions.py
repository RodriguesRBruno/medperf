import dagster as dg
from assets import file_sensor
import assets
from dagster_docker import PipesDockerClient

rano_assets = dg.load_assets_from_modules([assets])

rano_pipeline_job = dg.define_asset_job(name="rano_pipeline_job")

defs = dg.Definitions(
    assets=rano_assets,
    sensors=[file_sensor],
    resources={"docker_pipes_client": PipesDockerClient()},
    jobs=[rano_pipeline_job],
)
