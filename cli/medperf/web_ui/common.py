import logging
from pathlib import Path

import anyio
from fastapi import HTTPException, Security
from fastapi.security import APIKeyCookie, APIKeyHeader
from fastapi.templating import Jinja2Templates
from importlib import resources

from fastapi.requests import Request
from medperf import config
from starlette.responses import RedirectResponse
from pydantic.datetime_parse import parse_datetime

from medperf.enums import Status
from medperf.web_ui.auth import (
    security_token,
    AUTH_COOKIE_NAME,
    API_KEY_NAME,
    NotAuthenticatedException,
)
import uuid
import time

from medperf.account_management.account_management import read_user_account

templates_folder_path = Path(resources.files("medperf.web_ui")) / "templates"
templates = Jinja2Templates(directory=templates_folder_path)

logger = logging.getLogger(__name__)

ALLOWED_PATHS = ["/events", "/notifications", "/current_task", "/fetch-yaml"]


def generate_uuid():
    return str(uuid.uuid4())


def initialize_state_task(request: Request, task_name: str) -> str:
    form_data = dict(anyio.run(lambda: request.form()))
    new_task_id = generate_uuid()
    config.ui.set_task_id(new_task_id)
    config.ui.set_request(request)
    request.app.state.task = {
        "id": new_task_id,
        "name": task_name,
        "running": True,
        "logs": [],
        "formData": form_data,
    }
    request.app.state.task_running = True

    return new_task_id


def reset_state_task(request: Request):
    current_task = request.app.state.task
    current_task["running"] = False
    if len(request.app.state.old_tasks) == 10:
        request.app.state.old_tasks.pop(0)
    request.app.state.old_tasks.append(current_task)
    request.app.state.task = {
        "id": "",
        "name": "",
        "running": False,
        "logs": [],
        "formData": {},
    }
    request.app.state.task_running = False


def add_notification(
    request: Request, message: str, return_response: dict, url: str = ""
):
    if return_response["status"] == "failed":
        message += f": {return_response['error']}"
    request.app.state.new_notifications.append(
        {
            "id": generate_uuid(),
            "message": message,
            "type": return_response["status"],
            "read": False,
            "timestamp": time.time(),
            "url": url,
        }
    )


def custom_exception_handler(request: Request, exc: Exception):
    # Log the exception details
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    # Prepare the context for the error page
    context = {"request": request, "exception": exc}

    if "You are not logged in" in str(exc):
        return RedirectResponse("/medperf_login?redirect=true")

    # Return a detailed error page
    return templates.TemplateResponse("error.html", context, status_code=500)


def sort_associations_display(associations: list[dict]) -> list[dict]:
    """
    Sorts associations:
    - by approval status (pending, approved, rejected)
    - by date (recent first)
    Args:
        associations: associations to sort
    Returns: sorted list
    """

    approval_status_order = {
        Status.PENDING: 0,
        Status.APPROVED: 1,
        Status.REJECTED: 2,
    }

    def assoc_sorting_key(assoc):
        # lower status - first
        status_order = approval_status_order.get(assoc["approval_status"], -1)
        # recent associations - first
        date_order = -parse_datetime(
            assoc["approved_at"] or assoc["created_at"]
        ).timestamp()
        return status_order, date_order

    return sorted(associations, key=assoc_sorting_key)


api_key_cookie = APIKeyCookie(name=AUTH_COOKIE_NAME, auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def is_logged_in():
    return read_user_account() is not None


def check_user_ui(
    request: Request,
    token: str = Security(api_key_cookie),
):
    request.app.state.logged_in = is_logged_in()
    if token == security_token:
        return True
    else:
        login_url = f"/security_check?redirect_url={request.url.path}"
        raise NotAuthenticatedException(redirect_url=login_url)


def check_user_api(
    request: Request,
    token: str = Security(api_key_cookie),
):
    request_path = request.url.path

    request.app.state.logged_in = is_logged_in()
    if request.app.state.task_running:
        if not any(request_path.startswith(path) for path in ALLOWED_PATHS):
            raise HTTPException(
                status_code=400,
                detail="A task is currently running, please wait until it is finished",
            )
    if token == security_token:
        return True
    else:
        raise HTTPException(status_code=401, detail="Not authorized")
