"""Match providers — simulated IPL chase for demos."""

from __future__ import annotations

from app.schemas import MatchState

_match = MatchState()


class SimulatedMatchProvider:
    def get_state(self) -> MatchState:
        return _match

    def simulate(
        self,
        *,
        required_run_rate: float = 14.0,
        is_timeout: bool = True,
        is_tense_chase: bool = True,
        overs: float = 17.3,
        teams: str = "MI vs CSK",
    ) -> MatchState:
        global _match
        _match = MatchState(
            match_id="ipl-sim-1",
            teams=teams,
            overs=overs,
            required_run_rate=required_run_rate,
            is_timeout=is_timeout,
            is_tense_chase=is_tense_chase,
            status="in_play",
            note="Simulated tense chase for Concierge Ops demo",
        )
        return _match

    def reset(self) -> MatchState:
        global _match
        _match = MatchState(is_timeout=False, is_tense_chase=False, required_run_rate=6.0)
        return _match


match_provider = SimulatedMatchProvider()
