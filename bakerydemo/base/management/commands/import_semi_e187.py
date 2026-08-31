from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from bakerydemo.base.semi_e187.parser import parse_source_site
from bakerydemo.base.semi_e187.schema import SourceValidationError
from bakerydemo.base.semi_e187.targets import (
    TargetValidationError,
    format_dry_run,
    validate_targets,
)


class Command(BaseCommand):
    help = "Validate, preview, or publish the SEMI E187 source site."

    def add_arguments(self, parser):
        parser.add_argument("--html-dir", type=Path, required=True)
        parser.add_argument("--asset-dir", type=Path, required=True)
        parser.add_argument("--home-id", type=int, default=60)
        mode = parser.add_mutually_exclusive_group(required=True)
        mode.add_argument("--dry-run", action="store_true")
        mode.add_argument("--publish", action="store_true")

    def handle(self, *args, **options):
        try:
            plan = parse_source_site(options["html_dir"], options["asset_dir"])
            targets = validate_targets(plan, options["home_id"])
        except (SourceValidationError, TargetValidationError) as error:
            raise CommandError(str(error)) from error

        if options["dry_run"]:
            self.stdout.write(format_dry_run(plan, targets))
            return

        from bakerydemo.base.semi_e187.publisher import (
            PublishError,
            format_publish_result,
            publish_import,
        )

        try:
            result = publish_import(plan, targets)
        except PublishError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(format_publish_result(result))
