from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bakerydemo.base.i18n import UnsupportedLocale
from bakerydemo.base.semi_e187.english import (
    TranslationCatalogError,
    translate_import_plan,
)
from bakerydemo.base.semi_e187.parser import parse_source_site
from bakerydemo.base.semi_e187.schema import SourceValidationError
from bakerydemo.base.semi_e187.translation_publisher import (
    TranslationPublishError,
    format_translation_dry_run,
    format_translation_result,
    publish_translations,
    validate_translation_targets,
)


class Command(BaseCommand):
    help = "Validate, preview, or publish SEMI E187 English translations."

    def add_arguments(self, parser):
        parser.add_argument("--html-dir", type=Path, required=True)
        parser.add_argument("--asset-dir", type=Path, required=True)
        parser.add_argument("--home-id", type=int, default=60)
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--publish", action="store_true")

    def handle(self, *args, **options):
        try:
            source_plan = parse_source_site(
                options["html_dir"],
                options["asset_dir"],
            )
            translated_plan = translate_import_plan(source_plan)
            targets = validate_translation_targets(
                source_plan,
                options["home_id"],
            )
        except (
            SourceValidationError,
            TranslationCatalogError,
            TranslationPublishError,
            UnsupportedLocale,
        ) as error:
            raise CommandError(str(error)) from error

        if options["dry_run"]:
            self.stdout.write(format_translation_dry_run(targets))
            return

        try:
            result = publish_translations(
                source_plan,
                translated_plan,
                options["home_id"],
            )
        except (TranslationPublishError, UnsupportedLocale) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(format_translation_result(result))
