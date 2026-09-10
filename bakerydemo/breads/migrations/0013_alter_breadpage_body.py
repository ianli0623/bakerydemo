import wagtail.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("breads", "0012_add_case_study_security_heading"),
    ]

    operations = [
        migrations.AlterField(
            model_name="breadpage",
            name="body",
            field=wagtail.fields.StreamField(
                [
                    ("heading_block", 2),
                    ("paragraph_block", 3),
                    ("image_block", 6),
                    ("block_quote", 12),
                    ("card_grid", 22),
                    ("document_table", 26),
                    ("process_steps", 33),
                    ("case_study", 39),
                    ("embed_block", 40),
                ],
                blank=True,
                block_lookup={
                    0: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {"form_classname": "title", "required": True},
                    ),
                    1: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "blank": True,
                            "choices": [("h2", "H2"), ("h3", "H3"), ("h4", "H4")],
                            "required": False,
                        },
                    ),
                    2: (
                        "wagtail.blocks.StructBlock",
                        [[("heading_text", 0), ("size", 1)]],
                        {},
                    ),
                    3: (
                        "wagtail.blocks.RichTextBlock",
                        (),
                        {
                            "description": "A rich text paragraph",
                            "icon": "pilcrow",
                            "preview_value": '\n            <h2>Our bread pledge</h2>\n            <p>As a bakery, <b>breads</b> have <i>always</i> been in our hearts.\n            <a href="https://en.wikipedia.org/wiki/Staple_food">Staple foods</a>\n            are essential for society, and – bread is the tastiest of all.\n            We love to transform batters and doughs into baked goods with a firm\n            dry crust and fluffy center.</p>\n            ',
                            "template": "blocks/paragraph_block.html",
                        },
                    ),
                    4: (
                        "wagtail.images.blocks.ImageChooserBlock",
                        (),
                        {"required": True},
                    ),
                    5: ("wagtail.blocks.CharBlock", (), {"required": False}),
                    6: (
                        "wagtail.blocks.StructBlock",
                        [[("image", 4), ("caption", 5), ("attribution", 5)]],
                        {},
                    ),
                    7: ("wagtail.blocks.TextBlock", (), {}),
                    8: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {"blank": True, "label": "e.g. Mary Berry", "required": False},
                    ),
                    9: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                ("default", "Default"),
                                ("highlight", "Highlight"),
                            ],
                            "required": False,
                        },
                    ),
                    10: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [("default", "Default"), ("large", "Large")],
                            "required": False,
                        },
                    ),
                    11: (
                        "wagtail.blocks.StructBlock",
                        [[("theme", 9), ("text_size", 10)]],
                        {"collapsed": True},
                    ),
                    12: (
                        "wagtail.blocks.StructBlock",
                        [[("text", 7), ("attribute_name", 8), ("settings", 11)]],
                        {},
                    ),
                    13: ("wagtail.blocks.CharBlock", (), {"required": True}),
                    14: ("wagtail.blocks.TextBlock", (), {"required": False}),
                    15: (
                        "wagtail.blocks.ChoiceBlock",
                        [],
                        {
                            "choices": [
                                ("two", "Two columns"),
                                ("three", "Three columns"),
                                ("four", "Four columns"),
                            ]
                        },
                    ),
                    16: ("wagtail.blocks.TextBlock", (), {"required": True}),
                    17: (
                        "wagtail.blocks.CharBlock",
                        (),
                        {
                            "help_text": "不需要連結時請留空；設定連結目標時才需要填寫。",
                            "required": False,
                        },
                    ),
                    18: ("wagtail.blocks.PageChooserBlock", (), {"required": False}),
                    19: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("label", 17),
                                ("internal_page", 18),
                                ("external_url", 5),
                                ("fragment", 5),
                            ]
                        ],
                        {"required": False},
                    ),
                    20: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("number", 5),
                                ("eyebrow", 5),
                                ("title", 13),
                                ("summary", 16),
                                ("link", 19),
                            ]
                        ],
                        {},
                    ),
                    21: ("wagtail.blocks.ListBlock", (20,), {"min_num": 1}),
                    22: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("eyebrow", 5),
                                ("heading", 13),
                                ("introduction", 14),
                                ("layout", 15),
                                ("cards", 21),
                            ]
                        ],
                        {},
                    ),
                    23: (
                        "wagtail.blocks.RegexBlock",
                        ("[A-Za-z][A-Za-z0-9_-]*\\Z",),
                        {
                            "error_messages": {
                                "invalid": "Use letters, numbers, hyphens, and underscores only."
                            }
                        },
                    ),
                    24: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("number", 13),
                                ("title", 13),
                                ("summary", 16),
                                ("status", 13),
                                ("link", 19),
                            ]
                        ],
                        {},
                    ),
                    25: ("wagtail.blocks.ListBlock", (24,), {"min_num": 1}),
                    26: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("heading", 13),
                                ("caption", 5),
                                ("anchor_id", 23),
                                ("rows", 25),
                            ]
                        ],
                        {},
                    ),
                    27: ("wagtail.blocks.CharBlock", (), {}),
                    28: ("wagtail.blocks.ListBlock", (27,), {"required": False}),
                    29: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("label", 17),
                                ("internal_page", 18),
                                ("external_url", 5),
                                ("fragment", 5),
                            ]
                        ],
                        {},
                    ),
                    30: ("wagtail.blocks.ListBlock", (29,), {"required": False}),
                    31: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("number", 13),
                                ("title", 13),
                                ("summary", 16),
                                ("checklist", 28),
                                ("resource_links", 30),
                            ]
                        ],
                        {},
                    ),
                    32: ("wagtail.blocks.ListBlock", (31,), {"min_num": 1}),
                    33: (
                        "wagtail.blocks.StructBlock",
                        [[("heading", 13), ("introduction", 14), ("steps", 32)]],
                        {},
                    ),
                    34: (
                        "wagtail.blocks.StructBlock",
                        [[("label", 13), ("value", 13)]],
                        {},
                    ),
                    35: ("wagtail.blocks.ListBlock", (34,), {"min_num": 1}),
                    36: ("wagtail.blocks.RichTextBlock", (), {"required": True}),
                    37: (
                        "wagtail.blocks.StructBlock",
                        [[("title", 13), ("summary", 16)]],
                        {},
                    ),
                    38: ("wagtail.blocks.ListBlock", (37,), {"min_num": 1}),
                    39: (
                        "wagtail.blocks.StructBlock",
                        [
                            [
                                ("case_label", 13),
                                ("company", 13),
                                ("product", 13),
                                ("certification_status", 13),
                                ("summary", 16),
                                ("metadata", 35),
                                ("equipment_image", 4),
                                ("equipment_caption", 5),
                                ("challenge_heading", 13),
                                ("challenge", 36),
                                ("solution_heading", 13),
                                ("solution", 36),
                                ("security_controls_heading", 13),
                                ("security_controls", 38),
                                ("outcome_image", 4),
                                ("outcome_caption", 5),
                            ]
                        ],
                        {},
                    ),
                    40: (
                        "wagtail.embeds.blocks.EmbedBlock",
                        (),
                        {
                            "description": "An embedded video or other media",
                            "help_text": "Insert an embed URL e.g https://www.youtube.com/watch?v=SGJFWirQ3ks",
                            "icon": "media",
                            "preview_template": "base/preview/static_embed_block.html",
                            "preview_value": "https://www.youtube.com/watch?v=mwrGSfiB1Mg",
                            "template": "blocks/embed_block.html",
                        },
                    ),
                },
                verbose_name="Page body",
            ),
        ),
    ]
