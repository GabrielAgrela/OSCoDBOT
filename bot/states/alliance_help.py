from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, State
from bot.actions import Screenshot, FindAndClick, Wait, EndCycle, CooldownGate, SetCooldownRandom


def build_alliance_help_state(cfg: AppConfig) -> tuple[State, Context]:
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )

    steps = [
        # Skip running while in cooldown
        GraphStep(
            name="CooldownGate",
            actions=[CooldownGate(name="alliance_help_cooldown_gate", key="alliance_help")],
            on_success="ClickHelp",
            on_failure="CooldownGate",
        ),
        GraphStep(
            name="ClickHelp",
            actions=[
                Screenshot(name="help_cap_1"),
                Wait(name="wait_after_screenshot", seconds=2.0),
                FindAndClick(
                    name="AllianceHelp",
                    templates=["AllianceHelp.png", "AllianceHelpBig.png"],
                    region_pct=cfg.alliance_help_region_pct,
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="CooldownAndEnd",
            on_failure="CooldownAndEnd",
        ),
        GraphStep(
            name="CooldownAndEnd",
            actions=[
                SetCooldownRandom(
                    name="alliance_help_set_cooldown",
                    key="alliance_help",
                    min_seconds=getattr(cfg, 'alliance_help_cooldown_min_s', 300),
                    max_seconds=getattr(cfg, 'alliance_help_cooldown_max_s', 900),
                ),
            ],
            on_success="End",
            on_failure="End",
        ),
        GraphStep(
            name="End",
            actions=[EndCycle(name="end_cycle")],
            on_success="CooldownGate",
            on_failure="CooldownGate",
        ),
    ]
    state = GraphState(steps=steps, start="CooldownGate", loop_sleep_s=0.05)
    return state, ctx
