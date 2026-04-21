"""Policy engine treats ASR transcript signals like OCR text."""

import sys
from pathlib import Path
from types import SimpleNamespace

src = Path(__file__).resolve().parent.parent / "src"
if str(src) not in sys.path:
    sys.path.insert(0, str(src))

from zataone.policy_engine.engine import PolicyEngine


def test_asr_text_signal_triggers_text_rules():
    engine = PolicyEngine()
    engine.load_policy_pack(
        rules={
            "misleading_exaggerated_claims": {
                "name": "Misleading Claims",
                "prohibited_terms": ["guaranteed"],
                "severity": "HIGH",
            },
        }
    )
    sig = SimpleNamespace(
        signal_id="asr-1",
        signal_type="text",
        source_model="ad_compliance_asr",
        confidence=0.95,
        raw_data={
            "type": "asr_text",
            "text": "We guaranteed results overnight",
            "source": "audio",
        },
    )
    violations = engine.evaluate([sig])
    assert len(violations) >= 1
    assert violations[0].rule_id == "misleading_exaggerated_claims"
