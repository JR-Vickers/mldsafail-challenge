"""Compatibility entrypoint for the packaged MLWE experiment workflow."""
import sys
from mldsafail import development

if __name__ == "__main__":
    raise SystemExit(development.main())
else:
    sys.modules[__name__] = development
