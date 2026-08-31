from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator

from .contact import phone_to_href, validate_contact_email

HTTP_SCHEMES = {"http", "https"}
EXTERNAL_SCHEMES = HTTP_SCHEMES | {"mailto", "tel"}


def validate_external_url(value: str) -> str:
    value = value.strip()
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    if scheme not in EXTERNAL_SCHEMES:
        raise ValueError("Use an HTTP(S), mailto, or tel URL.")

    if scheme in HTTP_SCHEMES:
        try:
            URLValidator(schemes=HTTP_SCHEMES)(value)
        except ValidationError as error:
            raise ValueError("Enter a complete HTTP(S) URL.") from error
    elif scheme == "mailto":
        if not parsed.path or parsed.query or parsed.fragment:
            raise ValueError("Email links cannot contain query strings or fragments.")
        validate_contact_email(parsed.path)
    else:
        if not parsed.path or parsed.query or parsed.fragment:
            raise ValueError("Phone links cannot contain query strings or fragments.")
        phone_to_href(parsed.path)

    return value
