import responses
from config.settings import get_settings
from src.outbound.header import get_header
from src.outbound.models import Option_Submission, option_status
from src.utils.jsonParser import create_json_file, parse_json_file
from src.outbound.trading.options import submit_option_order
# from models import 

@responses.activate
def test_submit_option_order():
    SETTINGS = get_settings()
    BASE_URL= SETTINGS.BASE_URL

    order: Option_Submission = Option_Submission(
        order_symbol="AAPL260918C00230000",
        qty=1,
        side="buy",
        strike_price=2.50,
        status=option_status.ACTIVE,
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
    result = submit_option_order(order)

    assert result["status"] == "accepted"