# zataone policy engine

import re
from typing import Any

from zataone.policy_engine.rule import Rule
from zataone.schemas.violation import Violation as ViolationSchema

_SEVERITY_WEIGHTS = {"LOW": 0.2, "MEDIUM": 0.4, "HIGH": 0.7, "CRITICAL": 1.0}


class PolicyEngine:
    """
    Deterministic policy evaluation engine.
    Policies are loaded from configuration (YAML/registry), never hard-coded.
    """

    def __init__(self) -> None:
        self._rules: dict[str, dict] = {}
        self._vision_support_map: dict = {}
        self._embedding_rule_map: dict = {}
        self._domain_schemas: Any = None

    def load_policy_pack(
        self,
        config_path: str | dict[str, Any] | None = None,
        rules: dict[str, Any] | None = None,
        vision_support_map: dict | None = None,
        embedding_rule_map: dict | None = None,
    ) -> list[Rule]:
        """
        Load policy pack from config file or dict.
        Returns list of Rule instances.
        """
        if rules is not None:
            self._rules = rules
        if vision_support_map is not None:
            self._vision_support_map = vision_support_map
        if embedding_rule_map is not None:
            self._embedding_rule_map = embedding_rule_map

        if config_path is not None and isinstance(config_path, dict):
            self._rules = config_path.get("rules", config_path)

        return [Rule.from_config({"rule_id": k, **v}) for k, v in self._rules.items()]

    def evaluate(
        self,
        signals: list[Any],
        policy_pack_id: str | None = None,
        rules: list[Rule] | None = None,
    ) -> list[ViolationSchema]:
        """
        Evaluate policies against signals. Returns List[Violation].
        Each violation has signal_id, rule_id, violation_type, severity, evidence_data.
        """
        if not self._rules:
            return []

        def _severity_to_float(sev: str) -> float:
            return _SEVERITY_WEIGHTS.get(str(sev), 0.5)

        def _is_text_signal(s):
            if hasattr(s, "signal_type"):
                st = s.signal_type
                if st is not None:
                    val = getattr(st, "value", str(st))
                    if val == "text" or str(st).endswith("TEXT"):
                        return True
            rd = getattr(s, "raw_data", None) or {}
            return (
                rd.get("type") == "ocr_text"
                or rd.get("type") == "asr_text"
                or "text" in rd
            )

        text_signals = [s for s in signals if _is_text_signal(s)]

        vision_object_signals = [
            s for s in signals
            if hasattr(s, "raw_data") and s.raw_data.get("type") == "vision_object"
        ]

        embedding_signals_by_regulation = {}
        for s in signals:
            if not hasattr(s, "raw_data") or s.raw_data.get("type") != "image_embedding_similarity":
                continue
            reg = s.raw_data.get("regulation")
            if reg:
                embedding_signals_by_regulation.setdefault(reg, []).append(s)

        rule_matches = {}
        for signal in text_signals:
            text_content = (getattr(signal, "raw_data", {}) or {}).get("text", "").lower()
            for rule_id, rule in self._rules.items():
                match_result = self._matches_rule(text_content, rule)
                if match_result:
                    matched_term, confidence = match_result
                    if rule_id not in rule_matches:
                        rule_matches[rule_id] = []
                    rule_matches[rule_id].append((signal, matched_term, confidence))

        def _make_evidence_data(evidence_type: str, data: dict, rule: dict) -> dict:
            return {"evidence_type": evidence_type, "rule_name": rule.get("name", ""), **data}

        vision_triggered_rules = {}
        for rule_id, rule in self._rules.items():
            primary_labels = rule.get("vision_primary_labels")
            if not primary_labels:
                continue
            allowed = {str(l).strip().lower() for l in primary_labels}
            matched = [
                s for s in vision_object_signals
                if str((s.raw_data or {}).get("label", "")).strip().lower() in allowed
            ]
            if matched:
                vision_triggered_rules[rule_id] = matched

        vision_primary_rule_ids = {
            r for r, rule in self._rules.items() if rule.get("vision_primary_labels")
        }
        ocr_triggered_ids = set(rule_matches.keys()) - vision_primary_rule_ids
        all_violation_rule_ids = ocr_triggered_ids | set(vision_triggered_rules.keys())

        violations = []
        for rule_id in all_violation_rule_ids:
            rule = self._rules[rule_id]
            matches = rule_matches.get(rule_id, [])
            vision_signals = vision_triggered_rules.get(rule_id, [])
            evidence_list = []

            severity_float = _severity_to_float(rule.get("severity", "HIGH"))

            for signal, matched_term, confidence in matches:
                signal_id = str(getattr(signal, "signal_id", "unknown"))
                evidence_data = _make_evidence_data(
                    "text_match",
                    {
                        "matched_text": (signal.raw_data or {}).get("text", ""),
                        "matched_term": matched_term,
                        "confidence": confidence,
                        "signal_confidence": getattr(signal, "confidence", 0.8),
                        "ocr_text": (signal.raw_data or {}).get("text", ""),
                        "bbox": getattr(signal, "bounding_box", None),
                    },
                    rule,
                )
                violations.append(
                    ViolationSchema(
                        signal_id=signal_id,
                        rule_id=rule_id,
                        violation_type="text_match",
                        severity=severity_float,
                        evidence_data=evidence_data,
                    )
                )

            for s in vision_signals:
                signal_id = str(getattr(s, "signal_id", "unknown"))
                evidence_data = _make_evidence_data(
                    "vision_object",
                    {
                        "label": (s.raw_data or {}).get("label"),
                        "confidence": 1.0,
                        "signal_confidence": getattr(s, "confidence", 0.8),
                        "bbox": (s.raw_data or {}).get("bbox"),
                        "model": (s.raw_data or {}).get("model", "grounding_dino"),
                    },
                    rule,
                )
                violations.append(
                    ViolationSchema(
                        signal_id=signal_id,
                        rule_id=rule_id,
                        violation_type="vision_object",
                        severity=severity_float,
                        evidence_data=evidence_data,
                    )
                )

            if vision_signals and not matches:
                for signal in text_signals:
                    text_content = (getattr(signal, "raw_data", {}) or {}).get("text", "").lower()
                    match_result = self._matches_rule(text_content, rule)
                    if match_result:
                        matched_term, confidence = match_result
                        signal_id = str(getattr(signal, "signal_id", "unknown"))
                        evidence_data = _make_evidence_data(
                            "text_match",
                            {
                                "matched_text": (signal.raw_data or {}).get("text", ""),
                                "matched_term": matched_term,
                                "confidence": confidence,
                                "signal_confidence": getattr(signal, "confidence", 0.8),
                                "ocr_text": (signal.raw_data or {}).get("text", ""),
                                "bbox": getattr(signal, "bounding_box", None),
                            },
                            rule,
                        )
                        violations.append(
                            ViolationSchema(
                                signal_id=signal_id,
                                rule_id=rule_id,
                                violation_type="text_match",
                                severity=severity_float,
                                evidence_data=evidence_data,
                            )
                        )

            regulation_name = self._embedding_rule_map.get(rule_id)
            if regulation_name:
                for signal in embedding_signals_by_regulation.get(regulation_name, []):
                    signal_id = str(getattr(signal, "signal_id", "unknown"))
                    evidence_data = _make_evidence_data(
                        "image_embedding_similarity",
                        {
                            "score": (signal.raw_data or {}).get("score", 0.0),
                            "model": (signal.raw_data or {}).get("model", "siglip"),
                            "confidence": 0.2,
                            "signal_confidence": getattr(signal, "confidence", 0.8),
                        },
                        rule,
                    )
                    violations.append(
                        ViolationSchema(
                            signal_id=signal_id,
                            rule_id=rule_id,
                            violation_type="image_embedding_similarity",
                            severity=severity_float,
                            evidence_data=evidence_data,
                        )
                    )

            if rule_id in self._vision_support_map and vision_object_signals:
                allowed = self._vision_support_map[rule_id]
                if not isinstance(allowed, set):
                    allowed = set(allowed) if allowed else set()
                matched_vision = [
                    s for s in vision_object_signals
                    if str((s.raw_data or {}).get("label", "")).strip().lower() in allowed
                ]
                if matched_vision:
                    for s in matched_vision:
                        signal_id = str(getattr(s, "signal_id", "unknown"))
                        evidence_data = _make_evidence_data(
                            "vision_object",
                            {
                                "label": (s.raw_data or {}).get("label"),
                                "confidence": 1.0,
                                "signal_confidence": getattr(s, "confidence", 0.8),
                                "bbox": (s.raw_data or {}).get("bbox"),
                                "model": (s.raw_data or {}).get("model", "grounding_dino"),
                            },
                            rule,
                        )
                        violations.append(
                            ViolationSchema(
                                signal_id=signal_id,
                                rule_id=rule_id,
                                violation_type="vision_object",
                                severity=severity_float,
                                evidence_data=evidence_data,
                            )
                        )

        return violations

    def _matches_rule(self, text: str, rule: dict) -> tuple[str, float] | None:
        for pat in rule.get("exception_patterns", []):
            if re.search(pat, text, re.IGNORECASE):
                return None
        text_lower = text.lower()
        for term in rule.get("exception_terms", []):
            if term.lower() in text_lower:
                return None
        context_terms = rule.get("context_terms", [])
        if context_terms:
            if not any(t.lower() in text_lower for t in context_terms):
                return None
        for pattern_info in rule.get("patterns", []):
            pattern = pattern_info.get("pattern", "")
            confidence = pattern_info.get("confidence", 0.9)
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return (match.group(0), confidence)
        for term in rule.get("prohibited_terms", []):
            term_lower = term.lower()
            if term_lower in text:
                text_with_spaces = f" {text} "
                if f" {term_lower} " in text_with_spaces:
                    return (term, 0.95)
                return (term, 0.85)
        return None
