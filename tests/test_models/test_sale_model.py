from models.enums import SaleStatus
from models.sale import VALID_STATUSES


def test_valid_statuses_match_sale_status_enum():
    assert {status.value for status in SaleStatus} == VALID_STATUSES
