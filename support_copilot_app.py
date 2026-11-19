"""Temporary recovery entry point for Enterprise Support Copilot.

The original application entry source was accidentally overwritten.
This module loads the verified Python 3.13 recovery bytecode.

Backend application modules under app/ remain readable Python source.
Replace this recovery loader with reconstructed source before making
the repository public.
"""

import importlib.machinery
import importlib.util
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent

RECOVERY_MODULE_PATH = (
    PROJECT_ROOT
    / "support_copilot_app.recovery.pyc"
)


if not RECOVERY_MODULE_PATH.exists():
    raise FileNotFoundError(
        "Recovery application bytecode was not found: "
        f"{RECOVERY_MODULE_PATH}"
    )


loader = importlib.machinery.SourcelessFileLoader(
    "_recovered_support_copilot_app",
    str(RECOVERY_MODULE_PATH),
)

spec = importlib.util.spec_from_loader(
    loader.name,
    loader,
)

if spec is None:
    raise ImportError(
        "Could not create the recovery module specification."
    )


recovered_module = importlib.util.module_from_spec(
    spec
)

loader.exec_module(
    recovered_module
)


application = recovered_module.application
