from enum import Enum

class PlanType(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTREPRENEUR = "entrepreneur"

PRICING_PLANS = {
    PlanType.FREE: {
        "name": "Normal (Free)",
        "max_docs": 5,
        "max_size_bytes": 10 * 1024 * 1024, # 10MB
        "description": "For individuals and hobbyists"
    },
    PlanType.PRO: {
        "name": "Pro",
        "max_docs": 30,
        "max_size_bytes": 30 * 1024 * 1024, # 30MB
        "description": "For power users and small teams"
    },
    PlanType.ENTREPRENEUR: {
        "name": "Entrepreneur",
        "max_docs": 100,
        "max_size_bytes": 50 * 1024 * 1024, # 50MB
        "description": "For growing businesses"
    }
}

DEFAULT_PLAN = PlanType.FREE
