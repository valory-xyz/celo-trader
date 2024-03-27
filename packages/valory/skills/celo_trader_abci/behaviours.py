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

"""This package contains round behaviours of CeloTraderAbciApp."""

import json
import uuid
from abc import ABC
from dataclasses import asdict
from typing import Dict, Generator, Optional, Set, Type, cast

from packages.valory.skills.abstract_round_abci.base import AbstractRound
from packages.valory.skills.abstract_round_abci.behaviours import (
    AbstractRoundBehaviour,
    BaseBehaviour,
)
from packages.valory.skills.celo_trader_abci.models import Params, SharedState
from packages.valory.skills.celo_trader_abci.rounds import (
    CeloTraderAbciApp,
    DecisionMakingPayload,
    DecisionMakingRound,
    Event,
    MechMetadata,
    PostTxDecisionMakingPayload,
    PostTxDecisionMakingRound,
    SynchronizedData,
)


CELO_TOOL_NAME = ""
MECH_PROMPT = ""


class CeloSwapperBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the celo_swapper skill."""

    @property
    def synchronized_data(self) -> SynchronizedData:
        """Return the synchronized data."""
        return cast(SynchronizedData, super().synchronized_data)

    @property
    def params(self) -> Params:
        """Return the params."""
        return cast(Params, super().params)

    @property
    def local_state(self) -> SharedState:
        """Return the state."""
        return cast(SharedState, self.context.state)


class DecisionMakingBehaviour(CeloSwapperBaseBehaviour):
    """DecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = DecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            payload_data = self.get_payload()
            payload = DecisionMakingPayload(**payload_data)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_payload(self) -> Dict:
        """Get the payload"""

        # Default payload data which clears everything before resetting
        data = dict(
            event=Event.DONE.value,
            mech_requests="[]",
            tx_hash="",
            post_tx_event="",
        )

        # If there is both mech_response and tx_hash, it means we have already traded.
        # We emit DONE and clean all data.
        if (
            self.synchronized_data.mech_responses
            and self.synchronized_data.most_voted_tx_hash
        ):
            return data

        # If there is no mech_response, it means we still need to interact with the Mech
        # We transition into mech interact
        if not self.synchronized_data.mech_responses:
            data["event"] = Event.MECH.value
            data["mech_requests"] = self.get_mech_requests()
            data[
                "post_tx_event"
            ] = Event.MECH.value  # go back to mech response after settling
            return data

        # We have a mech response at this point.
        tx_hash = self.process_mech_response()

        # If the mech tool has decided not to trade, we skip trading.
        if not tx_hash:
            return data

        # We are settling a transaction
        data["event"] = Event.SETTLE.value
        data["tx_hash"] = tx_hash
        data[
            "post_tx_event"
        ] = Event.DECISION_MAKING.value  # come back to this skill after settling

        return data

    def get_mech_requests(self):
        """Get mech requests"""

        mech_requests = [
            asdict(
                MechMetadata(
                    nonce=str(uuid.uuid4()),
                    tool=CELO_TOOL_NAME,
                    prompt=MECH_PROMPT,
                )
            )
        ]

        return json.dumps(mech_requests)

    def process_mech_response(self) -> Optional[str]:
        """Get the swap data from the mech response"""
        mech_responses = self.synchronized_data.mech_responses

        # TODO: this method should return None if the mech tool has decided not to trade
        # or the tx_hash from that tool if it has decided to trade
        tx_hash = None

        return tx_hash


class PostTxDecisionMakingBehaviour(CeloSwapperBaseBehaviour):
    """PostTxDecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = PostTxDecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            event = cast(str, self.synchronized_data.post_tx_event)
            sender = self.context.agent_address
            payload = PostTxDecisionMakingPayload(sender=sender, event=event)

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()


class CeloTraderRoundBehaviour(AbstractRoundBehaviour):
    """CeloTraderRoundBehaviour"""

    initial_behaviour_cls = DecisionMakingBehaviour
    abci_app_cls = CeloTraderAbciApp  # type: ignore
    behaviours: Set[Type[BaseBehaviour]] = [
        DecisionMakingBehaviour,
        PostTxDecisionMakingBehaviour,
    ]
