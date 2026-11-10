"""Independent Canadian-ness evaluation. Set privacy switches before DeepEval imports."""

import os

os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "YES"
os.environ["DEEPEVAL_UPDATE_WARNING_OPT_OUT"] = "YES"
os.environ["CONFIDENT_TRACE_FLUSH"] = "NO"

__version__ = "0.1.0"
