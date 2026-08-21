from PySide6.QtWidgets import QListWidget

DEFAULT_MAX_VISIBLE_ROWS = 6


def fit_list_height_to_contents(list_widget: QListWidget, max_visible_rows: int = DEFAULT_MAX_VISIBLE_ROWS) -> None:
    """Size `list_widget` to fit its items (up to `max_visible_rows`) instead of stretching to
    fill whatever vertical space its layout gives it, which otherwise leaves blank space below
    the last real row that looks like an empty, selectable item."""
    row_count = list_widget.count()
    visible_rows = max(1, min(row_count, max_visible_rows))
    row_height = list_widget.sizeHintForRow(0) if row_count else list_widget.fontMetrics().height() + 4
    frame = 2 * list_widget.frameWidth()
    list_widget.setFixedHeight(visible_rows * row_height + frame + 4)
