from typing import Optional

from app.schemas.base import AuditMixin, TransfermarktBaseModel


class TransferEntry(TransfermarktBaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    position: Optional[str] = None
    age: Optional[int] = None
    club_id: Optional[str] = None
    club_name: Optional[str] = None
    fee: Optional[int] = None


class TransferSummary(TransfermarktBaseModel):
    income_count: int = 0
    income_total: Optional[int] = None
    expenditure_count: int = 0
    expenditure_total: Optional[int] = None
    balance: Optional[int] = None


class ClubTransfers(TransfermarktBaseModel, AuditMixin):
    id: str
    season_id: str
    arrivals: list[TransferEntry]
    departures: list[TransferEntry]
    summary: TransferSummary
