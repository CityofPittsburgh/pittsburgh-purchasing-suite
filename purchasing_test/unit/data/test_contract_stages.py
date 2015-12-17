# -*- coding: utf-8 -*-

import datetime

from unittest import TestCase
from mock import Mock

from purchasing.opportunities import models
from purchasing.data import contracts, flows, stages
from purchasing.users import models

from purchasing_test.factories import (
    ContractBaseFactory, ContractStageActionItemFactory,
    StageFactory, FlowFactory, ContractStageFactory
)

class TestContractStageSort(TestCase):
    def setUp(self):
        super(TestContractStageSort, self).setUp()
        now = datetime.datetime.now().replace(second=0, microsecond=0)
        old = now - datetime.timedelta(minutes=1)
        older = now - datetime.timedelta(minutes=2)
        new = now + datetime.timedelta(minutes=1)
        newer = now + datetime.timedelta(minutes=2)

        stage1, stage2 = StageFactory.build(), StageFactory.build()
        flow = FlowFactory.build(stage_order=[stage1.id, stage2.id])
        self.contract = ContractBaseFactory.build(current_stage_id=stage2.id)

        contract_stage1 = ContractStageFactory.build(
            stage=stage1, stage_id=stage1.id, flow=flow
        )
        contract_stage2 = ContractStageFactory.build(
            stage=stage2, stage_id=stage2.id, flow=flow
        )

        self.contract.build_complete_action_log = Mock()

        self.enter_one = ContractStageActionItemFactory.build(
            action_type='entered', taken_at=older, contract_stage=contract_stage1,
            action_detail={'timestamp': older.isoformat()}
        )
        self.exit_one = ContractStageActionItemFactory.build(
            action_type='exited', taken_at=old, contract_stage=contract_stage1,
            action_detail={'timestamp': old.isoformat()}
        )
        self.enter_two = ContractStageActionItemFactory.build(
            action_type='entered', taken_at=old.replace(second=1),
            contract_stage=contract_stage2,
            action_detail={'timestamp': old.isoformat()}
        )

        self.revert_one = ContractStageActionItemFactory.build(
            action_type='reversion', taken_at=now,
            contract_stage=contract_stage1,
            action_detail={'timestamp': now.isoformat()}
        )
        self.exit_one_post_revert = ContractStageActionItemFactory.build(
            action_type='exited', taken_at=new, contract_stage=contract_stage1,
            action_detail={'timestamp': new.isoformat()}
        )
        self.enter_two_post_revert = ContractStageActionItemFactory.build(
            action_type='entered', taken_at=new.replace(second=1),
            contract_stage=contract_stage2,
            action_detail={'timestamp': new.isoformat()}
        )

        self.note = ContractStageActionItemFactory.build(
            action_type='note', taken_at=newer,
            contract_stage=contract_stage2,
            action_detail={'timestamp': newer.isoformat()}
        )

    def test_simple_sort(self):
        self.contract.build_complete_action_log.return_value = [
            self.enter_one, self.exit_one, self.enter_two
        ]
        order = self.contract.filter_action_log()
        self.assertEquals(order, [self.enter_two, self.exit_one, self.enter_one])

    def test_complex_sort(self):
        self.contract.build_complete_action_log.return_value = [
            self.enter_one, self.exit_one, self.enter_two,
            self.revert_one, self.exit_one_post_revert,
            self.enter_two_post_revert, self.note
        ]

        order = self.contract.filter_action_log()
        self.assertEquals(order, [
            self.note, self.enter_two_post_revert,
            self.exit_one_post_revert, self.revert_one
        ])
