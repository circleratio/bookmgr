from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    client_key,
    create_session,
    revoke_session,
    verify_api_key,
)

router = APIRouter()


def get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


@router.get("/login")
def login_form(request: Request):
    return get_templates(request).TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login(request: Request, api_key: str = Form(...)):
    limiter = request.app.state.login_limiter
    key = client_key(request)
    limiter.check(key)

    if not verify_api_key(api_key, request):
        limiter.record_failure(key)
        return get_templates(request).TemplateResponse(
            request,
            "login.html",
            {"error": "APIキーが正しくありません"},
            status_code=401,
        )
    limiter.record_success(key)

    token = create_session(request)
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        path="/",
        httponly=True,
        samesite="lax",
        secure=request.app.state.cookie_secure,
        max_age=SESSION_TTL_SECONDS,
    )
    return response


@router.post("/logout")
def logout(request: Request):
    revoke_session(request, request.cookies.get(SESSION_COOKIE_NAME))
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
