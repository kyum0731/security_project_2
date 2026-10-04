"""No network access, target imports, or file writes during analysis."""

from .analyzer import analyze_project
from .models import AnalysisResult, VERSION as __version__

__all__ = ["analyze_project", "AnalysisResult", "__version__"]

