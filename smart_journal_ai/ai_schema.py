from pydantic import BaseModel, ConfigDict, Field


class AIJudgmentResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    debit_account: str = Field(..., min_length=1)
    credit_account: str = Field(..., min_length=1)
    debit_amount: float = Field(..., ge=0)
    credit_amount: float = Field(..., ge=0)
    reason: str = Field(..., min_length=1)
    evidence: str = Field(default="")
    alternative: str = Field(default="")
    review_priority: str = Field(default="中")
