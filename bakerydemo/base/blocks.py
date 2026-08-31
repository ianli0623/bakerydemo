import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from wagtail.blocks import (
    CharBlock,
    ChoiceBlock,
    ListBlock,
    PageChooserBlock,
    RegexBlock,
    RichTextBlock,
    StreamBlock,
    StructBlock,
    StructBlockValidationError,
    TextBlock,
)
from wagtail.embeds.blocks import EmbedBlock
from wagtail.images import get_image_model
from wagtail.images.blocks import ImageChooserBlock

from .link_validation import HTTP_SCHEMES, validate_external_url


def get_image_api_representation(image, filter_spec=None):
    """
    Build the API representation for an image used in a StreamField block.

    When ``filter_spec`` is provided, also serialise a ``meta.rendition`` with
    the details of the rendered image (same keys as ``ImageRenditionField``).
    """
    representation = {
        "id": image.pk,
        "title": image.title,
        "meta": {
            "type": type(image)._meta.label,
            "download_url": image.file.url,
        },
    }
    if filter_spec:
        rendition = image.get_rendition(filter_spec)
        representation["meta"]["rendition"] = {
            "url": rendition.url,
            "full_url": rendition.full_url,
            "width": rendition.width,
            "height": rendition.height,
            "alt": rendition.alt,
        }
    return representation


class ContentLinkBlock(StructBlock):
    label = CharBlock(required=True)
    internal_page = PageChooserBlock(required=False)
    external_url = CharBlock(required=False)
    fragment = CharBlock(required=False)

    fragment_pattern = re.compile(r"[A-Za-z][A-Za-z0-9_-]*\Z")

    def clean(self, value):
        cleaned = super().clean(value)
        if not cleaned:
            return cleaned
        errors = {}
        internal_page = cleaned["internal_page"]
        external_url = cleaned["external_url"].strip()
        fragment = cleaned["fragment"].strip()
        if internal_page and external_url:
            destination_error = ValidationError(
                "Choose an internal page or an external URL, not both."
            )
            errors["internal_page"] = destination_error
            errors["external_url"] = destination_error
        if external_url:
            try:
                validate_external_url(external_url)
            except ValueError:
                errors["external_url"] = ValidationError(
                    "Use a complete HTTP(S), mailto, or tel URL."
                )
        if fragment and not internal_page:
            errors["fragment"] = ValidationError(
                "Choose an internal page before adding a fragment."
            )
        elif fragment and not self.fragment_pattern.fullmatch(fragment):
            errors["fragment"] = ValidationError(
                "Use letters, numbers, hyphens, and underscores only."
            )
        if errors:
            raise StructBlockValidationError(block_errors=errors)
        return cleaned

    def get_api_representation(self, value, context=None):
        if not value or not value.get("label"):
            return None
        internal_page = value["internal_page"]
        if internal_page and internal_page.url:
            href = urlsplit(internal_page.url).path or "/"
            fragment = value["fragment"].strip()
            if fragment:
                href = f"{href}#{fragment}"
            return {
                "label": value["label"],
                "kind": "internal",
                "href": href,
                "new_tab": False,
            }

        external_url = value["external_url"]
        if external_url:
            try:
                external_url = validate_external_url(external_url)
            except ValueError:
                external_url = ""
            if external_url:
                scheme = urlsplit(external_url).scheme.lower()
                return {
                    "label": value["label"],
                    "kind": "external",
                    "href": external_url,
                    "new_tab": scheme in HTTP_SCHEMES,
                }

        return {
            "label": value["label"],
            "kind": "disabled",
            "href": None,
            "new_tab": False,
        }


class CardBlock(StructBlock):
    number = CharBlock(required=False)
    eyebrow = CharBlock(required=False)
    title = CharBlock(required=True)
    summary = TextBlock(required=True)
    link = ContentLinkBlock(required=False)


class CardGridBlock(StructBlock):
    eyebrow = CharBlock(required=False)
    heading = CharBlock(required=True)
    introduction = TextBlock(required=False)
    layout = ChoiceBlock(
        choices=[
            ("two", "Two columns"),
            ("three", "Three columns"),
            ("four", "Four columns"),
        ],
        default="three",
    )
    cards = ListBlock(CardBlock(), min_num=1)

    class Meta:
        icon = "grip"
        template = "blocks/card_grid.html"
        description = "A heading and an ordered grid of linked cards"


class DocumentRowBlock(StructBlock):
    number = CharBlock(required=True)
    title = CharBlock(required=True)
    summary = TextBlock(required=True)
    status = CharBlock(required=True)
    link = ContentLinkBlock(required=False)


class DocumentTableBlock(StructBlock):
    heading = CharBlock(required=True)
    caption = CharBlock(required=False)
    anchor_id = RegexBlock(
        r"[A-Za-z][A-Za-z0-9_-]*\Z",
        error_messages={
            "invalid": "Use letters, numbers, hyphens, and underscores only."
        },
    )
    rows = ListBlock(DocumentRowBlock(), min_num=1)

    class Meta:
        icon = "list-ul"
        template = "blocks/document_table.html"
        description = "A titled table of documents and optional links"


class ProcessStepBlock(StructBlock):
    number = CharBlock(required=True)
    title = CharBlock(required=True)
    summary = TextBlock(required=True)
    checklist = ListBlock(CharBlock(), required=False)
    resource_links = ListBlock(ContentLinkBlock(), required=False)


class ProcessStepsBlock(StructBlock):
    heading = CharBlock(required=True)
    introduction = TextBlock(required=False)
    steps = ListBlock(ProcessStepBlock(), min_num=1)

    class Meta:
        icon = "list-ol"
        template = "blocks/process_steps.html"
        description = "An ordered process with checklists and resource links"


class MetadataPairBlock(StructBlock):
    label = CharBlock(required=True)
    value = CharBlock(required=True)


class SecurityControlBlock(StructBlock):
    title = CharBlock(required=True)
    summary = TextBlock(required=True)


class CaseStudyBlock(StructBlock):
    case_label = CharBlock(required=True)
    company = CharBlock(required=True)
    product = CharBlock(required=True)
    certification_status = CharBlock(required=True)
    summary = TextBlock(required=True)
    metadata = ListBlock(MetadataPairBlock(), min_num=1)
    equipment_image = ImageChooserBlock(required=True)
    equipment_caption = CharBlock(required=False)
    challenge_heading = CharBlock(required=True)
    challenge = RichTextBlock(required=True)
    solution_heading = CharBlock(required=True)
    solution = RichTextBlock(required=True)
    security_controls_heading = CharBlock(required=True)
    security_controls = ListBlock(SecurityControlBlock(), min_num=1)
    outcome_image = ImageChooserBlock(required=True)
    outcome_caption = CharBlock(required=False)

    def get_api_representation(self, value, context=None):
        data = super().get_api_representation(value, context)
        data["equipment_image"] = get_image_api_representation(
            value["equipment_image"], "max-1200x800"
        )
        data["outcome_image"] = get_image_api_representation(
            value["outcome_image"], "max-1200x800"
        )
        return data

    class Meta:
        icon = "doc-full"
        template = "blocks/case_study.html"
        description = "A detailed implementation and certification case study"


class CaptionedImageBlock(StructBlock):
    """
    Custom `StructBlock` for utilizing images with associated caption and
    attribution data
    """

    image = ImageChooserBlock(required=True)
    caption = CharBlock(required=False)
    attribution = CharBlock(required=False)

    @cached_property
    def preview_image(self):
        # Cache the image object for previews to avoid repeated queries
        return get_image_model().objects.last()

    def get_preview_value(self):
        return {
            **self.meta.preview_value,
            "image": self.preview_image,
            "caption": self.preview_image.description,
        }

    def get_api_representation(self, value, context=None):
        data = super().get_api_representation(value, context)
        data["image"] = get_image_api_representation(value["image"], "fill-600x338")
        return data

    class Meta:
        icon = "image"
        template = "blocks/captioned_image_block.html"
        preview_value = {"attribution": "The Wagtail Bakery"}
        description = "An image with optional caption and attribution"


class HeadingBlock(StructBlock):
    """
    Custom `StructBlock` that allows the user to select h2 - h4 sizes for headings
    """

    heading_text = CharBlock(classname="title", required=True)
    size = ChoiceBlock(
        choices=[
            ("h2", "H2"),
            ("h3", "H3"),
            ("h4", "H4"),
        ],
        blank=True,
        required=False,
    )

    class Meta:
        icon = "title"
        template = "blocks/heading_block.html"
        preview_value = {"heading_text": "Healthy bread types", "size": "h2"}
        description = "A heading with level two, three, or four"


class ThemeSettingsBlock(StructBlock):
    theme = ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("highlight", "Highlight"),
        ],
        required=False,
        default="default",
    )
    text_size = ChoiceBlock(
        choices=[
            ("default", "Default"),
            ("large", "Large"),
        ],
        required=False,
        default="default",
    )

    class Meta:
        icon = "cog"
        label_format = "Theme: {theme}, Text size: {text_size}"


class BlockQuote(StructBlock):
    """
    Custom `StructBlock` that allows the user to attribute a quote to the author
    """

    text = TextBlock()
    attribute_name = CharBlock(blank=True, required=False, label="e.g. Mary Berry")
    settings = ThemeSettingsBlock(collapsed=True)

    class Meta:
        icon = "openquote"
        template = "blocks/blockquote.html"
        preview_value = {
            "text": (
                "If you read a lot you're well read / "
                "If you eat a lot you're well bread."
            ),
            "attribute_name": "Willie Wagtail",
        }
        description = "A quote with an optional attribution"


# StreamBlocks
class BaseStreamBlock(StreamBlock):
    """
    Define the custom blocks that `StreamField` will utilize
    """

    heading_block = HeadingBlock()
    paragraph_block = RichTextBlock(
        icon="pilcrow",
        template="blocks/paragraph_block.html",
        preview_value=(
            """
            <h2>Our bread pledge</h2>
            <p>As a bakery, <b>breads</b> have <i>always</i> been in our hearts.
            <a href="https://en.wikipedia.org/wiki/Staple_food">Staple foods</a>
            are essential for society, and – bread is the tastiest of all.
            We love to transform batters and doughs into baked goods with a firm
            dry crust and fluffy center.</p>
            """
        ),
        description="A rich text paragraph",
    )
    image_block = CaptionedImageBlock()
    block_quote = BlockQuote()
    card_grid = CardGridBlock()
    document_table = DocumentTableBlock()
    process_steps = ProcessStepsBlock()
    case_study = CaseStudyBlock()
    embed_block = EmbedBlock(
        help_text="Insert an embed URL e.g https://www.youtube.com/watch?v=SGJFWirQ3ks",
        icon="media",
        template="blocks/embed_block.html",
        preview_template="base/preview/static_embed_block.html",
        preview_value="https://www.youtube.com/watch?v=mwrGSfiB1Mg",
        description="An embedded video or other media",
    )
