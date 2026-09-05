from enum import Enum
from app.core.roles import UserRole


class Permission(str, Enum):
    AUTH_ME = "auth:me"
    USERS_READ = "users:read"
    USERS_MANAGE = "users:manage"
    INSPECTION_READ = "inspection:read"
    INSPECTION_CREATE = "inspection:create"
    INSPECTION_EDIT = "inspection:edit"
    INSPECTION_FINALIZE = "inspection:finalize"
    INSPECTION_EXPORT = "inspection:export"
    DECLARATION_CORRECT = "declaration:correct"
    FINDING_REVIEW = "finding:review"
    NOTICE_READ = "notice:read"
    NOTICE_DRAFT = "notice:draft"
    NOTICE_EDIT = "notice:edit"
    NOTICE_REVIEW = "notice:review"
    NOTICE_ISSUE = "notice:issue"
    ASSISTANT_READ = "assistant:read"
    RULES_READ = "rules:read"
    ANALYTICS_READ = "analytics:read"


ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    UserRole.ADMIN.value: {
        Permission.AUTH_ME,
        Permission.USERS_READ,
        Permission.USERS_MANAGE,
        Permission.INSPECTION_READ,
        Permission.INSPECTION_CREATE,
        Permission.INSPECTION_EDIT,
        Permission.INSPECTION_FINALIZE,
        Permission.INSPECTION_EXPORT,
        Permission.DECLARATION_CORRECT,
        Permission.FINDING_REVIEW,
        Permission.NOTICE_READ,
        Permission.NOTICE_DRAFT,
        Permission.NOTICE_EDIT,
        Permission.NOTICE_REVIEW,
        Permission.NOTICE_ISSUE,
        Permission.ASSISTANT_READ,
        Permission.RULES_READ,
        Permission.ANALYTICS_READ,
    },
    UserRole.SUPERVISING_OFFICER.value: {
        Permission.AUTH_ME,
        Permission.USERS_READ,
        Permission.INSPECTION_READ,
        Permission.INSPECTION_CREATE,
        Permission.INSPECTION_EDIT,
        Permission.INSPECTION_FINALIZE,
        Permission.INSPECTION_EXPORT,
        Permission.DECLARATION_CORRECT,
        Permission.FINDING_REVIEW,
        Permission.NOTICE_READ,
        Permission.NOTICE_DRAFT,
        Permission.NOTICE_EDIT,
        Permission.NOTICE_REVIEW,
        Permission.NOTICE_ISSUE,
        Permission.ASSISTANT_READ,
        Permission.RULES_READ,
        Permission.ANALYTICS_READ,
    },
    UserRole.LEGAL_METROLOGY_INSPECTOR.value: {
        Permission.AUTH_ME,
        Permission.INSPECTION_READ,
        Permission.INSPECTION_CREATE,
        Permission.INSPECTION_EDIT,
        Permission.INSPECTION_FINALIZE,
        Permission.INSPECTION_EXPORT,
        Permission.DECLARATION_CORRECT,
        Permission.FINDING_REVIEW,
        Permission.NOTICE_READ,
        Permission.NOTICE_DRAFT,
        Permission.NOTICE_EDIT,
        Permission.ASSISTANT_READ,
        Permission.RULES_READ,
    },
    UserRole.REVIEWER.value: {
        Permission.AUTH_ME,
        Permission.INSPECTION_READ,
        Permission.INSPECTION_EXPORT,
        Permission.FINDING_REVIEW,
        Permission.NOTICE_READ,
        Permission.ASSISTANT_READ,
        Permission.RULES_READ,
        Permission.ANALYTICS_READ,
    },
}
