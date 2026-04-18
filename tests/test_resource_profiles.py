"""Tests for resource profile system."""

import os

import pytest

from src.resource_profiles import (
    PROFILES,
    ProfileName,
    ResourceProfile,
    detect_hardware,
    detect_recommended_profile,
    feature_enabled,
    get_active_profile,
    reset_active_profile,
    set_active_profile,
)


@pytest.fixture(autouse=True)
def _reset_profile():
    """Reset cached active profile and MITS_PROFILE env var before each test."""
    reset_active_profile()
    prev = os.environ.pop("MITS_PROFILE", None)
    yield
    reset_active_profile()
    if prev is not None:
        os.environ["MITS_PROFILE"] = prev


class TestProfileDefinitions:
    def test_three_profiles_registered(self) -> None:
        assert set(PROFILES.keys()) == {
            ProfileName.LITE,
            ProfileName.STANDARD,
            ProfileName.MAX,
        }

    def test_lite_runs_on_cpu(self) -> None:
        p = PROFILES[ProfileName.LITE]
        assert p.min_vram_gb == 0
        assert p.llm_gpu_layers == 0
        assert p.llm_quantization == "Q4_K_M"

    def test_max_enables_all_features(self) -> None:
        p = PROFILES[ProfileName.MAX]
        assert p.enable_rubert_affect
        assert p.enable_dkt
        assert p.enable_llm_verifier
        assert p.enable_batch_inference
        assert p.enable_speculative_decoding
        assert p.enable_tom_agent  # ToM-Tutor (017)

    def test_tom_agent_flags_per_profile(self) -> None:
        """T008: enable_tom_agent корректно установлен per profile."""
        assert PROFILES[ProfileName.LITE].enable_tom_agent is False
        assert PROFILES[ProfileName.STANDARD].enable_tom_agent is True
        assert PROFILES[ProfileName.MAX].enable_tom_agent is True

    def test_tom_prompt_style_per_profile(self) -> None:
        """T008: tom_prompt_style соответствует профилю."""
        assert PROFILES[ProfileName.LITE].tom_prompt_style == "short"
        assert PROFILES[ProfileName.STANDARD].tom_prompt_style == "full"
        assert PROFILES[ProfileName.MAX].tom_prompt_style == "full"

    def test_tom_output_cap_increases_with_profile(self) -> None:
        """T008: output cap растёт с профилем (больше ресурсов = полнее reasoning)."""
        lite = PROFILES[ProfileName.LITE]
        std = PROFILES[ProfileName.STANDARD]
        mx = PROFILES[ProfileName.MAX]
        assert lite.tom_output_cap < std.tom_output_cap <= mx.tom_output_cap

    def test_profile_ordering_consistent(self) -> None:
        """Each profile should require >= resources than smaller one."""
        lite = PROFILES[ProfileName.LITE]
        std = PROFILES[ProfileName.STANDARD]
        mx = PROFILES[ProfileName.MAX]

        assert lite.min_ram_gb <= std.min_ram_gb <= mx.min_ram_gb
        assert lite.min_vram_gb <= std.min_vram_gb <= mx.min_vram_gb
        assert lite.llm_context_tokens <= std.llm_context_tokens <= mx.llm_context_tokens


class TestProfileSelection:
    def test_env_var_override(self) -> None:
        os.environ["MITS_PROFILE"] = "lite"
        p = get_active_profile()
        assert p.name == ProfileName.LITE

    def test_invalid_env_var_falls_to_detect(self) -> None:
        os.environ["MITS_PROFILE"] = "not_a_profile"
        # Should fall back to auto-detect, not crash
        p = get_active_profile()
        assert isinstance(p, ResourceProfile)

    def test_set_active_profile_overrides(self) -> None:
        set_active_profile(ProfileName.MAX)
        assert get_active_profile().name == ProfileName.MAX

    def test_reset_clears_cache(self) -> None:
        set_active_profile(ProfileName.MAX)
        reset_active_profile()
        # After reset, should re-detect (no assertion on result, just no crash)
        get_active_profile()


class TestHardwareDetection:
    def test_detect_returns_dict(self) -> None:
        hw = detect_hardware()
        assert "ram_gb" in hw
        assert "vram_gb" in hw
        assert hw["ram_gb"] > 0
        assert hw["vram_gb"] >= 0

    def test_recommended_profile_is_valid(self) -> None:
        name = detect_recommended_profile()
        assert name in PROFILES


class TestFeatureFlags:
    def test_lite_disables_heavy_features(self) -> None:
        set_active_profile(ProfileName.LITE)
        assert not feature_enabled("enable_rubert_affect")
        assert not feature_enabled("enable_llm_verifier")
        assert not feature_enabled("enable_batch_inference")

    def test_max_enables_heavy_features(self) -> None:
        set_active_profile(ProfileName.MAX)
        assert feature_enabled("enable_rubert_affect")
        assert feature_enabled("enable_llm_verifier")
        assert feature_enabled("enable_batch_inference")

    def test_unknown_feature_returns_false(self) -> None:
        set_active_profile(ProfileName.MAX)
        assert not feature_enabled("enable_nonexistent_thing")


class TestProfileIntegration:
    """Verify profile is respected by downstream components."""

    def test_graph_evolver_honors_profile(self, tmp_path) -> None:
        """GraphEvolver should disable LLM verifier when profile forbids it."""
        from src.knowledge.graph_evolution import GraphEvolver, ProposalQueue
        from src.knowledge.knowledge_forge import KnowledgeGraph

        set_active_profile(ProfileName.LITE)
        graph = KnowledgeGraph()
        queue = ProposalQueue(storage_path=tmp_path / "q.json")

        def dummy_verifier(proposal, graph):
            return True, "dummy"

        evolver = GraphEvolver(
            graph=graph,
            queue=queue,
            llm_verifier=dummy_verifier,
            growth_log_path=tmp_path / "g.jsonl",
        )
        # Profile LITE has enable_llm_verifier=False → verifier should be cleared
        assert evolver._llm_verifier is None

    def test_max_profile_keeps_verifier(self, tmp_path) -> None:
        from src.knowledge.graph_evolution import GraphEvolver, ProposalQueue
        from src.knowledge.knowledge_forge import KnowledgeGraph

        set_active_profile(ProfileName.MAX)
        graph = KnowledgeGraph()
        queue = ProposalQueue(storage_path=tmp_path / "q.json")

        def dummy_verifier(proposal, graph):
            return True, "dummy"

        evolver = GraphEvolver(
            graph=graph,
            queue=queue,
            llm_verifier=dummy_verifier,
            growth_log_path=tmp_path / "g.jsonl",
        )
        # Profile MAX allows verifier
        assert evolver._llm_verifier is not None
