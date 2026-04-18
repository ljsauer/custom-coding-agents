# presentation/app.py
#
# Flask Application Factory
#
# create_app() is the single entry point for building the Flask application.
# It receives fully-constructed use-case objects from the composition root
# (main.py) and makes them available to the blueprint via app.config.
#
# Nothing here knows about SQLAlchemy, cv2, or Google Images.
# The presentation layer speaks only to use-case interfaces.

from __future__ import annotations

from flask import Flask

from collage_maker.application.use_cases.create_collage import CreateCollageUseCase
from collage_maker.application.use_cases.delete_collage import DeleteCollageUseCase
from collage_maker.application.use_cases.list_collages import ListCollagesUseCase
from collage_maker.application.use_cases.rename_collage import RenameCollageUseCase
from collage_maker.presentation.routes.collage_routes import collage_bp


def create_app(
    create_uc: CreateCollageUseCase,
    rename_uc: RenameCollageUseCase,
    delete_uc: DeleteCollageUseCase,
    list_uc: ListCollagesUseCase,
    img_thumbnail_size: int = 240,
) -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="../../../static",  # served from project root /static
    )
    app.secret_key = "change-me-in-production"

    # Store use-cases in app config so the blueprint can retrieve them.
    # Using config avoids globals and keeps the blueprint testable.
    app.config["CREATE_UC"] = create_uc
    app.config["RENAME_UC"] = rename_uc
    app.config["DELETE_UC"] = delete_uc
    app.config["LIST_UC"] = list_uc
    app.config["IMG_THUMBNAIL_SIZE"] = img_thumbnail_size

    app.register_blueprint(collage_bp)

    return app
