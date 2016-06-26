# -*- coding: utf-8 -*-

import datetime
from collections import defaultdict
from purchasing.database import db
from purchasing_test.integration.conductor.test_conductor import TestConductorSetup
from purchasing_test.util import insert_a_contract

class TestConductorMetrics(TestConductorSetup):
    render_templates = True

    def setUp(self):
        super(TestConductorMetrics, self).setUp()

        self.assign_contract()
        transition_url_1 = self.build_detail_view(self.contract1) + '/transition'

        self.assign_contract(contract=self.contract2)
        transition_url_2 = self.build_detail_view(self.contract2) + '/transition'

        for stage in self.flow.stage_order:
            self.client.get(transition_url_1)
            self.client.get(transition_url_2)

        self.contract3 = insert_a_contract(
            contract_type=self.county_type, description='scuba repair 2', financial_id=789,
            expiration_date=datetime.date.today() + datetime.timedelta(120),
            properties=[{'key': 'Spec Number', 'value': '789'}],
            is_visible=True
        )

    def test_metrics_index(self):
        self.assert200(self.client.get('/conductor/metrics/'))

        self.logout_user()
        self.assertEquals(self.client.get('/conductor/metrics/').status_code, 302)

    def test_metrics_tsv_download(self):
        request = self.client.get('/conductor/metrics/download/{}'.format(self.flow.id), follow_redirects=True)
        self.assertEquals(request.mimetype, 'text/tsv')
        self.assertEquals(
            request.headers.get('Content-Disposition'),
            'attachment; filename=conductor-{}-metrics.tsv'.format(self.flow.flow_name)
        )

        tsv_data = request.data.split('\n')[:-1]

        # we should have two rows plus the header
        self.assertEquals(len(tsv_data), 3)
        for row in tsv_data[1:]:
            # there should be four metadata columns plus the number of stages
            self.assertEquals(len(row.split('\t')), len(self.flow.stage_order) + 4)

    def test_metrics_tsv_download_all(self):
        insert_a_contract(
            contract_type=self.county_type, description='scuba supplies 2', financial_id=789,
            expiration_date=datetime.date.today(), properties=[{'key': 'Spec Number', 'value': '789'}],
            is_visible=False, department=self.department, is_archived=False
        )
        insert_a_contract(
            contract_type=self.county_type, description='scuba supplies 3', financial_id=101,
            expiration_date=datetime.date.today(), properties=[{'key': 'Spec Number', 'value': '789'}],
            is_visible=True, department=self.department, is_archived=True
        )
        insert_a_contract(
            contract_type=self.county_type, description='scuba supplies 4', financial_id=102,
            expiration_date=datetime.date.today(), properties=[{'key': 'Spec Number', 'value': '789'}],
            is_visible=True, department=self.department, is_archived=False, parent_id=self.contract1.id
        )
        self.contract1.update(is_archived=True)
        self.contract3.update(has_metrics=False)
        db.session.commit()
        request = self.client.get('/conductor/metrics/download/all', follow_redirects=True)
        self.assertEquals(request.mimetype, 'text/tsv')
        self.assertEquals(
            request.headers.get('Content-Disposition'),
            "attachment; filename=conductor-all-{}.tsv".format(datetime.date.today())
        )

        tsv_data = request.data.split('\n')[:-1]
        # eight contracts + a header row
        self.assertEquals(len(tsv_data), 9)
        status, in_metrics = defaultdict(int), defaultdict(int)
        for i in tsv_data[1:]:
            status[i.split('\t')[-1]] += 1
            in_metrics[i.split('\t')[-2]] += 1

        self.assertEquals(status['archived'], 1)
        self.assertEquals(status['completed'], 1)
        self.assertEquals(status['started'], 2)
        self.assertEquals(status['not started, in all contracts list'], 2)
        self.assertEquals(status['child contract complete'], 1)
        self.assertEquals(status['removed from conductor'], 1)

        self.assertEquals(in_metrics['True'], 7)
        self.assertEquals(in_metrics['False'], 1)

    def test_metrics_data(self):
        data = self.client.get('/conductor/metrics/overview/{}/data'.format(self.flow.id))
        self.assert200(data)
        self.assertEquals(len(data.json['complete']), 2)
        self.assertEquals(len(data.json['current']), 0)

    def test_metrics_data_archived(self):
        assign = self.assign_contract(contract=self.contract3)
        transition_url = self.build_detail_view(assign) + '/transition'
        self.client.get(transition_url)

        data = self.client.get('/conductor/metrics/overview/{}/data'.format(self.flow.id))
        self.assert200(data)
        self.assertEquals(len(data.json['complete']), 3)
        self.assertEquals(len(data.json['current']), 1)

        assign.update(is_archived=True, flow=self.flow, has_metrics=True)
        db.session.commit()

        data = self.client.get('/conductor/metrics/overview/{}/data'.format(self.flow.id))
        self.assert200(data)
        self.assertEquals(len(data.json['complete']), 3)
        self.assertEquals(len(data.json['current']), 0)
