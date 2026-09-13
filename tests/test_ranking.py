from src.schemas import AdRecord
from src.tools.apify_ads import rank_top_ads


def _ad(ad_id: str, days_running: int, body_len: int = 10) -> AdRecord:
    return AdRecord(ad_id=ad_id, page_name="Test", body_text="x" * body_len, days_running=days_running)


def test_rank_top_ads_orders_by_days_running_desc():
    ads = [_ad("a", 5), _ad("b", 40), _ad("c", 20)]
    ranked = rank_top_ads(ads, top_n=10)
    assert [a.ad_id for a in ranked] == ["b", "c", "a"]


def test_rank_top_ads_respects_top_n():
    ads = [_ad(str(i), i) for i in range(20)]
    ranked = rank_top_ads(ads, top_n=5)
    assert len(ranked) == 5
    assert ranked[0].ad_id == "19"


def test_rank_top_ads_tiebreaks_on_body_length():
    ads = [_ad("short", 10, body_len=5), _ad("long", 10, body_len=50)]
    ranked = rank_top_ads(ads, top_n=2)
    assert ranked[0].ad_id == "long"
