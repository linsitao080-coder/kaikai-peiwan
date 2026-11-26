"""
Backwards-compatible shim exporting ControlCenterServer as LocalSettingsServer.
All new Visual Communication Design Control Studio code lives in control_center.py.
"""

from control_center import (  # noqa: F401
    ControlCenterServer,
    DEFAULT_STUDIO_LOGICAL_H,
    DEFAULT_STUDIO_LOGICAL_W,
    HTML_PAGE,
    LocalSettingsServer,
    OUTFIT_CATALOG,
    VALID_OUTFITS,
    build_app_launch_cmd,
    compute_studio_window_rect,
    find_app_mode_browser,
    launch_control_center_window,
)
