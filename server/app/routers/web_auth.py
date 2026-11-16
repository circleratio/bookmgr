from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    client_key,
    require_same_origin,
    verify_api_key,
)

router = APIRouter(dependencies=[Depends(require_same_origin)])


def get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


def _cookie_secure(request: Request) -> bool:
    """Marks the session cookie Secure when COOKIE_SECURE is set, or whenever
    the request itself arrived over HTTPS, so a forgotten COOKIE_SECURE
    behind Caddy still yields a Secure cookie. The scheme reflects
    X-Forwarded-Proto only from uvicorn's trusted proxies (forwarded_allow_ips,
    127.0.0.1 by default), so clients cannot spoof it."""
    return request.app.state.cookie_secure or request.url.scheme == "https"


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

    token = request.app.state.sessions.create()
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
        max_age=SESSION_TTL_SECONDS,
    )
    return response


@router.post("/logout")
def logout(request: Request):
    request.app.state.sessions.revoke(request.cookies.get(SESSION_COOKIE_NAME))
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
    )
    return response
