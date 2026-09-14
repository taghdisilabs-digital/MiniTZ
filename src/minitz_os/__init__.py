"""MiniTZ OS native system entrypoints; donor mechanisms remain components."""

from .capabilities import (
    ActionContract,
    ActionRequest,
    ActionResult,
    Availability,
    CapabilityDescriptor,
    CapabilityStatus,
    CapabilitySurface,
    CapabilitySurfaceError,
    CapabilityUnavailableError,
    ResourceContract,
)

PRODUCT = "MiniTZ OS"

__all__ = [
    "ActionContract",
    "ActionRequest",
    "ActionResult",
    "Availability",
    "CapabilityDescriptor",
    "CapabilityStatus",
    "CapabilitySurface",
    "CapabilitySurfaceError",
    "CapabilityUnavailableError",
    "PRODUCT",
    "ResourceContract",
]
