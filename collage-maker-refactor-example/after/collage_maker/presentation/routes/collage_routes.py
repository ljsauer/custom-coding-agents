"""
Collage Blueprint — Presentation Layer

Each route does exactly three things:
  1. Extract input from the HTTP request.
  2. Call a use case.
  3. Return an HTTP response (render, redirect, or error).

There is no business logic here. Validation of business invariants (blank
names, missing collages) is handled by the domain and surfaces here as
exceptions that are caught and converted into user-facing flash messages.
"""

from __future__ import annotations

from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from collage_maker.application.use_cases.create_collage import CreateCollageUseCase
from collage_maker.application.use_cases.delete_collage import DeleteCollageUseCase
from collage_maker.application.use_cases.list_collages import ListCollagesUseCase
from collage_maker.application.use_cases.rename_collage import RenameCollageUseCase
from collage_maker.domain.exceptions import (
    CollageCreationError,
    CollageNotFoundError,
    InvalidCollageNameError,
)

collage_bp = Blueprint("collages", __name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_uc() -> CreateCollageUseCase:
    return current_app.config["CREATE_UC"]


def _rename_uc() -> RenameCollageUseCase:
    return current_app.config["RENAME_UC"]


def _delete_uc() -> DeleteCollageUseCase:
    return current_app.config["DELETE_UC"]


def _list_uc() -> ListCollagesUseCase:
    return current_app.config["LIST_UC"]


def _thumbnail_size() -> int:
    return current_app.config["IMG_THUMBNAIL_SIZE"]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@collage_bp.route("/", methods=["GET"])
def index() -> str:
    collages = _list_uc().execute()
    return render_template(
        "index.html",
        collages=collages,
        img_size=_thumbnail_size(),
        storage_public_path=_public_path_for,
    )


@collage_bp.route("/collage", methods=["POST"])
def create_collage() -> Response:
    uploaded_file = request.files.get("file")
    if not uploaded_file:
        flash("Please upload a text file.", "warning")
        return redirect(url_for("collages.index"))

    text = uploaded_file.read().decode("utf-8", errors="ignore")
    if not text.strip():
        flash("The uploaded file appears to be empty.", "warning")
        return redirect(url_for("collages.index"))

    try:
        _create_uc().execute(text)
        flash("Your collage is being created — check back shortly.", "success")
    except CollageCreationError as exc:
        flash(str(exc), "danger")
    except Exception as exc:
        flash(f"Could not create collage: {exc}", "danger")

    return redirect(url_for("collages.index"))


@collage_bp.route("/collage/<collage_id>/rename", methods=["POST"])
def rename_collage(collage_id: str) -> Response:
    new_name = request.form.get("name", "").strip()
    try:
        _rename_uc().execute(collage_id, new_name)
        flash("Collage renamed successfully.", "success")
    except (CollageNotFoundError, InvalidCollageNameError) as exc:
        flash(str(exc), "danger")

    return redirect(url_for("collages.index"))


@collage_bp.route("/collage/<collage_id>/delete", methods=["POST"])
def delete_collage(collage_id: str) -> Response:
    try:
        _delete_uc().execute(collage_id)
        flash("Collage deleted.", "success")
    except CollageNotFoundError as exc:
        flash(str(exc), "danger")

    return redirect(url_for("collages.index"))


# ---------------------------------------------------------------------------
# Template helper — keeps storage path logic out of templates
# ---------------------------------------------------------------------------


def _public_path_for(collage_id: str) -> str:
    storage = current_app.config.get("STORAGE")
    if storage:
        return storage.public_path(collage_id)
    return f"{collage_id}.jpg"
