# zetaone policy engine

from typing import Any

from zetaone.policy_engine.evaluator import PolicyEvaluator
from zetaone.policy_engine.rule import Rule


class PolicyEngine:
    """
    Deterministic policy evaluation engine.
    Policies are loaded from configuration (YAML/registry), never hard-coded.
    """

    def __init__(self) -> None:
        self._evaluator = PolicyEvaluator()

    def load_policy_pack(self, config_path: str | dict[str, Any]) -> list[Rule]:
        """
        Load policy pack from config file or dict.
        Returns list of Rule instances.
        """
        pass

    def evaluate(
        self,
        signals: dict[str, Any],
        policy_pack_id: str | None = None,
        rules: list[Rule] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Evaluate policies against signals. Returns violations.
        Either policy_pack_id (load from config) or rules must be provided.
        Deterministic: same inputs → same outputs.
        """
        pass
