from enum import Enum


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    SUPERVISING_OFFICER = "SUPERVISING_OFFICER"
    LEGAL_METROLOGY_INSPECTOR = "LEGAL_METROLOGY_INSPECTOR"
    REVIEWER = "REVIEWER"

    @classmethod
    def normalize(cls, value: str) -> "UserRole":
        if not value:
            return cls.REVIEWER
        v = value.strip()
        mapping = {
            "inspector": cls.LEGAL_METROLOGY_INSPECTOR,
            "supervisor": cls.SUPERVISING_OFFICER,
            "supervising_officer": cls.SUPERVISING_OFFICER,
            "admin": cls.ADMIN,
            "reviewer": cls.REVIEWER,
        }
        if v.lower() in mapping:
            return mapping[v.lower()]
        try:
            return cls(v)
        except ValueError:
            pass
        try:
            return cls[v.upper()]
        except KeyError:
            pass
        raise ValueError(f"Unknown or invalid role: {value}")
