"""Smoke tests for the PNG report card renderer."""

from __future__ import annotations

import io
import os

import pytest
from PIL import Image

from src.bot_state import BotState
from src.card_renderer import CARD_H, CARD_W, _PC_H, _PC_W, build_card_from_state, build_periodic_card


class TestCardRendererSmoke:
    def test_spot_card_returns_bytesio(self, connected_spot_state: BotState) -> None:
        buf = build_card_from_state("Test-Spot", connected_spot_state)
        assert isinstance(buf, io.BytesIO)
        assert buf.tell() == 0
        data = buf.read()
        assert len(data) > 5_000  # non-trivial PNG

    def test_perp_card_returns_bytesio(self, connected_perp_state: BotState) -> None:
        buf = build_card_from_state("Test-Perp", connected_perp_state)
        assert isinstance(buf, io.BytesIO)
        assert buf.tell() == 0
        data = buf.read()
        assert len(data) > 5_000

    def test_spot_card_is_valid_png(self, connected_spot_state: BotState) -> None:
        buf = build_card_from_state("Test-Spot", connected_spot_state)
        img = Image.open(buf)
        assert img.size == (CARD_W, CARD_H)
        assert img.mode == "RGB"

    def test_perp_card_is_valid_png(self, connected_perp_state: BotState) -> None:
        buf = build_card_from_state("Test-Perp", connected_perp_state)
        img = Image.open(buf)
        assert img.size == (CARD_W, CARD_H)
        assert img.mode == "RGB"

    def test_raises_on_no_summary(self) -> None:
        state = BotState(label="X", url="ws://x", connected=True)
        with pytest.raises(ValueError, match="No summary data"):
            build_card_from_state("X", state)

    def test_spot_card_with_nonzero_deltas(self, connected_spot_state: BotState) -> None:
        connected_spot_state.prev_roundtrips = 10
        connected_spot_state.prev_matched_profit = 30.0
        connected_spot_state.prev_total_fees = 1.5
        buf = build_card_from_state("Delta-Spot", connected_spot_state)
        img = Image.open(buf)
        assert img.size == (CARD_W, CARD_H)

    def test_perp_card_with_nonzero_deltas(self, connected_perp_state: BotState) -> None:
        connected_perp_state.prev_roundtrips = 5
        connected_perp_state.prev_matched_profit = 80.0
        connected_perp_state.prev_total_fees = 4.0
        buf = build_card_from_state("Delta-Perp", connected_perp_state)
        img = Image.open(buf)
        assert img.size == (CARD_W, CARD_H)

    def test_spot_card_negative_pnl(self, connected_spot_state: BotState) -> None:
        connected_spot_state.summary.total_profit = -42.50  # type: ignore[union-attr]
        connected_spot_state.summary.matched_profit = -38.00  # type: ignore[union-attr]
        buf = build_card_from_state("Loss-Spot", connected_spot_state)
        img = Image.open(buf)
        assert img.size == (CARD_W, CARD_H)

    def test_saves_card_when_requested(
        self, connected_spot_state: BotState, connected_perp_state: BotState, tmp_path
    ) -> None:
        """Visual inspection helper: set SAVE_TEST_CARDS=1 to write PNGs to /tmp."""
        if not os.environ.get("SAVE_TEST_CARDS"):
            pytest.skip("Set SAVE_TEST_CARDS=1 to enable visual output")

        for label, state in [("spot", connected_spot_state), ("perp", connected_perp_state)]:
            buf = build_card_from_state(f"Test-{label.upper()}", state)
            out_path = tmp_path / f"card_{label}.png"
            out_path.write_bytes(buf.read())
            print(f"Saved {label} card to {out_path}")


class TestPeriodicCardSmoke:
    def test_spot_periodic_card_returns_bytesio(self, connected_spot_state: BotState) -> None:
        buf = build_periodic_card("Test-Spot", connected_spot_state)
        assert isinstance(buf, io.BytesIO)
        assert buf.tell() == 0
        assert len(buf.read()) > 1_000

    def test_perp_periodic_card_returns_bytesio(self, connected_perp_state: BotState) -> None:
        buf = build_periodic_card("Test-Perp", connected_perp_state)
        assert isinstance(buf, io.BytesIO)
        assert buf.tell() == 0
        assert len(buf.read()) > 1_000

    def test_periodic_card_dimensions(self, connected_spot_state: BotState) -> None:
        buf = build_periodic_card("Test-Spot", connected_spot_state)
        img = Image.open(buf)
        assert img.size == (_PC_W, _PC_H)
        assert img.mode == "RGB"

    def test_periodic_card_with_deltas(self, connected_spot_state: BotState) -> None:
        connected_spot_state.prev_roundtrips = 10
        connected_spot_state.prev_matched_profit = 30.0
        connected_spot_state.prev_total_fees = 1.5
        buf = build_periodic_card("Delta-Spot", connected_spot_state)
        img = Image.open(buf)
        assert img.size == (_PC_W, _PC_H)

    def test_periodic_card_raises_on_no_summary(self) -> None:
        state = BotState(label="X", url="ws://x", connected=True)
        with pytest.raises(ValueError, match="No summary data"):
            build_periodic_card("X", state)

    def test_saves_periodic_card_when_requested(
        self, connected_spot_state: BotState, connected_perp_state: BotState, tmp_path
    ) -> None:
        """Visual inspection: set SAVE_TEST_CARDS=1 to write PNGs."""
        if not os.environ.get("SAVE_TEST_CARDS"):
            pytest.skip("Set SAVE_TEST_CARDS=1 to enable visual output")

        for label, state in [("spot", connected_spot_state), ("perp", connected_perp_state)]:
            state.prev_roundtrips = 5
            state.prev_matched_profit = 20.0
            state.prev_total_fees = 1.0
            buf = build_periodic_card(f"Periodic-{label.upper()}", state)
            out_path = tmp_path / f"periodic_{label}.png"
            out_path.write_bytes(buf.read())
            print(f"Saved periodic {label} card to {out_path}")
