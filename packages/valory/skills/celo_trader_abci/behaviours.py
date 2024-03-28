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
from packages.valory.skills.celo_trader_abci.payloads import (
    DecisionMakingPayload,
    PostTxDecisionMakingPayload,
)
from packages.valory.skills.celo_trader_abci.rounds import (
    CeloTraderAbciApp,
    DecisionMakingRound,
    Event,
    MechMetadata,
    PostTxDecisionMakingRound,
    SynchronizedData,
)




class CeloTraderBaseBehaviour(BaseBehaviour, ABC):
    """Base behaviour for the celo_trader_abci skill."""

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


class DecisionMakingBehaviour(CeloTraderBaseBehaviour):
    """DecisionMakingBehaviour"""

    matching_round: Type[AbstractRound] = DecisionMakingRound

    def async_act(self) -> Generator:
        """Do the act, supporting asynchronous execution."""

        with self.context.benchmark_tool.measure(self.behaviour_id).local():
            payload_data = self.get_payload_data()
            payload = DecisionMakingPayload(
                sender=self.context.agent_address,
                content=json.dumps(payload_data, sort_keys=True),
            )

        with self.context.benchmark_tool.measure(self.behaviour_id).consensus():
            yield from self.send_a2a_transaction(payload)
            yield from self.wait_until_round_end()

        self.set_done()

    def get_payload_data(self) -> Dict:
        """Get the payload"""

        # Default payload data which clears everything before resetting
        data = dict(
            event=Event.DONE.value,
            mech_requests="[]",
            mech_responses="[]",
            tx_hash="",
            post_tx_event="",
        )

        # If there are user requests, we need to send mech requests
        n_pending = len(self.local_state.user_requests)
        if n_pending:
            self.context.logger.info(f"{n_pending} pending user requests.")
            data["event"] = Event.MECH.value
            data["mech_requests"] = self.get_mech_requests()
            data[
                "post_tx_event"
            ] = Event.MECH.value  # go back to mech response after settling
            return data

        # If there are mech responses, we settle them
        mech_responses = self.synchronized_data.mech_responses
        if mech_responses:
            tx_hash = self.process_next_mech_response()
            mech_responses.pop(0)  # remove the processed response
            data["mech_responses"] = json.dumps(mech_responses, sort_keys=True)

            # If the mech tool has decided not to trade, we skip trading.
            if not tx_hash:
                return data

            # We are settling a transaction
            data["event"] = Event.SETTLE.value
            data["tx_hash"] = tx_hash
            data[
                "post_tx_event"
            ] = Event.DECISION_MAKING.value  # come back to this skill after settling

        # Reset
        return data

    def get_mech_requests(self):
        """Get mech requests"""

        mech_requests = [
            asdict(
                MechMetadata(
                    nonce=str(uuid.uuid4()),
                    tool=self.params.celo_tool_name,
                    prompt=request,
                )
            )
            for request in self.local_state.user_requests
        ]

        # Clear pending requests
        # TODO: for multi-agent, this has to be done after this round
        self.local_state.user_requests = []

        return json.dumps(mech_requests)

    def process_next_mech_response(self) -> Optional[str]:
        """Get the call data from the mech response"""
        mech_responses = self.synchronized_data.mech_responses  # noqa: F841

        # TODO: this method should return None if the mech tool has decided not to trade
        # or the tx_hash from that tool if it has decided to trade
        tx_hash = None

        return tx_hash


class PostTxDecisionMakingBehaviour(CeloTraderBaseBehaviour):
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
