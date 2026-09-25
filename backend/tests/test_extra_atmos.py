"""extra_atmos collectors against REAL payloads captured 2026-09-24 (no network).

psl_romi_tail.txt = the last 400 real rows of romi.cpcolr.1x.txt (the full file is 650 kB).
"""

from datetime import date
from pathlib import Path

import httpx
import pytest
import respx

from app import db
from app.collectors import extra_atmos as A
from app.collectors.base import SourceChanged, run_collector

FIX = Path(__file__).parent / "fixtures" / "extra"


def fx(name: str) -> bytes:
    return (FIX / name).read_bytes()


@pytest.fixture(autouse=True)
def mem_db():
    db.reset_for_tests()


def latest(series: str) -> dict:
    return db.query("SELECT * FROM observations WHERE series=? ORDER BY ts DESC LIMIT 1",
                    (series,))[0]


@respx.mock
async def test_cpc_atmos_indices_anomaly_block():
    for f in A.CPC_ATMOS:
        respx.get(A.CPC_IDX + f).mock(return_value=httpx.Response(200, content=fx(f"cpc_{f}.txt")))
    async with httpx.AsyncClient() as c:
        res = await run_collector(A.CpcAtmosIndices(), c)
    assert res["ok"], res
    w = latest("trade_wind_850_cpac_anom")
    assert (w["ts"], w["value"], w["unit"]) == ("2026-08-15", -6.3, "m/s")
    assert w["meta"]["standardized"] == -2.5
    assert latest("trade_wind_850_wpac_anom")["value"] == -4.8  # ANOMALY, not ORIGINAL (-1.3)
    assert latest("zonal_wind_200_anom")["value"] == -5.0
    olr = latest("olr_dateline_anom")
    assert (olr["value"], olr["unit"]) == (-14.9, "W/m2")
    # -999.9 placeholders (future months / 2030+ rows) are never stored
    assert not db.query("SELECT 1 FROM observations WHERE value <= -999")


def test_cpc_wrong_file_is_source_changed():
    with pytest.raises(SourceChanged):
        A.parse_cpc_monthly(fx("cpc_olr.txt").decode(), "wpac850")


def test_romi_parse():
    rows = A.parse_romi(fx("psl_romi_tail.txt").decode(), today=date(2026, 9, 24))
    amp = [r for r in rows if r["series"] == "mjo_romi_amplitude"]
    assert amp[-1] == {"series": "mjo_romi_amplitude", "ts": "2026-09-19", "value": 1.09851,
                       "unit": "index", "meta": {"pc1": 0.38131, "pc2": 1.0302}}
    assert all(r["ts"] >= "2024-09-25" for r in rows)


def test_romi_garbage_is_source_changed():
    with pytest.raises(SourceChanged):
        A.parse_romi("<html>\n<body>moved</body>\n</html>\n\n<p>\n<p>\n<p>\n")
