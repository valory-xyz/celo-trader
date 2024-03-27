# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2024 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""This package contains the rounds of CeloTraderAbciApp."""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple, cast

from packages.valory.skills.celo_trader_abci.payloads import (
    DecisionMakingPayload,
    MechRequestPreparationPayload,
    PostTxDecisionMakingPayload,
    SwapPreparationPayload,
)
from packages.valory.skills.abstract_round_abci.base import (
    AbciApp,
    AbciAppTransitionFunction,
    AppState,
    BaseSynchronizedData,
    CollectSameUntilThresholdRound,
    DegenerateRound,
    EventToTimeout,
    get_name,
)


class Event(Enum):
    """CeloTraderAbciApp Events"""

    DECISION_MAKING = "decision_making"
    MECH = "mech"
    SETTLE = "settle"
    DONE = "done"
    NO_MAJORITY = "no_majority"
    ROUND_TIMEOUT = "round_timeout"


@dataclass
class MechMetadata:
    """A Mech's metadata."""

    prompt: str
    tool: str
    nonce: str


@dataclass
class MechRequest:
    """A Mech's request."""

    data: str = ""
    requestId: int = 0


@dataclass
class MechInteractionResponse(MechRequest):
    """A structure for the response of a mech interaction task."""

    nonce: str = ""
    result: Optional[str] = None
    error: str = "Unknown"

    def retries_exceeded(self) -> None:
        """Set an incorrect format response."""
        self.error = "Retries were exceeded while trying to get the mech's response."

    def incorrect_format(self, res: Any) -> None:
        """Set an incorrect format response."""
        self.error = f"The response's format was unexpected: {res}"


class SynchronizedData(BaseSynchronizedData):
    """
    Class to represent the synchronized data.

    This data is replicated by the tendermint application.
    """

    @property
    def mech_requests(self) -> List[MechMetadata]:
        """Get the mech requests."""
        serialized = self.db.get("mech_requests", "[]")
        requests = json.loads(serialized)  # type: ignore
        return [MechMetadata(**metadata_item) for metadata_item in requests]

    @property
    def mech_responses(self) -> List[MechInteractionResponse]:
        """Get the mech responses."""
        serialized = self.db.get("mech_responses", "[]")
        responses = json.loads(serialized)  # type: ignore
        return [MechInteractionResponse(**response_item) for response_item in responses]

    @property
    def most_voted_tx_hash(self) -> str:
        """Get the most_voted_tx_hash."""
        return cast(str, self.db.get_strict("most_voted_tx_hash"))

    @property
    def post_tx_event(self) -> Optional[str]:
        """Get the post_tx_event."""
        return cast(str, self.db.get("post_tx_event", None))


class DecisionMakingRound(CollectSameUntilThresholdRound):
    """DecisionMakingRound"""

    payload_class = DecisionMakingPayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            event = Event(self.most_voted_payload.event)

            updates = {
                "mech_requests": self.most_voted_payload.mech_requests,
                "mech_responses": self.most_voted_payload.mech_responses,
                "most_voted_tx_hash": self.most_voted_payload.tx_hash,
                "post_tx_event": self.most_voted_payload.post_tx_event,
            }

            synchronized_data = self.synchronized_data.update(
                synchronized_data_class=self.synchronized_data_class,
                **{
                    get_name(getattr(SynchronizedData, k)): v
                    for k, v in updates.items()
                },
            )

            return synchronized_data, event

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class PostTxDecisionMakingRound(CollectSameUntilThresholdRound):
    """PostTxDecisionMakingRound"""

    payload_class = PostTxDecisionMakingPayload
    synchronized_data_class = SynchronizedData

    def end_block(self) -> Optional[Tuple[BaseSynchronizedData, Event]]:
        """Process the end of the block."""
        if self.threshold_reached:
            return self.synchronized_data, Event(self.most_voted_payload)

        if not self.is_majority_possible(
            self.collection, self.synchronized_data.nb_participants
        ):
            return self.synchronized_data, Event.NO_MAJORITY
        return None


class FinishedDecisionMakingMechRound(DegenerateRound):
    """FinishedDecisionMakingMechRound"""


class FinishedDecisionMakingSettleRound(DegenerateRound):
    """FinishedDecisionMakingSettleRound"""


class FinishedPostTxDecisionMakingMechRound(DegenerateRound):
    """FinishedPostTxDecisionMakingMechRound"""


class FinishedDecisionMakingResetRound(DegenerateRound):
    """FinishedDecisionMakingResetRound"""


class CeloTraderAbciApp(AbciApp[Event]):
    """CeloTraderAbciApp"""

    initial_round_cls: AppState = DecisionMakingRound
    initial_states: Set[AppState] = {
        PostTxDecisionMakingRound,
        DecisionMakingRound,
    }
    transition_function: AbciAppTransitionFunction = {
        DecisionMakingRound: {
            Event.MECH: FinishedDecisionMakingMechRound,
            Event.SETTLE: FinishedDecisionMakingSettleRound,
            Event.NO_MAJORITY: DecisionMakingRound,
            Event.ROUND_TIMEOUT: DecisionMakingRound,
            Event.DONE: FinishedDecisionMakingResetRound,
        },
        PostTxDecisionMakingRound: {
            Event.MECH: FinishedPostTxDecisionMakingMechRound,
            Event.DECISION_MAKING: DecisionMakingRound,
            Event.NO_MAJORITY: PostTxDecisionMakingRound,
            Event.ROUND_TIMEOUT: PostTxDecisionMakingRound,
        },
        FinishedDecisionMakingMechRound: {},
        FinishedDecisionMakingSettleRound: {},
        FinishedPostTxDecisionMakingMechRound: {},
    }
    final_states: Set[AppState] = {
        FinishedDecisionMakingMechRound,
        FinishedDecisionMakingSettleRound,
        FinishedPostTxDecisionMakingMechRound,
        FinishedDecisionMakingResetRound
    }
    event_to_timeout: EventToTimeout = {}
    cross_period_persisted_keys: FrozenSet[str] = frozenset()
    db_pre_conditions: Dict[AppState, Set[str]] = {
        DecisionMakingRound: set(),
        PostTxDecisionMakingRound: set(),
    }
    db_post_conditions: Dict[AppState, Set[str]] = {
        FinishedDecisionMakingMechRound: set(),
        FinishedDecisionMakingSettleRound: set(),
        FinishedPostTxDecisionMakingMechRound: set(),
        FinishedDecisionMakingResetRound: set(),
    }
