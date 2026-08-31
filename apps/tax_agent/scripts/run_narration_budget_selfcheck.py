#!/usr/bin/env python3
"""C5 narration budget + fallbackReason contract selfcheck."""

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tax_agent.answer_composer import (
    FALLBACK_REASONS,
    NarrationBudgetExceeded,
    compose_grounded_reply,
    finalize_turn_with_composer,
    long_reply_allowed,
    max_reply_chars_for_profile,
    narration_stream_first_token_s,
    narration_stream_total_s,
    narration_timeout_seconds,
    normalize_fallback_reason,
    stream_compose_grounded_reply,
)
from tax_agent.fx_rates import FxRateProvider
from tax_agent.session_context import SessionContext
from tax_agent.tax_provenance import try_provenance_fast_turn

SNAP = ROOT / "rules" / "cn_resident_us_equity" / "snapshots" / "2026.06.01"


def _bundle():
    provider = FxRateProvider.from_snapshot_dir(SNAP)
    ctx = SessionContext(
        dataset_id=None,
        tax_year=2025,
        fx_policy="cn_supplemental",
        fx_provider=provider,
    )
    turn = try_provenance_fast_turn("22年的补申报的汇率是如何确定的", ctx)
    assert turn and turn.fact_bundle
    return turn.fact_bundle


def main() -> int:
    assert narration_timeout_seconds() == 45.0
    assert narration_stream_first_token_s() == 20.0
    assert narration_stream_total_s() == 90.0
    print("PASS C5 env defaults (45s / 20s / 90s)")

    os.environ["TAX_NARRATION_TIMEOUT_S"] = "3"
    assert narration_timeout_seconds() == 3.0
    del os.environ["TAX_NARRATION_TIMEOUT_S"]
    print("PASS C5 env override TAX_NARRATION_TIMEOUT_S")

    for raw, expected in [
        ("timeout", "timeout"),
        ("audit_numerics", "audit_numerics"),
        ("narration_error:Connection timed out", "timeout"),
        ("composer_disabled", "llm_unavailable"),
        ("empty_narration", "llm_unavailable"),
        (None, "none"),
    ]:
        assert normalize_fallback_reason(raw) == expected, (raw, expected)
    assert normalize_fallback_reason("audit_citation", narrated=True) == "none"
    print("PASS C5 fallbackReason normalization")

    bundle = _bundle()
    assert not long_reply_allowed(bundle.profile)
    assert max_reply_chars_for_profile(bundle.profile) <= 500
    assert long_reply_allowed("guided_filing")
    assert max_reply_chars_for_profile("guided_filing") > 500
    print("PASS C5 long-reply profile contract")

    def _slow_stream(b, **kwargs):
        time.sleep(0.05)
        raise NarrationBudgetExceeded("timeout")

    finals = list(
        stream_compose_grounded_reply(
            bundle,
            user_message="22年汇率",
            llm_on=True,
            stream_fn=_slow_stream,
        )
    )
    assert finals[-1][0] == "final"
    composed = finals[-1][1]
    assert not composed.narrated
    assert composed.fallback_reason == "timeout"
    assert composed.fallback_reason in FALLBACK_REASONS
    print("PASS C5-1 stream timeout → template + fallbackReason=timeout")

    long_text = "说明" * 320
    composed_long = compose_grounded_reply(
        bundle,
        user_message="22年汇率",
        llm_on=True,
        narrate_fn=lambda b, **kw: (long_text, ""),
    )
    assert not composed_long.narrated
    assert composed_long.fallback_reason == "llm_unavailable"
    print("PASS C5-2 overlength policy_explain → fallback")

    turn = try_provenance_fast_turn(
        "22年的补申报的汇率是如何确定的",
        SessionContext(
            dataset_id=None,
            tax_year=2025,
            fx_policy="cn_supplemental",
            fx_provider=FxRateProvider.from_snapshot_dir(SNAP),
        ),
    )
    _, meta = finalize_turn_with_composer(
        turn,
        user_message="22年汇率",
        llm_on=False,
    )
    assert meta["composer"]["fallbackReason"] in FALLBACK_REASONS
    assert meta["composer"]["fallbackReason"] == "llm_unavailable"
    print("PASS C5 harnessReport composer.fallbackReason enum")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
