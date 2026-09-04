import responses
from config.settings import get_settings
from src.outbound.market_data.options_chain import fetch_all_option_snapshots
from src.outbound.header import get_header
from src.outbound.models import Option_Submission, order_side
from src.utils.jsonParser import create_json_file, parse_json_file
from src.outbound.trading.options import submit_option_order
# from models import 

@responses.activate
def test_submit_option_order():
    SETTINGS = get_settings()
    BASE_URL= SETTINGS.BASE_URL

    order: Option_Submission = Option_Submission(
        symbol="AAPL260918C00230000",
        qty=1,
        side=order_side.BUY,
    )

    responses.add(
        responses.POST,
        f"{BASE_URL}/v2/orders",
        json = {
            "id": "testID_12345",
            "status": "accepted",
        },
        status = 200,
    )
    result = submit_option_order(order, dry_run=False)  # force past ENABLE_DRY_RUNNING to hit the mocked endpoint

    assert result["status"] == "accepted"

@responses.activate
def test_pagination():
    responses.add(responses.GET, ".../v1beta1/options/snapshots/AAPL",
                   json={"snapshots": {"CONTRACT_A": {...}}, "next_page_token": "page2"},
                   status=200)
    responses.add(responses.GET, ".../v1beta1/options/snapshots/AAPL",
                   json={"snapshots": {"CONTRACT_B": {...}}, "next_page_token": None},
                   status=200)

    result = fetch_all_option_snapshots("AAPL")
    assert "CONTRACT_A" in result and "CONTRACT_B" in result


test_submit_option_order()
