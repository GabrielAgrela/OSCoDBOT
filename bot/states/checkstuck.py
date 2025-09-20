from __future__ import annotations

from bot.config import AppConfig
from bot.core.state_machine import Context, GraphState, GraphStep, State
from bot.actions import Screenshot, FindAndClick, Wait, EndCycle


def build_checkstuck_state(cfg: AppConfig) -> tuple[State, Context]:
    """Build a simple state that tries to click a Back/Close arrow.

    Currently: capture -> find BackArrow.png in the top-left region -> click -> short wait -> end cycle.
    """
    ctx = Context(
        window_title_substr=cfg.window_title_substr,
        templates_dir=cfg.templates_dir,
        save_shots=cfg.save_shots,
        shots_dir=cfg.shots_dir,
    )

    steps = [
        GraphStep(
            name="ClickBackArrow",
            actions=[
                Screenshot(name="checkstuck_cap_1"),
                FindAndClick(
                    name="BackArrow",
                    templates=["BackArrow.png"],
                    region_pct=getattr(cfg, "back_arrow_region_pct", (0.0, 0.0, 0.1, 0.1)),
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="ClickBackArrow",
            on_failure="ClickCloseButton",
        ),
        GraphStep(
            name="ClickCloseButton",
            actions=[
                Screenshot(name="checkstuck_cap_2"),
                FindAndClick(
                    name="CloseButton",
                    templates=["CloseButton.png"],
                    region_pct=cfg.resource_buy_window_close_button_region_pct,
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="EndCycleStep",
            on_failure="ClickReconnectConfirm",
        ),
        GraphStep(
            name="ClickReconnectConfirm",
            actions=[
                Screenshot(name="checkstuck_cap_3"),
                FindAndClick(
                    name="ReconnectConfirmButton",
                    templates=["ReconnectConfirmButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="EndCycleStep",
            on_failure="ChatCloseButton",
        ),
        GraphStep(
            name="ChatCloseButton",
            actions=[
                Screenshot(name="checkstuck_cap_3"),
                FindAndClick(
                    name="ChatCloseButton",
                    templates=["ChatCloseButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="EndCycleStep",
            on_failure="OfferCloseButton",
        ),
        GraphStep(
            name="OfferCloseButton",
            actions=[
                Screenshot(name="checkstuck_cap_3"),
                FindAndClick(
                    name="OfferCloseButton",
                    templates=["OfferCloseButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                ),
            ],
            on_success="EndCycleStep",
            on_failure="CloseNewHeroesButton",
        ),
        GraphStep(
            name="CloseNewHeroesButton",
            actions=[
                Screenshot(name="checkstuck_cap_3"),
                FindAndClick(
                    name="CloseNewHeroesButton",
                    templates=["CloseNewHeroesButton.png"],
                    region_pct=(0.0, 0.0, 1.0, 1.0),
                    threshold=cfg.match_threshold,
                    verify_threshold=0.9,
                ),
            ],
            on_success="EndCycleStep",
            on_failure="EndCycleStep",
        ),
        GraphStep(
            name="EndCycleStep",
            actions=[
                EndCycle(name="end_cycle"),
            ],
            on_success="ClickBackArrow",
            on_failure="ClickBackArrow",
        ),
    ]

    state = GraphState(steps=steps, start="ClickBackArrow", loop_sleep_s=0.05)
    return state, ctx

