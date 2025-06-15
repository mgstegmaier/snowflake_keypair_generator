import backend.snowflake_client as sfc

def test_stub_call():
    result = sfc.client.call_stored_procedure("sp_test", [1, 2, 3])
    assert result["procedure"] == "sp_test"
    assert result["status"] == "not-implemented" 