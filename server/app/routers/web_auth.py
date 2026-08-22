from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..auth import SESSION_COOKIE_NAME

router = APIRouter()


def get_templates(request: Request) -> Jinja2Templates:
    return request.app.state.templates


@router.get("/login")
def login_form(request: Request):
    return get_templates(request).TemplateResponse(request, "login.html", {"error": None})


@router.post("/login")
def login(request: Request, api_key: str = Form(...)):
    if api_key != request.app.state.api_key:
        return get_templates(request).TemplateResponse(
            request,
            "login.html",
            {"error": "APIキーが正しくありません"},
            status_code=401,
        )
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(SESSION_COOKIE_NAME, api_key, path="/", httponly=True, samesite="lax")
    return response


@router.post("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return response
