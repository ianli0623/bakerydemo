import copy
import json

from django.utils.translation import gettext_lazy
from wagtail.admin.ui.tables import DateColumn
from wagtail.admin.views.generic.history import (
    ActionColumn,
    HistoryView,
    LogEntryUserColumn,
)

# These values describe Wagtail's publication state, rather than editor-authored
# page content. Autosave and publish can change them without changing the page.
REVISION_STATE_FIELDS = {
    "first_published_at",
    "has_unpublished_changes",
    "last_published_at",
    "latest_revision",
    "latest_revision_created_at",
    "live",
    "live_revision",
}
REVISION_ACTIONS = {"wagtail.edit", "wagtail.publish"}


def revision_content_signature(log_entry):
    """Return a stable signature of the editor-authored revision content."""
    if not log_entry.revision_id or not log_entry.revision:
        return None

    content = {
        key: value
        for key, value in log_entry.revision.content.items()
        if key not in REVISION_STATE_FIELDS
    }
    return json.dumps(content, ensure_ascii=False, sort_keys=True, default=str)


def collapse_equivalent_revision_entries(entries):
    """Keep one history row for adjacent autosave/publish copies of a revision."""
    collapsed = []
    previous_signature = None

    for entry in entries:
        signature = (
            revision_content_signature(entry)
            if entry.action in REVISION_ACTIONS
            else None
        )
        if signature is not None and signature == previous_signature:
            continue

        collapsed.append(entry)
        previous_signature = signature

    # Comparison links should skip hidden metadata-only autosave revisions.
    older_revision_id = None
    for entry in reversed(collapsed):
        if entry.revision_id:
            entry.previous_revision_id = older_revision_id
            older_revision_id = entry.revision_id

    return collapsed


class CollapsedPageHistoryActionColumn(ActionColumn):
    """Expose revision actions on the retained publish row."""

    def get_actions(self, instance, parent_context):
        if instance.action != "wagtail.publish":
            return super().get_actions(instance, parent_context)

        revision_entry = copy.copy(instance)
        revision_entry.action = "wagtail.edit"
        revision_entry.content_changed = True
        return super().get_actions(revision_entry, parent_context)


def get_collapsed_page_history_queryset(view):
    queryset = HistoryView.get_queryset(view)
    return collapse_equivalent_revision_entries(list(queryset))


def get_collapsed_page_history_columns(view):
    return [
        CollapsedPageHistoryActionColumn(
            "message",
            label=gettext_lazy("Action"),
            object=view.object,
            url_names={
                "edit": view.edit_url_name,
                "revisions_view": view.revisions_view_url_name,
                "revisions_revert": view.revisions_revert_url_name,
                "revisions_compare": view.revisions_compare_url_name,
                "revisions_unschedule": view.revisions_unschedule_url_name,
            },
            user_can_unschedule=view.user_can_unschedule(),
        ),
        LogEntryUserColumn("user", label=gettext_lazy("User"), width="25%"),
        DateColumn("timestamp", label=gettext_lazy("Date"), width="15%"),
    ]
