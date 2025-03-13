import dagster as dg
from assets import file_sensor, automation_sensor
import assets


rano_assets = dg.load_assets_from_modules([assets])

defs = dg.Definitions(
    assets=rano_assets,
    sensors=[file_sensor, automation_sensor],
)
