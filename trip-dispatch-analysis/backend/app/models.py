from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class DriverSummary(BaseModel):
    driver_name: str
    driver_mobile: str
    total_trips: int
    eta_met: int
    eta_missed: int
    eta_success_rate: float

class PaginatedResponse(BaseModel):
    data: List
    page: int
    limit: int
    total: int
    pages: int