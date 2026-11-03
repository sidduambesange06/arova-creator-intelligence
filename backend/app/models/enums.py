from enum import Enum
import uuid

# Fixed deterministic namespace from Task 4 Shared Header
NAMESPACE_AROVA_VERSION = uuid.UUID("15e68111-cb50-55cb-9518-e6ed85b67dfd")


class ExecutionProfile(str, Enum):
    FULLY_OFFLINE_NO_AI = "fully_offline_no_ai"
    LOCAL_AI = "local_ai"
    BYOK_REMOTE_AI = "byok_remote_ai"
    HYBRID_AI = "hybrid_ai"


class RootType(str, Enum):
    LOCAL_FIXED = "local_fixed"
    REMOVABLE = "removable"
    NETWORK = "network"
    UNKNOWN = "unknown"


class RootPolicy(str, Enum):
    LOCAL_ONLY = "local_only"
    ALLOW_REMOTE = "allow_remote"


class CapabilityStatus(str, Enum):
    AVAILABLE = "available"
    INSTALLED_UNVERIFIED = "installed_unverified"
    NOT_INSTALLED = "not_installed"
    HARDWARE_UNSUPPORTED = "hardware_unsupported"
    DISABLED_BY_USER = "disabled_by_user"
    BLOCKED_BY_PRIVACY_POLICY = "blocked_by_privacy_policy"
    PROVIDER_UNAVAILABLE = "provider_unavailable"


class CapabilityReason(str, Enum):
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    MODEL_NOT_INSTALLED = "model_not_installed"
    HARDWARE_UNSUPPORTED = "hardware_unsupported"
    DISABLED_BY_USER = "disabled_by_user"
    PRIVACY_POLICY_BLOCKED = "privacy_policy_blocked"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    VALIDATION_REQUIRED = "validation_required"
    CONSENT_REQUIRED = "consent_required"
    REMOTE_NOT_ALLOWED = "remote_not_allowed"
    NETWORK_TIMEOUT = "network_timeout"
    DEPENDENCY_MISSING = "dependency_missing"


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"
    STALE = "stale"


class LocationAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    MISSING = "missing"
    RELINK_REQUIRED = "relink_required"


class IdentityState(str, Enum):
    VERIFIED = "verified"
    IDENTITY_UNVERIFIED = "identity_unverified"


class AuthorType(str, Enum):
    ASR = "asr"
    AI = "ai"
    HUMAN = "human"


class TrustLevel(str, Enum):
    UNVERIFIED = "unverified"
    ASR = "asr"
    AI_GENERATED = "ai_generated"
    HUMAN_CONFIRMED = "human_confirmed"


class AssetRelationType(str, Enum):
    DUPLICATE_OF = "duplicate_of"
    DERIVED_FROM = "derived_from"
    PROXY_OF = "proxy_of"


class EntityType(str, Enum):
    ASSET = "asset"
    VERSION = "version"
    MOMENT = "moment"
    ANNOTATION = "annotation"


def compute_deterministic_version_id(sha256_hex: str) -> str:
    """Derive deterministic version ID as UUIDv5 using the fixed namespace and lowercase full SHA-256 digest."""
    clean_hex = sha256_hex.strip().lower()
    if len(clean_hex) != 64:
        raise ValueError(f"Invalid SHA-256 digest: expected 64 hex characters, got {len(clean_hex)}")
    return str(uuid.uuid5(NAMESPACE_AROVA_VERSION, clean_hex))

