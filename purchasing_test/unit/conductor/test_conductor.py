# -*- coding: utf-8 -*-

import json
import datetime
import urllib2
from mock import Mock, patch

from flask import session
from werkzeug.datastructures import ImmutableMultiDict

from purchasing.data.models import (
    ContractStage, ContractStageActionItem, ContractBase
)
from purchasing.opportunities.models import Opportunity
from purchasing.extensions import mail

from purchasing_test.unit.test_base import BaseTestCase
from purchasing_test.unit.util import (
    insert_a_contract, insert_a_stage, insert_a_flow,
    insert_a_role, insert_a_user
)

class TestConductor(BaseTestCase):
    render_templates = True

    def setUp(self):
        super(TestConductor, self).setUp()
        # create a conductor and general staff person
        self.conductor_role_id = insert_a_role('conductor')
        self.staff_role_id = insert_a_role('staff')
        self.conductor = insert_a_user(email='foo@foo.com', role=self.conductor_role_id)
        self.staff = insert_a_user(email='foo2@foo.com', role=self.staff_role_id)

        # create three stages, and set up a flow between them
        self.stage1 = insert_a_stage(name='stage1', send_notifs=True, post_opportunities=True)
        self.stage2 = insert_a_stage(name='stage2', send_notifs=True, post_opportunities=False)
        self.stage3 = insert_a_stage(name='stage3', send_notifs=False, post_opportunities=False)

        self.flow = insert_a_flow(stage_ids=[self.stage1.id, self.stage2.id, self.stage3.id])
        self.flow2 = insert_a_flow(name='test2', stage_ids=[self.stage1.id, self.stage3.id, self.stage2.id])
        self.simple_flow = insert_a_flow(name='simple', stage_ids=[self.stage1.id])

        # create two contracts
        self.contract1 = insert_a_contract(
            contract_type='County', description='scuba supplies', financial_id=123,
            expiration_date=datetime.date.today(), properties=[{'key': 'Spec Number', 'value': '123'}],
            is_visible=True
        )
        self.contract2 = insert_a_contract(
            contract_type='County', description='scuba repair', financial_id=456,
            expiration_date=datetime.date.today() + datetime.timedelta(120),
            properties=[{'key': 'Spec Number', 'value': '456'}],
            is_visible=True
        )

        self.login_user(self.conductor)
        self.detail_view = '/conductor/contract/{}/stage/{}'

    def tearDown(self):
        super(TestConductor, self).tearDown()
        session.clear()

    def assign_contract(self, flow=None):
        flow = flow if flow else self.flow
        return self.client.get('/conductor/contract/{}/assign/{}/flow/{}'.format(
            self.contract1.id, self.conductor.id, flow.id
        ))

    def get_current_contract_stage_id(self, contract, old_stage=None):
        if contract.current_stage_id is None:
            return -1

        if not old_stage:
            stage = ContractStage.query.filter(
                contract.current_stage_id == ContractStage.stage_id,
                contract.id == ContractStage.contract_id
            ).first()
        else:
            stage = ContractStage.query.filter(
                old_stage.id == ContractStage.stage_id,
                contract.id == ContractStage.contract_id
            ).first()

        return stage.id

    def build_detail_view(self, contract, old_stage=None):
        return self.detail_view.format(
            contract.id, self.get_current_contract_stage_id(contract, old_stage)
        )

    def test_conductor_contract_list(self):
        '''Test basic conductor list view
        '''
        index_view = self.client.get('/conductor', follow_redirects=True)
        self.assert200(index_view)
        self.assert_template_used('conductor/index.html')

        # we have 2 contracts
        _all = self.get_context_variable('_all')
        self.assertEquals(len(_all), 2)

        # we can't get to the page normally
        self.logout_user()
        index_view = self.client.get('/conductor', follow_redirects=True)
        self.assert200(index_view)
        # it should redirect us to the home page
        self.assert_template_used('public/home.html')

        self.login_user(self.staff)
        index_view = self.client.get('/conductor', follow_redirects=True)
        self.assert200(index_view)
        # it should redirect us to the home page
        self.assert_template_used('public/home.html')

    def test_conductor_contract_assign(self):
        '''Test contract assignment via conductor
        '''
        self.assertEquals(ContractStage.query.count(), 0)

        assign = self.assign_contract()

        self.assertEquals(ContractStage.query.count(), len(self.flow.stage_order))
        self.assertEquals(self.contract1.current_stage_id, self.flow.stage_order[0])
        self.assertEquals(self.contract1.assigned_to, self.conductor.id)

        self.assertEquals(assign.status_code, 302)
        self.assert_flashes('Successfully assigned to {}!'.format(self.conductor.email), 'alert-success')
        self.assertEquals(assign.location, 'http://localhost/conductor/')

        # re-assigning shouldn't cause problems
        self.assign_contract()

    def test_conductor_contract_detail_view(self):
        '''Test basic conductor detail view
        '''
        self.assert404(self.client.get(self.detail_view.format(999, 999)))

        self.assign_contract()

        detail_view_url = self.build_detail_view(self.contract1)

        detail = self.client.get(self.build_detail_view(self.contract1))
        self.assert200(detail)
        self.assert_template_used('conductor/detail.html')
        self.assertEquals(self.get_context_variable('active_tab'), '#activity')
        self.assertEquals(
            self.get_context_variable('current_stage').id,
            self.get_context_variable('active_stage').id
        )
        self.assertEquals(len(self.get_context_variable('actions')), 1)

        # make sure the redirect works
        redir = self.client.get('/conductor/contract/{}'.format(self.contract1.id))
        self.assertEquals(redir.status_code, 302)
        self.assertEquals(redir.location, 'http://localhost' + detail_view_url)

        self.logout_user()

        # make sure we can't get to it unless we are the right user
        detail = self.client.get(detail_view_url, follow_redirects=True)
        self.assert200(detail)
        # it should redirect us to the home page
        self.assert_template_used('public/home.html')

        self.login_user(self.staff)
        detail = self.client.get(detail_view_url, follow_redirects=True)
        self.assert200(detail)
        # it should redirect us to the home page
        self.assert_template_used('public/home.html')

    def test_conductor_contract_transition(self):
        '''Test conductor stage transition
        '''
        self.assign_contract()

        transition_url = self.build_detail_view(self.contract1) + '?transition=true'
        transition = self.client.get(transition_url)
        self.assertEquals(transition.status_code, 302)
        self.assertEquals(
            transition.location, 'http://localhost' + self.build_detail_view(self.contract1)
        )
        new_page = self.client.get(self.build_detail_view(self.contract1))
        self.assertTrue('<a href="#post" aria-controls="post" role="tab" data-toggle="tab">' not in new_page.data)

        contract_stages = ContractStage.query.all()
        for stage in contract_stages:
            if stage.id == self.stage1.id:
                self.assertTrue(stage.entered is not None and stage.exited is not None)
            elif stage.id == self.stage2.id:
                self.assertTrue(stage.entered is not None and stage.exited is None)
            elif stage.id == self.stage3.id:
                self.assertTrue(stage.entered is None and stage.exited is None)

    def test_conductor_directed_transition(self):
        '''Test conductor stage transition backwards/to specific point
        '''
        self.assign_contract()
        self.assertEquals(ContractStageActionItem.query.count(), 1)

        # transition to the third stage
        transition_url = self.build_detail_view(self.contract1) + '?transition=true'
        self.client.get(transition_url)
        self.client.get(transition_url)

        self.assertEquals(self.contract1.current_stage_id, self.stage3.id)

        revert_url = self.build_detail_view(self.contract1) + '?transition=true&destination={}'
        # revert to the original stage
        self.client.get(revert_url.format(self.stage1.id))

        self.assertEquals(ContractStageActionItem.query.count(), 12)
        # there should be 3 for stage 1 & 2 (enter, exit, reopen)
        self.assertEquals(ContractStageActionItem.query.join(ContractStage).filter(
            ContractStage.stage_id == self.stage1.id
        ).count(), 5)

        self.assertEquals(ContractStageActionItem.query.join(ContractStage).filter(
            ContractStage.stage_id == self.stage2.id
        ).count(), 5)

        self.assertEquals(ContractStageActionItem.query.join(ContractStage).filter(
            ContractStage.stage_id == self.stage3.id
        ).count(), 2)

        self.assertEquals(self.contract1.current_stage_id, self.stage1.id)
        self.assertTrue(ContractStage.query.filter(ContractStage.stage_id == self.stage1.id).first().entered is not None)
        self.assertTrue(ContractStage.query.filter(ContractStage.stage_id == self.stage2.id).first().entered is None)
        self.assertTrue(ContractStage.query.filter(ContractStage.stage_id == self.stage3.id).first().entered is None)

        self.assertTrue(ContractStage.query.filter(ContractStage.stage_id == self.stage1.id).first().exited is None)
        self.assertTrue(ContractStage.query.filter(ContractStage.stage_id == self.stage2.id).first().exited is None)
        self.assertTrue(ContractStage.query.filter(ContractStage.stage_id == self.stage3.id).first().exited is None)

    def test_conductor_link_directions(self):
        '''Test that we can access completed stages but not non-started ones
        '''
        self.assign_contract()
        self.client.get(self.detail_view.format(self.contract1.id, self.stage1.id) + '?transition=true')

        # assert the current stage is stage 2
        redir = self.client.get('/conductor/contract/{}'.format(self.contract1.id))
        self.assertEquals(redir.status_code, 302)
        self.assertEquals(redir.location, 'http://localhost' + self.build_detail_view(self.contract1))
        # assert we can/can't go the correct locations
        old_view = self.client.get(self.build_detail_view(self.contract1, old_stage=self.stage1))
        self.assert200(old_view)
        self.assertTrue('You are viewing an already-completed stage.' in old_view.data)
        self.assert200(self.client.get(self.build_detail_view(self.contract1, old_stage=self.stage2)))
        self.assert404(self.client.get(self.build_detail_view(self.contract1, old_stage=self.stage3)))

    def test_conductor_flow_switching(self):
        '''Test flow switching back and forth in conductor
        '''
        self.assign_contract()
        self.client.get(self.detail_view.format(self.contract1.id, self.stage1.id) + '?transition=true')
        # we should have three actions -- entered, exited, entered
        self.assertEquals(ContractStageActionItem.query.count(), 3)

        self.client.get(self.detail_view.format(self.contract1.id, self.stage2.id) +
            '?flow_switch={}'.format(self.flow2.id))

        # assert that we have been updated appropriately
        self.assertEquals(self.contract1.flow_id, self.flow2.id)
        self.assertEquals(self.contract1.current_stage_id, self.flow2.stage_order[0])

        # assert that the action log has been properly cleaned
        new_actions = ContractStageActionItem.query.all()
        self.assertEquals(len(new_actions), 2)

        flow_switch_action, entered_action = 0, 0
        for i in new_actions:
            if i.action_type == 'entered':
                entered_action += 1
            elif i.action_type == 'flow_switch':
                flow_switch_action += 1
        self.assertEquals(entered_action, 1)
        self.assertEquals(flow_switch_action, 1)

        # assert that the old contract stages from the previous flow
        # have had their enter/exit times cleared
        old_stages = ContractStage.query.filter(
            ContractStage.flow_id == self.flow.id,
            ContractStage.contract_id == self.contract1.id
        ).all()
        for i in old_stages:
            self.assertTrue(i.entered is None)
            self.assertTrue(i.exited is None)

        # assert that you can transition back to the original flow
        current_stage = ContractStage.query.filter(
            ContractStage.stage_id == self.contract1.current_stage_id,
            ContractStage.contract_id == self.contract1.id,
            ContractStage.flow_id == self.contract1.flow_id
        ).first()

        # switch back to the first stage
        self.client.get(
            self.detail_view.format(self.contract1.id, current_stage.id) +
            '?flow_switch={}'.format(self.flow.id)
        )

        # assert that our contract properties work as expected
        self.assertEquals(self.contract1.flow_id, self.flow.id)
        self.assertEquals(self.contract1.current_stage_id, self.flow.stage_order[0])

        # assert that the actions were logged correctly
        new_actions = ContractStageActionItem.query.all()
        self.assertEquals(len(new_actions), 3)
        flow_switch_action, entered_action, restarted_action = 0, 0, 0
        for i in new_actions:
            if i.action_type == 'entered':
                entered_action += 1
            elif i.action_type == 'flow_switch':
                flow_switch_action += 1
            elif i.action_type == 'restarted':
                restarted_action += 1
        self.assertEquals(entered_action, 0)
        self.assertEquals(flow_switch_action, 2)
        self.assertEquals(restarted_action, 0)

    @patch('urllib2.urlopen')
    def test_url_validation(self, urlopen):
        '''Test url validation HEAD requests work as expected
        '''
        mock_open = Mock()
        mock_open.getcode.side_effect = [200, urllib2.HTTPError('', 404, 'broken', {}, file)]
        urlopen.return_value = mock_open

        post_url = '/conductor/contract/{}/edit/url-exists'.format(self.contract1.id)

        post1 = self.client.post(
            post_url, data=json.dumps(dict(no_url='')),
            headers={'Content-Type': 'application/json;charset=UTF-8'}
        )
        self.assertEquals(json.loads(post1.data).get('status'), 404)

        post2 = self.client.post(
            post_url, data=json.dumps(dict(url='works')),
            headers={'Content-Type': 'application/json;charset=UTF-8'}
        )
        self.assertEquals(json.loads(post2.data).get('status'), 200)

        post3 = self.client.post(
            post_url, data=json.dumps(dict(url='doesnotwork')),
            headers={'Content-Type': 'application/json;charset=UTF-8'}
        )
        self.assertEquals(json.loads(post3.data).get('status'), 404)

    def test_conductor_contract_post_note(self):
        '''Test posting a note to the activity stream
        '''
        self.assign_contract()

        self.assertEquals(ContractStageActionItem.query.count(), 1)

        detail_view_url = self.build_detail_view(self.contract1)
        self.client.post(detail_view_url + '?form=activity', data=dict(
            note='a test note!'
        ))
        self.assertEquals(ContractStageActionItem.query.count(), 2)
        detail_view = self.client.get(detail_view_url)
        self.assertEquals(len(self.get_context_variable('actions')), 2)
        self.assertTrue('a test note!' in detail_view.data)

        # make sure you can't post notes to an unstarted stage
        self.assert404(self.client.post(
            self.build_detail_view(self.contract1, old_stage=self.stage3) + '?form=activity',
            data=dict(note='a test note!')
        ))

        # make sure you can't post a note to an unstarted contract
        self.assert404(self.client.post(
            self.build_detail_view(self.contract2) + '?form=activity',
            data=dict(note='a test note!')
        ))

    def test_delete_note(self):
        '''Test you can delete a note
        '''
        self.assign_contract()
        self.assertEquals(ContractStageActionItem.query.count(), 1)
        detail_view_url = self.build_detail_view(self.contract1)
        self.client.post(detail_view_url + '?form=activity', data=dict(
            note='a test note!'
        ))
        self.client.post(detail_view_url + '?form=activity', data=dict(
            note='a second test note!'
        ))

        self.assertEquals(ContractStageActionItem.query.count(), 3)
        self.client.get('/conductor/contract/1/stage/1/note/1/delete')
        self.assertEquals(ContractStageActionItem.query.count(), 2)

        self.client.get('/conductor/contract/1/stage/1/note/100/delete')
        self.assert_flashes("That note doesn't exist!", 'alert-warning')

        self.logout_user()
        # make sure you can't delete notes randomly
        self.assert200(
            self.client.get('/conductor/contract/1/stage/1/note/1/delete', follow_redirects=True)
        )
        self.assertEquals(ContractStageActionItem.query.count(), 2)
        self.assert_template_used('public/home.html')

    def test_conductor_send_update(self):
        '''Test sending an email/into the activity stream
        '''
        self.assign_contract()

        self.assertEquals(ContractStageActionItem.query.count(), 1)
        detail_view_url = self.build_detail_view(self.contract1)
        # make sure the form validators work
        bad_post = self.client.post(detail_view_url + '?form=update', data=dict(
            send_to='bademail', subject='test', body='test'
        ), follow_redirects=True)
        self.assertEquals(ContractStageActionItem.query.count(), 1)
        self.assertEquals(bad_post.status_code, 200)
        self.assertTrue('One of the supplied emails is invalid' in bad_post.data)

        with mail.record_messages() as outbox:
            good_post = self.client.post(detail_view_url + '?form=update', data=dict(
                send_to='foo@foo.com; foo2@foo.com', subject='test', body='test'
            ), follow_redirects=True)

            self.assertEquals(len(outbox), 1)
            self.assertEquals(ContractStageActionItem.query.count(), 2)
            self.assertTrue('test' in outbox[0].subject)
            self.assertTrue('with the subject' in good_post.data)

    def test_conductor_post_to_beacon_validation(self):
        '''Test failure posting to beacon from Conductor
        '''
        self.assign_contract()

        detail_view_url = self.build_detail_view(self.contract1)

        bad1 = self.client.post(detail_view_url + '?form=post', data=dict(contact_email='foo'))
        self.assertTrue('Invalid email address.' in bad1.data)

        bad2 = self.client.post(detail_view_url + '?form=post', data=dict(contact_email='foo@BADDOMAIN.com'))
        self.assertTrue('not a valid contact!' in bad2.data)

        self.assertEquals(Opportunity.query.count(), 0)
        self.assertEquals(ContractStageActionItem.query.count(), 1)

    def test_conductor_post_to_beacon(self):
        '''Test successful posting to beacon from Conductor
        '''
        self.assign_contract()

        detail_view_url = self.build_detail_view(self.contract1)

        self.client.post(detail_view_url + '?form=post', data=dict(
            contact_email=self.conductor.email, title='foobar', description='barbaz',
            planned_advertise=datetime.date.today() + datetime.timedelta(1),
            planned_open=datetime.date.today() + datetime.timedelta(2),
            planned_deadline=datetime.date.today() + datetime.timedelta(2)
        ))

        self.assertEquals(Opportunity.query.count(), 1)
        self.assertEquals(ContractStageActionItem.query.count(), 2)
        detail_view = self.client.get(detail_view_url)
        self.assertEquals(len(self.get_context_variable('actions')), 2)
        self.assertTrue('barbaz' in detail_view.data)

    def test_edit_contract_metadata(self):
        '''Test editing a contract's metadata from the conductor detail form
        '''
        self.assign_contract()

        detail_view_url = self.build_detail_view(self.contract1, self.stage1)
        self.client.post(detail_view_url + '?form=update-metadata', data=dict(
            financial_id=999
        ))

        self.assertEquals(ContractStageActionItem.query.count(), 2)
        for i in ContractStageActionItem.query.all():
            self.assertTrue(i.action_detail is not None)
        self.assertEquals(self.contract1.financial_id, 999)

    def test_edit_contract_complete(self):
        '''Test the completion views are locked until a contract is in its last stage
        '''
        self.assign_contract(flow=self.simple_flow)
        should_redir = self.client.get('/conductor/contract/{}/edit/contract'.format(self.contract1.id))
        self.assertEquals(should_redir.status_code, 302)
        self.assertEquals(
            should_redir.location,
            'http://localhost/conductor/contract/{}'.format(self.contract1.id)
        )

        should_redir = self.client.get('/conductor/contract/{}/edit/company'.format(self.contract1.id))
        self.assertEquals(should_redir.status_code, 302)
        self.assertEquals(
            should_redir.location,
            'http://localhost/conductor/contract/{}/edit/contract'.format(self.contract1.id)
        )

        should_redir = self.client.get('/conductor/contract/{}/edit/contacts'.format(self.contract1.id))
        self.assertEquals(should_redir.status_code, 302)
        self.assertEquals(
            should_redir.location,
            'http://localhost/conductor/contract/{}/edit/contract'.format(self.contract1.id)
        )

    def test_contract_completion_session_set(self):
        '''Test we set the proper session variables on contract completion
        '''
        with self.client as c:
            self.assign_contract(flow=self.simple_flow)

            transition_url = self.build_detail_view(self.contract1) + '?transition=true'
            self.client.get(transition_url)

            self.assertTrue(self.contract1.completed_last_stage())
            self.assert200(c.get('/conductor/contract/{}/edit/contract'.format(self.contract1.id)))
            c.post('conductor/contract/{}/edit/contract'.format(self.contract1.id), data=dict(
                expiration_date=datetime.date(2020, 1, 1), spec_number='abcd',
                description='foo'
            ))

            self.assertTrue(session['contract'] is not None)

            self.assert200(c.get('/conductor/contract/{}/edit/company'.format(self.contract1.id)))

            c.post('conductor/contract/{}/edit/company'.format(self.contract1.id), data=ImmutableMultiDict([
                ('companies-0-new_company_controller_number', u'1234'),
                ('companies-0-company_name', u'__None'),
                ('companies-0-controller_number', u''),
                ('companies-0-new_company_name', u'test')
            ]))

            self.assertTrue(session['companies'] is not None)
            self.assert200(c.get('/conductor/contract/{}/edit/contacts'.format(self.contract1.id)))

    def test_edit_contract_form_validators(self):
        with self.client as c:

            self.assign_contract(flow=self.simple_flow)

            transition_url = self.build_detail_view(self.contract1) + '?transition=true'
            self.client.get(transition_url)


            # set contract session variable so we can post to the company endpoint
            c.post('conductor/contract/{}/edit/contract'.format(self.contract1.id), data=dict(
                expiration_date=datetime.date(2020, 1, 1), spec_number='abcd',
                description='foo'
            ))
            self.assertTrue('companies' not in session.keys())

            # assert you can't set both controller numbers
            c.post('conductor/contract/{}/edit/company'.format(self.contract1.id), data=ImmutableMultiDict([
                ('companies-0-new_company_controller_number', u'1234'),
                ('companies-0-company_name', u'__None'),
                ('companies-0-controller_number', u'1234'),
                ('companies-0-new_company_name', u'')
            ]))
            self.assertTrue('companies' not in session.keys())

            # assert you can't set both company names
            c.post('conductor/contract/{}/edit/company'.format(self.contract1.id), data=ImmutableMultiDict([
                ('companies-0-new_company_controller_number', u''),
                ('companies-0-company_name', u'foobar'),
                ('companies-0-controller_number', u''),
                ('companies-0-new_company_name', u'foobar')
            ]))
            self.assertTrue('companies' not in session.keys())

            # assert you can't set mismatched names/numbers
            c.post('conductor/contract/{}/edit/company'.format(self.contract1.id), data=ImmutableMultiDict([
                ('companies-0-new_company_controller_number', u''),
                ('companies-0-company_name', u''),
                ('companies-0-controller_number', u'1234'),
                ('companies-0-new_company_name', u'foobar')
            ]))
            self.assertTrue('companies' not in session.keys())

            # assert new works
            c.post('conductor/contract/{}/edit/company'.format(self.contract1.id), data=ImmutableMultiDict([
                ('companies-0-new_company_controller_number', u'1234'),
                ('companies-0-company_name', u''),
                ('companies-0-controller_number', u''),
                ('companies-0-new_company_name', u'foobar')
            ]))
            self.assertTrue(session['companies'] is not None)
            session.pop('companies')

            # assert old works
            c.post('conductor/contract/{}/edit/company'.format(self.contract1.id), data=ImmutableMultiDict([
                ('companies-0-new_company_controller_number', u''),
                ('companies-0-company_name', u'foobar'),
                ('companies-0-controller_number', u'1234'),
                ('companies-0-new_company_name', u'')
            ]))
            self.assertTrue(session['companies'] is not None)
            session.pop('companies')

            # assert multiple companies work
            c.post('conductor/contract/{}/edit/company'.format(self.contract1.id), data=ImmutableMultiDict([
                ('companies-0-new_company_controller_number', u''),
                ('companies-0-company_name', u'foobar'),
                ('companies-0-controller_number', u'1234'),
                ('companies-0-new_company_name', u''),
                ('companies-1-new_company_controller_number', u'1234'),
                ('companies-1-company_name', u''),
                ('companies-1-controller_number', u''),
                ('companies-1-new_company_name', u'foobar2')
            ]))

            self.assertTrue(session['companies'] is not None)
            session.pop('companies')

    def test_actual_contract_completion(self):
        '''Test the flow of completing a contract with one company
        '''
        with self.client as c:
            self.assertTrue(self.contract1.is_visible)

            self.assign_contract(flow=self.simple_flow)

            transition_url = self.build_detail_view(self.contract1) + '?transition=true'
            self.client.get(transition_url)

            c.post('conductor/contract/{}/edit/contract'.format(self.contract1.id), data=dict(
                expiration_date=datetime.date(2020, 1, 1), spec_number='abcd',
                description='foo'
            ))

            c.post('conductor/contract/{}/edit/company'.format(self.contract1.id), data=ImmutableMultiDict([
                ('companies-0-new_company_controller_number', u'1234'),
                ('companies-0-company_name', u''),
                ('companies-0-controller_number', u''),
                ('companies-0-new_company_name', u'foobar')
            ]))

            c.post('/conductor/contract/{}/edit/contacts'.format(self.contract1.id), data=ImmutableMultiDict([
                ('companies-0-contacts-0-first_name', 'foo'),
                ('companies-0-contacts-0-last_name', 'bar'),
                ('companies-0-contacts-0-phone_number', '123-456-7890'),
                ('companies-0-contacts-0-email', 'foo@foo.com'),
            ]))

            self.assertTrue(self.contract1.parent.is_archived)
            self.assertFalse(self.contract1.parent.is_visible)
            self.assertTrue(self.contract1.is_visible)

            self.assertEquals(ContractBase.query.count(), 3)
            self.assertEquals(self.contract1.description, 'foo')
            self.assertEquals(self.contract1.parent.description, 'scuba supplies [Archived]')

    def test_actual_contract_completion_multi_company(self):
        '''Test the flow of completing a contract with multiple companies
        '''
        with self.client as c:
            self.assertTrue(self.contract1.is_visible)

            self.assign_contract(flow=self.simple_flow)

            transition_url = self.build_detail_view(self.contract1) + '?transition=true'
            self.client.get(transition_url)

            c.post('conductor/contract/{}/edit/contract'.format(self.contract1.id), data=dict(
                expiration_date=datetime.date(2020, 1, 1), spec_number='abcd',
                description='foo'
            ))

            c.post('conductor/contract/{}/edit/company'.format(self.contract1.id), data=ImmutableMultiDict([
                ('companies-0-new_company_controller_number', u'1234'),
                ('companies-0-company_name', u''),
                ('companies-0-controller_number', u''),
                ('companies-0-new_company_name', u'foobar'),
                ('companies-1-new_company_controller_number', u'1234'),
                ('companies-1-company_name', u''),
                ('companies-1-controller_number', u''),
                ('companies-1-new_company_name', u'foobar2')
            ]))

            c.post('/conductor/contract/{}/edit/contacts'.format(self.contract1.id), data=ImmutableMultiDict([
                ('companies-0-contacts-0-first_name', 'foo'),
                ('companies-0-contacts-0-last_name', 'bar'),
                ('companies-0-contacts-0-phone_number', '123-456-7890'),
                ('companies-0-contacts-0-email', 'foo@foo.com'),
                ('companies-1-contacts-0-first_name', 'foo'),
                ('companies-1-contacts-0-last_name', 'bar'),
                ('companies-1-contacts-0-phone_number', '123-456-7890'),
                ('companies-1-contacts-0-email', 'foo@foo.com'),

            ]))

            # we should create two new contract objects
            self.assertEquals(ContractBase.query.count(), 4)
            self.assertTrue(self.contract1.parent.is_archived)
            self.assertFalse(self.contract1.parent.is_visible)

            # two of the contracts should be children of our parent contract
            children = self.contract1.parent.children
            self.assertEquals(len(children), 2)

            for child in children:
                self.assertTrue(child.is_visible)
                self.assertEquals(child.description, 'foo')
                self.assertEquals(child.parent.description, 'scuba supplies [Archived]')

    def test_contract_extension(self):
        '''Test our flow works with contract extensions
        '''
        self.assign_contract()
        detail_view_url = self.build_detail_view(self.contract1)
        extend = self.client.get(detail_view_url + '?extend=true')

        self.assertEquals(extend.status_code, 302)
        self.assertEquals(
            extend.location,
            'http://localhost/conductor/contract/{}/edit/contract'.format(self.contract1.parent.id)
        )

        extend_post = self.client.post('conductor/contract/{}/edit/contract'.format(self.contract1.parent.id), data=dict(
            expiration_date=datetime.date.today(), spec_number='1234',
            description=self.contract1.parent.description
        ))

        self.assertEquals(extend_post.status_code, 302)
        self.assertEquals(
            extend_post.location,
            'http://localhost/conductor/'
        )

        self.assertEquals(self.contract1.parent.expiration_date, datetime.date.today())
        # we should have deleted our child contract
        self.assertEquals(ContractBase.query.count(), 2)
