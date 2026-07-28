from enum import StrEnum


class TransportSecurity(StrEnum):
    SSL = "SSL"
    STARTTLS = "STARTTLS"


class ApplicationStage(StrEnum):
    APPLIED = "APPLIED"
    ASSESSMENT = "ASSESSMENT"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class ApplicationStatus(StrEnum):
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    WITHDRAWN = "WITHDRAWN"


class ApplicationSource(StrEnum):
    MANUAL = "MANUAL"
    EMAIL = "EMAIL"


class EmailParseStatus(StrEnum):
    PENDING = "PENDING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ArchiveStatus(StrEnum):
    NONE = "NONE"
    PROPOSED = "PROPOSED"
    ARCHIVED = "ARCHIVED"
    RESTORED = "RESTORED"
    FAILED = "FAILED"


class EmailCategory(StrEnum):
    INTERVIEW = "INTERVIEW"
    ASSESSMENT = "ASSESSMENT"
    OFFER = "OFFER"
    REJECTION = "REJECTION"
    MATERIAL_REQUEST = "MATERIAL_REQUEST"
    APPLICATION_UPDATE = "APPLICATION_UPDATE"
    RECRUITER_COMMUNICATION = "RECRUITER_COMMUNICATION"
    JOB_RELATED_OTHER = "JOB_RELATED_OTHER"
    NON_JOB = "NON_JOB"


class EmailPriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class RequiredCapability(StrEnum):
    EXTRACT = "EXTRACT"
    MATCH_APPLICATION = "MATCH_APPLICATION"
    DRAFT_REPLY = "DRAFT_REPLY"
    PROPOSE_ARCHIVE = "PROPOSE_ARCHIVE"
