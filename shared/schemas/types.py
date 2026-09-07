"""
Shared type definitions baseline for Storage Lifecycle Optimizer.
This file defines core domain types used across backend and worker modules.
"""

from enum import Enum


class ActionRecommendation(str, Enum):
    KEEP = "KEEP"
    MOVE_TO_INFREQUENT_ACCESS = "MOVE_TO_INFREQUENT_ACCESS"
    ARCHIVE = "ARCHIVE"
    DELETE_CANDIDATE = "DELETE_CANDIDATE"
    HOLD = "HOLD"
