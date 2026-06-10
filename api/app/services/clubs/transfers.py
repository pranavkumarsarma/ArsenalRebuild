import re
from dataclasses import dataclass
from typing import Optional

from app.services.base import TransfermarktBase
from app.utils.utils import extract_from_url, trim
from app.utils.xpath import Clubs


def _parse_money(text: str) -> Optional[int]:
    if not text or not any(c.isdigit() for c in text):
        return None
    value = text.lower().replace("€", "").replace("+", "").replace("-", "").replace(",", ".").strip()
    value = re.sub(r"\s+", "", value)
    try:
        if "k" in value:
            return int(float(value.replace("k", "")) * 1_000)
        elif "m" in value:
            return int(float(value.replace("m", "")) * 1_000_000)
        elif "bn" in value or "b" in value:
            return int(float(re.sub(r"b.*", "", value)) * 1_000_000_000)
        else:
            return int(float(value))
    except (ValueError, TypeError):
        return None


@dataclass
class TransfermarktClubTransfers(TransfermarktBase):
    club_id: str = None
    season_id: str = None
    URL: str = "https://www.transfermarkt.com/-/transfers/verein/{club_id}/saison_id/{season_id}"

    def __post_init__(self) -> None:
        self.URL = self.URL.format(club_id=self.club_id, season_id=self.season_id)
        self.page = self.request_url_page()

    def __parse_transfers(self, base_xpath: str) -> list[dict]:
        rows = self.page.xpath(base_xpath + Clubs.Transfers.ROWS)
        transfers = []
        for row in rows:
            player_href = row.xpath(Clubs.Transfers.PLAYER_HREF)
            player_name = row.xpath(Clubs.Transfers.PLAYER_NAME)
            position = row.xpath(Clubs.Transfers.PLAYER_POSITION)
            age = row.xpath(Clubs.Transfers.AGE)
            club_href = row.xpath(Clubs.Transfers.CLUB_HREF)
            club_name = row.xpath(Clubs.Transfers.CLUB_NAME)
            fee_parts = row.xpath(Clubs.Transfers.FEE)
            fee_text = trim("".join(fee_parts)) if fee_parts else None
            if fee_text and any(k in fee_text.lower() for k in ("loan", "free", "draft", "?")):
                fee_text = None

            transfers.append({
                "id": extract_from_url(player_href[0]) if player_href else None,
                "name": player_name[0] if player_name else None,
                "position": trim(position[0]) if position else None,
                "age": trim(age[0]) if age else None,
                "clubId": extract_from_url(club_href[0]) if club_href else None,
                "clubName": club_name[0] if club_name else None,
                "fee": fee_text,
            })
        return transfers

    def __parse_summary(self) -> dict:
        income_count = trim("".join(self.page.xpath(Clubs.Transfers.SUMMARY_INCOME_COUNT)))
        income_total = trim("".join(self.page.xpath(Clubs.Transfers.SUMMARY_INCOME_TOTAL)))
        expenditure_count = trim("".join(self.page.xpath(Clubs.Transfers.SUMMARY_EXPENDITURE_COUNT)))
        expenditure_total = trim("".join(self.page.xpath(Clubs.Transfers.SUMMARY_EXPENDITURE_TOTAL)))
        balance = trim("".join(self.page.xpath(Clubs.Transfers.SUMMARY_BALANCE)))

        return {
            "incomeCount": int(income_count) if income_count.isdigit() else 0,
            "incomeTotal": _parse_money(income_total),
            "expenditureCount": int(expenditure_count) if expenditure_count.isdigit() else 0,
            "expenditureTotal": _parse_money(expenditure_total),
            "balance": _parse_money(balance),
        }

    def get_club_transfers(self) -> dict:
        self.response["id"] = self.club_id
        self.response["seasonId"] = self.season_id
        self.response["arrivals"] = self.__parse_transfers(Clubs.Transfers.BASE_ARRIVALS)
        self.response["departures"] = self.__parse_transfers(Clubs.Transfers.BASE_DEPARTURES)
        self.response["summary"] = self.__parse_summary()
        return self.response
