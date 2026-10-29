"""Request-local nonces for trusted Django and Wagtail rendering paths."""

from contextvars import ContextVar
from functools import wraps

from csp.middleware import CSPMiddleware
from django.utils.html import format_html
from django.utils.safestring import mark_safe

_request = ContextVar("bakery_csp_request", default=None)


def current_nonce():
    request = _request.get()
    return str(request.csp_nonce) if request is not None else ""


class StrictCSPMiddleware(CSPMiddleware):
    # Django adapts this synchronous middleware for ASGI while preserving
    # ContextVars. Keep the request binding alive through template rendering.
    async_capable = False

    def __call__(self, request):
        token = _request.set(request)
        try:
            return super().__call__(request)
        finally:
            _request.reset(token)


def install_wagtail_chooser_nonce():
    """Adapt Wagtail 7's Python-generated chooser initializer, exactly once.

    Wagtail's BaseChooser appends its own final script outside any template.
    Only that known initializer receives the nonce, never arbitrary response
    HTML, rich text, or scripts inside the widget's rendered content.
    """
    from wagtail.admin.widgets.chooser import BaseChooser

    if getattr(BaseChooser.render, "_bakery_csp_nonce", False):
        return
    original_render = BaseChooser.render

    @wraps(original_render)
    def render_with_nonce(self, name, value, attrs=None, renderer=None):
        output = original_render(self, name, value, attrs=attrs, renderer=renderer)
        nonce = current_nonce()
        if not nonce:
            return output
        prefix, marker, initializer = output.rpartition("<script>")
        if marker and initializer.endswith("</script>"):
            return format_html(
                '{}<script nonce="{}">{}',
                mark_safe(prefix),
                nonce,
                mark_safe(initializer),
            )
        return output

    render_with_nonce._bakery_csp_nonce = True
    BaseChooser.render = render_with_nonce
