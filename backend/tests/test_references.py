# spec: AS-D01 AS-D03
import os
import pytest
import verify_references as vr

def test_every_real_evidence_row_declares_a_url_and_the_phrase_it_rests_on():
    assert vr.main(offline=True) == 0

def test_phrase_matching_ignores_markup_case_whitespace_and_curly_quotes():
    page = "<html><script>x</script><p>Multiple   languages spoken in the same meeting aren&#39;t\n currently supported.</p></html>"
    assert vr.contains(page, "multiple languages spoken in the same meeting aren’t currently supported")
    assert not vr.contains(page, "Hindi")

@pytest.mark.network
@pytest.mark.skipif(os.environ.get("AIRSTACK_NETWORK_TESTS") != "1", reason="set AIRSTACK_NETWORK_TESTS=1 to re-check every reference against the live web")
def test_every_reference_resolves_and_contains_its_phrase_live():
    assert vr.main() == 0
