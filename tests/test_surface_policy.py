"""Dedicated comprehensive tests for SurfacePolicyEngine.

Covers:
- Hot-reloading config/surfaces.yaml on disk changes and error resilience
- Time-based urgency rules (after-hours, weekends, cross-midnight windows)
- Keyword-based urgency detection and hint overrides
- Autonomy restriction recommendations by surface type (mobile = supervised, urgent overrides)
- Dynamic token budgets for urgency and off-hours
- Fallback defaults for unconfigured or unknown surfaces
"""

import os
import time as stdlib_time
from datetime import datetime, time, timezone
from pathlib import Path

import yaml
from contracts.models import PolicyEvaluation, SurfaceContext
from routing_surface_policy.policy import (
    SurfacePolicyEngine,
    SurfacePolicyRegistry,
    _is_in_time_window,
    _parse_time,
)


def test_parse_time_helper() -> None:
    """Test time parsing utility with valid and invalid values."""
    assert _parse_time("18:00") == time(18, 0, 0)
    assert _parse_time("08:30:15") == time(8, 30, 15)
    assert _parse_time(time(12, 0)) == time(12, 0)
    assert _parse_time("invalid") is None
    assert _parse_time(12345) is None


def test_is_in_time_window_helper() -> None:
    """Test time window logic for same-day and overnight windows."""
    # Daytime window: 09:00 to 17:00
    start_day = time(9, 0)
    end_day = time(17, 0)
    assert _is_in_time_window(time(12, 0), start_day, end_day) is True
    assert _is_in_time_window(time(8, 59), start_day, end_day) is False
    assert _is_in_time_window(time(17, 0), start_day, end_day) is False
    assert _is_in_time_window(time(20, 0), start_day, end_day) is False

    # Overnight window: 18:00 to 08:00
    start_night = time(18, 0)
    end_night = time(8, 0)
    assert _is_in_time_window(time(18, 0), start_night, end_night) is True
    assert _is_in_time_window(time(23, 59), start_night, end_night) is True
    assert _is_in_time_window(time(4, 30), start_night, end_night) is True
    assert _is_in_time_window(time(7, 59), start_night, end_night) is True
    assert _is_in_time_window(time(8, 0), start_night, end_night) is False
    assert _is_in_time_window(time(12, 0), start_night, end_night) is False


def test_hot_reload_on_file_change(tmp_path: Path) -> None:
    """Verify that SurfacePolicyEngine detects file modification and reloads config."""
    cfg_file = tmp_path / "surfaces.yaml"
    initial_config = {
        "version": "1.0",
        "surfaces": {
            "cli": {
                "max_tokens_budget": 2048,
                "urgency_keywords": ["urgent"],
                "default_autonomy": "semi",
            }
        },
    }
    cfg_file.write_text(yaml.dump(initial_config), encoding="utf-8")

    engine = SurfacePolicyEngine(cfg_file)
    ctx = SurfaceContext(surface_type="cli", client_id="cli-1")

    # Initial evaluation
    eval1 = engine.evaluate(ctx, "regular query")
    assert eval1.max_tokens_budget == 2048
    assert eval1.is_urgent is False

    # Update config file on disk and bump mtime deterministically without sleep
    updated_config = {
        "version": "1.0",
        "surfaces": {
            "cli": {
                "max_tokens_budget": 8192,
                "urgency_keywords": ["critical", "p0"],
                "default_autonomy": "full",
            }
        },
    }
    cfg_file.write_text(yaml.dump(updated_config), encoding="utf-8")
    new_mtime = (engine.config_mtime or stdlib_time.time()) + 2
    os.utime(cfg_file, (new_mtime, new_mtime))

    # Second evaluation picks up the new config automatically
    eval2 = engine.evaluate(ctx, "regular query")
    assert eval2.max_tokens_budget == 8192
    assert eval2.default_autonomy == "full"
    assert eval2.extras.get("config_reloaded") is True

    # Check new keywords
    eval_urgent = engine.evaluate(ctx, "this is a critical bug")
    assert eval_urgent.is_urgent is True


def test_hot_reload_error_resilience(tmp_path: Path) -> None:
    """Verify that corrupt YAML files do not crash the engine and keep previous valid config."""
    cfg_file = tmp_path / "surfaces.yaml"
    valid_config = {
        "version": "1.0",
        "surfaces": {
            "web": {
                "max_tokens_budget": 4000,
                "default_autonomy": "semi",
            }
        },
    }
    cfg_file.write_text(yaml.dump(valid_config), encoding="utf-8")

    engine = SurfacePolicyEngine(cfg_file)
    ctx = SurfaceContext(surface_type="web", client_id="web-1")
    eval_initial = engine.evaluate(ctx, "hello")
    assert eval_initial.max_tokens_budget == 4000

    # Write broken YAML and bump mtime deterministically without sleep
    cfg_file.write_text("invalid: [yaml: broken :::", encoding="utf-8")
    new_mtime = (engine.config_mtime or stdlib_time.time()) + 2
    os.utime(cfg_file, (new_mtime, new_mtime))

    # Evaluate should not raise an exception, and keeps previous config
    eval_broken = engine.evaluate(ctx, "hello")
    assert eval_broken.max_tokens_budget == 4000


def test_keyword_urgency_detection() -> None:
    """Test keyword-based urgency matching and urgency hints."""
    engine = SurfacePolicyEngine("config/surfaces.yaml")
    ctx = SurfaceContext(surface_type="cli", client_id="cli-1")
    day_dt = datetime(2026, 10, 14, 14, 0, 0, tzinfo=timezone.utc)

    # Matches keyword 'urgent'
    eval_kw = engine.evaluate(ctx, "Please handle this urgent ticket", now=day_dt)
    assert eval_kw.is_urgent is True
    assert eval_kw.urgency == "high"
    assert eval_kw.extras["keyword_matched"] is True

    # Matches keyword 'asap'
    eval_asap = engine.evaluate(ctx, "Need this done ASAP", now=day_dt)
    assert eval_asap.is_urgent is True

    # Normal text
    eval_norm = engine.evaluate(ctx, "List all active users", now=day_dt)
    assert eval_norm.is_urgent is False
    assert eval_norm.urgency == "normal"

    # Urgency hint override
    ctx_hint = SurfaceContext(surface_type="cli", client_id="cli-1", urgency_hint="high")
    eval_hint = engine.evaluate(ctx_hint, "Normal text with high hint", now=day_dt)
    assert eval_hint.is_urgent is True
    assert eval_hint.urgency == "high"

    # Urgent keyword with low urgency hint should NOT be downgraded
    ctx_low_hint = SurfaceContext(surface_type="cli", client_id="cli-1", urgency_hint="low")
    eval_urgent_low = engine.evaluate(ctx_low_hint, "CRITICAL BUG FIX ASAP", now=day_dt)
    assert eval_urgent_low.is_urgent is True
    assert eval_urgent_low.urgency == "high"


def test_time_based_after_hours_escalation() -> None:
    """Test after-hours time rules with deterministic timestamps."""
    engine = SurfacePolicyEngine("config/surfaces.yaml")
    ctx = SurfaceContext(surface_type="cli", client_id="cli-1")

    # Wednesday at 14:00 (daytime business hours)
    day_dt = datetime(2026, 10, 14, 14, 0, 0, tzinfo=timezone.utc)
    eval_day = engine.evaluate(ctx, "Run standard deployment", now=day_dt)
    assert eval_day.is_urgent is False
    assert eval_day.extras["time_escalation_applied"] is False

    # Wednesday at 23:00 (after hours: 18:00 - 08:00) with urgent keyword
    night_dt = datetime(2026, 10, 14, 23, 0, 0, tzinfo=timezone.utc)
    eval_night_urgent = engine.evaluate(ctx, "urgent: db cluster failure", now=night_dt)
    assert eval_night_urgent.is_urgent is True
    assert eval_night_urgent.urgency == "high"
    assert eval_night_urgent.extras["time_escalation_applied"] is True
    assert eval_night_urgent.extras["time_reason"] == "after_hours"


def test_time_based_all_messages_rule(tmp_path: Path) -> None:
    """Test a surface configured to treat all off-hours traffic as urgent."""
    cfg_file = tmp_path / "surfaces.yaml"
    config = {
        "version": "1.0",
        "surfaces": {
            "pager": {
                "max_tokens_budget": 1024,
                "default_autonomy": "semi",
                "time_urgency_rules": {
                    "after_hours": {
                        "start": "20:00",
                        "end": "06:00",
                        "all_messages": True,
                        "escalate_to": "urgent",
                    }
                },
            }
        },
    }
    cfg_file.write_text(yaml.dump(config), encoding="utf-8")
    engine = SurfacePolicyEngine(cfg_file)
    ctx = SurfaceContext(surface_type="pager", client_id="pager-1")

    night_dt = datetime(2026, 10, 14, 22, 0, 0)
    eval_night = engine.evaluate(ctx, "Routine heartbeat", now=night_dt)
    assert eval_night.is_urgent is True
    assert eval_night.urgency == "high"
    assert eval_night.extras["time_reason"] == "after_hours"

    day_dt = datetime(2026, 10, 14, 10, 0, 0)
    eval_day = engine.evaluate(ctx, "Routine heartbeat", now=day_dt)
    assert eval_day.is_urgent is False


def test_autonomy_restrictions_mobile_and_urgent() -> None:
    """Verify that mobile surfaces recommend supervised autonomy and urgent rules restrict further."""
    engine = SurfacePolicyEngine("config/surfaces.yaml")
    day_dt = datetime(2026, 10, 14, 14, 0, 0, tzinfo=timezone.utc)

    # Telegram (mobile) defaults to supervised
    tg_ctx = SurfaceContext(surface_type="telegram", client_id="tg-1")
    eval_tg_normal = engine.evaluate(tg_ctx, "status check", now=day_dt)
    assert eval_tg_normal.default_autonomy == "supervised"

    # Telegram on urgent restricts to read_only per surfaces.yaml
    eval_tg_urgent = engine.evaluate(tg_ctx, "urgent: database alert", now=day_dt)
    assert eval_tg_urgent.is_urgent is True
    assert eval_tg_urgent.default_autonomy == "read_only"
    assert eval_tg_urgent.extras["autonomy_restriction_applied"] is True

    # CLI defaults to semi, and restricts to supervised on urgent per surfaces.yaml
    cli_ctx = SurfaceContext(surface_type="cli", client_id="cli-1")
    eval_cli_normal = engine.evaluate(cli_ctx, "git status", now=day_dt)
    assert eval_cli_normal.default_autonomy == "semi"
    assert eval_cli_normal.extras["autonomy_restriction_applied"] is False

    eval_cli_urgent = engine.evaluate(cli_ctx, "emergency server rollback", now=day_dt)
    assert eval_cli_urgent.is_urgent is True
    assert eval_cli_urgent.default_autonomy == "supervised"
    assert eval_cli_urgent.extras["autonomy_restriction_applied"] is True


def test_dynamic_token_budgets() -> None:
    """Verify dynamic token budget adjustments for urgent and after-hours requests."""
    engine = SurfacePolicyEngine("config/surfaces.yaml")
    day_dt = datetime(2026, 10, 14, 14, 0, 0, tzinfo=timezone.utc)
    night_dt = datetime(2026, 10, 14, 23, 0, 0, tzinfo=timezone.utc)

    # CLI normal budget: 4096; urgent budget: 2048; after_hours budget: 1024
    cli_ctx = SurfaceContext(surface_type="cli", client_id="cli-1")
    eval_cli_norm = engine.evaluate(cli_ctx, "run benchmark", now=day_dt)
    assert eval_cli_norm.max_tokens_budget == 4096
    assert eval_cli_norm.extras["budget_policy"] == "default"

    # Daytime urgent request selects urgent budget
    eval_cli_urgent = engine.evaluate(cli_ctx, "urgent: process locked", now=day_dt)
    assert eval_cli_urgent.max_tokens_budget == 2048
    assert eval_cli_urgent.extras["budget_policy"] == "urgent_dynamic_budget"

    # Off-hours request selects after_hours dynamic budget (1024) instead of urgent budget (2048)
    eval_cli_night = engine.evaluate(cli_ctx, "night maintenance", now=night_dt)
    assert eval_cli_night.is_urgent is True
    assert eval_cli_night.max_tokens_budget == 1024
    assert eval_cli_night.extras["budget_policy"] == "after_hours_dynamic_budget"

    # Weekend request with all_messages: true escalates to high
    weekend_dt = datetime(2026, 10, 18, 12, 0, 0, tzinfo=timezone.utc)  # Sunday
    eval_cli_weekend = engine.evaluate(cli_ctx, "routine weekend ping", now=weekend_dt)
    assert eval_cli_weekend.is_urgent is True
    assert eval_cli_weekend.extras["time_escalation_applied"] is True
    assert eval_cli_weekend.extras["time_reason"] == "weekend"

    # Telegram normal budget: 1024; urgent budget: 512
    tg_ctx = SurfaceContext(surface_type="telegram", client_id="tg-1")
    eval_tg_norm = engine.evaluate(tg_ctx, "get summary", now=day_dt)
    assert eval_tg_norm.max_tokens_budget == 1024

    eval_tg_urgent = engine.evaluate(tg_ctx, "sos system failure", now=day_dt)
    assert eval_tg_urgent.max_tokens_budget == 512


def test_unconfigured_surface_fallback() -> None:
    """Verify robust fallbacks when an unconfigured surface type is passed."""
    engine = SurfacePolicyEngine()  # No config loaded
    ctx = SurfaceContext(surface_type="custom_iot_device", client_id="iot-1")

    res: PolicyEvaluation = engine.evaluate(ctx, "normal telemetric signal")
    assert res.is_urgent is False
    assert res.urgency == "normal"
    assert res.default_autonomy == "semi"
    assert res.max_tokens_budget == 2048


def test_surface_policy_registry() -> None:
    """Verify registry defaults and factory lookups."""
    SurfacePolicyRegistry.register_defaults("config/surfaces.yaml")
    engine = SurfacePolicyRegistry.get("yaml")
    assert isinstance(engine, SurfacePolicyEngine)

    ctx = SurfaceContext(surface_type="cli", client_id="cli-1")
    res = engine.evaluate(ctx, "test", now=datetime(2026, 10, 14, 14, 0, 0, tzinfo=timezone.utc))
    assert res.max_tokens_budget == 4096
