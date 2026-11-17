from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    TECHNICIAN = "technician"
    CLIENT = "client"


class TicketStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AssigneeType(StrEnum):
    TECHNICIAN = "technician"
    PROVIDER = "provider"


class PhotoKind(StrEnum):
    BEFORE = "before"
    AFTER = "after"


class TicketEventType(StrEnum):
    CREATED = "created"
    UPDATED = "updated"
    ASSIGNED = "assigned"
    UNASSIGNED = "unassigned"
    STATUS_CHANGED = "status_changed"
    PHOTO_ADDED = "photo_added"
    ARCHIVED = "archived"
