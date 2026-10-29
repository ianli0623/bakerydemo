from django import template

from bakerydemo.account_security.csp import current_nonce

register = template.Library()
register.simple_tag(current_nonce, name="csp_nonce")
