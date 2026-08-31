import re

from django.core.exceptions import ValidationError
from django.core.validators import validate_email


def phone_to_href(value: str) -> str:
    """Convert an editor-managed phone number into a conservative tel URL."""
    value = value.strip()
    if not value:
        return ""

    extension_match = re.search(
        r"(?:#|,|;ext=|ext\.?|x)\s*(\d+)\s*$",
        value,
        re.IGNORECASE,
    )
    extension = extension_match.group(1) if extension_match else ""
    number_part = value[: extension_match.start()] if extension_match else value
    if re.search(r"[^\d+().\s-]", number_part):
        raise ValueError("Phone number contains unsupported characters.")

    digits = re.sub(r"\D", "", number_part)
    if not digits:
        raise ValueError("Phone number must contain at least one digit.")
    if number_part.count("+") > 1 or (
        "+" in number_part and not number_part.lstrip().startswith("+")
    ):
        raise ValueError("Phone number has a misplaced country prefix.")

    if number_part.lstrip().startswith("+"):
        normalized = f"+{digits}"
    elif digits.startswith("0"):
        normalized = f"+886{digits[1:]}"
    elif digits.startswith("886"):
        normalized = f"+{digits}"
    else:
        normalized = digits

    if extension:
        normalized = f"{normalized},{extension}"
    return f"tel:{normalized}"


def validate_contact_email(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    try:
        validate_email(value)
    except ValidationError as error:
        raise ValueError("Enter a valid email address.") from error
    return value
