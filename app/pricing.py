from enum import Enum

class PlanType(str, Enum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"

PRICING_PLANS = {
    PlanType.FREE: {
        "name": "Normal (Free)",
        "max_docs": 3,
        "max_storage_mb": 30,
        "description": "For individuals and hobbyists"
    },
    PlanType.PRO: {
        "name": "Pro",
        "max_docs": 10,
        "max_storage_mb": 200,
        "description": "For power users and small teams"
    },
    PlanType.ENTERPRISE: {
        "name": "Enterprise",
        "max_docs": 30,
        "max_storage_mb": 500 ,
        "description": "For large organizations"
    }
}

DEFAULT_PLAN = PlanType.FREE
